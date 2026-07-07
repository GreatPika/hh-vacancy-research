# Profile Mapping

Use this reference after the user confirms topics, terms, and filters.

## Profile Source

Create every production profile from `templates/search_profile.template.json`. Do not reuse `examples/*.json` as production profiles.

Profiles must validate against `templates/search_profile.schema.json` and `scripts/hh_vacancy_scraper.py --validate-profile`.

## Pre-Profile Confirmation Summary

Before creating the profile, show the user a complete Russian summary with these user-facing parts:

- цель исследования;
- одна тема или несколько тем;
- слова внутри каждой темы;
- исключения;
- регион;
- все фильтры hh.ru;
- где hh.ru ищет слова;
- рабочая папка в текущем проекте, по правилу ниже;
- какие файлы будут созданы.

Create a short lowercase `research-slug` from the confirmed research title before showing the summary.

Use this work directory pattern:

```text
<codex-start-directory>/outputs/hh-vacancy-research/<research-slug>/
```

Resolve `<codex-start-directory>` to the current Codex working directory: the project or folder from which the user started this Codex session. By default, runtime artifacts belong to the user's current project, not to the skill installation directory or the user's home directory.

The resolved absolute work directory must not be inside the installed skill package, such as `$CODEX_HOME/skills/hh-vacancy-research` or `~/.codex/skills/hh-vacancy-research`. If the current Codex working directory is the installed skill package, stop and ask the user for the project directory where outputs should be written. Do not silently choose another root.

Explain files by purpose using this Russian copy:

```text
В конце я создам несколько файлов:

- Профиль поиска — сохранённые настройки поиска, которые можно переиспользовать для повторного запуска или корректировки запроса.
- Markdown — удобная текстовая версия для быстрого просмотра.
- CSV — упрощённая таблица для импорта в другие инструменты.
- XLSX — основная таблица для просмотра в Excel или Google Sheets.
```

Wait for explicit user confirmation before creating the profile.

## Required Profile Fields

- `title`
- `hh.area`
- `hh.max_pages`
- `hh.search_delay_min`
- `hh.search_delay_max`
- `hh.vacancy_delay_min`
- `hh.vacancy_delay_max`
- `hh.filters`
- `match_scope`
- `search_terms`
- `term_patterns`
- `exclude_patterns`
- `notes`

## Defaults

- `hh.area`: `"113"` for Russia by default; `"0"` only for all hh.ru regions with no country or region limit.
- `hh.max_pages`: `3`.
- `hh.search_delay_min`: `2.0`.
- `hh.search_delay_max`: `5.0`.
- `hh.vacancy_delay_min`: `2.0`.
- `hh.vacancy_delay_max`: `5.0`.
- `hh.filters.search_field`: `[]`.
- `hh.filters.experience`: `[]`.
- `hh.filters.schedule`: `[]`.
- `hh.filters.employment`: `[]`.
- `hh.filters.industry`: `[]`.
- `hh.filters.salary`: `null`.
- `hh.filters.only_with_salary`: `false`.
- `hh.filters.order_by`: `"relevance"`.
- `hh.filters.period`: `null`.

## Match Scope Mapping

Do not ask the user to choose `match_scope` in the normal wizard flow.

Build `match_scope` mechanically from `hh.filters.search_field`. This keeps the local confirmation step aligned with the hh.ru text search area the user already selected.

Set all supported `match_scope` keys explicitly in the generated profile:

- `title`
- `company`
- `description`
- `skills`

Use this exact mapping for the normal wizard choices:

| `hh.filters.search_field` | Meaning | Generated `match_scope` |
| --- | --- | --- |
| `[]` | hh.ru searches everywhere | `{"title": true, "company": false, "description": true, "skills": true}` |
| `["name"]` | hh.ru searches only vacancy titles | `{"title": true, "company": false, "description": false, "skills": false}` |
| `["company_name"]` | hh.ru searches only employer names | `{"title": false, "company": true, "description": false, "skills": false}` |
| `["description"]` | hh.ru searches only vacancy descriptions | `{"title": false, "company": false, "description": true, "skills": false}` |

For any non-empty `hh.filters.search_field` array, generate `match_scope` with this deterministic rule:

- `title` is `true` only when `"name"` is present.
- `company` is `true` only when `"company_name"` is present.
- `description` is `true` only when `"description"` is present.
- `skills` is always `false`.

For example, `["name", "description"]` must generate `{"title": true, "company": false, "description": true, "skills": false}`.

Only override this mapping when the user explicitly asks for a different confirmation scope. If overriding, record the reason in `notes`.

## Native Filter Values

| Пользовательский выбор | Profile value |
| --- | --- |
| Искать везде | `hh.filters.search_field: []` |
| Искать только в названиях вакансий | `hh.filters.search_field: ["name"]` |
| Искать только в названиях компаний | `hh.filters.search_field: ["company_name"]` |
| Искать только в описаниях | `hh.filters.search_field: ["description"]` |
| Нет опыта | `hh.filters.experience: ["noExperience"]` |
| От 1 года до 3 лет | `hh.filters.experience: ["between1And3"]` |
| От 3 до 6 лет | `hh.filters.experience: ["between3And6"]` |
| Более 6 лет | `hh.filters.experience: ["moreThan6"]` |
| Удаленная работа | `hh.filters.schedule: ["remote"]` |
| Полный день | `hh.filters.schedule: ["fullDay"]` |
| Сменный график | `hh.filters.schedule: ["shift"]` |
| Гибкий график | `hh.filters.schedule: ["flexible"]` |
| Вахтовый метод | `hh.filters.schedule: ["flyInFlyOut"]` |
| Полная занятость | `hh.filters.employment: ["full"]` |
| Частичная занятость | `hh.filters.employment: ["part"]` |
| Проектная работа | `hh.filters.employment: ["project"]` |
| Волонтерство | `hh.filters.employment: ["volunteer"]` |
| Стажировка | `hh.filters.employment: ["probation"]` |
| Индустрия компании по hh id | `hh.filters.industry: ["7", "7.540"]` |
| Минимальная зарплата N | `hh.filters.salary: N` |
| Только вакансии с указанной зарплатой | `hh.filters.only_with_salary: true` |
| Сортировка по релевантности | `hh.filters.order_by: "relevance"` |
| Сначала новые | `hh.filters.order_by: "publication_time"` |
| Зарплата по убыванию | `hh.filters.order_by: "salary_desc"` |
| Зарплата по возрастанию | `hh.filters.order_by: "salary_asc"` |
| Последние N дней, максимум 30 | `hh.filters.period: N` |

## Search Topics And Terms

Каждую подтверждённую тему нужно записать в оба поля:

- `search_terms`: фразы для поиска этой темы на hh.ru;
- `term_patterns`: принятые слова и выражения для проверки полной карточки вакансии.

Если пользователь оставляет одну тему, используйте короткое название из цели пользователя.

Если пользователь подтверждает несколько тем, у каждой темы должны быть свои `search_terms` и `term_patterns`.

Используйте `exclude_patterns` для подтверждённых ложных значений или шумных контекстов. Исключения подавляют вакансию целиком для этой темы, поэтому они должны быть узкими.

Используйте `notes` для неоднозначных, широких, рискованных или ограниченных пользователем решений.
