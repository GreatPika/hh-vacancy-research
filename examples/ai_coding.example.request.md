# Example Request

Find hh.ru vacancies where employers mention AI coding tools or AI-assisted development workflows.

## Example Discovery Decisions

- Audience: product and recruiting stakeholders who need a spreadsheet.
- Geography: all Russia on hh.ru (`area=113`).
- Native hh filters: none; use hh.ru relevance order.
- Match scope: title, full description, and key skills; company name matching is off for this example.
- Strictness: keep only vacancies where a confirmed term appears in one of the allowed fields.
- Languages: English and Russian terms are allowed.
- Risky terms: short names such as `Cursor` must have regex boundaries and exclusions for false-positive contexts.

## Example Confirmation Summary

Show a profile summary before collection:

- Search groups: Claude Code, Cursor, GitHub Copilot, AI coding workflow.
- Native hh filters: none.
- Enabled fields: title, description, skills. Company name matching is disabled.
- Risk controls: Cursor excludes database/SQL cursor contexts.
- Outputs: JSON source, Markdown, CSV, XLSX, and checkpoint JSONL.

## Example Final Response Shape

For a Russian user, use Russian headings and concise Russian prose:

- `Итог`: one compact paragraph with checked/kept/skipped counts and top groups.
- `Файлы`: inline clickable links, for example `[XLSX](</absolute/path/ai-coding-tools.vacancies.xlsx>)`.
- `Колонки`: short explanations for `Название вакансии`, `Компания`, `Ссылка`, `Поисковые группы`, `Поля совпадения`, `Навыки`, and `Описание`.
- `Группы`: explain Claude Code, Cursor, GitHub Copilot, and AI coding workflow in plain Russian.
- `Правила матчинга`: enabled fields and exclusions in one short paragraph.
- `Ограничения`: only observed blockers and user-approved limits.

This example is illustrative. Create a fresh profile for the user's real request.
