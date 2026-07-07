import unittest
import argparse
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import scripts.hh_vacancy_scraper as scraper
from scripts.hh_vacancy_scraper import parse_vacancy, vacancy_to_record


class VacancyParsingTest(unittest.TestCase):
    def search_results(
        self,
        ids_by_group: dict[str, list[str]] | None = None,
        queries_by_vacancy: dict[str, list[str]] | None = None,
    ) -> scraper.SearchResults:
        return scraper.SearchResults(
            ids_by_group=ids_by_group or {"RAG": ["123"]},
            queries_by_vacancy=queries_by_vacancy or {"123": ["RAG"]},
        )

    def scraper_args(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            cache_dir=root / "cache",
            checkpoint_jsonl=root / "checkpoint.jsonl",
            write_every=0,
            output_json=root / "out.json",
        )

    def search_profile(self) -> scraper.SearchProfile:
        return scraper.SearchProfile(
            title="Test",
            hh=scraper.HhSettings(
                area="1",
                max_pages=1,
                search_delay_min=0,
                search_delay_max=0,
                vacancy_delay_min=0,
                vacancy_delay_max=0,
            ),
            match_scope={"title": True, "description": True, "skills": True, "company": False},
            term_patterns={"RAG": [scraper.re.compile("RAG", scraper.re.I)]},
            exclude_patterns={},
            search_terms={"RAG": ["RAG"]},
        )

    def profile_payload(self, filters: dict[str, object] | None = None, area: str = "2") -> dict[str, object]:
        hh: dict[str, object] = {
            "area": area,
            "max_pages": 1,
            "search_delay_min": 0,
            "search_delay_max": 0,
            "vacancy_delay_min": 0,
            "vacancy_delay_max": 0,
        }
        if filters is not None:
            hh["filters"] = filters
        return {
            "title": "Profile validation test",
            "hh": hh,
            "match_scope": {
                "title": False,
                "company": False,
                "description": True,
                "skills": False,
            },
            "search_terms": {"MCP": ["MCP"]},
            "term_patterns": {"MCP": ["MCP"]},
            "exclude_patterns": {},
            "notes": "",
        }

    def test_parse_vacancy_extracts_visible_vacancy_attributes(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <html>
              <head>
                <title>Вакансия ML Engineer в Москве</title>
              </head>
              <body>
                <h1 data-qa="vacancy-title">ML Engineer</h1>
                <a data-qa="vacancy-company-name">Example AI</a>
                <div data-qa="vacancy-salary">
                  <span>от 300 000 ₽ на руки</span>
                </div>
                <p data-qa="work-experience-text">
                  Опыт работы: <span data-qa="vacancy-experience">3–6 лет</span>
                </p>
                <div data-qa="common-employment-text"><span>Полная занятость</span></div>
                <p data-qa="work-schedule-by-days-text">График: 5/2</p>
                <div data-qa="working-hours-text"><span>Рабочие часы: 8</span></div>
                <p data-qa="work-formats-text">Формат работы: удалённо</p>
                <div data-qa="vacancy-description">Build RAG systems</div>
                <span data-qa="bloko-tag__text">Python</span>
              </body>
            </html>
            """,
        )

        self.assertEqual(vacancy.salary, "от 300 000 ₽ на руки")
        self.assertEqual(vacancy.experience, "3–6 лет")
        self.assertEqual(vacancy.work_format, "удалённо")

    def test_parse_vacancy_unescapes_json_description_fallback(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <script>
            {"description":"&lt;p&gt;First &lt;strong&gt;RAG&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Use GitHub Copilot&lt;/li&gt;&lt;/ul&gt;"}
            </script>
            """,
        )

        self.assertEqual(vacancy.description, "First RAG\nUse GitHub Copilot")

    def test_parse_vacancy_preserves_self_closing_breaks_in_json_description(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <script>
            {"description":"&lt;p&gt;First&lt;br/&gt;Second&lt;/p&gt;"}
            </script>
            """,
        )

        self.assertEqual(vacancy.description, "First\nSecond")

    def test_parse_vacancy_uses_short_vacancy_state_fallback(self) -> None:
        vacancy = parse_vacancy(
            "134105824",
            """
            <script>
            {"vacancies":{"134105824":{"shortVacancy":{
              "vacancyId":134105824,
              "name":"Middle Unity Developer (Marketing, Playable Ads)",
              "company":{"id":2666179,"name":"Azur Games","visibleName":"Azur Games"}
            }}},"description":"&lt;p&gt;Use &lt;strong&gt;GitHub Copilot&lt;/strong&gt;&lt;/p&gt;"}
            </script>
            """,
        )

        self.assertEqual(vacancy.title, "Middle Unity Developer (Marketing, Playable Ads)")
        self.assertEqual(vacancy.company, "Azur Games")
        self.assertEqual(vacancy.employer_id, "2666179")
        self.assertEqual(vacancy.description, "Use GitHub Copilot")

    def test_parse_vacancy_uses_matching_short_vacancy_state(self) -> None:
        vacancy = parse_vacancy(
            "134105824",
            """
            <script>
            {"vacancies":{
              "111":{"shortVacancy":{
                "vacancyId":111,
                "name":"Wrong Vacancy",
                "company":{"id":1111,"name":"Wrong Company"}
              }},
              "134105824":{"shortVacancy":{
                "vacancyId":134105824,
                "name":"Middle Unity Developer (Marketing, Playable Ads)",
                "company":{"id":2666179,"name":"Azur Games"}
              }}
            },"description":"&lt;p&gt;Use &lt;strong&gt;GitHub Copilot&lt;/strong&gt;&lt;/p&gt;"}
            </script>
            """,
        )

        self.assertEqual(vacancy.title, "Middle Unity Developer (Marketing, Playable Ads)")
        self.assertEqual(vacancy.company, "Azur Games")
        self.assertEqual(vacancy.employer_id, "2666179")

    def test_parse_vacancy_ignores_non_object_id_key_before_other_short_vacancy(self) -> None:
        vacancy = parse_vacancy(
            "134105824",
            """
            <script>
            {"134105824":true,"other":{"shortVacancy":{
              "vacancyId":111,
              "name":"Wrong Vacancy",
              "company":{"id":1111,"name":"Wrong Company"}
            }}}
            </script>
            """,
        )

        self.assertEqual(vacancy.title, "")
        self.assertEqual(vacancy.company, "")
        self.assertEqual(vacancy.employer_id, "")

    def test_parse_vacancy_ignores_non_object_short_vacancy_before_other_object(self) -> None:
        vacancy = parse_vacancy(
            "134105824",
            """
            <script>
            {"shortVacancy":null,"other":{
              "vacancyId":134105824,
              "name":"Wrong Vacancy",
              "company":{"id":1111,"name":"Wrong Company"}
            }}
            </script>
            """,
        )

        self.assertEqual(vacancy.title, "")
        self.assertEqual(vacancy.company, "")
        self.assertEqual(vacancy.employer_id, "")

    def test_parse_vacancy_extracts_employer_id_for_profile_enrichment(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175?hhtmFrom=vacancy">Beoma</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )

        self.assertEqual(vacancy.employer_id, "3797175")

    def test_parse_vacancy_does_not_use_unscoped_state_employer_id(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name">Example AI</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            <template id="HH-Lux-InitialState">
            {"analytics":{"employerId":999999}}
            </template>
            """,
        )

        self.assertEqual(vacancy.employer_id, "")

    def test_parse_vacancy_collapses_repeated_company_name(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>
            <a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )

        self.assertEqual(vacancy.company, "Beoma")

    def test_parse_vacancy_preserves_legitimate_repeated_company_name(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175">Foo Bar Foo Bar</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )

        self.assertEqual(vacancy.company, "Foo Bar Foo Bar")

    def test_extract_employer_industry_from_employer_page_state(self) -> None:
        self.assertEqual(
            scraper.extract_employer_industry_from_employer_page(
                """
                <template id="HH-Lux-InitialState">
                {"employerInfo":{"industries":[
                  {"id":41,"trl":"Розничная торговля","items":[525]},
                  {"id":7,"trl":"Информационные технологии","items":[539]}
                ]}}
                </template>
                """
            ),
            "Розничная торговля; Информационные технологии",
        )

    def test_vacancy_page_industries_do_not_set_employer_industry(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175?hhtmFrom=vacancy">Beoma</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            <template id="HH-Lux-InitialState">
            {"industries":[{"name":"Не источник"}]}
            </template>
            """,
        )

        self.assertEqual(vacancy.employer_industry, "")

    def test_enrich_employer_industry_uses_employer_page(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175?hhtmFrom=vacancy">Beoma</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            <template id="HH-Lux-InitialState">
            {"industries":[{"name":"Не источник"}]}
            </template>
            """,
        )
        args = self.scraper_args(Path("work"))
        profile = self.search_profile()

        with patch.object(
            scraper,
            "fetch_url",
            return_value=(
                '<template id="HH-Lux-InitialState">'
                '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                "</template>"
            ),
        ) as fetch_url:
            scraper.enrich_employer_industry(args, profile, vacancy)

        self.assertEqual(vacancy.employer_industry, "Розничная торговля")
        fetch_url.assert_called_once()

    def test_enrich_employer_industry_replaces_existing_non_employer_page_value(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <a data-qa="vacancy-company-name" href="/employer/3797175?hhtmFrom=vacancy">Beoma</a>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )
        vacancy.employer_industry = "Не источник"
        args = self.scraper_args(Path("work"))
        profile = self.search_profile()

        with patch.object(
            scraper,
            "fetch_url",
            return_value=(
                '<template id="HH-Lux-InitialState">'
                '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                "</template>"
            ),
        ):
            scraper.enrich_employer_industry(args, profile, vacancy)

        self.assertEqual(vacancy.employer_industry, "Розничная торговля")

    def test_reused_checkpoint_appends_enriched_employer_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                """
                <h1 data-qa="vacancy-title">ML Engineer</h1>
                <a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                scraper,
                "fetch_url",
                return_value=(
                    '<template id="HH-Lux-InitialState">'
                    '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                    "</template>"
                ),
            ):
                vacancies = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(vacancies[0].employer_id, "3797175")
            self.assertEqual(vacancies[0].employer_industry, "Розничная торговля")
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["employer_id"], "3797175")
            self.assertEqual(records[-1]["employer_industry"], "Розничная торговля")

    def test_reused_full_checkpoint_reads_cached_vacancy_for_missing_employer_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                """
                <h1 data-qa="vacancy-title">ML Engineer</h1>
                <a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "description": "Build RAG systems",
                        "skills": [],
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                scraper,
                "fetch_url",
                return_value=(
                    '<template id="HH-Lux-InitialState">'
                    '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                    "</template>"
                ),
            ) as fetch_url:
                vacancies = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(vacancies[0].employer_id, "3797175")
            self.assertEqual(vacancies[0].employer_industry, "Розничная торговля")
            fetch_url.assert_called_once()

    def test_reused_full_checkpoint_recovers_employer_id_from_partial_cached_vacancy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                '<a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>',
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "description": "Build RAG systems",
                        "skills": [],
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                scraper,
                "fetch_url",
                return_value=(
                    '<template id="HH-Lux-InitialState">'
                    '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                    "</template>"
                ),
            ) as fetch_url:
                vacancies = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(vacancies[0].employer_id, "3797175")
            self.assertEqual(vacancies[0].employer_industry, "Розничная торговля")
            fetch_url.assert_called_once()

    def test_reused_checkpoint_clears_stale_employer_industry_when_employer_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                '<a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>',
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "description": "Build RAG systems",
                        "skills": [],
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "employer_industry": "Не источник",
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                scraper,
                "fetch_url",
                side_effect=scraper.FetchError("blocked", kind="blocked"),
            ):
                vacancies = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(vacancies[0].employer_id, "3797175")
            self.assertEqual(vacancies[0].employer_industry, "")
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["employer_id"], "3797175")
            self.assertEqual(records[-1]["employer_industry"], "")

    def test_reused_full_checkpoint_replaces_stale_employer_id_from_cached_vacancy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                '<a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>',
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "description": "Build RAG systems",
                        "skills": [],
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "employer_id": "999999",
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            fetched_urls: list[str] = []

            def fetch_url(url: str, *_args: object) -> str:
                fetched_urls.append(url)
                return (
                    '<template id="HH-Lux-InitialState">'
                    '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                    "</template>"
                )

            with patch.object(scraper, "fetch_url", side_effect=fetch_url):
                vacancies = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(vacancies[0].employer_id, "3797175")
            self.assertEqual(fetched_urls, [scraper.employer_profile_url("3797175")])
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["employer_id"], "3797175")

    def test_refreshed_full_checkpoint_remains_reusable_with_partial_cached_vacancy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            fingerprint = scraper.profile_fingerprint(profile)
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                '<a data-qa="vacancy-company-name" href="/employer/3797175">Beoma</a>',
                encoding="utf-8",
            )
            args.checkpoint_jsonl.write_text(
                scraper.json.dumps(
                    {
                        "id": "123",
                        "title": "ML Engineer",
                        "company": "Beoma",
                        "url": vacancy_url,
                        "description": "Build RAG systems",
                        "skills": [],
                        "matched_terms": ["RAG"],
                        "matches": [{"term": "RAG", "fields": ["description"]}],
                        "kept": True,
                        "skip_reason": "",
                        "status": "kept",
                        "profile_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                scraper,
                "fetch_url",
                return_value=(
                    '<template id="HH-Lux-InitialState">'
                    '{"employerInfo":{"industries":[{"trl":"Розничная торговля"}]}}'
                    "</template>"
                ),
            ):
                first = scraper.collect_vacancies(args, profile, ["123"], self.search_results())
                second = scraper.collect_vacancies(args, profile, ["123"], self.search_results())

            self.assertEqual(first[0].employer_id, "3797175")
            self.assertEqual(second[0].employer_id, "3797175")
            self.assertEqual(second[0].description, "Build RAG systems")
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["description"], "Build RAG systems")

    def test_resume_refreshes_escaped_html_description_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            url = "https://hh.ru/vacancy/123"
            cache_path = scraper.cache_path_for_url(cache_dir, "vacancies", url, "123")
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                """
                <script>
                {"shortVacancy":{
                  "vacancyId":123,
                  "name":"Middle Unity Developer (Marketing, Playable Ads)",
                  "company":{"id":2666179,"name":"Azur Games","visibleName":"Azur Games"}
                },"description":"&lt;p&gt;Use &lt;strong&gt;GitHub Copilot&lt;/strong&gt;&lt;/p&gt;"}
                </script>
                """,
                encoding="utf-8",
            )
            record = {
                "id": "123",
                "url": url,
                "description": "&lt;p&gt;Use &lt;strong&gt;GitHub Copilot&lt;/strong&gt;&lt;/p&gt;",
                "skills": [],
                "matches": [{"term": "GitHub Copilot", "fields": ["description"]}],
            }

            vacancy = scraper.vacancy_from_checkpoint_record(record, self.search_profile(), cache_dir)

            self.assertIsNotNone(vacancy)
            assert vacancy is not None
            self.assertEqual(vacancy.title, "Middle Unity Developer (Marketing, Playable Ads)")
            self.assertEqual(vacancy.company, "Azur Games")
            self.assertEqual(vacancy.employer_id, "2666179")
            self.assertEqual(vacancy.description, "Use GitHub Copilot")
            self.assertTrue(scraper.checkpoint_record_needs_refresh(record, vacancy))

    def test_resume_recalculates_matches_after_cache_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            url = "https://hh.ru/vacancy/123"
            cache_path = scraper.cache_path_for_url(cache_dir, "vacancies", url, "123")
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                """
                <h1 data-qa="vacancy-title">RAG Engineer</h1>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            record = {
                "id": "123",
                "url": url,
                "description": "&lt;p&gt;Use &lt;strong&gt;GitHub Copilot&lt;/strong&gt;&lt;/p&gt;",
                "skills": [],
                "matches": [{"term": "GitHub Copilot", "fields": ["description"]}],
            }

            vacancy = scraper.vacancy_from_checkpoint_record(record, self.search_profile(), cache_dir)

            self.assertIsNotNone(vacancy)
            assert vacancy is not None
            self.assertEqual(vacancy.description, "Build RAG systems")
            self.assertEqual(vacancy.matches, [scraper.Match(term="RAG", fields=["title", "description"])])

    def test_resume_replaces_stale_plain_text_description_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            url = "https://hh.ru/vacancy/123"
            cache_path = scraper.cache_path_for_url(cache_dir, "vacancies", url, "123")
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                """
                <h1 data-qa="vacancy-title">RAG Engineer</h1>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            record = {
                "id": "123",
                "url": url,
                "description": "Old stale text",
                "skills": [],
                "matches": [{"term": "RAG", "fields": ["title"]}],
            }

            vacancy = scraper.vacancy_from_checkpoint_record(record, self.search_profile(), cache_dir)

            self.assertIsNotNone(vacancy)
            assert vacancy is not None
            self.assertEqual(vacancy.description, "Build RAG systems")
            self.assertEqual(vacancy.matches, [scraper.Match(term="RAG", fields=["title", "description"])])

    def test_resume_replaces_stale_non_empty_title_and_company_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            url = "https://hh.ru/vacancy/123"
            cache_path = scraper.cache_path_for_url(cache_dir, "vacancies", url, "123")
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                """
                <h1 data-qa="vacancy-title">RAG Engineer</h1>
                <a data-qa="vacancy-company-name" href="/employer/3797175">Right Co</a>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            record = {
                "id": "123",
                "title": "Wrong Title",
                "company": "Wrong Co",
                "url": url,
                "description": "&lt;p&gt;Build RAG systems&lt;/p&gt;",
                "skills": [],
                "matches": [{"term": "RAG", "fields": ["description"]}],
            }

            vacancy = scraper.vacancy_from_checkpoint_record(record, self.search_profile(), cache_dir)

            self.assertIsNotNone(vacancy)
            assert vacancy is not None
            self.assertEqual(vacancy.title, "RAG Engineer")
            self.assertEqual(vacancy.company, "Right Co")
            self.assertTrue(scraper.checkpoint_record_needs_refresh(record, vacancy))

    def test_vacancy_record_preserves_vacancy_attributes(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <div data-qa="vacancy-salary">300 000 ₽</div>
            <span data-qa="vacancy-experience">3–6 лет</span>
            <p data-qa="work-formats-text">Формат работы: удалённо</p>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )

        record = vacancy_to_record(vacancy, kept=True, reason="")

        self.assertEqual(record["salary"], "300 000 ₽")
        self.assertEqual(record["experience"], "3–6 лет")
        self.assertEqual(record["work_format"], "удалённо")
        self.assertEqual(record["employer_industry"], "")

    def test_vacancy_record_includes_exact_search_queries(self) -> None:
        vacancy = scraper.Vacancy(
            vacancy_id="123",
            title="ML Engineer",
            description="Build RAG systems",
            url="https://hh.ru/vacancy/123",
            search_queries=["RAG", "LangChain"],
            matches=[scraper.Match(term="AI", fields=["description"])],
        )

        record = vacancy_to_record(vacancy, kept=True, reason="")

        self.assertEqual(record["search_queries"], ["RAG", "LangChain"])

    def test_search_url_includes_native_work_format_filters(self) -> None:
        hh = scraper.HhSettings(
            area="2",
            max_pages=1,
            search_delay_min=0,
            search_delay_max=0,
            vacancy_delay_min=0,
            vacancy_delay_max=0,
            filters=scraper.HhFilters(work_format=("REMOTE", "HYBRID")),
        )

        url = scraper.search_url("MCP", hh, 0)

        self.assertIn("work_format=REMOTE", url)
        self.assertIn("work_format=HYBRID", url)
        self.assertNotIn("schedule=", url)

    def test_search_url_includes_all_supported_filters(self) -> None:
        hh = scraper.HhSettings(
            area="2",
            max_pages=1,
            search_delay_min=0,
            search_delay_max=0,
            vacancy_delay_min=0,
            vacancy_delay_max=0,
            filters=scraper.HhFilters(
                search_field=("name", "company_name", "description"),
                experience=("noExperience", "between1And3", "between3And6", "moreThan6"),
                work_format=("ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK"),
                employment=("full", "part", "project", "volunteer", "probation"),
                industry=("7", "7.540"),
                salary=100000,
                only_with_salary=True,
                order_by="salary_desc",
                period=30,
            ),
        )

        query = parse_qs(urlparse(scraper.search_url("MCP", hh, 0)).query)

        self.assertEqual(query["area"], ["2"])
        self.assertEqual(query["text"], ["MCP"])
        self.assertEqual(query["page"], ["0"])
        self.assertEqual(query["search_field"], ["name", "company_name", "description"])
        self.assertEqual(query["experience"], ["noExperience", "between1And3", "between3And6", "moreThan6"])
        self.assertEqual(query["work_format"], ["ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK"])
        self.assertEqual(query["employment"], ["full", "part", "project", "volunteer", "probation"])
        self.assertEqual(query["industry"], ["7", "7.540"])
        self.assertEqual(query["salary"], ["100000"])
        self.assertEqual(query["only_with_salary"], ["true"])
        self.assertEqual(query["order_by"], ["salary_desc"])
        self.assertEqual(query["period"], ["30"])
        self.assertNotIn("schedule", query)

    def test_collect_search_ids_tracks_queries_by_vacancy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.scraper_args(root)
            profile = scraper.SearchProfile(
                title="Search query tracking",
                hh=scraper.HhSettings(
                    area="1",
                    max_pages=1,
                    search_delay_min=0,
                    search_delay_max=0,
                    vacancy_delay_min=0,
                    vacancy_delay_max=0,
                ),
                match_scope={"title": True, "description": True, "skills": True, "company": False},
                search_terms={"AI": ["RAG", "LangChain"]},
                term_patterns={"AI": [scraper.re.compile("RAG", scraper.re.I)]},
                exclude_patterns={},
            )

            def fetch_url(url: str, *_args: object) -> str:
                query = parse_qs(urlparse(url).query)
                if query["text"] == ["RAG"]:
                    return '<a href="/vacancy/101">one</a><a href="/vacancy/202">two</a>'
                if query["text"] == ["LangChain"]:
                    return '<a href="/vacancy/202">two</a><a href="/vacancy/303">three</a>'
                raise AssertionError(f"unexpected url: {url}")

            with patch.object(scraper, "fetch_url", side_effect=fetch_url):
                search_results = scraper.collect_search_ids(args, profile)

        self.assertEqual(search_results.ids_by_group, {"AI": ["101", "202", "303"]})
        self.assertEqual(
            search_results.queries_by_vacancy,
            {
                "101": ["RAG"],
                "202": ["RAG", "LangChain"],
                "303": ["LangChain"],
            },
        )

    def test_collect_vacancies_sets_search_queries_for_new_and_checkpointed_vacancies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            args = self.scraper_args(root)
            vacancy_url = "https://hh.ru/vacancy/123"
            vacancy_cache = scraper.cache_path_for_url(args.cache_dir, "vacancies", vacancy_url, "123")
            vacancy_cache.parent.mkdir(parents=True)
            vacancy_cache.write_text(
                """
                <h1 data-qa="vacancy-title">RAG Engineer</h1>
                <div data-qa="vacancy-description">Build RAG systems</div>
                """,
                encoding="utf-8",
            )
            search_results = scraper.SearchResults(
                ids_by_group={"RAG": ["123"]},
                queries_by_vacancy={"123": ["RAG", "retrieval augmented generation"]},
            )

            with patch.object(scraper, "fetch_url", return_value=vacancy_cache.read_text(encoding="utf-8")):
                first = scraper.collect_vacancies(args, profile, ["123"], search_results)
                second = scraper.collect_vacancies(args, profile, ["123"], search_results)

            self.assertEqual(first[0].search_queries, ["RAG", "retrieval augmented generation"])
            self.assertEqual(second[0].search_queries, ["RAG", "retrieval augmented generation"])
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["search_queries"], ["RAG", "retrieval augmented generation"])

    def test_collect_vacancies_sets_search_queries_for_permanent_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.search_profile()
            args = self.scraper_args(root)
            search_results = scraper.SearchResults(
                ids_by_group={"RAG": ["123"]},
                queries_by_vacancy={"123": ["RAG"]},
            )

            with patch.object(
                scraper,
                "fetch_url",
                side_effect=scraper.FetchError("blocked", kind="permanent"),
            ):
                vacancies = scraper.collect_vacancies(args, profile, ["123"], search_results)

            self.assertEqual(vacancies, [])
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["search_queries"], ["RAG"])

    def test_load_profile_accepts_native_work_format_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(
                scraper.json.dumps(
                    {
                        "title": "Work format test",
                        "hh": {
                            "area": "2",
                            "max_pages": 1,
                            "search_delay_min": 0,
                            "search_delay_max": 0,
                            "vacancy_delay_min": 0,
                            "vacancy_delay_max": 0,
                            "filters": {
                                "search_field": ["description"],
                                "experience": [],
                                "work_format": ["REMOTE", "HYBRID"],
                                "employment": [],
                                "industry": [],
                                "salary": None,
                                "only_with_salary": False,
                                "order_by": "relevance",
                                "period": None,
                            },
                        },
                        "match_scope": {
                            "title": False,
                            "company": False,
                            "description": True,
                            "skills": False,
                        },
                        "search_terms": {"MCP": ["MCP"]},
                        "term_patterns": {"MCP": ["MCP"]},
                        "exclude_patterns": {},
                        "notes": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            profile = scraper.load_profile(path)

        self.assertEqual(profile.hh.filters.work_format, ("REMOTE", "HYBRID"))

    def test_load_profile_rejects_duplicate_filter_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            payload = self.profile_payload(
                {
                    "search_field": ["description"],
                    "experience": [],
                    "work_format": ["REMOTE", "REMOTE"],
                    "employment": [],
                    "industry": [],
                    "salary": None,
                    "only_with_salary": False,
                    "order_by": "relevance",
                    "period": None,
                }
            )
            path.write_text(scraper.json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate value"):
                scraper.load_profile(path)

    def test_load_profile_rejects_duplicate_industry_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            payload = self.profile_payload(
                {
                    "search_field": ["description"],
                    "experience": [],
                    "work_format": [],
                    "employment": [],
                    "industry": ["7", "7"],
                    "salary": None,
                    "only_with_salary": False,
                    "order_by": "relevance",
                    "period": None,
                }
            )
            path.write_text(scraper.json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate value"):
                scraper.load_profile(path)

    def test_load_profile_requires_filters_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(
                scraper.json.dumps(self.profile_payload(filters=None), ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "missing hh.filters"):
                scraper.load_profile(path)

    def test_load_profile_rejects_non_numeric_area(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            payload = self.profile_payload(
                {
                    "search_field": ["description"],
                    "experience": [],
                    "work_format": [],
                    "employment": [],
                    "industry": [],
                    "salary": None,
                    "only_with_salary": False,
                    "order_by": "relevance",
                    "period": None,
                },
                area="not-an-area-id",
            )
            path.write_text(scraper.json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "hh.area"):
                scraper.load_profile(path)

    def test_load_profile_rejects_schedule_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(
                scraper.json.dumps(
                    {
                        "title": "Legacy schedule test",
                        "hh": {
                            "area": "2",
                            "max_pages": 1,
                            "search_delay_min": 0,
                            "search_delay_max": 0,
                            "vacancy_delay_min": 0,
                            "vacancy_delay_max": 0,
                            "filters": {
                                "search_field": ["description"],
                                "experience": [],
                                "schedule": ["fullDay"],
                                "work_format": [],
                                "employment": [],
                                "industry": [],
                                "salary": None,
                                "only_with_salary": False,
                                "order_by": "relevance",
                                "period": None,
                            },
                        },
                        "match_scope": {
                            "title": False,
                            "company": False,
                            "description": True,
                            "skills": False,
                        },
                        "search_terms": {"MCP": ["MCP"]},
                        "term_patterns": {"MCP": ["MCP"]},
                        "exclude_patterns": {},
                        "notes": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown hh.filters fields: schedule"):
                scraper.load_profile(path)

    def test_validate_work_paths_allows_current_project_outputs(self) -> None:
        project_outputs = Path.cwd() / "outputs" / "hh-vacancy-research" / "sample"
        args = argparse.Namespace(
            profile=project_outputs / "sample.profile.json",
            cache_dir=project_outputs / "cache",
            output_json=project_outputs / "sample.source.json",
            checkpoint_jsonl=project_outputs / "sample.checkpoint.jsonl",
        )

        scraper.validate_work_paths(args)

    def test_validate_work_paths_rejects_installed_skill_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            skill_output = codex_home / "skills" / "hh-vacancy-research" / "outputs" / "sample"
            args = argparse.Namespace(
                profile=skill_output / "sample.profile.json",
                cache_dir=skill_output / "cache",
                output_json=skill_output / "sample.source.json",
                checkpoint_jsonl=skill_output / "sample.checkpoint.jsonl",
            )

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    scraper.validate_work_paths(args)

    def test_validate_work_paths_rejects_default_codex_home_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            skill_output = home / ".codex" / "skills" / "hh-vacancy-research" / "outputs" / "sample"
            args = argparse.Namespace(
                profile=skill_output / "sample.profile.json",
                cache_dir=skill_output / "cache",
                output_json=skill_output / "sample.source.json",
                checkpoint_jsonl=skill_output / "sample.checkpoint.jsonl",
            )

            with patch.object(scraper.Path, "home", return_value=home):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    scraper.validate_work_paths(args)

    def test_validate_work_paths_rejects_current_installed_skill_root_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_root = Path(tmp) / ".codex" / "plugins" / "cache" / "hh-vacancy-research"
            skill_output = skill_root / "outputs" / "sample"
            args = argparse.Namespace(
                profile=skill_output / "sample.profile.json",
                cache_dir=skill_output / "cache",
                output_json=skill_output / "sample.source.json",
                checkpoint_jsonl=skill_output / "sample.checkpoint.jsonl",
            )

            with patch.object(scraper, "skill_root", return_value=skill_root):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    scraper.validate_work_paths(args)

    def test_validate_work_paths_rejects_installed_skill_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            project_outputs = Path.cwd() / "outputs" / "hh-vacancy-research" / "sample"
            protected_profile = (
                codex_home
                / "skills"
                / "hh-vacancy-research"
                / "outputs"
                / "sample"
                / "sample.profile.json"
            )
            args = argparse.Namespace(
                profile=protected_profile,
                cache_dir=project_outputs / "cache",
                output_json=project_outputs / "sample.source.json",
                checkpoint_jsonl=project_outputs / "sample.checkpoint.jsonl",
            )

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    scraper.validate_work_paths(args)

    def test_main_validate_profile_rejects_installed_skill_profile_before_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            project_outputs = Path.cwd() / "outputs" / "hh-vacancy-research" / "sample"
            args = argparse.Namespace(
                profile=(
                    codex_home
                    / "skills"
                    / "hh-vacancy-research"
                    / "outputs"
                    / "sample"
                    / "sample.profile.json"
                ),
                cache_dir=project_outputs / "cache",
                output_json=project_outputs / "sample.source.json",
                checkpoint_jsonl=project_outputs / "sample.checkpoint.jsonl",
                validate_profile=True,
            )

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with patch.object(scraper, "parse_args", return_value=args):
                    with patch.object(scraper, "load_profile") as load_profile:
                        with self.assertRaisesRegex(ValueError, "skill package"):
                            scraper.main()

            load_profile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
