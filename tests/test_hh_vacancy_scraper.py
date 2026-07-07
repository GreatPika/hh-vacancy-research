import unittest
import argparse
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import scripts.hh_vacancy_scraper as scraper
from scripts.hh_vacancy_scraper import parse_vacancy, vacancy_to_record


class VacancyParsingTest(unittest.TestCase):
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
        self.assertEqual(vacancy.schedule, "Полная занятость; 5/2; 8; удалённо")

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
                vacancies = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

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
                vacancies = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

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
                vacancies = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

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
                vacancies = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

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
                vacancies = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

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
                first = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})
                second = scraper.collect_vacancies(args, profile, ["123"], {"RAG": ["123"]})

            self.assertEqual(first[0].employer_id, "3797175")
            self.assertEqual(second[0].employer_id, "3797175")
            self.assertEqual(second[0].description, "Build RAG systems")
            records = list(scraper.iter_checkpoint_records(args.checkpoint_jsonl))
            self.assertEqual(records[-1]["description"], "Build RAG systems")

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
        self.assertEqual(record["schedule"], "удалённо")
        self.assertEqual(record["employer_industry"], "")

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
