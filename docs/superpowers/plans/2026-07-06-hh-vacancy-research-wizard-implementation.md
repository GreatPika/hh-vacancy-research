# hh-vacancy-research Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the `hh-vacancy-research` skill as a short controlling workflow plus focused references that guide users through intent discovery, optional web research, search topics, hh.ru filters, confirmation, collection, export, and final reporting.

**Architecture:** Keep `SKILL.md` as the high-level process contract and move detailed guidance into `references/*.md`. The implementation changes documentation only; scraper/export code and templates should remain unchanged unless verification exposes a real mismatch.

**Tech Stack:** Markdown skill files, existing Python scraper/export scripts, existing JSON schema/template, shell verification with `rg`, `wc`, and existing tests where relevant.

---

## File Structure

Modify:

- `SKILL.md` - replace the long mixed-responsibility instruction file with a short controlling workflow and links to reference files.

Create:

- `references/discovery_wizard.md` - intent discovery, user-approved web search, search topics, default single topic, optional multiple topics, and term confirmation.
- `references/filter_wizard.md` - user-facing hh.ru filter wizard, supported values, unsupported filters, geography and industry dictionary lookup, progress updates.
- `references/profile_mapping.md` - profile contract, defaults, and mapping from user-facing choices to JSON values.
- `references/runbook.md` - runtime paths, profile validation, preflight, full collection, checkpoint/resume, noise handling, export.
- `references/final_response.md` - final Russian response contract, human file explanations, column explanations, topic explanations, limitations.

Do not modify unless verification finds a mismatch:

- `scripts/hh_vacancy_scraper.py`
- `scripts/export_hh_vacancies.py`
- `templates/search_profile.schema.json`
- `templates/search_profile.template.json`
- `tests/test_export_hh_vacancies.py`

## Implementation Tasks

### Task 1: Define Skill Verification Scenarios

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-hh-vacancy-research-wizard-implementation.md`

- [ ] **Step 1: Use these pressure scenarios before editing skill files**

Run these as manual review prompts against the current skill text and again after implementation. They are not committed as a separate artifact; record pass/fail notes in the implementation summary.

Scenario A, broad topic with web search:

```text
User: Хочу найти на hh.ru вакансии, где встречаются AI-инструменты.

Expected after rewrite:
- Agent first restates the research intent.
- Agent offers web search in Russian with the required explanation.
- Agent does not search the web until the user confirms.
- Agent explains that the default is one topic and extra groups are optional.
- Agent does not ask hh.ru filters before topic and terms are confirmed.
```

Scenario B, optional multiple topics:

```text
User: Хочу найти AI-инструменты, но не знаю какие именно.
User confirms web search.

Expected after rewrite:
- Agent proposes a single topic by default.
- Agent explains optional groups in plain Russian.
- If proposing multiple groups, each group has its own terms.
- Agent lets the user rename, remove, merge, split, or approve groups.
```

Scenario C, unsupported filter and ambiguous dictionary values:

```text
User: Ищу Python вакансии, только гибрид, рядом с метро, в индустрии AI, город Тбилиси.

Expected after rewrite:
- Agent does not invent unsupported native filters for hybrid or metro.
- Agent explains unsupported filters and offers text-term alternatives where possible.
- Agent checks geography through hh areas instead of guessing.
- Agent checks industry through hh industries instead of inventing "AI".
```

Scenario D, internal settings pressure:

```text
User: Найди Cursor вакансии.

Expected after rewrite:
- Agent does not ask for max_pages, delays, regex syntax, checkpoint path, output filenames, or slug.
- Agent uses defaults internally.
- Agent shows human file explanations before confirmation.
```

- [ ] **Step 2: Confirm the scenarios cover the design**

Check each scenario against `docs/superpowers/specs/2026-07-06-hh-vacancy-research-wizard-design.md`.

Expected: scenarios cover web-search approval, search topics, per-topic terms, unsupported filters, dictionary lookup, internal defaults, artifact explanation, and no collection before confirmation.

### Task 2: Rewrite `SKILL.md` As The Controlling Workflow

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Replace the current body with a short workflow**

Keep the existing frontmatter unchanged:

```markdown
---
name: hh-vacancy-research
description: Use when a user wants to research hh.ru vacancies.
---
```

Replace the body after frontmatter with:

```markdown
# hh-vacancy-research

Use this skill when a user wants to research hh.ru vacancies. The user may be looking for a role, company, industry, technology, tool, work practice, requirement, keyword, or key skill.

This is a guided workflow. Do not collect vacancies until the user has confirmed the completed search plan.

## Required References

Read the referenced file before executing that stage:

- `references/discovery_wizard.md` before asking about intent, web research, search topics, or search terms.
- `references/filter_wizard.md` before asking about hh.ru filters.
- `references/profile_mapping.md` before creating or validating a profile.
- `references/runbook.md` before running scraper or exporter commands.
- `references/final_response.md` before reporting results.

## Mandatory Flow

1. Discovery wizard.
   Clarify what the user wants to find. Offer web research, explain why it helps, and run it only after explicit confirmation.

2. Search topic and term review.
   Default to one topic. Additional topics are optional. Confirm topic names and terms before filters.

3. HH filter wizard.
   Walk through supported filters with real hh.ru values, user-facing explanations, defaults, and progress updates.

4. Full summary and confirmation.
   Show the research goal, topics, terms, exclusions, filters, match fields, work directory, and human explanations of produced files. Wait for explicit user confirmation.

5. Profile creation and validation.
   Create a fresh profile from `templates/search_profile.template.json` outside the skill package. Validate it before collection.

6. Preflight and collection.
   Run the bundled scraper only. Start with `--limit-vacancies 2`; continue to the full run only when preflight is relevant and unblocked.

7. Export.
   Run the bundled exporter only. XLSX output is required.

8. Final response.
   Report results in Russian by default using the final response contract.

## Hard Rules

- Use only `scripts/hh_vacancy_scraper.py` for collection and `scripts/export_hh_vacancies.py` for export.
- Do not use hh vacancy APIs, ad hoc scraping, shell one-liners, unrelated scripts, or manually assembled vacancy lists unless the user explicitly abandons this workflow.
- The official hh API may be used only for dictionary lookups: `https://api.hh.ru/areas` and `https://api.hh.ru/industries`.
- Keep runtime artifacts outside the skill package.
- Keep internal settings internal unless the user explicitly asks to control them.
- Communicate with the user in Russian by default unless the user asks for another language.
```

- [ ] **Step 2: Verify `SKILL.md` is short and points to all references**

Run:

```bash
wc -w SKILL.md
test "$(wc -w < SKILL.md)" -lt 350
rg -n 'references/discovery_wizard\.md' SKILL.md
rg -n 'references/filter_wizard\.md' SKILL.md
rg -n 'references/profile_mapping\.md' SKILL.md
rg -n 'references/runbook\.md' SKILL.md
rg -n 'references/final_response\.md' SKILL.md
rg -n 'Mandatory Flow|Hard Rules' SKILL.md
```

Expected: `SKILL.md` is under 350 words and mentions all five reference files.

- [ ] **Step 3: Commit controlling workflow**

```bash
git add SKILL.md
git commit -m "docs: streamline hh vacancy skill workflow" -m "Keep SKILL.md focused on the mandatory wizard flow and delegate detailed discovery, filters, mapping, runbook, and reporting guidance to references."
```

### Task 3: Create Discovery Wizard Reference

**Files:**
- Create: `references/discovery_wizard.md`

- [ ] **Step 1: Create `references/discovery_wizard.md`**

Add this content:

````markdown
# Discovery Wizard

Use this reference before any hh.ru filter questions.

## Goal

First decide what should count as a relevant vacancy. Do not assume the user knows the right search words.

Clarify whether the user is looking for:

- a role or vacancy title;
- a technology, tool, method, requirement, or key skill mention;
- companies or industries;
- broad market research.

Restate the goal in simple Russian before moving on.

## Web Research Offer

Always offer web research during term selection. Explain why it helps and wait for explicit approval before searching.

Use this Russian copy:

```text
Перед тем как подбирать слова для hh.ru, я могу быстро поискать в интернете.

Зачем это нужно:
- найти актуальные названия инструментов, компаний и продуктов;
- собрать русские и английские варианты написания;
- заметить синонимы и близкие термины;
- заранее отсеять слова, которые могут давать лишний шум.

Особенно полезно поискать в интернете, если тема широкая, новая, завязана на бренды или может называться по-разному.

Я начну веб-поиск только с вашего подтверждения.
Искать в интернете или продолжить по тем словам, которые уже есть?
```

If the user agrees, search broadly but include only explainable terms in the proposed topics. Prefer official product pages, documentation, credible articles, rankings, and repeated independent mentions.

If the user declines, continue from the user's words and say in Russian that the term list may be narrower or less current.

## Search Topics

Explain topics before hh.ru filters. Use this Russian copy:

```text
Перед фильтрами нужно договориться о поиске.

По умолчанию я не буду делить поиск на несколько групп.
Мы можем искать всё одной темой — так проще, если задача узкая.

Дополнительные группы нужны, если тема широкая и её удобно разделить.
Например, “AI-инструменты” можно разделить на “AI для кода”, “AI для встреч”, “AI для текстов”.

В итоговой таблице будет видно, по какой теме вакансия попала в результат.

Я предложу название темы или групп и слова внутри них.
Вы сможете сказать: оставить, убрать, объединить, разделить или переименовать.
```

Default to one topic. Name it from the user's goal, such as `AI-инструменты`, `Cursor`, or `Senior Flutter`. Do not use a generic label such as `Общий поиск`.

Additional topics are optional and require user consent. If the user chooses multiple topics, propose the topic names yourself and let the user rename, remove, merge, split, or approve them.

## Terms Per Topic

Each topic must have its own confirmed terms.

Use this Russian copy when multiple topics are used:

```text
Теперь для каждой поисковой группы нужно подобрать слова.

Важно: у каждой группы будет свой набор слов.
Так мы сможем искать точнее и потом показать в таблице, какая именно тема нашлась в вакансии.

Я предложу слова для каждой группы отдельно.
Вы сможете убрать лишнее, добавить свои варианты или попросить расширить список.
```

Для каждой темы предложите:

- фразы для поиска на hh.ru;
- русские и английские варианты написания;
- названия продуктов, инструментов или компаний, если они важны;
- близкие формулировки и синонимы;
- возможные лишние значения или контексты, которые могут давать шум.

Do not proceed to hh.ru filters until the user confirms the topic structure and terms.
````

- [ ] **Step 2: Verify required Russian copy exists**

Run:

```bash
rg -n 'Перед тем как подбирать слова' references/discovery_wizard.md
rg -n 'Перед фильтрами нужно договориться' references/discovery_wizard.md
rg -n 'Теперь для каждой поисковой группы' references/discovery_wizard.md
rg -n 'Default to one topic' references/discovery_wizard.md
rg -n 'Do not proceed' references/discovery_wizard.md
```

Expected: every required phrase is found.

- [ ] **Step 3: Commit discovery reference**

```bash
git add references/discovery_wizard.md
git commit -m "docs: add hh discovery wizard reference" -m "Document intent discovery, user-approved web research, default single-topic search, optional grouped topics, and per-topic term confirmation."
```

### Task 4: Create Filter Wizard Reference

**Files:**
- Create: `references/filter_wizard.md`

- [ ] **Step 1: Create `references/filter_wizard.md`**

Add a reference that contains these exact sections and supported values:

````markdown
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

### Work Format

Объяснение: этот фильтр ограничивает формат работы на hh.ru: на месте работодателя, удалённо, гибрид или разъездной формат. Если формат работы не важен, лучше оставить без фильтра.

По умолчанию: без фильтра.

Варианты:

- на месте работодателя;
- удалённо;
- гибрид;
- разъездной;
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

### Full-Card Match Fields

Объяснение: эти поля определяют, где в полной карточке вакансии совпадение будет считаться подходящим: в названии, компании, описании или навыках.

По умолчанию: название, описание и навыки включены. Компания включается только когда пользователь ищет названия или упоминания компаний.

Варианты:

- название вакансии;
- работодатель/компания;
- полный текст вакансии;
- ключевые навыки.

At least one match field must be enabled.

## Progress Updates

Show compact progress after each answer or block. Include the current topic or topics, selected filters, filters still left unset, and the next step. Do not expose JSON field names unless the user asks.

Use this style:

```text
Настройки поиска сейчас:

Тема: AI-инструменты
Регион: Россия
Где искать на hh.ru: везде
Опыт: без фильтра
Формат работы: без фильтра

Следующий шаг: формат работы.
Оставляем без фильтра или ограничиваем?
```

If the user does not understand a filter, explain it using only real supported values or verified dictionary values.
````

- [ ] **Step 2: Verify unsupported and supported filter text**

Run:

```bash
rg -n 'офис/гибрид|профессиональная роль|сортировка по расстоянию' references/filter_wizard.md
rg -n 'нет опыта|удалённо|гибрид|разъездной|стажировка' references/filter_wizard.md
rg -n 'https://api\.hh\.ru/areas|https://api\.hh\.ru/industries' references/filter_wizard.md
rg -n 'Настройки поиска сейчас' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр определяет, в каком регионе' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр определяет, где hh\.ru будет искать' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает вакансии по опыту' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает формат работы' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает вакансии по типу занятости' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает отрасль работодателя' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает вакансии по зарплате' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр ограничивает вакансии по дате публикации' references/filter_wizard.md
rg -n 'Объяснение: этот фильтр задаёт порядок выдачи' references/filter_wizard.md
rg -n 'Объяснение: эти поля определяют, где в полной карточке' references/filter_wizard.md
```

Expected: unsupported filters, dictionary URLs, progress copy, and all user-facing fixed choices are present.

- [ ] **Step 3: Commit filter reference**

```bash
git add references/filter_wizard.md
git commit -m "docs: add hh filter wizard reference" -m "Document supported hh filter choices, unsupported native filters, dictionary lookups, defaults, match fields, and progress updates."
```

### Task 5: Create Profile Mapping Reference

**Files:**
- Create: `references/profile_mapping.md`

- [ ] **Step 1: Create `references/profile_mapping.md`**

Add mapping tables matching `templates/search_profile.schema.json` and `scripts/hh_vacancy_scraper.py`:

````markdown
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
- где полная карточка проверяется на совпадение;
- рабочая папка;
- какие файлы будут созданы.

Explain files by purpose using this Russian copy:

```text
В конце я создам несколько файлов:

- Профиль поиска — здесь сохранены выбранные вами настройки. Он нужен, чтобы потом повторить или поправить этот же поиск.
- Исходные результаты — это полный результат сбора до удобной выгрузки. Нужен для проверки и повторного экспорта.
- Экспорт JSON — те же найденные вакансии в удобной структуре для других программ или повторной обработки.
- Таблица XLSX — основной файл для просмотра в Excel или Google Sheets.
- CSV — упрощённая таблица для импорта в другие инструменты.
- Markdown — удобная текстовая версия для быстрого просмотра.
- Файл продолжения — технический файл. Он нужен, чтобы не начинать заново, если сбор прервётся.
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
- `hh.filters.work_format`: `[]`.
- `hh.filters.employment`: `[]`.
- `hh.filters.industry`: `[]`.
- `hh.filters.salary`: `null`.
- `hh.filters.only_with_salary`: `false`.
- `hh.filters.order_by`: `"relevance"`.
- `hh.filters.period`: `null`.
- `match_scope.title`: `true`.
- `match_scope.company`: `false` unless searching for company names or mentions.
- `match_scope.description`: `true`.
- `match_scope.skills`: `true`.

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
| На месте работодателя | `hh.filters.work_format: ["ON_SITE"]` |
| Удалённо | `hh.filters.work_format: ["REMOTE"]` |
| Гибрид | `hh.filters.work_format: ["HYBRID"]` |
| Удалённо и гибрид | `hh.filters.work_format: ["REMOTE", "HYBRID"]` |
| Разъездной формат | `hh.filters.work_format: ["FIELD_WORK"]` |
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
````

- [ ] **Step 2: Verify mappings against schema**

Run:

```bash
python3 - <<'PY'
import importlib.util
import json
from pathlib import Path

mapping = Path("references/profile_mapping.md").read_text(encoding="utf-8")
schema = json.loads(Path("templates/search_profile.schema.json").read_text(encoding="utf-8"))

spec = importlib.util.spec_from_file_location("hh_vacancy_scraper", "scripts/hh_vacancy_scraper.py")
scraper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(scraper)

filters = schema["properties"]["hh"]["properties"]["filters"]["properties"]
expected_sets = {
    "search_field": set(filters["search_field"]["items"]["enum"]),
    "experience": set(filters["experience"]["items"]["enum"]),
    "work_format": set(filters["work_format"]["items"]["enum"]),
    "employment": set(filters["employment"]["items"]["enum"]),
    "order_by": set(filters["order_by"]["enum"]),
}
scraper_sets = {
    "search_field": set(scraper.SEARCH_FIELD_VALUES),
    "experience": set(scraper.EXPERIENCE_VALUES),
    "work_format": set(scraper.WORK_FORMAT_VALUES),
    "employment": set(scraper.EMPLOYMENT_VALUES),
    "order_by": set(scraper.ORDER_BY_VALUES),
}

if expected_sets != scraper_sets:
    raise SystemExit(f"schema/scraper enum mismatch: {expected_sets!r} != {scraper_sets!r}")

period = filters["period"]
if period.get("maximum") != 30:
    raise SystemExit(f"period maximum must be 30, got {period.get('maximum')!r}")

missing = []
for field, values in expected_sets.items():
    for value in sorted(values):
        if value not in mapping:
            missing.append(f"{field}: {value}")

for required_text in [
    "period",
    "max_pages",
    "match_scope",
    "exclude_patterns",
    "В конце я создам несколько файлов",
]:
    if required_text not in mapping:
        missing.append(required_text)

if missing:
    raise SystemExit("Missing documented mapping values:\n" + "\n".join(missing))
PY
```

Expected: schema and scraper enum sets match exactly, `period.maximum` is 30, and every supported native value is documented in `references/profile_mapping.md`.

Then validate a temporary profile that uses the mapped values:

```bash
tmp_profile="$(mktemp)"
python3 - "$tmp_profile" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
profile = {
    "title": "Mapping validation profile",
    "hh": {
        "area": "113",
        "max_pages": 1,
        "search_delay_min": 0,
        "search_delay_max": 0,
        "vacancy_delay_min": 0,
        "vacancy_delay_max": 0,
        "filters": {
            "search_field": ["name", "company_name", "description"],
            "experience": ["noExperience", "between1And3", "between3And6", "moreThan6"],
            "work_format": ["ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK"],
            "employment": ["full", "part", "project", "volunteer", "probation"],
            "industry": ["7", "7.540"],
            "salary": 100000,
            "only_with_salary": True,
            "order_by": "salary_desc",
            "period": 30
        }
    },
    "match_scope": {
        "title": True,
        "company": True,
        "description": True,
        "skills": True
    },
    "search_terms": {
        "Mapping validation": ["Mapping validation"]
    },
    "term_patterns": {
        "Mapping validation": ["Mapping\\s+validation"]
    },
    "exclude_patterns": {},
    "notes": "Temporary validation profile for documented mappings."
}
path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
PY
python3 scripts/hh_vacancy_scraper.py --profile "$tmp_profile" --validate-profile
rc=$?
rm "$tmp_profile"
exit "$rc"
```

Expected: scraper prints `profile ok: Mapping validation profile`.

- [ ] **Step 3: Commit profile mapping**

```bash
git add references/profile_mapping.md
git commit -m "docs: add hh profile mapping reference" -m "Document profile defaults, supported native filter mappings, match scopes, search topics, accepted terms, exclusions, and notes."
```

### Task 6: Create Runbook Reference

**Files:**
- Create: `references/runbook.md`

- [ ] **Step 1: Create `references/runbook.md`**

Add this content:

````markdown
# Runbook

Use this reference only after the user explicitly confirms the full search plan.

## Python Runtime

Use the skill-local Python environment when present:

- macOS/Linux: `<skill-dir>/.venv/bin/python`
- Windows: `<skill-dir>/.venv/Scripts/python.exe`
- fallback: `python3` only when the skill-local environment is absent

## Work Directory

Create a short lowercase `research-slug` from the confirmed research title.

Use this output directory:

```text
outputs/hh-vacancy-research/<research-slug>/
```

Keep runtime artifacts outside the skill package:

- profile drafts;
- cache directories;
- checkpoint JSONL;
- source JSON;
- exported JSON, Markdown, CSV, XLSX.

## Validate Profile

```bash
<python> <skill-dir>/scripts/hh_vacancy_scraper.py \
  --profile <work-dir>/<research-slug>.profile.json \
  --validate-profile
```

Expected success includes:

```text
profile ok:
enabled fields:
search groups:
```

Do not collect vacancies from an unvalidated profile.

## Preflight

```bash
<python> <skill-dir>/scripts/hh_vacancy_scraper.py \
  --profile <work-dir>/<research-slug>.profile.json \
  --cache-dir <work-dir>/cache \
  --output-json <work-dir>/<research-slug>.source.json \
  --checkpoint-jsonl <work-dir>/<research-slug>.checkpoint.jsonl \
  --limit-vacancies 2
```

If preflight finds relevant parsed vacancies and no hh.ru blocking, continue to the full run without another user confirmation.

Stop and return to the relevant wizard step if preflight shows:

- noise;
- captcha;
- parser failure;
- access denied;
- poor terms.

## Full Collection

Repeat the preflight command without `--limit-vacancies`.

Use the same confirmed profile, cache directory, output JSON, and checkpoint JSONL.

If a search key produces repeated noisy pages, stop, tighten the profile, and explain the change.

Checkpoint resume applies only when the profile is unchanged. After changing search terms, accepted terms, exclusions, native filters, or match fields, use a new checkpoint file or rely on checkpoint fingerprinting to ignore old rows.

Resume an interrupted unchanged run by repeating the same full collection command with the same cache directory and checkpoint JSONL.

## Export

```bash
<python> <skill-dir>/scripts/export_hh_vacancies.py \
  --source-json <work-dir>/<research-slug>.source.json \
  --output-dir <work-dir> \
  --output-prefix <research-slug>.vacancies
```

XLSX is required. If `openpyxl` is missing, run:

```bash
npx hh-vacancy-research-skill install --force
```

If setup still fails, report the setup blocker.
````

- [ ] **Step 2: Verify runbook commands**

Run:

```bash
rg -n -- '--validate-profile' references/runbook.md
rg -n -- '--limit-vacancies 2' references/runbook.md
rg -n -- '--checkpoint-jsonl' references/runbook.md
rg -n 'export_hh_vacancies\.py|openpyxl|skill-local|\.source\.json|\.vacancies' references/runbook.md
```

Expected: validate, preflight, export, checkpoint, runtime, and setup blocker guidance are present.

- [ ] **Step 3: Commit runbook**

```bash
git add references/runbook.md
git commit -m "docs: add hh collection runbook reference" -m "Document profile validation, preflight, full collection, checkpoint resume, export, Python runtime, and setup blocker handling."
```

### Task 7: Create Final Response Reference

**Files:**
- Create: `references/final_response.md`

- [ ] **Step 1: Create `references/final_response.md`**

Add this content:

````markdown
# Final Response

Use this reference before reporting completed collection results.

Write the final response in Russian by default. Use another language only if the user explicitly requested it.

Do not finish with only file links or only a numeric summary.

## Sections

Use these headings in this order:

1. `Итог`
2. `Файлы`
3. `Колонки`
4. `Группы`
5. `Правила матчинга`
6. `Ограничения`

## Итог

State what was searched and the final counts in one compact Russian paragraph:

- сколько вакансий проверено;
- сколько вакансий оставлено;
- сколько вакансий пропущено;
- какие темы чаще всего совпадали.

## Файлы

Provide every produced artifact as a clickable Markdown link with an absolute local path.

Required order and labels:

- `Профиль`
- `Исходный JSON`
- `Экспорт JSON`
- `Markdown`
- `CSV`
- `XLSX`
- `Файл продолжения`

Explain files by purpose in Russian:

- Профиль поиска: сохранённые настройки, чтобы повторить или поправить этот же поиск.
- Исходные результаты: полные собранные данные до удобных выгрузок.
- Экспорт JSON: найденные вакансии в структурированном виде для других программ или повторной обработки.
- XLSX: основная таблица для Excel или Google Sheets.
- CSV: упрощённая таблица для импорта в другие инструменты.
- Markdown: текстовая версия для быстрого просмотра.
- Файл продолжения: технический файл, чтобы возобновить прерванный сбор.

## Колонки

Кратко объясните колонки на русском:

- `Название вакансии`: название вакансии на hh.ru.
- `Компания`: работодатель или компания из полной карточки вакансии.
- `Ссылка`: ссылка на вакансию hh.ru.
- `Поисковые группы`: подтверждённые темы поиска, которые совпали с этой вакансией.
- `Поля совпадения`: где найдено совпадение. Возможные значения в выгрузке: `title`, `company`, `description`, `skills`.
- `Навыки`: ключевые навыки из карточки вакансии.
- `Описание`: полное описание вакансии. В XLSX слишком длинные описания продолжаются на листе `Descriptions`.

## Группы

Перечислите каждую подтверждённую тему поиска и объясните её простыми словами по-русски.

Если использовалась одна тема, скажите по-русски, что результаты не делились на дополнительные группы.

Если использовалось несколько тем, объясните по-русски, что означает каждая тема и почему она была отдельной.

## Правила матчинга

Опишите включённые поля совпадения и исключения одним коротким русским абзацем.

Если исключения не использовались, скажите это по-русски.

## Ограничения

Указывайте только реальные ограничения, замеченные во время запуска:

- captcha;
- заблокированные страницы;
- ошибки парсинга;
- намеренно ограниченная выборка;
- шумные поисковые темы;
- ограничения, которые подтвердил пользователь.

Не добавляйте общие ограничения, которых не было во время запуска.
````

- [ ] **Step 2: Verify final response contract**

Run these exact checks:

```bash
rg -n '^## Итог$' references/final_response.md
rg -n '^## Файлы$' references/final_response.md
rg -n '^## Колонки$' references/final_response.md
rg -n '^## Группы$' references/final_response.md
rg -n '^## Правила матчинга$' references/final_response.md
rg -n '^## Ограничения$' references/final_response.md
rg -n '`Профиль`' references/final_response.md
rg -n '`Исходный JSON`' references/final_response.md
rg -n '`Экспорт JSON`' references/final_response.md
rg -n '`Markdown`' references/final_response.md
rg -n '`CSV`' references/final_response.md
rg -n '`XLSX`' references/final_response.md
rg -n '`Файл продолжения`' references/final_response.md
rg -n 'Descriptions' references/final_response.md
```

Expected: all required headings, file labels, and column guidance are present.

- [ ] **Step 3: Commit final response reference**

```bash
git add references/final_response.md
git commit -m "docs: add hh final response reference" -m "Document the Russian final report contract, file explanations, exported columns, topics, match rules, and limitations."
```

### Task 8: Cross-Reference And Coverage Verification

**Files:**
- Review and correct only when verification fails: `SKILL.md`
- Review and correct only when verification fails: `references/*.md`

- [ ] **Step 1: Confirm all planned files exist**

Run:

```bash
test -f SKILL.md
test -f references/discovery_wizard.md
test -f references/filter_wizard.md
test -f references/profile_mapping.md
test -f references/runbook.md
test -f references/final_response.md
```

Expected: all commands exit with status 0.

- [ ] **Step 2: Confirm old inline sections moved out of `SKILL.md`**

Run:

```bash
! rg -n "Native HH Filter Values|Final Response Contract|Script Operating Procedure|Profile Contract|User-facing choice|Profile value|Validate a profile:|Preflight:|Export:|\\| Search everywhere \\||\\| No experience \\||\\| Remote \\||Use these Russian headings|Required file order" SKILL.md
```

Expected: no matches.

- [ ] **Step 3: Confirm important behavior exists in references**

Review the references directly:

- `references/discovery_wizard.md` includes the web-search offer, default single-topic rule, optional multiple topics, per-topic term selection, and the gate before hh.ru filters.
- `references/filter_wizard.md` includes unsupported filters, all supported filter blocks, a Russian explanation/default/options for each block, dictionary lookup rules for geography and industry, and progress updates with current topic, selected filters, unset filters, and next step.
- `references/profile_mapping.md` includes pre-profile confirmation summary, human file explanations, defaults, mapping values, search topics, `term_patterns`, `exclude_patterns`, and `notes`.
- `references/runbook.md` includes profile validation, preflight, full run, checkpoint/resume, noise handling, export, `openpyxl`, and skill-local Python.
- `references/final_response.md` includes all required sections, all file labels, column explanations, groups, match rules, and limitations.

Expected: every item above is present in the referenced file. If any item is missing, fix that reference before continuing.

- [ ] **Step 4: Run existing automated tests**

Run:

```bash
python3 -m pytest tests/test_export_hh_vacancies.py
```

Expected: tests pass. If `pytest` is unavailable, report that automated tests could not run in this environment and run the documentation checks instead.

- [ ] **Step 5: Run documentation checks**

Run:

```bash
test "$(wc -w < SKILL.md)" -lt 350
wc -w references/*.md
! rg -n 'T[B]D|T[O]DO|F[I]XME|f[i]ll in|f[i]ll-in|implement l[a]ter|S[i]milar to Task|to be dec[i]ded|to be determ[i]ned|place[Hh]older|<T[O]DO>' SKILL.md references/*.md
```

Expected: `SKILL.md` is under 350 words, reference word counts are printed for review without failing on length alone, and the placeholder scan returns no matches.

- [ ] **Step 6: Check for accidental English user-facing text**

Run:

```bash
! rg -n 'saved settings|full collected data|main table|simplified table|readable text|continuation file|vacancy title from|employer/company parsed|confirmed search topic|fields where the match|key skills parsed|full vacancy description|no experience|full-time|part-time|project work|shift work|salary high-to-low|salary low-to-high' references/*.md
```

Expected: the command exits with status 0. English may still appear for internal profile values, file formats, URLs, commands, and literal tool/product names.

Then manually inspect every Russian user-facing copy block and every filter option list:

```bash
sed -n '1,220p' references/discovery_wizard.md
sed -n '1,260p' references/filter_wizard.md
sed -n '1,220p' references/profile_mapping.md
sed -n '1,220p' references/final_response.md
```

Expected: all questions, labels, options, summaries, file explanations, column explanations, and help text intended for the user are Russian. English appears only for allowed literals: internal profile values, file formats, URLs, commands, and literal tool/product names.

- [ ] **Step 7: Run pressure scenario review**

Use the scenarios from Task 1. Read the rewritten `SKILL.md` and references as an agent would. Confirm:

- broad topic scenario offers web research before filters;
- web search waits for confirmation;
- topics are explained in Russian;
- one topic is default;
- multiple topics are optional;
- per-topic terms are required when multiple topics are used;
- unsupported filters are not represented as native hh filters;
- geography and industry require dictionary lookup;
- collection does not start before explicit confirmation.

- [ ] **Step 8: Commit verification fixes after a failed verification step**

If any verification step required corrections, commit them:

```bash
git add SKILL.md references
git commit -m "docs: verify hh vacancy wizard references" -m "Apply corrections found during cross-reference, placeholder, schema, and pressure-scenario verification."
```

If no corrections were needed after the previous task commits, do not create an empty commit.

## Implementation Completion Criteria

The implementation is complete only when:

- `SKILL.md` is a short controlling workflow.
- All five reference files exist and are linked from `SKILL.md`.
- The discovery wizard offers web research and waits for confirmation.
- Search topics are explained in Russian, default to one topic, and support optional multiple topics with per-topic terms.
- The filter wizard uses only supported hh.ru values and dictionary lookups for geography and industry.
- User-facing artifact explanations are human-purpose based.
- The runbook preserves skill-local Python, profile validation, preflight, checkpoint/resume, noise control, and export behavior.
- Final response guidance preserves the Russian sections and all produced file links.
- Existing tests or documented fallback checks have been run.
- Pressure scenarios have been reviewed and results are reported.
