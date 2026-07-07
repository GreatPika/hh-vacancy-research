# Vacancy Search Query Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-facing export column that shows the concrete hh.ru search words or phrases that returned each vacancy.

**Architecture:** Keep existing search groups as topic-level match evidence and add a separate per-vacancy `search_queries` field for the exact hh.ru query strings. Build that field during search result collection, preserve it through checkpoint reuse and source JSON output, then expose it in Markdown, CSV, and XLSX exports.

**Tech Stack:** Python 3, `unittest`, existing scraper/export scripts, existing JSON/CSV/XLSX export flow.

## Global Constraints

- User-visible communication remains Russian; code and docs stay English unless an existing artifact uses Russian UI text.
- Do not change the profile schema for this feature; the information is derived from existing `search_terms`.
- Do not replace or rename the existing `Поисковые группы` column.
- New user-facing column name: `Найдена по словам`.
- The new column must contain exact query strings from `profile.search_terms`, deduplicated in first-seen order.
- Existing source JSON consumers must keep working: add fields, do not remove or rename current fields.
- Existing checkpoint files without `search_queries` must remain reusable.

---

## File Structure

- Modify `scripts/hh_vacancy_scraper.py`: derive and store exact search query strings per vacancy id, add `Vacancy.search_queries`, serialize it, and refresh it when checkpointed vacancies are reused.
- Modify `scripts/export_hh_vacancies.py`: add `Найдена по словам` to exported rows and read `search_queries` from vacancy records.
- Modify `tests/test_hh_vacancy_scraper.py`: cover query tracking, source JSON serialization, and checkpoint compatibility.
- Modify `tests/test_export_hh_vacancies.py`: cover the new column header and row value.

No new module is needed. The behavior belongs to the existing scraper/export boundary, and splitting the current scripts would be unrelated scope.

---

### Task 1: Track Exact Search Queries During Search Collection

**Files:**
- Modify: `scripts/hh_vacancy_scraper.py`
- Test: `tests/test_hh_vacancy_scraper.py`

**Interfaces:**
- Produces: `SearchResults` dataclass with `ids_by_group: dict[str, list[str]]` and `queries_by_vacancy: dict[str, list[str]]`.
- Updates: `collect_search_ids(args: argparse.Namespace, profile: SearchProfile) -> SearchResults`.
- Preserves: `search_ids` output semantics through `SearchResults.ids_by_group`.

- [ ] **Step 1: Write the failing test**

Add this test method to `VacancyParsingTest` in `tests/test_hh_vacancy_scraper.py`:

```python
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
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_collect_search_ids_tracks_queries_by_vacancy -v
```

Expected: FAIL because `collect_search_ids` currently returns a plain `dict` and has no `queries_by_vacancy`.

- [ ] **Step 3: Implement `SearchResults` and query tracking**

In `scripts/hh_vacancy_scraper.py`, add this dataclass near `SearchProfile`:

```python
@dataclass(frozen=True)
class SearchResults:
    ids_by_group: dict[str, list[str]]
    queries_by_vacancy: dict[str, list[str]]
```

Replace `collect_search_ids` with this implementation:

```python
def collect_search_ids(args: argparse.Namespace, profile: SearchProfile) -> SearchResults:
    found: dict[str, list[str]] = {}
    queries_by_vacancy: dict[str, list[str]] = {}
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
                for vacancy_id in ids:
                    queries = queries_by_vacancy.setdefault(vacancy_id, [])
                    if query not in queries:
                        queries.append(query)
                previous_ids.update(ids)

                if not ids:
                    empty_pages += 1
                else:
                    empty_pages = 0

                if empty_pages >= 2 or not has_next_page(search_html, page):
                    break
    return SearchResults(
        ids_by_group={term: unique(ids) for term, ids in found.items()},
        queries_by_vacancy=queries_by_vacancy,
    )
```

- [ ] **Step 4: Update the main caller to use `SearchResults`**

In `main`, replace:

```python
    search_ids = collect_search_ids(args, profile)
    vacancy_ids = unique(vacancy_id for ids in search_ids.values() for vacancy_id in ids)
```

with:

```python
    search_results = collect_search_ids(args, profile)
    vacancy_ids = unique(vacancy_id for ids in search_results.ids_by_group.values() for vacancy_id in ids)
```

Also replace:

```python
    vacancies = collect_vacancies(args, profile, vacancy_ids, search_ids)
    write_outputs(args, profile, vacancies, search_ids, vacancy_ids)
```

with:

```python
    vacancies = collect_vacancies(args, profile, vacancy_ids, search_results)
    write_outputs(args, profile, vacancies, search_results.ids_by_group, vacancy_ids)
```

- [ ] **Step 5: Run the focused test again**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_collect_search_ids_tracks_queries_by_vacancy -v
```

Expected: PASS.

---

### Task 2: Store Search Queries On Vacancy Records And Checkpoints

**Files:**
- Modify: `scripts/hh_vacancy_scraper.py`
- Test: `tests/test_hh_vacancy_scraper.py`

**Interfaces:**
- Consumes: `SearchResults.queries_by_vacancy` from Task 1.
- Produces: `Vacancy.search_queries: list[str]`.
- Produces JSON field: `"search_queries": list[str]` on kept vacancy records.
- Updates: `collect_vacancies(args, profile, vacancy_ids, search_results)`.

- [ ] **Step 1: Write failing serialization test**

Add this test method to `VacancyParsingTest`:

```python
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
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_vacancy_record_includes_exact_search_queries -v
```

Expected: FAIL because `Vacancy` has no `search_queries` field or the record omits it.

- [ ] **Step 3: Add `search_queries` to `Vacancy` and records**

In the `Vacancy` dataclass, add:

```python
    search_queries: list[str] = field(default_factory=list)
```

In `vacancy_to_record`, add `"search_queries": vacancy.search_queries` to both kept and skipped records directly after `"url": vacancy.url,`.

In `vacancy_from_record`, read the field:

```python
    raw_search_queries = record.get("search_queries", [])
    search_queries = raw_search_queries if isinstance(raw_search_queries, list) else []
```

Then pass it into `Vacancy(...)`:

```python
        search_queries=[str(item) for item in search_queries if isinstance(item, str)],
```

- [ ] **Step 4: Run the serialization test**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_vacancy_record_includes_exact_search_queries -v
```

Expected: PASS.

- [ ] **Step 5: Write failing collection/checkpoint test**

Add this test method to `VacancyParsingTest`:

```python
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
```

- [ ] **Step 6: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py::VacancyParsingTest::test_collect_vacancies_sets_search_queries_for_new_and_checkpointed_vacancies -v
```

Expected: FAIL because `collect_vacancies` still accepts a `dict` and never assigns `search_queries`.

- [ ] **Step 7: Thread search results into collection**

Change the `collect_vacancies` signature:

```python
def collect_vacancies(
    args: argparse.Namespace,
    profile: SearchProfile,
    vacancy_ids: list[str],
    search_results: SearchResults,
) -> list[Vacancy]:
```

Near the start of the function, add:

```python
    queries_by_vacancy = search_results.queries_by_vacancy
```

When reusing a kept checkpoint vacancy, after `vacancy = vacancy_from_checkpoint_record(...)`, add:

```python
            vacancy.search_queries = list(queries_by_vacancy.get(vacancy_id, vacancy.search_queries))
```

After parsing a newly fetched vacancy, before matching, add:

```python
        vacancy.search_queries = list(queries_by_vacancy.get(vacancy_id, []))
```

Update any tests or calls that pass a plain search id dictionary to pass:

```python
scraper.SearchResults(ids_by_group={"RAG": ["123"]}, queries_by_vacancy={"123": ["RAG"]})
```

- [ ] **Step 8: Ensure checkpoint refresh notices missing or stale search queries**

In `checkpoint_record_needs_refresh`, add this condition:

```python
        or string_list(record.get("search_queries")) != vacancy.search_queries
```

If `string_list` is unavailable in `scripts/hh_vacancy_scraper.py`, add this helper near `unique`:

```python
def string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
```

- [ ] **Step 9: Run scraper tests**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py -v
```

Expected: PASS.

---

### Task 3: Export `Найдена по словам` In Markdown, CSV, And XLSX Rows

**Files:**
- Modify: `scripts/export_hh_vacancies.py`
- Test: `tests/test_export_hh_vacancies.py`

**Interfaces:**
- Consumes: vacancy JSON field `"search_queries": list[str]`.
- Produces: new exported column `Найдена по словам`.
- Preserves: existing `Поисковые группы` column and meaning.

- [ ] **Step 1: Update failing header test**

In `test_rows_for_uses_russian_column_headers`, change the expected header list to:

```python
            [
                "Название вакансии",
                "Компания",
                "Заработная плата",
                "Опыт",
                "Формат работы",
                "Отрасль работодателя",
                "Ссылка",
                "Найдена по словам",
                "Поисковые группы",
                "Поля совпадения",
                "Навыки",
                "Описание",
            ],
```

- [ ] **Step 2: Update failing row test**

In `test_rows_for_exports_vacancy_attributes_before_match_details`, add `"search_queries": ["RAG", "LangChain"],` to the input vacancy and update the expected row to:

```python
            [
                "ML Engineer",
                "Example AI",
                "от 300 000 ₽ на руки",
                "3–6 лет",
                "удалённо",
                "Информационные технологии",
                "https://hh.ru/vacancy/1",
                "RAG, LangChain",
                "RAG",
                "description",
                "Python, LLM",
                "Build RAG systems",
            ],
```

- [ ] **Step 3: Update failing Markdown test**

In `test_markdown_export_uses_russian_column_headers`, change the expected Markdown header to:

```python
                "| Название вакансии | Компания | Заработная плата | Опыт | Формат работы | Отрасль работодателя | Ссылка | Найдена по словам | Поисковые группы | Поля совпадения | Навыки | Описание |",
```

- [ ] **Step 4: Run export tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_export_hh_vacancies.py -v
```

Expected: FAIL because the exporter does not include the new column yet.

- [ ] **Step 5: Implement export helper and column**

In `scripts/export_hh_vacancies.py`, add the header after `"Ссылка"`:

```python
    "Найдена по словам",
```

Add this helper near `matched_terms`:

```python
def search_queries(vacancy: dict[str, object]) -> str:
    return ", ".join(string_list(vacancy.get("search_queries")))
```

In `rows_for`, add the new cell after the URL:

```python
                search_queries(vacancy),
```

In `validate_input`, add validation beside the existing list checks:

```python
        if "search_queries" in vacancy and not isinstance(vacancy["search_queries"], list):
            raise ValueError(f"{source_path}: vacancies[{index}].search_queries must be a list")
```

- [ ] **Step 6: Run export tests**

Run:

```bash
python3 -m pytest tests/test_export_hh_vacancies.py -v
```

Expected: PASS.

---

### Task 4: Verify End-To-End Compatibility

**Files:**
- Modify only if earlier tasks reveal a broken caller: `scripts/hh_vacancy_scraper.py`, `scripts/export_hh_vacancies.py`, tests.

**Interfaces:**
- Consumes all completed tasks.
- Produces a tested implementation that supports old source JSON without `search_queries` and new source JSON with `search_queries`.

- [ ] **Step 1: Run all Python tests**

Run:

```bash
python3 -m pytest tests/test_hh_vacancy_scraper.py tests/test_export_hh_vacancies.py -v
```

Expected: PASS.

- [ ] **Step 2: Run installer tests if Node dependencies are available**

Run:

```bash
npm test
```

Expected: PASS. If dependencies are missing, report the exact error and do not claim this check passed.

- [ ] **Step 3: Manual data-shape check with a small source JSON**

Create a temporary file outside the repo with one vacancy containing:

```json
{
  "title": "Manual export check",
  "vacancies": [
    {
      "title": "ML Engineer",
      "company": "Example AI",
      "salary": "",
      "experience": "",
      "work_format": "",
      "employer_industry": "",
      "url": "https://hh.ru/vacancy/1",
      "search_queries": ["RAG", "LangChain"],
      "matched_terms": ["AI"],
      "matches": [{"term": "AI", "fields": ["description"]}],
      "skills": ["Python"],
      "description": "Build RAG systems"
    }
  ]
}
```

Run:

```bash
python3 scripts/export_hh_vacancies.py \
  --source-json /tmp/hh-search-query-column-source.json \
  --output-dir /tmp/hh-search-query-column-export \
  --output-prefix vacancies
```

Expected: the command writes Markdown, CSV, and XLSX. The Markdown and CSV headers include `Найдена по словам`, and the row contains `RAG, LangChain` in that column.

- [ ] **Step 4: Inspect git diff for accidental scope creep**

Run:

```bash
git diff -- scripts/hh_vacancy_scraper.py scripts/export_hh_vacancies.py tests/test_hh_vacancy_scraper.py tests/test_export_hh_vacancies.py
```

Expected: diff only adds exact search query tracking, serialization, export column, and tests.

---

## Self-Review

- Spec coverage: the plan adds an exact per-vacancy search phrase column, keeps groups unchanged, preserves old JSON/checkpoints, and verifies scraper plus exporter behavior.
- Placeholder scan: no `TBD`, `TODO`, or deferred implementation markers remain.
- Type consistency: `SearchResults`, `Vacancy.search_queries`, and JSON `search_queries` use `list[str]` throughout.
