# Task 1 Report: Track Exact Search Queries During Search Collection

## Outcome

Implemented the first search-collection slice so the scraper now records the exact hh.ru query strings used for each vacancy ID while keeping grouped search IDs intact.

## What changed

- Added a frozen `SearchResults` dataclass with:
  - `ids_by_group: dict[str, list[str]]`
  - `queries_by_vacancy: dict[str, list[str]]`
- Updated `collect_search_ids(args, profile)` to return `SearchResults` instead of a plain dictionary.
- Tracked exact query strings per vacancy ID during search collection.
- Updated `main` to consume `SearchResults.ids_by_group` for vacancy ID aggregation and output writing.
- Updated the main caller path so downstream behavior continues to use grouped search IDs exactly as before.

## Verification

- `python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_collect_search_ids_tracks_queries_by_vacancy -v`
- `python3 -m pytest tests/test_hh_vacancy_scraper.py -v`

## Notes

- Scoped to `scripts/hh_vacancy_scraper.py` and `tests/test_hh_vacancy_scraper.py`.
- Did not implement later tasks: no `Vacancy.search_queries`, no exporter column changes, and no checkpoint serialization changes.
