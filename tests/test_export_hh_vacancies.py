import unittest
from tempfile import TemporaryDirectory
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
