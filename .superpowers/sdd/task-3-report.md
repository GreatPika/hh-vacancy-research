# Task 3 Report

Implemented the new exported column `Найдена по словам` in Markdown, CSV, and XLSX rows.

What changed:
- `search_queries` is now rendered as a comma-separated value in the export row, placed immediately after `Ссылка`.
- The exporter validates `search_queries` as a list when it is present in vacancy JSON.
- XLSX column widths were adjusted so the inserted column does not compress later fields.
- Tests now cover the new column header, row ordering, and Markdown output.

Verification:
- `python3 -m pytest tests/test_export_hh_vacancies.py -v`

Commit:
- `9182ac2` `feat: export search query column`

Fix report:
- Command: `python3 -m pytest tests/test_export_hh_vacancies.py -v`
- Result: `8 passed`
