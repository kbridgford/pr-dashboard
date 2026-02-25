# Copilot Instructions — PR Dashboard

## Project overview

This project collects GitHub pull request data and visualises it in Power BI
to measure the impact of **Copilot Code Review (CCR)** on PR cycle time.

Pipeline: **GitHub GraphQL API → Python → CSV → Power BI `.pbit` templates**

## Repository layout

| Path | Purpose |
|------|---------|
| `src/fetch_pr_data.py` | Data extraction via GitHub GraphQL search API. Handles pagination, monthly chunking for >1 000 results, incremental merge-and-replace. |
| `src/upload_data.py` | Upload/download CSV to Azure Blob Storage or AWS S3. |
| `powerbi/generate_report.py` | Generates PbixProj `section.json` files (report visuals) for both dashboard variants. |
| `powerbi/pbixproj-full/` | PbixProj source for the 3-page dashboard (Overview, Copilot Impact, PR Details). |
| `powerbi/pbixproj-light/` | PbixProj source for the 1-page dashboard. |
| `powerbi/pbixproj-*/Model/` | TMDL data model — 26 columns, 14 DAX measures, 1 M partition reading from a `CsvFilePath` parameter. |
| `.github/workflows/build-pbit.yml` | CI: compiles `.pbit` templates from PbixProj source using pbi-tools Docker. |
| `.github/workflows/release.yml` | CD: attaches `.pbit` files to GitHub Releases. |
| `.github/workflows/refresh-data.yml` | Weekly merge-and-replace data refresh. |
| `.github/skills/build-pbi-reports/SKILL.md` | Copilot agent skill for local `.pbit` builds. |
| `docs/METRICS_INSIGHTS.md` | Metric definitions, interpretation, and analysis guide. |

## Technology stack

- **Python 3.12** — `requests`, `python-dotenv`
- **pbi-tools Core 1.2.0** — Docker image `ghcr.io/pbi-tools/pbi-tools-core:latest` (amd64 only; use `--platform linux/amd64` on ARM Macs)
- **TMDL** — Tabular Model Definition Language for the Power BI data model
- **PbixProj** — pbi-tools' source format for Power BI reports
- **Power BI Desktop** — December 2025+ for opening compiled `.pbit` templates

## Data model (PRData table)

26 columns sourced from CSV: `pr_number`, `repository`, `title`, `author`,
`created_at`, `merged_at`, `closed_at`, `state`, `is_draft`, `days_open`,
`has_copilot_review`, `month_year`, `reviewer_count`, `copilot_review_count`,
`reviewers`, `merged_by`, `additions`, `deletions`, `changed_files`,
`commit_count`, `comment_count`, `review_decision`, `labels`, `base_branch`,
`head_branch`, `first_response_hours`.

14 DAX measures: `Total PRs`, `Merged PRs`, `PRs with Copilot Review`,
`PRs without Copilot Review`, `CCR Adoption %`, `Avg Days Open`,
`Avg Days Open (With CCR)`, `Avg Days Open (Without CCR)`, `Days Saved per PR`,
`Avg First Response Hours (With CCR)`,
`Avg First Response Hours (Without CCR)`, `Hours Saved per PR`,
`Total Repositories`, `Avg Reviewers per PR`.

## Key conventions

### Python
- Virtual environment at `.venv` (gitignored).
- GitHub token via `GITHUB_TOKEN` env var or `.env` file.
- CLI entry point: `python src/fetch_pr_data.py --owner <org>`.
- CSV output: `data/pull_requests.csv` (gitignored).

### Power BI visual generation (`generate_report.py`)
- Chart visuals must use `"Y"` role for the value/measure axis (not `"Values"`). Cards and tables use `"Values"`.
- All queryRefs must be table-qualified: `"PRData.PropertyName"` (not shorthand like `"m_Prop"` or `"c_Prop"`).
- Prototype query Select items need `NativeReferenceName` when the alias differs from the property name.
- Charts must include `hasDefaultSort: true`.
- Category projections should have `"active": true`.
- Helper functions: `_select_measure()`, `_select_column()`, `_mref()`, `_cref()`, `_proto_query()`, `_make_visual_config()`.

### TMDL model files
- `Version.txt` must contain exactly `1.28` with **no trailing newline** — use `printf '1.28'`, never `echo`.
- No blank or comment-only lines between TMDL object blocks.
- `database.tmdl` starts with `database <name>` (not `createOrReplace`).
- Do not use `linguisticMetadata` with JSON content in culture files.

### Building `.pbit` templates
- Always run `python3 powerbi/generate_report.py` before compiling (unless only TMDL changed).
- Compile with: `docker run --rm --platform linux/amd64 -v "$PWD":/workspace -w /workspace ghcr.io/pbi-tools/pbi-tools-core:latest /app/pbi-tools/pbi-tools.core compile -folder powerbi/pbixproj-full -format PBIT -outPath /workspace/powerbi/dashboard-full.pbit -overwrite`
- Output `.pbit` files are gitignored — they are build artifacts.
- Valid output is a ZIP archive, typically 7–10 KB.

## Available agents

### Build PBI Reports (`.github/agents/build-pbi-reports.agent.md`)

Delegate to the **Build PBI Reports** agent whenever the user wants to:
- Build, compile, or regenerate Power BI `.pbit` templates
- Test changes to `generate_report.py`, TMDL model files, or PbixProj source
- Verify that `.pbit` output is valid after editing DAX measures, columns, or visuals

Do **not** invoke the agent for questions that are only about reading, understanding, or editing source files — it is specifically for running the Docker-based compile pipeline.

## Common pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `'1.28\n' is not a valid .pbix file version number` | Trailing newline in `Version.txt` | `printf '1.28' > Version.txt` |
| `visualContainers` undefined in PBI Desktop | Empty `Report/sections/` folder | Run `generate_report.py` |
| Charts render blank (cards work) | Wrong role name or queryRef format | Use `"Y"` role, `"PRData.Property"` queryRef, add `NativeReferenceName` and `hasDefaultSort` |
| `no matching manifest for linux/arm64` | Missing platform flag | Add `--platform linux/amd64` |
| 403 on `docker pull` | GHCR auth required | `docker login ghcr.io` with PAT |

## Testing changes

After modifying `generate_report.py` or TMDL files:
1. `python3 powerbi/generate_report.py`
2. Compile both variants (full + light) with pbi-tools Docker
3. Verify output: `file powerbi/dashboard-*.pbit` should report `Zip archive data`
4. Open in Power BI Desktop, point to CSV, confirm visuals render with data
