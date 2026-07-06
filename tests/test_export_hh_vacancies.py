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
                "Ссылка",
                "Поисковые группы",
                "Поля совпадения",
                "Навыки",
                "Описание",
            ],
        )

    def test_markdown_export_uses_russian_column_headers(self) -> None:
        rows = rows_for([])

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "vacancies.md"
            write_markdown(path, {"title": "Vacancies"}, rows)

            self.assertIn(
                "| Название вакансии | Компания | Ссылка | Поисковые группы | Поля совпадения | Навыки | Описание |",
                path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
