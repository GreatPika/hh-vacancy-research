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
