# Final Response

Use this reference before reporting completed collection results.

Write the final response in Russian by default. Use another language only if the user explicitly requested it.

## Required Shape

Return only a short completion message and links to the four user-facing files.

Do not include sections or explanations for:

- counts or top groups;
- source JSON;
- export JSON;
- checkpoint JSONL;
- exported columns;
- search groups;
- matching rules;
- limitations.

## Fixed Message

Use this sentence:

`Готово, сбор и выгрузка завершены.`

## Required Links

Then provide exactly these links in this order, with absolute local paths:

1. `[Профиль](...) — сохранённые настройки поиска.`
2. `[Markdown](...) — текстовая версия для просмотра.`
3. `[CSV](...) — упрощённая таблица.`
4. `[XLSX](...) — основная таблица для Excel/Google Sheets.`

Do not include bullet links to source JSON, export JSON, checkpoint JSONL, or any extra runtime files unless the user explicitly asks for them.
