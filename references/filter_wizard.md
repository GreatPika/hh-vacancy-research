# HH Filter Wizard

Use this reference after search topics and terms are confirmed.

## Rules

- Ask only for filters the scraper can represent.
- Use real values from `templates/search_profile.schema.json`, `scripts/hh_vacancy_scraper.py`, and `references/profile_mapping.md`.
- Do not invent native hh.ru filter values.
- Explain every filter in Russian.
- All user-facing questions, labels, options, summaries, and help text must be Russian. Use English only for literal product names, tool names, file formats, URLs, or internal profile values when the user asks for implementation detail.
- Offer a default and an unset option when applicable.
- Recommend leaving optional filters unset when the filter may hide relevant vacancies.
- If a value is already obvious from the user's request, pre-fill it and ask for confirmation.

## Stepwise Interaction

Walk through filter blocks one at a time. Do not present all filter blocks in one large list and ask the user to accept or edit everything at once.

For each block:

- explain what the filter controls;
- show the recommended default or pre-filled value;
- show only the options for that block;
- ask one clear question;
- after the answer, show compact progress and name the next block.

You may group only tightly coupled choices in the same question, such as minimum salary and "only vacancies with salary". If the user explicitly asks to keep all recommended defaults, skip the remaining optional filter questions and proceed to the full summary.

Do not ask the user to configure profile `match_scope`. It is an internal confirmation scope and must be derived from the selected "Где искать на hh.ru" value according to `references/profile_mapping.md`.

## Unsupported Native Filters

Do not ask the user to configure these as native hh.ru filters:

- офис/гибрид как отдельный нативный фильтр;
- тип работодателя;
- метро;
- образование;
- язык;
- профессиональная роль;
- сортировка по расстоянию.

If the user volunteers a text-like constraint, represent it as search terms, accepted terms, or exclusions. If the user asks for a native-only constraint the scraper cannot represent, explain that plainly in Russian and offer the closest supported alternative.

## Filter Blocks

### Geography

Объяснение: этот фильтр определяет, в каком регионе hh.ru искать вакансии. Если пользователь не уверен, лучше начать с России или явно выбранного города/страны.

По умолчанию: Россия.

Use the all-regions internal value only when the user wants all hh.ru regions with no country or region limit. Keep the internal value in `references/profile_mapping.md`, not in this user-facing wizard.

For a specific city, country, or region, look up the id in `https://api.hh.ru/areas`. Do not guess ids. If the request is ambiguous or unavailable, show the closest real choices.

### HH Text Search Fields

Объяснение: этот фильтр определяет, где hh.ru будет искать введённые слова: во всей вакансии или только в отдельной части карточки.

По умолчанию: искать везде.

Варианты:

- везде;
- только в названиях вакансий;
- только в названиях компаний;
- только в описаниях.

### Experience

Объяснение: этот фильтр ограничивает вакансии по опыту, который указал работодатель на hh.ru. Если нет жёсткого требования по опыту, лучше оставить без фильтра.

По умолчанию: без фильтра.

Варианты:

- нет опыта;
- от 1 года до 3 лет;
- от 3 до 6 лет;
- более 6 лет;
- без фильтра.

### Schedule

Объяснение: этот фильтр ограничивает вакансии по графику работы на hh.ru. Если график не важен, лучше оставить без фильтра, чтобы не потерять подходящие вакансии.

По умолчанию: без фильтра.

Варианты:

- удаленная работа;
- полный день;
- сменный график;
- гибкий график;
- вахтовый метод;
- без фильтра.

### Employment

Объяснение: этот фильтр ограничивает вакансии по типу занятости. Если формат занятости не важен, лучше оставить без фильтра.

По умолчанию: без фильтра.

Варианты:

- полная занятость;
- частичная занятость;
- проектная работа;
- волонтерство;
- стажировка;
- без фильтра.

### Company Industry

Объяснение: этот фильтр ограничивает отрасль работодателя, а не текст вакансии. Если пользователь ищет упоминания технологии или инструмента в любых компаниях, чаще лучше оставить индустрию без фильтра.

По умолчанию: без фильтра.

When the user chooses an industry, look up real values in `https://api.hh.ru/industries`. Show real industry names to the user. Keep ids internal unless the user asks for implementation detail.

### Salary

Объяснение: этот фильтр ограничивает вакансии по зарплате. Важно предупредить, что многие вакансии скрывают зарплату, поэтому фильтр может сильно уменьшить выдачу.

По умолчанию: без фильтра.

Варианты:

- минимальная зарплата;
- только вакансии с указанной зарплатой;
- минимальная зарплата и только вакансии с указанной зарплатой;
- без фильтра.

### Freshness

Объяснение: этот фильтр ограничивает вакансии по дате публикации. hh.ru поддерживает период до 30 дней.

По умолчанию: без фильтра.

Варианты: последние N дней, где N от 1 до 30, или без фильтра.

### Sort Order

Объяснение: этот фильтр задаёт порядок выдачи hh.ru. Для обычного поиска лучше использовать релевантность.

По умолчанию: релевантность.

Варианты:

- релевантность;
- сначала новые;
- зарплата по убыванию;
- зарплата по возрастанию.

## Progress Updates

Show compact progress after each answer. Include the current topic or topics, selected filters, filters still left unset, and the next filter block. Do not expose JSON field names unless the user asks.

Use Markdown formatting to make the current settings visually separate from the active question.

Use this style:

```text
**Текущие настройки поиска**

> **Темы:** AI-инструменты
> **Регион:** Россия
> **Где искать на hh.ru:** везде
> **Опыт:** без фильтра
> **График:** без фильтра
> **Занятость:** без фильтра
> **Отрасль работодателя:** без фильтра
> **Зарплата:** без фильтра
> **Свежесть:** еще не выбрана

---

**Следующий фильтр: график работы**

Если график не важен, лучше оставить без фильтра, чтобы не потерять подходящие вакансии.

Что выбираем?

1. **Без фильтра** — рекомендую.
2. **Удаленная работа**
3. **Полный день**
4. **Другой поддерживаемый график**
```

If the user does not understand a filter, explain it using only real supported values or verified dictionary values.
