---
name: hh-vacancy-research
description: Use when a user wants to research hh.ru vacancies.
---

# hh-vacancy-research

Use this skill when a user wants to find hh.ru vacancies by any explicit search intent: vacancy titles, role names, companies, industries, domains, technologies, tools, platforms, methods, work practices, requirements, or key skills.

This skill is a guided workflow. Do not run collection immediately from a vague request.

## Execution Requirements

- Use only the bundled scripts in this skill for collection and export:
  - `scripts/hh_vacancy_scraper.py` for hh.ru search, full-card parsing, matching, checkpointing, and result JSON.
  - `scripts/export_hh_vacancies.py` for JSON, Markdown, CSV, and XLSX export.
- Do not replace the scraper with ad hoc browser scraping, shell one-liners, unrelated local scripts, the hh.ru API, or manually assembled vacancy lists unless the user explicitly asks to abandon this skill workflow.
- The official hh API may be used only for dictionary lookups: `https://api.hh.ru/areas` for `hh.area` ids and `https://api.hh.ru/industries` for `hh.filters.industry` ids. Do not use hh APIs to collect vacancies.
- Before collection, create a fresh profile from `templates/search_profile.template.json` and validate it with the bundled scraper.
- The profile is the required settings source. It must explicitly define hh.ru area, native hh search filters, page count, delays, match scope, search queries, validation regexes, exclusions, and notes for risky terms.
- Keep runtime artifacts outside the skill package. Cache directories, checkpoints, profile drafts, result JSON, and exported files belong in the user's working/output directory.
- Communicate with the user in Russian by default throughout this skill: discovery questions, profile summaries, progress updates, column explanations, group explanations, limitations, and final reports. Use another language only if the user explicitly requests it.
- Use the skill-local Python virtual environment when it exists:
  - macOS/Linux: `<skill-dir>/.venv/bin/python`
  - Windows: `<skill-dir>/.venv/Scripts/python.exe`
    Fall back to `python3` only when the skill-local virtual environment is absent.

## Mandatory Workflow

1. Discovery gate.
   Ask only for filters this skill can represent. Use user-facing hh.ru wording, then translate answers into the profile yourself:

   | Askable filter          | User-facing question example                                                                                                               | Profile setting                                    |
   | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
   | hh.ru region            | "Which hh.ru region should I search: Russia, Moscow, Saint Petersburg, or another city/country?"                                           | `hh.area`                                          |
   | Search intent           | "What kind of vacancies or mentions are you trying to find? A role, technology, company, requirement, tool, or topic is enough."           | `search_terms`                                     |
   | hh search fields        | "Should hh.ru search text everywhere, only in vacancy titles, only in company names, or only in descriptions?"                             | `hh.filters.search_field`                          |
   | Experience              | "Which hh.ru experience levels should I include: no experience, 1-3 years, 3-6 years, or 6+ years?"                                        | `hh.filters.experience`                            |
   | Schedule                | "Which hh.ru schedule filters should I include: remote, full day, shift, flexible, or fly-in/fly-out?"                                     | `hh.filters.schedule`                              |
   | Employment              | "Which employment types should I include: full-time, part-time, project, volunteer, or probation?"                                         | `hh.filters.employment`                            |
   | Company industry        | "Should I filter by the employer's business industry, such as IT, media, banking, logistics, or another hh.ru industry?"                   | `hh.filters.industry`                              |
   | Salary                  | "Should I set a minimum salary or require vacancies with a visible salary?"                                                                | `hh.filters.salary`, `hh.filters.only_with_salary` |
   | Freshness               | "Should I limit results to vacancies published in the last N days? hh supports up to 30 days."                                             | `hh.filters.period`                                |
   | Sort order              | "Should hh.ru sort by relevance, publication date, salary high-to-low, or salary low-to-high?"                                             | `hh.filters.order_by`                              |
   | Vacancy title match     | "Should a mention in the vacancy title count?"                                                                                             | `match_scope.title`                                |
   | Company name match      | "Should a mention in the employer/company name count?"                                                                                     | `match_scope.company`                              |
   | Full vacancy text match | "Should a mention in the full vacancy text count?"                                                                                         | `match_scope.description`                          |
   | Key skills match        | "Should a mention in key skills count?"                                                                                                    | `match_scope.skills`                               |
   | Accepted meanings       | "Which meanings must count? I will propose exact words, spellings, Russian/English variants, and product names."                           | `term_patterns`                                    |
   | False-positive contexts | "Are there meanings that must not count? Example: SQL cursor when searching for Cursor. I will propose exclusions if the terms are risky." | `exclude_patterns`                                 |

   Do not ask users for internal implementation settings such as `max_pages`, delays, regex syntax, file paths, checkpoint paths, or output filenames unless the user explicitly asks to control the run. Choose those settings yourself using this skill's defaults.

   Do not ask about filters or sort modes this scraper cannot represent: office/hybrid specifically, employer type, metro, education, language, professional role, or distance sorting. If the user volunteers a text-like constraint, encode it as ordinary text in `search_terms`/`term_patterns`/`exclude_patterns`; for native-only constraints such as distance sorting, state that this skill cannot apply it.

   Region defaults:
   - default to Russia: `hh.area = "113"`;
   - for all hh.ru regions with no country/region limit, use `hh.area = "0"`;
   - for a specific country, region, or city, look up the current id in the official hh areas endpoint: `https://api.hh.ru/areas`. Do not guess area ids.

   Industry defaults:
   - do not apply an industry filter unless the user asks for it;
   - look up industry ids in the official hh industries endpoint: `https://api.hh.ru/industries`;
   - use group ids such as `7` for broad industries or nested ids such as `7.540` for narrower industries. Do not guess industry ids.

2. Query/profile research.
   Do not expect the user to supply ready hh.ru queries or exact regex words. Use the user's intent to research or derive:
   - canonical search groups;
   - hh.ru search queries for each group;
   - exact accepted terms, spellings, Russian/English variants, and product names;
   - false-positive exclusions for risky terms.

   You may propose multiple groups when it improves search quality, for example direct terms and broader related terms. Before collection, explain what each group means, how it changes recall/noise, and explicitly confirm the group names with the user. Do not invent opaque labels such as `explicit` or `adjacent` unless the user approves those exact names.

   Exclusions are whole-vacancy suppressors: if an exclusion pattern matches any enabled field, that term is not counted for the vacancy. Use narrow exclusion patterns and explain this behavior when proposing exclusions.

   Group related queries by user-approved canonical label. Treat short names, common words, job-title fragments, and company names as risky unless the requested scope makes them intentionally broad.

3. Profile draft.
   Create a fresh JSON profile from `templates/search_profile.template.json`. Do not reuse `examples/*.json` as production profiles. Fill every required setting before validation:
   - `hh.area`, `hh.max_pages`, search delays, and vacancy delays;
   - `match_scope.title`, `match_scope.company`, `match_scope.description`, and `match_scope.skills`;
   - `search_terms`, `term_patterns`, and any `exclude_patterns`;
   - `notes` for ambiguous, broad, or risky terms.

   Use these internal defaults unless there is a concrete reason to change them:
   - `hh.area`: `"113"` for Russia by default, or `"0"` for no region limit;
   - `hh.filters`: empty lists, `salary: null`, `only_with_salary: false`, `order_by: "relevance"`, `period: null`;
   - `hh.max_pages`: `3`;
   - `hh.search_delay_min` / `hh.search_delay_max`: `2.0` / `5.0`;
   - `hh.vacancy_delay_min` / `hh.vacancy_delay_max`: `2.0` / `5.0`;
   - internal preflight: `--limit-vacancies 2`;
   - `research-slug`: a short lowercase slug derived from the confirmed research title; examples: `ai-coding-tools`, `senior-flutter`, `company-name-search`;
   - export prefix: `<research-slug>.vacancies`.

   Validate the profile with the bundled scraper and the selected Python runtime. Do not collect vacancies from an unvalidated profile.

4. Confirmation gate.
   Before any network collection, show the user:
   - canonical search groups;
   - proposed hh.ru search queries;
   - enabled native hh filters;
   - proposed accepted terms and variants;
   - enabled match fields;
   - risky short terms and proposed exclusions;
   - exact work directory and artifact paths.
     Wait for explicit user confirmation before running the scraper.

5. Collection.
   Run only `scripts/hh_vacancy_scraper.py` with the confirmed profile and with cache, checkpoint, and output paths outside the skill package. Use checkpoint JSONL so interrupted runs can resume. Start with an internal preflight using `--limit-vacancies 2`; if it shows relevant parsed vacancies and no hh.ru blocking, continue to the full run without another user gate. Ask the user again only if preflight reveals noise, parser failure, captcha, or blocked access.

6. Noise control.
   If a search key produces repeated pages of likely noise, stop the run, tighten the profile, and explain the change. Checkpoint resume only applies when repeating the same confirmed profile. After changing `search_terms`, `term_patterns`, `exclude_patterns`, native hh filters, or match scope, reuse the same cache directory but use a new checkpoint file or expect old checkpoint rows to be ignored by fingerprint.

7. Export.
   Run only `scripts/export_hh_vacancies.py` after collection. XLSX is required. If `openpyxl` is missing, run `npx hh-vacancy-research-skill install --force` to recreate the skill-local virtual environment, or report the setup blocker.

8. Final report.
   Use the standardized final response format from the Final Response Contract section. Do not finish with only file links or only a numeric summary.

## Profile Contract

Profiles must contain:

- `title`: human-readable research title.
- `hh`: `area`, `max_pages`, `search_delay_min`, `search_delay_max`, `vacancy_delay_min`, `vacancy_delay_max`.
- `hh.filters`: optional native hh search filters: `search_field`, `experience`, `schedule`, `employment`, `industry`, `salary`, `only_with_salary`, `order_by`, `period`.
- `match_scope`: booleans for `title`, `company`, `description`, and `skills`; at least one must be true.
- `search_terms`: canonical label to hh search queries.
- `term_patterns`: canonical label to regex patterns used for full-card validation.
- `exclude_patterns`: optional canonical label to regex patterns for false-positive contexts.
- `notes`: optional reasoning, especially for risky terms.

The scraper keeps a vacancy only when a `term_patterns` regex matches at least one enabled field and no matching exclusion applies.

## Final Response Contract

Write the final user-facing response in Russian by default. Localize section headings, column explanations, group explanations, limitations, and all prose. Do not mix English and Russian except for literal file formats, field ids, tool names, or user-approved group labels. Use another language only if the user explicitly requests it.

Use a short, friendly, decision-useful style. Avoid a long audit dump. Prefer compact paragraphs and short bullets. Keep the final answer focused on what the user can open, what the columns mean, and how to interpret groups.

Use these sections in this order:

1. Result.
   State what was searched and the final counts in one compact paragraph:
   checked vacancies; kept vacancies; skipped vacancies; top matched groups.

2. Files.
   Provide every produced artifact as a clickable inline Markdown file link with a concise label in the user's language. Do not print bare paths. Use absolute local paths in the link target.

   Required file order, with localized labels:
   - profile file: `[<localized profile label>](</absolute/path/<research-slug>.profile.json>)`
   - source JSON file: `[<localized source JSON label>](</absolute/path/<research-slug>.source.json>)`
   - export JSON file: `[<localized export JSON label>](</absolute/path/<research-slug>.vacancies.json>)`
   - Markdown file: `[<localized Markdown label>](</absolute/path/<research-slug>.vacancies.md>)`
   - CSV file: `[<localized CSV label>](</absolute/path/<research-slug>.vacancies.csv>)`
   - XLSX file: `[<localized XLSX label>](</absolute/path/<research-slug>.vacancies.xlsx>)`
   - checkpoint file: `[<localized checkpoint label>](</absolute/path/<research-slug>.checkpoint.jsonl>)`

3. Columns.
   Explain exported columns briefly:
   - `Название вакансии`: vacancy title from hh.ru.
   - `Компания`: employer/company name parsed from the full vacancy card.
   - `Ссылка`: hh.ru vacancy URL.
   - `Поисковые группы`: canonical search group labels that matched this vacancy.
   - `Поля совпадения`: fields where the match was found. Allowed values in exported rows: `title`, `company`, `description`, `skills`.
   - `Навыки`: key skills parsed from the vacancy card.
   - `Описание`: full vacancy description. In XLSX, descriptions longer than Excel's per-cell limit are continued in the `Descriptions` sheet.

4. Groups.
   List every canonical search group and explain what it means in plain language. Use user-approved group labels exactly. Translate group type labels into the user's language:
   - narrow/direct;
   - broader/contextual;
   - intentionally noisy for discovery.

5. Match rules.
   State enabled match fields and exclusions in one short paragraph. If no exclusions were used, say so in the user's language.

6. Limitations.
   Mention only real limitations observed during the run. Valid limitation types: captcha; blocked pages; parser failures; intentionally limited sample; noisy query groups; user-approved scope limits. Do not invent generic caveats.

Use these Russian headings: `Итог`, `Файлы`, `Колонки`, `Группы`, `Правила матчинга`, `Ограничения`.
Use these Russian file labels: `Профиль`, `Исходный JSON`, `Экспорт JSON`, `Markdown`, `CSV`, `XLSX`, `Checkpoint`.

## Native HH Filter Values

Translate user-facing choices into these profile values. Do not write display labels into JSON.

| User-facing choice                 | Profile value                                                |
| ---------------------------------- | ------------------------------------------------------------ |
| Search everywhere                  | `hh.filters.search_field: []`                                |
| Search vacancy titles              | `hh.filters.search_field: ["name"]`                          |
| Search company names               | `hh.filters.search_field: ["company_name"]`                  |
| Search descriptions                | `hh.filters.search_field: ["description"]`                   |
| No experience                      | `hh.filters.experience: ["noExperience"]`                    |
| 1-3 years                          | `hh.filters.experience: ["between1And3"]`                    |
| 3-6 years                          | `hh.filters.experience: ["between3And6"]`                    |
| 6+ years                           | `hh.filters.experience: ["moreThan6"]`                       |
| Remote                             | `hh.filters.schedule: ["remote"]`                            |
| Full day                           | `hh.filters.schedule: ["fullDay"]`                           |
| Shift work                         | `hh.filters.schedule: ["shift"]`                             |
| Flexible schedule                  | `hh.filters.schedule: ["flexible"]`                          |
| Fly-in/fly-out                     | `hh.filters.schedule: ["flyInFlyOut"]`                       |
| Full-time                          | `hh.filters.employment: ["full"]`                            |
| Part-time                          | `hh.filters.employment: ["part"]`                            |
| Project work                       | `hh.filters.employment: ["project"]`                         |
| Volunteer                          | `hh.filters.employment: ["volunteer"]`                       |
| Probation/internship               | `hh.filters.employment: ["probation"]`                       |
| Company industry by hh id          | `hh.filters.industry: ["7", "7.540"]`                        |
| Minimum salary N                   | `hh.filters.salary: N`                                       |
| Only vacancies with visible salary | `hh.filters.only_with_salary: true`                          |
| Sort by relevance                  | `hh.filters.order_by: "relevance"`                           |
| Sort by newest                     | `hh.filters.order_by: "publication_time"`                    |
| Sort by salary high-to-low         | `hh.filters.order_by: "salary_desc"`                         |
| Sort by salary low-to-high         | `hh.filters.order_by: "salary_asc"`                          |
| Last N days, max 30                | `hh.filters.period: N`                                       |
| No filter for a dimension          | empty list, `null`, `false`, or `"relevance"` as appropriate |

## Script Operating Procedure

Use this exact operating pattern for every run:

1. Create a `research-slug` from the confirmed research title.
2. Create a working directory outside the skill package: `outputs/hh-vacancy-research/<research-slug>/`.
3. Create `<research-slug>.profile.json` in that working directory from `templates/search_profile.template.json`.
4. Fill the profile from the user's answers and your term research. Keep examples as examples only.
5. Set `<python>` to the skill-local Python when available:
   - macOS/Linux: `<skill-dir>/.venv/bin/python`
   - Windows: `<skill-dir>/.venv/Scripts/python.exe`
   - fallback: `python3`
6. Validate the profile:

   ```bash
   <python> <skill-dir>/scripts/hh_vacancy_scraper.py \
     --profile <work-dir>/<research-slug>.profile.json \
     --validate-profile
   ```

7. Show the user the profile summary and wait for explicit confirmation.
8. Run an internal preflight:

   ```bash
   <python> <skill-dir>/scripts/hh_vacancy_scraper.py \
     --profile <work-dir>/<research-slug>.profile.json \
     --cache-dir <work-dir>/cache \
     --output-json <work-dir>/<research-slug>.source.json \
     --checkpoint-jsonl <work-dir>/<research-slug>.checkpoint.jsonl \
     --limit-vacancies 2
   ```

9. If preflight shows relevant parsed vacancies and no hh.ru blocking, continue to full collection by repeating the same scraper command without `--limit-vacancies`. Do not ask the user for another confirmation just because preflight passed.
10. If preflight is noisy or fails, stop, tighten the profile, validate again, and ask for confirmation again. After changing the profile, reuse the same cache directory but use a new checkpoint file or expect old checkpoint rows to be ignored by fingerprint.
11. Resume an interrupted run only when the profile is unchanged, by repeating the same full collection command with the same `--cache-dir` and `--checkpoint-jsonl`.
12. Export results:

    ```bash
    <python> <skill-dir>/scripts/export_hh_vacancies.py \
      --source-json <work-dir>/<research-slug>.source.json \
      --output-dir <work-dir> \
      --output-prefix <research-slug>.vacancies
    ```

13. If hh.ru returns captcha, access denied, repeated blocked pages, or obvious mass noise, stop. Report the blocker or proposed profile tightening instead of hammering hh.ru.

## Completion Bar

The work is complete only when:

- the profile was confirmed by the user before collection;
- all unique candidate vacancies were checked; limited samples require explicit user acceptance;
- output JSON, Markdown, CSV, XLSX, and checkpoint JSONL exist;
- the final response separates outcome from evidence and names any setup or collection limitations.
