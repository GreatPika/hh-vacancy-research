# hh-vacancy-research Wizard Skill Redesign

## Outcome

Redesign the `hh-vacancy-research` skill so the agent guides the user through a clear research wizard before any hh.ru collection starts. The wizard must first clarify what the user wants to find, help select search terms, optionally use web research with user approval, explain search topics in plain Russian, and only then walk through supported hh.ru filters.

The redesigned skill should use a short controlling `SKILL.md` plus focused reference files. `SKILL.md` should enforce the process order and gates; reference files should hold detailed wizard copy, filter mappings, run commands, and final response requirements.

## Problems To Solve

The current skill contains the right scraper/export mechanics, but it does not strongly enforce a user-facing wizard. It mixes process, filter tables, profile contract, final response format, and command runbook in one long file. That makes it harder for an agent to consistently guide the user through intent discovery, search term selection, optional web research, search topics, and filter confirmation.

The search topics concept is especially underexplained. Users should not have to understand internal terms such as queries, regexes, match scopes, or JSON fields. They need a simple explanation of why topics exist, when extra topics are useful, and how the chosen terms affect the final table.

## Design Principles

- Do not collect vacancies before the wizard is complete and explicitly confirmed.
- Start with research intent, not hh.ru filters.
- Always offer web research during term selection, explain why it helps, and run it only after explicit user approval.
- Default to one search topic. Additional topics are optional and require user consent.
- If multiple topics are used, each topic must have its own user-approved search terms.
- Use only real supported hh.ru filter values. Do not invent native hh.ru filter values.
- Explain files, columns, filters, topics, and limitations in user-facing Russian.
- Keep technical mapping details out of the user-facing wizard unless the user asks.

## Architecture

Use this structure:

```text
SKILL.md
references/
  discovery_wizard.md
  filter_wizard.md
  profile_mapping.md
  runbook.md
  final_response.md
```

`SKILL.md` is the short controlling document. It defines when to use the skill, required reference files, mandatory process order, and hard gates.

`references/discovery_wizard.md` defines intent discovery, the web-search offer, term research, search topic explanation, default single-topic behavior, optional additional topics, and confirmation before filters.

`references/filter_wizard.md` defines hh.ru filter questions, real supported values, human explanations, defaults, and dictionary lookup rules for geography and industry.

`references/profile_mapping.md` defines how confirmed user choices map to the JSON profile, including internal values such as `between1And3`, `salary_desc`, and `search_field`.

`references/runbook.md` defines the exact validate, preflight, full collection, export, cache, checkpoint, and failure-handling procedure.

`references/final_response.md` defines the final Russian response format, including human explanations for produced files and exported columns.

## Wizard Flow

The skill must enforce this order:

1. Intent discovery.
2. Web-search offer.
3. Term research.
4. Search topic review.
5. hh.ru filter wizard.
6. Full summary and artifact explanation.
7. Explicit user confirmation.
8. Profile creation and validation.
9. Preflight.
10. Full collection.
11. Export.
12. Final report.

### Intent Discovery

Before any filter questions, the agent restates the user's goal in simple Russian and confirms what kind of search this is:

- a role or vacancy title;
- a technology, tool, method, requirement, or key skill mention;
- companies or industries;
- broad market research.

The agent must not assume that the user already knows the right search words. The goal of this stage is to decide what should count as a relevant vacancy.

### Web-Search Offer

The agent must always offer web research during term selection. It must explain why web research helps and wait for explicit approval before searching.

Required user-facing meaning:

- web research can find current product names, tools, companies, categories, Russian and English spellings, synonyms, and likely false positives;
- it is useful when the topic is broad, new, brand-heavy, or ambiguous;
- if the user declines, the search continues from the user's words, but the term list may be narrower or less current.

When approved, the agent may search broadly, but should include only explainable terms in the proposed topics. Good evidence includes official product sites, documentation, credible articles, rankings, and repeated independent mentions.

### Search Topics

Search topics must be explained before hh.ru filters. A search topic is a user-facing theme used to organize the search and later explain why a vacancy appeared in the results.

The default is one topic. Additional topics are optional.

Required Russian copy:

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

If the user keeps one topic, the agent should name it from the user's goal, for example `AI-инструменты`, `Cursor`, or `Senior Flutter`, not a generic label such as `Общий поиск`.

If the user chooses multiple topics, the agent proposes the topic names. The user can rename, remove, merge, split, or approve them. Each topic must have a separate set of terms.

Required Russian copy for per-topic terms:

```text
Теперь для каждой поисковой группы нужно подобрать слова.

Важно: у каждой группы будет свой набор слов.
Так мы сможем искать точнее и потом показать в таблице, какая именно тема нашлась в вакансии.

Я предложу слова для каждой группы отдельно.
Вы сможете убрать лишнее, добавить свои варианты или попросить расширить список.
```

The agent must not proceed to hh.ru filters until the user confirms the topic structure and terms.

### HH Filter Wizard

After topics and terms are confirmed, the agent walks through all supported hh.ru filters. If a value is already obvious from the user's request, the agent pre-fills it and asks for confirmation instead of asking from scratch.

Supported filter blocks:

- geography;
- hh.ru text search fields;
- experience;
- schedule;
- employment;
- company industry;
- salary;
- freshness period;
- sort order;
- full-card match fields.

Each filter must include a plain Russian explanation, a default, and an option to leave it unset when applicable. The agent should recommend leaving optional filters unset when applying them could hide relevant vacancies.

Fixed filter values must come from repository source of truth: `templates/search_profile.schema.json`, `scripts/hh_vacancy_scraper.py`, and `references/profile_mapping.md`. The agent must not invent values.

Geography and industry are dictionary-backed filters:

- for a specific city, country, or region, the agent must look up real ids in `https://api.hh.ru/areas`;
- for company industry, the agent must look up real ids in `https://api.hh.ru/industries`;
- if the user asks for something ambiguous or unavailable, the agent must show the closest real choices or explain that the native filter cannot represent the request.

The agent must distinguish text meaning from native hh.ru filters. For example, if the user asks for "AI companies" and no exact hh industry exists, the agent should not invent an industry. It can suggest leaving industry unset, adding AI terms to the search, or selecting a real nearby industry with an explicit caveat.

### Full Summary And Artifact Explanation

Before creating the profile, the agent shows a complete Russian summary:

- research goal;
- one topic or multiple topics;
- terms inside each topic;
- exclusions;
- region;
- all hh.ru filters;
- where hh.ru searches text;
- which full-card fields count as matches;
- working directory and produced files.

File explanations must be user-facing and purpose-based, not format-based.

Required Russian copy:

```text
В конце я создам несколько файлов:

- Профиль поиска — здесь сохранены выбранные вами настройки. Он нужен, чтобы потом повторить или поправить этот же поиск.
- Исходные результаты — это полный результат сбора до удобной выгрузки. Нужен для проверки и повторного экспорта.
- Таблица XLSX — основной файл для просмотра в Excel или Google Sheets.
- CSV — упрощённая таблица для импорта в другие инструменты.
- Markdown — удобная текстовая версия для быстрого просмотра.
- Checkpoint — технический файл продолжения. Он нужен, чтобы не начинать заново, если сбор прервётся.
```

The agent must wait for explicit confirmation before creating the profile or running network collection.

## Profile, Run, And Export

After confirmation, the agent creates a fresh profile from `templates/search_profile.template.json` in `outputs/hh-vacancy-research/<research-slug>/`. It must not reuse `examples/*.json` as production profiles.

The agent validates the profile with `scripts/hh_vacancy_scraper.py --validate-profile`. If validation fails, the agent fixes the confirmed mapping or returns to the relevant wizard choice. It must not bypass validation.

The agent then runs an internal preflight with `--limit-vacancies 2`. If preflight finds relevant parsed vacancies and no hh.ru blocking, the full run continues without another user confirmation. If preflight shows noise, captcha, parser failure, access denial, or poor terms, the agent stops and returns to the appropriate wizard step.

Full collection must use the confirmed profile, cache directory, checkpoint JSONL, and output JSON outside the skill package.

Export must use `scripts/export_hh_vacancies.py`. XLSX is required. If `openpyxl` is missing, the agent may run `npx hh-vacancy-research-skill install --force` to recreate the skill-local environment, or report a setup blocker.

## Final Response

The final response must be in Russian unless the user explicitly requested another language. It should explain:

- what was searched;
- checked, kept, and skipped counts;
- produced files with clickable links and human explanations;
- exported columns;
- search topics and what each means;
- match rules and exclusions;
- real limitations observed during the run.

It must not end with only file links or only a numeric summary.

## Testing And Verification

The implementation should be verified with documentation-level and behavior-level checks:

- Confirm `SKILL.md` is short and points to the new reference files.
- Confirm all referenced files exist.
- Confirm the old inline filter/final-response/runbook details are removed or delegated.
- Confirm fixed filter values match `templates/search_profile.schema.json` and `scripts/hh_vacancy_scraper.py`.
- Run profile validation tests or existing project tests if implementation changes affect scripts or templates.
- Use at least one pressure scenario to check that the agent offers web search, waits for approval, explains topics in Russian, defaults to one topic, and does not start collection before confirmation.

## Open Decisions

None. The selected approach is a short controlling `SKILL.md` plus reference files.
