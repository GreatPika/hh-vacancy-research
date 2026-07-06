import unittest
from tempfile import TemporaryDirectory
from pathlib import Path


from scripts.export_hh_vacancies import rows_for, write_markdown


class ExportRowsTest(unittest.TestCase):
    def test_rows_for_labels_matched_group_column(self) -> None:
        rows = rows_for([])

        self.assertEqual(
            rows[0],
            [
                "Title",
                "Company",
                "URL",
                "Matched groups",
                "Matched fields",
                "Skills",
                "Description",
            ],
        )

    def test_markdown_export_uses_matched_group_column(self) -> None:
        rows = rows_for([])

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "vacancies.md"
            write_markdown(path, {"title": "Vacancies"}, rows)

            self.assertIn(
                "| Title | Company | URL | Matched groups | Matched fields | Skills | Description |",
                path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
