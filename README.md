# hh-vacancy-research

A Codex skill for guided hh.ru vacancy research.

The skill helps an agent turn a user's research intent into a confirmed search profile, collect full hh.ru vacancy cards, validate matches across vacancy title, employer/company name, description, and key skills, and export results to JSON, Markdown, CSV, and XLSX.

The workflow is intentionally gated: the agent must ask what to search for, where to match it, which geography and exclusions apply, and must show the draft profile before running any network collection.

## Quick Install

Recommended installer:

```bash
npx hh-vacancy-research-skill install
```

Standard Agent Skills installer:

```bash
npx skills add GreatPika/hh-vacancy-research -a codex
```

The standard `skills` installer installs the skill files. The dedicated `hh-vacancy-research-skill` installer also creates a skill-local Python virtual environment and installs the Python dependency required for XLSX export.

## Requirements

- Node.js 18 or newer for the `npx` installer.
- Python 3 for the scraper and exporter.
- Internet access for hh.ru collection.
- `openpyxl` for XLSX export; the dedicated installer installs it automatically into `~/.codex/skills/hh-vacancy-research/.venv`.

## Installer Commands

Install the skill and Python dependencies into a skill-local `.venv`:

```bash
npx hh-vacancy-research-skill install
```

Install only the skill files, without creating `.venv`:

```bash
npx hh-vacancy-research-skill install --skip-python-deps
```

Use a specific Python executable to create the skill-local `.venv`:

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

The installer writes to `$CODEX_HOME/skills/hh-vacancy-research` when `CODEX_HOME` is set, otherwise to `~/.codex/skills/hh-vacancy-research`.

Python dependencies are not installed into system Python. The installer creates `.venv` inside the installed skill directory, which avoids Homebrew and OS-managed Python restrictions.

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
5. Export to JSON, Markdown, CSV, and XLSX.
6. Final report with checked, kept, skipped, and top matched terms.

## Supported Filters

The skill asks users about filters that can be represented by the bundled scraper. The agent translates user-facing answers into hh.ru parameters and profile settings.

| User-facing choice | What it controls |
| --- | --- |
| Region | hh.ru area: Russia by default, all hh.ru regions, or a specific country, region, or city id from `https://api.hh.ru/areas`. |
| Search intent | The roles, companies, industries, technologies, tools, requirements, skills, or topics to search for. |
| hh.ru search field | Where hh.ru searches the query text: everywhere, vacancy titles, company names, or descriptions. |
| Experience | hh.ru experience levels: no experience, 1-3 years, 3-6 years, 6+ years. |
| Schedule | hh.ru schedule filters: remote, full day, shift, flexible, fly-in/fly-out. |
| Employment | hh.ru employment filters: full-time, part-time, project, volunteer, probation/internship. |
| Salary | Minimum salary and whether to include only vacancies with visible salary. |
| Freshness | Vacancies published in the last N days, up to hh.ru's 30-day limit. |
| Sort order | Relevance, newest first, salary high-to-low, or salary low-to-high. |
| Match fields | Which full-card fields count as a valid match: title, company name, full description, key skills. |
| Accepted meanings | Exact words, spellings, Russian/English variants, product names, and regex patterns that should count. |
| Exclusions | False-positive contexts that suppress a match, such as SQL cursor when searching for Cursor. |

The skill does not apply native hh.ru filters for office/hybrid specifically, employer type, metro, industry, education, language, or professional role. The agent can still encode user-provided constraints as search terms, match patterns, or exclusions when that is practical.

## Operational Notes

hh.ru can rate-limit, block, or show captcha pages. Use conservative delays for full collection runs, keep checkpoints, and resume interrupted runs instead of starting over.

The examples in this repository are educational only. They are not maintained production profiles and should not be reused without fresh research and user confirmation.
