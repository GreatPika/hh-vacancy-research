import unittest
import argparse
import os
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch


import scripts.export_hh_vacancies as exporter
from scripts.export_hh_vacancies import rows_for, write_markdown


class ExportRowsTest(unittest.TestCase):
    def test_rows_for_uses_russian_column_headers(self) -> None:
        rows = rows_for([])

        self.assertEqual(
            rows[0],
            [
                "Название вакансии",
                "Компания",
                "Заработная плата",
                "Опыт",
                "График",
                "Отрасль работодателя",
                "Ссылка",
                "Поисковые группы",
                "Поля совпадения",
                "Навыки",
                "Описание",
            ],
        )

    def test_rows_for_exports_vacancy_attributes_before_match_details(self) -> None:
        rows = rows_for([
            {
                "title": "ML Engineer",
                "company": "Example AI",
                "salary": "от 300 000 ₽ на руки",
                "experience": "3–6 лет",
                "schedule": "5/2; удалённо; 8 часов",
                "employer_industry": "Информационные технологии",
                "url": "https://hh.ru/vacancy/1",
                "matched_terms": ["RAG"],
                "matches": [{"term": "RAG", "fields": ["description"]}],
                "skills": ["Python", "LLM"],
                "description": "Build RAG systems",
            }
        ])

        self.assertEqual(
            rows[1],
            [
                "ML Engineer",
                "Example AI",
                "от 300 000 ₽ на руки",
                "3–6 лет",
                "5/2; удалённо; 8 часов",
                "Информационные технологии",
                "https://hh.ru/vacancy/1",
                "RAG",
                "description",
                "Python, LLM",
                "Build RAG systems",
            ],
        )

    def test_markdown_export_uses_russian_column_headers(self) -> None:
        rows = rows_for([])

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "vacancies.md"
            write_markdown(path, {"title": "Vacancies"}, rows)

            self.assertIn(
                "| Название вакансии | Компания | Заработная плата | Опыт | График | Отрасль работодателя | Ссылка | Поисковые группы | Поля совпадения | Навыки | Описание |",
                path.read_text(encoding="utf-8"),
            )

    def test_validate_work_paths_allows_current_project_outputs(self) -> None:
        output_dir = Path.cwd() / "outputs" / "hh-vacancy-research" / "sample"
        args = argparse.Namespace(output_dir=output_dir)
        outputs = {
            "json": output_dir / "sample.vacancies.json",
            "md": output_dir / "sample.vacancies.md",
            "csv": output_dir / "sample.vacancies.csv",
            "xlsx": output_dir / "sample.vacancies.xlsx",
        }

        exporter.validate_work_paths(args, outputs)

    def test_validate_work_paths_rejects_installed_skill_outputs(self) -> None:
        with TemporaryDirectory() as codex_home:
            output_dir = Path(codex_home) / "skills" / "hh-vacancy-research" / "outputs" / "sample"
            args = argparse.Namespace(output_dir=output_dir)
            outputs = {
                "json": output_dir / "sample.vacancies.json",
                "md": output_dir / "sample.vacancies.md",
                "csv": output_dir / "sample.vacancies.csv",
                "xlsx": output_dir / "sample.vacancies.xlsx",
            }

            with patch.dict(os.environ, {"CODEX_HOME": codex_home}):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    exporter.validate_work_paths(args, outputs)

    def test_validate_work_paths_rejects_default_codex_home_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            output_dir = home / ".codex" / "skills" / "hh-vacancy-research" / "outputs" / "sample"
            args = argparse.Namespace(output_dir=output_dir)
            outputs = {
                "json": output_dir / "sample.vacancies.json",
                "md": output_dir / "sample.vacancies.md",
                "csv": output_dir / "sample.vacancies.csv",
                "xlsx": output_dir / "sample.vacancies.xlsx",
            }

            with patch.object(exporter.Path, "home", return_value=home):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    exporter.validate_work_paths(args, outputs)

    def test_validate_work_paths_rejects_current_installed_skill_root_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_root = Path(tmp) / ".codex" / "plugins" / "cache" / "hh-vacancy-research"
            output_dir = skill_root / "outputs" / "sample"
            args = argparse.Namespace(output_dir=output_dir)
            outputs = {
                "json": output_dir / "sample.vacancies.json",
                "md": output_dir / "sample.vacancies.md",
                "csv": output_dir / "sample.vacancies.csv",
                "xlsx": output_dir / "sample.vacancies.xlsx",
            }

            with patch.object(exporter, "skill_root", return_value=skill_root):
                with self.assertRaisesRegex(ValueError, "skill package"):
                    exporter.validate_work_paths(args, outputs)


if __name__ == "__main__":
    unittest.main()
