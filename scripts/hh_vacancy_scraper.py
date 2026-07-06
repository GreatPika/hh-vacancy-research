#!/usr/bin/env python3
"""Collect hh.ru vacancies for a user-confirmed search profile.

The script reads public hh.ru HTML pages, caches fetched documents, parses full
vacancy pages, and keeps only vacancies with confirmed matches in the configured
fields. It intentionally does not use the hh.ru API.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib
import json
import math
import os
import random
import re
import ssl
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, HTTPCookieProcessor, Request, build_opener


BASE_URL = "https://hh.ru"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
ENABLED_FIELDS = ("title", "company", "description", "skills")
REQUIRED_MATCH_FIELDS = ("title", "description", "skills")
SEARCH_FIELD_VALUES = {"name", "company_name", "description"}
EXPERIENCE_VALUES = {"noExperience", "between1And3", "between3And6", "moreThan6"}
SCHEDULE_VALUES = {"remote", "fullDay", "shift", "flexible", "flyInFlyOut"}
EMPLOYMENT_VALUES = {"full", "part", "project", "volunteer", "probation"}
ORDER_BY_VALUES = {"publication_time", "salary_desc", "salary_asc", "relevance"}
HH_FILTER_FIELDS = {
    "search_field",
    "experience",
    "schedule",
    "employment",
    "industry",
    "salary",
    "only_with_salary",
    "order_by",
    "period",
}
PROFILE_FIELDS = {
    "title",
    "hh",
    "match_scope",
    "search_terms",
    "term_patterns",
    "exclude_patterns",
    "notes",
}
HH_FIELDS = {
    "area",
    "max_pages",
    "search_delay_min",
    "search_delay_max",
    "vacancy_delay_min",
    "vacancy_delay_max",
    "filters",
}
OPENER = build_opener(HTTPCookieProcessor())
TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
PERMANENT_HTTP_STATUSES = {404, 410}
MAX_FETCH_ATTEMPTS = 3


class FetchError(RuntimeError):
    def __init__(self, message: str, kind: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def cache_path_for_url(cache_dir: Path, category: str, url: str, label: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9А-Яа-я]+", "_", label).strip("_")[:80] or "item"
    return cache_dir / category / f"{slug}_{short_hash(url)}.html"


def blocked_page_reason(page_html: str) -> str:
    lowered = page_html.lower()
    captcha_markers = (
        'data-qa="captcha"',
        "g-recaptcha",
        "captcha-page",
        "captcha__",
        "/account/captcha",
    )
    if any(value in lowered for value in captcha_markers):
        return "captcha"
    access_markers = (
        "<title>доступ ограничен",
        "<title>access denied",
        "доступ заблокирован",
        "automated requests are not allowed",
    )
    if any(value in lowered for value in access_markers):
        return "access_denied"
    return ""


@dataclass(frozen=True)
class HhFilters:
    search_field: tuple[str, ...] = ()
    experience: tuple[str, ...] = ()
    schedule: tuple[str, ...] = ()
    employment: tuple[str, ...] = ()
    industry: tuple[str, ...] = ()
    salary: int | None = None
    only_with_salary: bool = False
    order_by: str = "relevance"
    period: int | None = None


@dataclass(frozen=True)
class HhSettings:
    area: str
    max_pages: int
    search_delay_min: float
    search_delay_max: float
    vacancy_delay_min: float
    vacancy_delay_max: float
    filters: HhFilters = field(default_factory=HhFilters)


@dataclass(frozen=True)
class SearchProfile:
    title: str
    hh: HhSettings
    match_scope: dict[str, bool]
    search_terms: dict[str, list[str]]
    term_patterns: dict[str, list[re.Pattern[str]]]
    exclude_patterns: dict[str, list[re.Pattern[str]]]
    notes: str = ""


@dataclass
class Match:
    term: str
    fields: list[str]


@dataclass
class Vacancy:
    vacancy_id: str
    title: str
    description: str
    url: str
    company: str = ""
    salary: str = ""
    experience: str = ""
    schedule: str = ""
    employer_industry: str = ""
    skills: list[str] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)

    @property
    def matched_terms(self) -> list[str]:
        return [match.term for match in self.matches]


class VacancyPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.company_parts: list[str] = []
        self.salary_parts: list[str] = []
        self.experience_parts: list[str] = []
        self.employment_parts: list[str] = []
        self.schedule_parts: list[str] = []
        self.description_parts: list[str] = []
        self.skill_parts: list[str] = []
        self._capture_title_depth = 0
        self._capture_company_depth = 0
        self._capture_salary_depth = 0
        self._capture_experience_depth = 0
        self._capture_employment_depth = 0
        self._capture_schedule_depth = 0
        self._capture_description_depth = 0
        self._capture_skill_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        data_qa = attr.get("data-qa", "")
        klass = attr.get("class") or ""

        if tag == "h1" and data_qa == "vacancy-title":
            self._capture_title_depth = 1
        elif self._capture_title_depth:
            self._capture_title_depth += 1

        if data_qa in {
            "vacancy-company-name",
            "vacancy-company-name-text",
            "vacancy-company-name-link",
        }:
            self._capture_company_depth = 1
        elif self._capture_company_depth:
            self._capture_company_depth += 1

        if data_qa == "vacancy-salary":
            self._capture_salary_depth = 1
        elif self._capture_salary_depth:
            self._capture_salary_depth += 1

        if data_qa == "vacancy-experience":
            self._capture_experience_depth = 1
        elif self._capture_experience_depth:
            self._capture_experience_depth += 1

        if data_qa == "common-employment-text":
            self._capture_employment_depth = 1
        elif self._capture_employment_depth:
            self._capture_employment_depth += 1

        if data_qa in {"work-schedule-by-days-text", "working-hours-text", "work-formats-text"}:
            if self.schedule_parts and self.schedule_parts[-1] != "\n":
                self.schedule_parts.append("\n")
            self._capture_schedule_depth = 1
        elif self._capture_schedule_depth:
            self._capture_schedule_depth += 1

        if data_qa == "vacancy-description":
            self._capture_description_depth = 1
        elif self._capture_description_depth:
            self._capture_description_depth += 1

        if (
            data_qa in {"bloko-tag__text", "skills-element"}
            or "bloko-tag__section_text" in klass
        ):
            self._capture_skill_depth = 1
        elif self._capture_skill_depth:
            self._capture_skill_depth += 1

        if self._capture_description_depth and tag in {"p", "br", "li", "div"}:
            self.description_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._capture_title_depth:
            self._capture_title_depth -= 1
        if self._capture_company_depth:
            self._capture_company_depth -= 1
        if self._capture_salary_depth:
            self._capture_salary_depth -= 1
        if self._capture_experience_depth:
            self._capture_experience_depth -= 1
        if self._capture_employment_depth:
            self._capture_employment_depth -= 1
        if self._capture_schedule_depth:
            self._capture_schedule_depth -= 1
        if self._capture_description_depth:
            if tag in {"p", "li", "div"}:
                self.description_parts.append("\n")
            self._capture_description_depth -= 1
        if self._capture_skill_depth:
            self._capture_skill_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_title_depth:
            self.title_parts.append(data)
        if self._capture_company_depth:
            self.company_parts.append(data)
        if self._capture_salary_depth:
            self.salary_parts.append(data)
        if self._capture_experience_depth:
            self.experience_parts.append(data)
        if self._capture_employment_depth:
            self.employment_parts.append(data)
        if self._capture_schedule_depth:
            self.schedule_parts.append(data)
        if self._capture_description_depth:
            self.description_parts.append(data)
        if self._capture_skill_depth:
            self.skill_parts.append(data)


def compact_text(value: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def compact_inline_text(value: str) -> str:
    return re.sub(r"\s+", " ", compact_text(value)).strip()


def strip_attribute_label(value: str) -> str:
    return re.sub(
        r"^(?:Опыт работы|График|Рабочие часы|Формат работы|Занятость)\s*:\s*",
        "",
        compact_inline_text(value),
        flags=re.I,
    ).strip()


def join_vacancy_attributes(*values: str) -> str:
    return "; ".join(unique(value for value in (strip_attribute_label(item) for item in values) if value))


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def certificate_error_help() -> str:
    return (
        "Python could not verify the TLS certificate. Install dependencies with "
        "`pip install -r requirements.txt` so the scraper can retry with certifi."
    )


def is_certificate_verification_error(exc: URLError) -> bool:
    reason = exc.reason
    return isinstance(reason, ssl.SSLCertVerificationError)


@lru_cache(maxsize=1)
def certifi_opener():
    try:
        certifi = importlib.import_module("certifi")
    except ModuleNotFoundError:
        return None
    certifi_where = getattr(certifi, "where", None)
    if not callable(certifi_where):
        return None
    context = ssl.create_default_context(cafile=str(certifi_where()))
    return build_opener(HTTPCookieProcessor(), HTTPSHandler(context=context))


def read_request_body(request: Request) -> str:
    try:
        with OPENER.open(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        if not is_certificate_verification_error(exc):
            raise
        opener = certifi_opener()
        if opener is None:
            raise FetchError(certificate_error_help(), kind="ssl") from exc
        print("Python certificate verification failed; retrying with certifi CA bundle.", flush=True)
        with opener.open(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")


def fetch_url(url: str, cache_path: Path, min_delay: float, max_delay: float) -> str:
    if cache_path.exists():
        cached = cache_path.read_text(encoding="utf-8", errors="replace")
        if cached.strip():
            blocked_reason = blocked_page_reason(cached)
            if blocked_reason:
                cache_path.unlink(missing_ok=True)
                raise FetchError(
                    f"Blocked cached page for {url}: {blocked_reason}. "
                    "Cached file was removed; rerun the same command to fetch again.",
                    kind="blocked",
                )
            return cached
        cache_path.unlink(missing_ok=True)

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        delay = random.uniform(min_delay, max_delay)
        if attempt > 1:
            delay += 2 ** (attempt - 2)
        print(f"sleep {delay:.1f}s before fetch: {url}", flush=True)
        time.sleep(delay)
        try:
            body = read_request_body(request)
        except HTTPError as exc:
            last_error = exc
            if exc.code in PERMANENT_HTTP_STATUSES:
                raise FetchError(f"HTTP {exc.code} for {url}", kind="permanent", status=exc.code) from exc
            if exc.code in TRANSIENT_HTTP_STATUSES:
                retry_after = exc.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 60))
                continue
            raise FetchError(f"HTTP {exc.code} for {url}", kind="http", status=exc.code) from exc
        except URLError as exc:
            last_error = exc
            continue

        if not body.strip():
            last_error = FetchError(f"Empty response for {url}", kind="empty")
            continue
        blocked_reason = blocked_page_reason(body)
        if blocked_reason:
            raise FetchError(f"Blocked page for {url}: {blocked_reason}", kind="blocked")
        atomic_write_text(cache_path, body)
        return body

    if isinstance(last_error, FetchError):
        raise last_error
    raise FetchError(f"Fetch failed after retries for {url}: {last_error}", kind="transient") from last_error


def search_url(query: str, hh: HhSettings, page: int) -> str:
    params: list[tuple[str, str | int]] = [
        ("area", hh.area),
        ("text", query),
        ("page", page),
    ]
    filters = hh.filters
    for field in filters.search_field:
        params.append(("search_field", field))
    for experience in filters.experience:
        params.append(("experience", experience))
    for schedule in filters.schedule:
        params.append(("schedule", schedule))
    for employment in filters.employment:
        params.append(("employment", employment))
    for industry in filters.industry:
        params.append(("industry", industry))
    if filters.salary is not None:
        params.append(("salary", filters.salary))
    if filters.only_with_salary:
        params.append(("only_with_salary", "true"))
    if filters.order_by != "relevance":
        params.append(("order_by", filters.order_by))
    if filters.period is not None:
        params.append(("period", filters.period))
    return f"{BASE_URL}/search/vacancy?{urlencode(params)}"


def extract_vacancy_ids(search_html: str) -> list[str]:
    ids = re.findall(r"https://hh\.ru/vacancy/(\d+)", search_html)
    ids.extend(re.findall(r'href="/vacancy/(\d+)[^"]*"', search_html))
    return unique(ids)


def has_next_page(search_html: str, page: int) -> bool:
    next_page = page + 1
    return f"page={next_page}" in search_html or 'data-qa="pager-next"' in search_html


def extract_skills_from_state(page_html: str) -> list[str]:
    skills: list[str] = []
    for match in re.finditer(r'"keySkills"\s*:\s*(null|\[[^\]]*\])', page_html):
        raw = match.group(1)
        if raw == "null":
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in parsed:
            if isinstance(item, dict):
                name = item.get("name") or item.get("title")
                if isinstance(name, str) and name.strip():
                    skills.append(name.strip())
    return unique(skills)


def extract_title_from_meta(page_html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.S | re.I)
    if not match:
        return ""
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    title = re.sub(r"^Вакансия\s+", "", title)
    title = re.sub(r"\s+в\s+.+?,\s+работа\s+в\s+компании\s+.+$", "", title)
    return title


def json_string_from_match(match: re.Match[str]) -> str:
    try:
        return compact_text(json.loads(f'"{match.group(1)}"'))
    except json.JSONDecodeError:
        return ""


def find_hiring_organization_name(value: object) -> str:
    if isinstance(value, dict):
        organization = value.get("hiringOrganization")
        if isinstance(organization, dict):
            name = organization.get("name")
            if isinstance(name, str) and name.strip():
                return compact_text(name)
        for nested in value.values():
            found = find_hiring_organization_name(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_hiring_organization_name(item)
            if found:
                return found
    return ""


def extract_company_from_json_ld(page_html: str) -> str:
    scripts = re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        re.S | re.I,
    )
    for script in scripts:
        raw = html.unescape(script.group(1)).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = find_hiring_organization_name(parsed)
        if name:
            return name
    return ""


def extract_company_from_state(page_html: str) -> str:
    patterns = (
        r'"employer"\s*:\s*\{.*?"name"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"companyName"\s*:\s*"((?:\\.|[^"\\])*)"',
    )
    for pattern in patterns:
        match = re.search(pattern, page_html, re.S)
        if match:
            value = json_string_from_match(match)
            if value:
                return value
    return ""


def extract_company_from_page(page_html: str, parser: VacancyPageParser) -> str:
    return (
        compact_text(" ".join(parser.company_parts))
        or extract_company_from_json_ld(page_html)
        or extract_company_from_state(page_html)
    )


def collect_named_values(value: object) -> list[str]:
    if isinstance(value, dict):
        found: list[str] = []
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            found.append(compact_inline_text(name))
        for nested in value.values():
            found.extend(collect_named_values(nested))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(collect_named_values(item))
        return found
    return []


def extract_employer_industry_from_state(page_html: str) -> str:
    for key in ("industries", "employerIndustries"):
        for match in re.finditer(rf'"{key}"\s*:\s*(\[[^\]]*\])', page_html):
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            names = unique(collect_named_values(parsed))
            if names:
                return "; ".join(names)
    return ""


def parse_vacancy(vacancy_id: str, page_html: str) -> Vacancy:
    parser = VacancyPageParser()
    parser.feed(page_html)

    title = compact_text(" ".join(parser.title_parts)) or extract_title_from_meta(page_html)
    company = extract_company_from_page(page_html, parser)
    salary = compact_inline_text(" ".join(parser.salary_parts))
    experience = compact_inline_text(" ".join(parser.experience_parts))
    schedule = join_vacancy_attributes(
        " ".join(parser.employment_parts),
        *compact_text("".join(parser.schedule_parts)).splitlines(),
    )
    employer_industry = extract_employer_industry_from_state(page_html)
    description = compact_text("".join(parser.description_parts))
    skills = unique(extract_skills_from_state(page_html) + [compact_text(s) for s in parser.skill_parts])

    if not description:
        match = re.search(r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', page_html)
        if match:
            try:
                raw_description = json.loads(f'"{match.group(1)}"')
                description = compact_text(re.sub(r"<[^>]+>", "\n", raw_description))
            except json.JSONDecodeError:
                pass

    return Vacancy(
        vacancy_id=vacancy_id,
        title=title,
        description=description,
        url=f"{BASE_URL}/vacancy/{vacancy_id}",
        company=company,
        salary=salary,
        experience=experience,
        schedule=schedule,
        employer_industry=employer_industry,
        skills=skills,
    )


def field_haystacks(vacancy: Vacancy) -> dict[str, str]:
    return {
        "title": vacancy.title,
        "company": vacancy.company,
        "description": vacancy.description,
        "skills": " ".join(vacancy.skills),
    }


def profile_enabled_fields(profile: SearchProfile) -> list[str]:
    return [field for field in ENABLED_FIELDS if profile.match_scope.get(field) is True]


def has_excluded_context(
    term: str,
    scoped_text: str,
    profile: SearchProfile,
) -> bool:
    patterns = profile.exclude_patterns.get(term, [])
    if not patterns:
        return False
    return any(pattern.search(scoped_text) for pattern in patterns)


def matching_terms(vacancy: Vacancy, profile: SearchProfile) -> list[Match]:
    haystacks = field_haystacks(vacancy)
    enabled_fields = profile_enabled_fields(profile)
    exclude_haystack = ""
    matches: list[Match] = []
    for term, patterns in profile.term_patterns.items():
        fields = [
            field
            for field in enabled_fields
            if any(pattern.search(haystacks[field]) for pattern in patterns)
        ]
        if fields and profile.exclude_patterns.get(term) and not exclude_haystack:
            exclude_haystack = "\n".join(haystacks[field] for field in enabled_fields)
        if fields and not has_excluded_context(term, exclude_haystack, profile):
            matches.append(Match(term=term, fields=fields))
    return matches


def collect_search_ids(args: argparse.Namespace, profile: SearchProfile) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for label, queries in profile.search_terms.items():
        for query in queries:
            previous_ids: set[str] = set()
            empty_pages = 0
            for page in range(profile.hh.max_pages):
                url = search_url(query, profile.hh, page)
                cache_path = cache_path_for_url(args.cache_dir, "search", url, f"{query}_page_{page}")
                search_html = fetch_url(
                    url,
                    cache_path,
                    profile.hh.search_delay_min,
                    profile.hh.search_delay_max,
                )
                blocked_reason = blocked_page_reason(search_html)
                if blocked_reason:
                    raise FetchError(
                        f"Blocked search page for {query!r}, page {page}: {blocked_reason}",
                        kind="blocked",
                    )
                ids = extract_vacancy_ids(search_html)
                new_ids = [vacancy_id for vacancy_id in ids if vacancy_id not in previous_ids]

                print(
                    f"search '{label}' / {query}, page {page}: "
                    f"{len(ids)} ids, {len(new_ids)} new on this query",
                    flush=True,
                )
                found.setdefault(label, [])
                found[label].extend(ids)
                previous_ids.update(ids)

                if not ids:
                    empty_pages += 1
                else:
                    empty_pages = 0

                if empty_pages >= 2 or not has_next_page(search_html, page):
                    break
    return {term: unique(ids) for term, ids in found.items()}


def collect_vacancies(
    args: argparse.Namespace,
    profile: SearchProfile,
    vacancy_ids: list[str],
    search_ids: dict[str, list[str]],
) -> list[Vacancy]:
    fingerprint = profile_fingerprint(profile)
    vacancy_id_set = set(vacancy_ids)
    checkpoint = load_checkpoint(args.checkpoint_jsonl, fingerprint)
    processed_ids: set[str] = set()
    vacancies: list[Vacancy] = []
    for vacancy_id, record in checkpoint.items():
        if vacancy_id not in vacancy_id_set:
            continue
        if record.get("kept") is True:
            vacancy = vacancy_from_checkpoint_record(record, profile, args.cache_dir)
            if vacancy is None:
                raise FetchError(
                    f"Checkpoint has kept vacancy {vacancy_id}, but full cached HTML is missing or unusable. "
                    "Restore the original --cache-dir to resume without data loss, or remove the checkpoint "
                    "entry/file if you intentionally want to reprocess it.",
                    kind="checkpoint",
                )
            vacancies.append(vacancy)
        processed_ids.add(vacancy_id)
    processed_since_write = 0

    for index, vacancy_id in enumerate(vacancy_ids, start=1):
        if vacancy_id in processed_ids:
            print(f"vacancy {index}/{len(vacancy_ids)} already checkpointed {vacancy_id}", flush=True)
            continue

        url = f"{BASE_URL}/vacancy/{vacancy_id}"
        cache_path = cache_path_for_url(args.cache_dir, "vacancies", url, vacancy_id)
        try:
            page_html = fetch_url(
                url,
                cache_path,
                profile.hh.vacancy_delay_min,
                profile.hh.vacancy_delay_max,
            )
        except FetchError as exc:
            if exc.kind == "permanent":
                vacancy = Vacancy(vacancy_id=vacancy_id, title="", description="", url=url)
                print(f"skip {vacancy_id}: {exc}", flush=True)
                append_checkpoint(
                    args.checkpoint_jsonl,
                    vacancy,
                    kept=False,
                    reason=str(exc),
                    profile_fingerprint=fingerprint,
                )
                continue
            raise

        blocked_reason = blocked_page_reason(page_html)
        if blocked_reason:
            raise FetchError(
                f"Blocked vacancy page for {vacancy_id}: {blocked_reason}",
                kind="blocked",
            )
        vacancy = parse_vacancy(vacancy_id, page_html)
        vacancy.matches = matching_terms(vacancy, profile)

        if not (vacancy.title or vacancy.company or vacancy.description or vacancy.skills):
            failed_path = quarantine_parse_failure_cache(cache_path)
            raise FetchError(
                f"Could not parse vacancy page {vacancy_id}; cached HTML moved to {failed_path}",
                kind="parse",
            )
        if not vacancy.description and profile.match_scope.get("description"):
            failed_path = quarantine_parse_failure_cache(cache_path)
            raise FetchError(
                f"No full description found for vacancy {vacancy_id}; cached HTML moved to {failed_path}",
                kind="parse",
            )
        if not vacancy.matches:
            enabled = "/".join(profile_enabled_fields(profile))
            print(f"skip {vacancy_id}: no requested term in {enabled}", flush=True)
            append_checkpoint(
                args.checkpoint_jsonl,
                vacancy,
                kept=False,
                reason=f"no requested term in {enabled}",
                profile_fingerprint=fingerprint,
            )
            continue

        print(
            f"vacancy {index}/{len(vacancy_ids)} kept {vacancy_id}: "
            f"{', '.join(vacancy.matched_terms)}",
            flush=True,
        )
        vacancies.append(vacancy)
        append_checkpoint(
            args.checkpoint_jsonl,
            vacancy,
            kept=True,
            reason="",
            profile_fingerprint=fingerprint,
        )
        processed_since_write += 1
        if args.write_every > 0 and processed_since_write >= args.write_every:
            write_outputs(args, profile, vacancies, search_ids, vacancy_ids)
            processed_since_write = 0
    return vacancies


def match_to_record(match: Match) -> dict[str, object]:
    return {"term": match.term, "fields": match.fields}


def vacancy_to_record(
    vacancy: Vacancy,
    kept: bool,
    reason: str,
    include_full_text: bool = True,
) -> dict[str, object]:
    if not kept:
        return {
            "id": vacancy.vacancy_id,
            "title": vacancy.title,
            "company": vacancy.company,
            "salary": vacancy.salary,
            "experience": vacancy.experience,
            "schedule": vacancy.schedule,
            "employer_industry": vacancy.employer_industry,
            "url": vacancy.url,
            "matched_terms": [],
            "matches": [],
            "kept": False,
            "skip_reason": reason,
        }
    record: dict[str, object] = {
        "id": vacancy.vacancy_id,
        "title": vacancy.title,
        "company": vacancy.company,
        "salary": vacancy.salary,
        "experience": vacancy.experience,
        "schedule": vacancy.schedule,
        "employer_industry": vacancy.employer_industry,
        "url": vacancy.url,
        "matched_terms": vacancy.matched_terms,
        "matches": [match_to_record(match) for match in vacancy.matches],
        "kept": kept,
        "skip_reason": reason,
    }
    if include_full_text:
        record["description"] = vacancy.description
        record["skills"] = vacancy.skills
    return record


def fingerprint_match_scope(match_scope: dict[str, bool]) -> dict[str, bool]:
    result = {field: match_scope[field] for field in REQUIRED_MATCH_FIELDS}
    if match_scope.get("company") is True:
        result["company"] = True
    return result


def fingerprint_hh_settings(hh: HhSettings) -> dict[str, object]:
    result: dict[str, object] = {
        "area": hh.area,
        "max_pages": hh.max_pages,
    }
    filters = filters_to_record(hh.filters)
    if filters != filters_to_record(HhFilters()):
        result["filters"] = filters
    return result


def profile_fingerprint(profile: SearchProfile) -> str:
    fingerprint_payload = {
        "hh": fingerprint_hh_settings(profile.hh),
        "match_scope": fingerprint_match_scope(profile.match_scope),
        "search_terms": profile.search_terms,
        "term_patterns": {
            term: [pattern.pattern for pattern in patterns]
            for term, patterns in profile.term_patterns.items()
        },
        "exclude_patterns": {
            term: [pattern.pattern for pattern in patterns]
            for term, patterns in profile.exclude_patterns.items()
        },
    }
    return hashlib.sha256(stable_json(fingerprint_payload).encode("utf-8")).hexdigest()


def match_from_record(record: dict[str, object]) -> Match:
    raw_fields = record.get("fields", [])
    fields = raw_fields if isinstance(raw_fields, list) else []
    return Match(
        term=str(record.get("term", "")),
        fields=[str(item) for item in fields if isinstance(item, str)],
    )


def vacancy_from_record(record: dict[str, object], profile: SearchProfile) -> Vacancy:
    raw_skills = record.get("skills", [])
    skills = raw_skills if isinstance(raw_skills, list) else []
    raw_matches = record.get("matches", [])
    matches = raw_matches if isinstance(raw_matches, list) else []
    vacancy = Vacancy(
        vacancy_id=str(record.get("id", "")),
        title=str(record.get("title", "")),
        description=str(record.get("description", "")),
        url=str(record.get("url", "")),
        company=str(record.get("company", "")),
        salary=str(record.get("salary", "")),
        experience=str(record.get("experience", "")),
        schedule=str(record.get("schedule", "")),
        employer_industry=str(record.get("employer_industry", "")),
        skills=[str(item) for item in skills if isinstance(item, str)],
        matches=[
            match_from_record(item)
            for item in matches
            if isinstance(item, dict)
        ],
    )
    if not vacancy.matches and any(field_haystacks(vacancy).values()):
        vacancy.matches = matching_terms(vacancy, profile)
    return vacancy


def vacancy_from_checkpoint_record(
    record: dict[str, object],
    profile: SearchProfile,
    cache_dir: Path,
) -> Vacancy | None:
    if record.get("description") or record.get("skills"):
        return vacancy_from_record(record, profile)

    vacancy_id = str(record.get("id", ""))
    url = str(record.get("url") or f"{BASE_URL}/vacancy/{vacancy_id}")
    if not vacancy_id:
        return None

    cache_path = cache_path_for_url(cache_dir, "vacancies", url, vacancy_id)
    if not cache_path.exists():
        return None
    page_html = cache_path.read_text(encoding="utf-8", errors="replace")
    if blocked_page_reason(page_html):
        cache_path.unlink(missing_ok=True)
        return None
    vacancy = parse_vacancy(vacancy_id, page_html)
    if not vacancy.description and profile.match_scope.get("description"):
        return None
    vacancy.matches = matching_terms(vacancy, profile)
    if not vacancy.matches:
        return None
    return vacancy


def iter_checkpoint_records(path: Path) -> Iterable[dict[str, object]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"ignore invalid checkpoint line {line_number}", flush=True)
                continue
            if isinstance(record, dict):
                yield record


def load_checkpoint(path: Path, expected_fingerprint: str | None = None) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    total = 0
    ignored_fingerprint = 0
    ignored_status = 0
    for record in iter_checkpoint_records(path):
        total += 1
        if expected_fingerprint and record.get("profile_fingerprint") != expected_fingerprint:
            ignored_fingerprint += 1
            continue
        if record.get("status") not in {None, "kept", "skipped"}:
            ignored_status += 1
            continue
        vacancy_id = str(record.get("id", ""))
        if vacancy_id:
            records[vacancy_id] = record
    if total:
        print(
            f"checkpoint records loaded: {len(records)} reused, "
            f"{ignored_fingerprint} ignored by profile_fingerprint mismatch, "
            f"{ignored_status} ignored by status",
            flush=True,
        )
    return records


def append_checkpoint(
    path: Path,
    vacancy: Vacancy,
    kept: bool,
    reason: str,
    profile_fingerprint: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    repair_checkpoint_tail(path)
    record = vacancy_to_record(vacancy, kept=kept, reason=reason, include_full_text=False)
    record["status"] = "kept" if kept else "skipped"
    record["profile_fingerprint"] = profile_fingerprint
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def repair_checkpoint_tail(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open("rb+") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(size - 1)
        if handle.read(1) == b"\n":
            return
        handle.seek(0)
        data = handle.read()
        last_newline = data.rfind(b"\n")
        handle.seek(0)
        if last_newline == -1:
            handle.truncate(0)
        else:
            handle.truncate(last_newline + 1)


def quarantine_parse_failure_cache(cache_path: Path) -> Path:
    failed_path = cache_path.with_name(f"{cache_path.name}.parse_failed")
    if cache_path.exists():
        cache_path.replace(failed_path)
    return failed_path


def summary_for(
    vacancies: list[Vacancy],
    checkpoint_path: Path,
    fingerprint: str,
    inspected_ids: Iterable[str],
) -> dict[str, object]:
    inspected_id_set = set(inspected_ids)
    latest_kept_by_id: dict[str, bool] = {}
    for record in iter_checkpoint_records(checkpoint_path):
        if record.get("profile_fingerprint") != fingerprint:
            continue
        if record.get("status") not in {None, "kept", "skipped"}:
            continue
        vacancy_id = str(record.get("id", ""))
        if vacancy_id not in inspected_id_set:
            continue
        latest_kept_by_id[vacancy_id] = record.get("kept") is True
    top_terms: Counter[str] = Counter()
    for vacancy in vacancies:
        top_terms.update(vacancy.matched_terms)
    return {
        "checked": len(latest_kept_by_id),
        "kept": len(vacancies),
        "skipped": sum(1 for kept in latest_kept_by_id.values() if not kept),
        "top_terms": dict(top_terms.most_common()),
    }


def write_outputs(
    args: argparse.Namespace,
    profile: SearchProfile,
    vacancies: list[Vacancy],
    search_ids: dict[str, list[str]],
    inspected_ids: Iterable[str],
) -> None:
    fingerprint = profile_fingerprint(profile)
    atomic_write_text(
        args.output_json,
        json.dumps(
            {
                "title": profile.title,
                "profile": profile_to_record(profile),
                "summary": summary_for(vacancies, args.checkpoint_jsonl, fingerprint, inspected_ids),
                "search_ids": search_ids,
                "vacancies": [
                    vacancy_to_record(vacancy, kept=True, reason="")
                    for vacancy in sorted(vacancies, key=lambda item: item.title.lower())
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def profile_to_record(profile: SearchProfile) -> dict[str, object]:
    return {
        "title": profile.title,
        "hh": {
            "area": profile.hh.area,
            "max_pages": profile.hh.max_pages,
            "search_delay_min": profile.hh.search_delay_min,
            "search_delay_max": profile.hh.search_delay_max,
            "vacancy_delay_min": profile.hh.vacancy_delay_min,
            "vacancy_delay_max": profile.hh.vacancy_delay_max,
            "filters": filters_to_record(profile.hh.filters),
        },
        "match_scope": profile.match_scope,
        "search_terms": profile.search_terms,
        "term_patterns": {
            term: [pattern.pattern for pattern in patterns]
            for term, patterns in profile.term_patterns.items()
        },
        "exclude_patterns": {
            term: [pattern.pattern for pattern in patterns]
            for term, patterns in profile.exclude_patterns.items()
        },
        "notes": profile.notes,
    }


def require_dict(raw: object, key: str, path: Path) -> dict[str, object]:
    value = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{path}: {key} must be a non-empty object")
    return value


def require_number(raw: dict[str, object], key: str, path: Path) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: hh.{key} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{path}: hh.{key} must be a finite non-negative number")
    return result


def filters_to_record(filters: HhFilters) -> dict[str, object]:
    return {
        "search_field": list(filters.search_field),
        "experience": list(filters.experience),
        "schedule": list(filters.schedule),
        "employment": list(filters.employment),
        "industry": list(filters.industry),
        "salary": filters.salary,
        "only_with_salary": filters.only_with_salary,
        "order_by": filters.order_by,
        "period": filters.period,
    }


def require_filter_list(
    raw: dict[str, object],
    key: str,
    allowed_values: set[str],
    path: Path,
) -> tuple[str, ...]:
    value = raw.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{path}: hh.filters.{key} must be a list")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: hh.filters.{key}[{index}] must be a non-empty string")
        normalized = item.strip()
        if normalized not in allowed_values:
            raise ValueError(
                f"{path}: hh.filters.{key}[{index}] has unsupported value {normalized!r}; "
                f"allowed values: {', '.join(sorted(allowed_values))}"
            )
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def require_hh_id_list(
    raw: dict[str, object],
    key: str,
    path: Path,
) -> tuple[str, ...]:
    value = raw.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{path}: hh.filters.{key} must be a list")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: hh.filters.{key}[{index}] must be a non-empty string")
        normalized = item.strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", normalized):
            raise ValueError(
                f"{path}: hh.filters.{key}[{index}] must be an hh.ru dictionary id, "
                "for example '7' or '7.540'"
            )
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def require_optional_positive_int(
    raw: dict[str, object],
    key: str,
    path: Path,
    maximum: int | None = None,
) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{path}: hh.filters.{key} must be a positive integer or null")
    if maximum is not None and value > maximum:
        raise ValueError(f"{path}: hh.filters.{key} must be <= {maximum}")
    return value


def load_hh_filters(hh_raw: dict[str, object], path: Path) -> HhFilters:
    filters_raw = hh_raw.get("filters", {})
    if filters_raw is None:
        filters_raw = {}
    if not isinstance(filters_raw, dict):
        raise ValueError(f"{path}: hh.filters must be an object when present")
    unknown_filters = set(filters_raw) - HH_FILTER_FIELDS
    if unknown_filters:
        raise ValueError(f"{path}: unknown hh.filters fields: {', '.join(sorted(unknown_filters))}")

    order_by = filters_raw.get("order_by", "relevance")
    if not isinstance(order_by, str) or not order_by.strip():
        raise ValueError(f"{path}: hh.filters.order_by must be a non-empty string")
    order_by = order_by.strip()
    if order_by not in ORDER_BY_VALUES:
        raise ValueError(
            f"{path}: hh.filters.order_by has unsupported value {order_by!r}; "
            f"allowed values: {', '.join(sorted(ORDER_BY_VALUES))}"
        )

    only_with_salary = filters_raw.get("only_with_salary", False)
    if not isinstance(only_with_salary, bool):
        raise ValueError(f"{path}: hh.filters.only_with_salary must be a boolean")

    return HhFilters(
        search_field=require_filter_list(filters_raw, "search_field", SEARCH_FIELD_VALUES, path),
        experience=require_filter_list(filters_raw, "experience", EXPERIENCE_VALUES, path),
        schedule=require_filter_list(filters_raw, "schedule", SCHEDULE_VALUES, path),
        employment=require_filter_list(filters_raw, "employment", EMPLOYMENT_VALUES, path),
        industry=require_hh_id_list(filters_raw, "industry", path),
        salary=require_optional_positive_int(filters_raw, "salary", path),
        only_with_salary=only_with_salary,
        order_by=order_by,
        period=require_optional_positive_int(filters_raw, "period", path, maximum=30),
    )


def load_json_object(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: profile must be an object")
    return raw


def load_profile(path: Path) -> SearchProfile:
    raw = load_json_object(path)
    unknown_profile_fields = set(raw) - PROFILE_FIELDS
    if unknown_profile_fields:
        raise ValueError(f"{path}: unknown profile fields: {', '.join(sorted(unknown_profile_fields))}")

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{path}: title must be a non-empty string")

    hh_raw = require_dict(raw, "hh", path)
    unknown_hh_fields = set(hh_raw) - HH_FIELDS
    if unknown_hh_fields:
        raise ValueError(f"{path}: unknown hh fields: {', '.join(sorted(unknown_hh_fields))}")
    area = hh_raw.get("area")
    max_pages = hh_raw.get("max_pages")
    if not isinstance(area, str) or not area.strip():
        raise ValueError(f"{path}: hh.area must be a non-empty string")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError(f"{path}: hh.max_pages must be a positive integer")

    hh = HhSettings(
        area=area.strip(),
        max_pages=max_pages,
        search_delay_min=require_number(hh_raw, "search_delay_min", path),
        search_delay_max=require_number(hh_raw, "search_delay_max", path),
        vacancy_delay_min=require_number(hh_raw, "vacancy_delay_min", path),
        vacancy_delay_max=require_number(hh_raw, "vacancy_delay_max", path),
        filters=load_hh_filters(hh_raw, path),
    )
    if hh.search_delay_min > hh.search_delay_max:
        raise ValueError(f"{path}: search_delay_min cannot exceed search_delay_max")
    if hh.vacancy_delay_min > hh.vacancy_delay_max:
        raise ValueError(f"{path}: vacancy_delay_min cannot exceed vacancy_delay_max")

    match_scope_raw = require_dict(raw, "match_scope", path)
    unknown_scope_fields = set(match_scope_raw) - set(ENABLED_FIELDS)
    required_scope_fields: set[str] = set(REQUIRED_MATCH_FIELDS)
    missing_scope_fields = required_scope_fields - set(match_scope_raw)
    if unknown_scope_fields:
        raise ValueError(f"{path}: unknown match_scope fields: {', '.join(sorted(unknown_scope_fields))}")
    if missing_scope_fields:
        raise ValueError(f"{path}: missing match_scope fields: {', '.join(sorted(missing_scope_fields))}")
    match_scope: dict[str, bool] = {}
    for field in ENABLED_FIELDS:
        value = match_scope_raw.get(field, False)
        if not isinstance(value, bool):
            raise ValueError(f"{path}: match_scope.{field} must be a boolean")
        match_scope[field] = value
    if not any(match_scope.values()):
        raise ValueError(f"{path}: match_scope must enable at least one field")

    search_terms = normalize_string_lists(require_dict(raw, "search_terms", path), "search_terms", path)
    pattern_strings = normalize_string_lists(require_dict(raw, "term_patterns", path), "term_patterns", path)
    missing_patterns = set(search_terms) - set(pattern_strings)
    if missing_patterns:
        raise ValueError(f"{path}: term_patterns missing labels: {', '.join(sorted(missing_patterns))}")
    extra_patterns = set(pattern_strings) - set(search_terms)
    if extra_patterns:
        raise ValueError(f"{path}: term_patterns has labels not present in search_terms: {', '.join(sorted(extra_patterns))}")

    exclude_raw = raw.get("exclude_patterns", {})
    if exclude_raw is None:
        exclude_raw = {}
    if not isinstance(exclude_raw, dict):
        raise ValueError(f"{path}: exclude_patterns must be an object when present")
    extra_exclusions = set(exclude_raw) - set(pattern_strings)
    if extra_exclusions:
        raise ValueError(f"{path}: exclude_patterns has labels not present in term_patterns: {', '.join(sorted(extra_exclusions))}")

    notes = raw.get("notes", "")
    if notes is None:
        notes = ""
    if not isinstance(notes, str):
        raise ValueError(f"{path}: notes must be a string when present")

    return SearchProfile(
        title=title.strip(),
        hh=hh,
        match_scope=match_scope,
        search_terms=search_terms,
        term_patterns=compile_patterns(pattern_strings, path),
        exclude_patterns=compile_patterns(
            normalize_string_lists(exclude_raw, "exclude_patterns", path, allow_empty=True),
            path,
        ),
        notes=notes,
    )


def normalize_string_lists(
    raw: dict[str, object],
    owner: str,
    path: Path,
    allow_empty: bool = False,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for label, values in raw.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{path}: {owner} labels must be non-empty strings")
        normalized_label = label.strip()
        if normalized_label in result:
            raise ValueError(f"{path}: {owner} has duplicate label after trimming: {normalized_label}")
        if not isinstance(values, list):
            raise ValueError(f"{path}: {owner}.{label} must be a list")
        normalized: list[str] = []
        for index, value in enumerate(values, start=1):
            if not isinstance(value, str):
                raise ValueError(f"{path}: {owner}.{label}[{index}] must be a string")
            stripped = value.strip()
            if not stripped:
                raise ValueError(f"{path}: {owner}.{label}[{index}] must be a non-empty string")
            normalized.append(stripped)
        if not normalized and not allow_empty:
            raise ValueError(f"{path}: {owner}.{label} must contain at least one string")
        if normalized:
            result[normalized_label] = normalized
    if not result and not allow_empty:
        raise ValueError(f"{path}: {owner} must contain at least one non-empty entry")
    return result


def compile_patterns(raw: dict[str, list[str]], path: Path) -> dict[str, list[re.Pattern[str]]]:
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for label, patterns in raw.items():
        try:
            compiled[label] = [re.compile(pattern, re.I) for pattern in patterns]
        except re.error as exc:
            raise ValueError(f"{path}: invalid regex in {label}: {exc}") from exc
    return compiled


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_work_paths(args: argparse.Namespace) -> None:
    root = skill_root()
    for label, path in {
        "cache-dir": args.cache_dir,
        "output-json": args.output_json,
        "checkpoint-jsonl": args.checkpoint_jsonl,
    }.items():
        if is_relative_to(path, root):
            raise ValueError(f"--{label} must not point inside the skill package")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect hh.ru vacancies for a confirmed search profile."
    )
    parser.add_argument("--profile", type=Path, required=True, help="Path to the confirmed search profile JSON.")
    parser.add_argument("--cache-dir", type=Path, default=Path("hh_cache"), help="Directory for cached hh.ru HTML pages.")
    parser.add_argument("--output-json", type=Path, default=Path("hh_vacancies.json"), help="Result JSON path.")
    parser.add_argument("--checkpoint-jsonl", type=Path, default=Path("hh_vacancies_checked.jsonl"), help="Resume checkpoint JSONL path.")
    parser.add_argument("--limit-vacancies", type=non_negative_int, default=0, help="Inspect only the first N unique vacancy IDs; 0 means no limit.")
    parser.add_argument("--write-every", type=non_negative_int, default=0, help="Write full JSON snapshots after every N kept vacancies; 0 writes only the final JSON.")
    parser.add_argument("--validate-profile", action="store_true", help="Validate the profile and exit without network access.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    if args.validate_profile:
        print(f"profile ok: {profile.title}")
        print(f"enabled fields: {', '.join(profile_enabled_fields(profile))}")
        print(f"search groups: {len(profile.search_terms)}")
        return 0

    validate_work_paths(args)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    search_ids = collect_search_ids(args, profile)
    vacancy_ids = unique(vacancy_id for ids in search_ids.values() for vacancy_id in ids)
    if args.limit_vacancies:
        vacancy_ids = vacancy_ids[: args.limit_vacancies]
    print(f"unique vacancy ids to inspect: {len(vacancy_ids)}", flush=True)

    vacancies = collect_vacancies(args, profile, vacancy_ids, search_ids)
    write_outputs(args, profile, vacancies, search_ids, vacancy_ids)
    print(f"wrote {args.output_json}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, json.JSONDecodeError, ValueError, FetchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
