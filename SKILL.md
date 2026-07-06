---
name: hh-vacancy-research
description: Use when a user wants to research hh.ru vacancies.
---

# hh-vacancy-research

Use this skill to research hh.ru vacancies by role, company, industry, technology, tool, work practice, requirement, keyword, or key skill.

This is a guided workflow. Do not collect vacancies until the user has confirmed the completed search plan.

## Required References

Read the referenced file before each stage:

- `references/discovery_wizard.md` before asking about intent, web research, search topics, or search terms.
- `references/filter_wizard.md` before asking about hh.ru filters.
- `references/profile_mapping.md` before full summary, profile creation, or validation.
- `references/runbook.md` before running scraper or exporter commands.
- `references/final_response.md` before reporting results.

## Mandatory Flow

1. Discovery wizard.
   Clarify intent. Offer web research, explain why it helps, and run it only after explicit confirmation.

2. Search topic and term review.
   Default to one topic. Extra topics are optional. Confirm topic names and terms before filters.

3. HH filter wizard.
   Walk through supported filters with real hh.ru values, explanations, defaults, and progress updates.

4. Full summary and confirmation.
   Show the goal, topics, terms, exclusions, filters, match fields, work directory, and human file explanations. Wait for explicit confirmation.

5. Profile creation and validation.
   Create a fresh profile from `templates/search_profile.template.json` outside the skill package. Validate before collection.

6. Preflight and collection.
   Run the bundled scraper only. Start with `--limit-vacancies 2`; continue only when preflight is relevant and unblocked.

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
