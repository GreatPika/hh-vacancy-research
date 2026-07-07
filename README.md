# hh-vacancy-research

A Codex skill for guided hh.ru vacancy research.

The skill helps an agent turn a user's research intent into a confirmed search profile, collect full hh.ru vacancy cards, confirm matches in the same text area selected for hh.ru search, and export results to Markdown, CSV, and XLSX.

The workflow is intentionally gated: the agent must ask what to search for, where hh.ru should search the query text, which geography and exclusions apply, and must show the draft profile before running any network collection.

## Quick Install

Recommended installer:

```bash
npx hh-vacancy-research-skill install
```

Standard Agent Skills installer:

```bash
npx skills add GreatPika/hh-vacancy-research -a codex
```

The standard `skills` installer installs the skill files. The dedicated `hh-vacancy-research-skill` installer also creates an external Python virtual environment and installs the Python dependency required for XLSX export.

## Requirements

- Node.js 18 or newer for the `npx` installer.
- Python 3 for the scraper and exporter.
- Internet access for hh.ru collection.
- `openpyxl` for XLSX export; the dedicated installer installs it automatically into a user cache directory.

## Installer Commands

Install the skill and Python dependencies:

```bash
npx hh-vacancy-research-skill install
```

Install only the skill files, without creating the Python environment:

```bash
npx hh-vacancy-research-skill install --skip-python-deps
```

Use a specific Python executable to create the external Python environment:

```bash
npx hh-vacancy-research-skill install --python python3.12
```

Check the installed skill:

```bash
npx hh-vacancy-research-skill doctor
```

Uninstall a marker-managed install:

```bash
npx hh-vacancy-research-skill uninstall
```

The installer writes skill files to `$CODEX_HOME/skills/hh-vacancy-research` when `CODEX_HOME` is set, otherwise to `~/.codex/skills/hh-vacancy-research`.

Python dependencies are not installed into system Python and are not stored inside the installed skill directory. The installer creates a virtual environment in the user cache directory, such as `~/Library/Caches/hh-vacancy-research-skill/venv` on macOS. Set `HH_VACANCY_RESEARCH_SKILL_CACHE` to override that location.

## Usage In Codex

After installation, restart Codex so it can discover the skill. Then ask for a hh.ru vacancy research task, for example:

```text
Use the hh-vacancy-research skill to find hh.ru vacancies that mention AI coding agents in requirements, descriptions, skills, job titles, or company names.
```

The agent should guide you through:

1. Discovery questions.
2. Search term research.
3. Profile confirmation.
4. hh.ru collection.
5. Export to Markdown, CSV, and XLSX.
6. Final response with links to the reusable profile, Markdown, CSV, and XLSX files.

By default, generated files are written under the current Codex working directory:

```text
outputs/hh-vacancy-research/<research-slug>/
```

Runtime files must not be written inside the installed skill package.

## Supported Filters

The skill asks users about filters that can be represented by the bundled scraper. The agent translates user-facing answers into hh.ru parameters and profile settings.

| User-facing choice | What it controls |
| --- | --- |
| Region | hh.ru area: Russia by default, all hh.ru regions, or a specific country, region, or city id from `https://api.hh.ru/areas`. |
| Search intent | The roles, companies, industries, technologies, tools, requirements, skills, or topics to search for. |
| hh.ru search field | Where hh.ru searches the query text: everywhere, vacancy titles, company names, or descriptions. |
| Experience | hh.ru experience levels: no experience, 1-3 years, 3-6 years, 6+ years. |
| Work format | hh.ru work format filters: on site, remote, hybrid, or field work. |
| Employment | hh.ru employment filters: full-time, part-time, project, volunteer, probation/internship. |
| Company industry | Employer business industry from `https://api.hh.ru/industries`, such as IT, media, banking, logistics, or a narrower nested industry. |
| Salary | Minimum salary and whether to include only vacancies with visible salary. |
| Freshness | Vacancies published in the last N days, up to hh.ru's 30-day limit. |
| Sort order | Relevance, newest first, salary high-to-low, or salary low-to-high. |
| Accepted meanings | Exact words, spellings, Russian/English variants, product names, and regex patterns that should count. |
| Exclusions | False-positive contexts that suppress a match, such as SQL cursor when searching for Cursor. |

The local match scope is an internal profile setting derived from the selected hh.ru search field. The normal wizard does not ask users to configure it separately.

The skill does not apply native hh.ru filters for employer type, metro, education, language, or professional role. The agent can still encode user-provided constraints as search terms, accepted meanings, or exclusions when that is practical.

## Operational Notes

hh.ru can rate-limit, block, or show captcha pages. Use conservative delays for full collection runs, keep checkpoints, and resume interrupted runs instead of starting over.

The examples in this repository are educational only. They are not maintained production profiles and should not be reused without fresh research and user confirmation.
