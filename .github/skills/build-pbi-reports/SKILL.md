---
name: build-pbi-reports
description: "Build Power BI .pbit template files locally from PbixProj source folders using pbi-tools in Docker. Compiles both the full (3-page) and light (1-page) dashboard variants. Use this skill when the user wants to build, compile, or regenerate Power BI templates, or after modifying TMDL model files, DAX measures, report visuals, or the generate_report.py script."
argument-hint: "[full|light|both] [--skip-generate]"
---

# Build Power BI Reports Locally

Compile Power BI `.pbit` template files from PbixProj source folders in this
repository. The build uses the **pbi-tools** Docker container running under
Rosetta (amd64 on Apple Silicon).

## Repository layout

```
powerbi/
├── generate_report.py          # generates Report section JSON from Python
├── pbixproj-full/              # 3-page dashboard (Overview, Copilot Impact, PR Details)
│   ├── .pbixproj.json
│   ├── Version.txt
│   ├── ReportMetadata.json
│   ├── ReportSettings.json
│   ├── Report/                 # report.json, config.json, sections/
│   ├── Model/                  # TMDL files (database, model, tables, expressions)
│   └── StaticResources/        # theme JSON
├── pbixproj-light/             # 1-page dashboard (key metrics + comparison charts)
│   └── (same structure, different Report/sections)
└── blank_template.pbit         # original blank template from PBI Desktop
```

## Prerequisites

- **Docker Desktop** must be running.
- The pbi-tools container image must be pulled:
  ```
  docker pull --platform linux/amd64 ghcr.io/pbi-tools/pbi-tools-core:latest
  ```
  If pulling fails with 403 Forbidden, authenticate first:
  ```
  echo "$GITHUB_TOKEN" | docker login ghcr.io -u <username> --password-stdin
  ```

## Build procedure

Run all commands from the repository root.

### Step 1 — Generate report pages

Run this whenever visual definitions or page layout in `generate_report.py`
have changed. Skip if only TMDL model files were modified.

```bash
python3 powerbi/generate_report.py
```

### Step 2 — Compile the full dashboard

```bash
docker run --rm --platform linux/amd64 \
  -v "$PWD":/workspace -w /workspace \
  ghcr.io/pbi-tools/pbi-tools-core:latest \
  /app/pbi-tools/pbi-tools.core compile \
    -folder powerbi/pbixproj-full \
    -format PBIT \
    -outPath /workspace/powerbi/dashboard-full.pbit \
    -overwrite
```

### Step 3 — Compile the light dashboard

```bash
docker run --rm --platform linux/amd64 \
  -v "$PWD":/workspace -w /workspace \
  ghcr.io/pbi-tools/pbi-tools-core:latest \
  /app/pbi-tools/pbi-tools.core compile \
    -folder powerbi/pbixproj-light \
    -format PBIT \
    -outPath /workspace/powerbi/dashboard-light.pbit \
    -overwrite
```

### Step 4 — Verify outputs

```bash
ls -lh powerbi/dashboard-full.pbit powerbi/dashboard-light.pbit
file powerbi/dashboard-*.pbit
```

Both files must report `Zip archive data`. Expected sizes: full ~8–10 KB,
light ~7–8 KB.

## How pbi-tools compile works

- Reads `.pbixproj.json` for settings (TMDL serialization mode).
- Deserializes `Model/` via the TMDL parser (`database.tmdl`, `model.tmdl`,
  `tables/*.tmdl`, `expressions.tmdl`, `cultures/*.tmdl`).
- Assembles Report Layout from `Report/report.json`, `Report/config.json`,
  and `Report/sections/*/section.json` (with inlined `visualContainers`).
- Writes each part into the OPC package as UTF-16 LE JSON (except
  `Connections` which is UTF-8).
- Outputs a valid `.pbit` ZIP file.

## Data model reference

The model defines a **PRData** table with:
- **26 columns** sourced from CSV (`pr_number`, `repository`, `title`, …,
  `first_response_hours`).
- **14 DAX measures** (`Total PRs`, `Merged PRs`, `CCR Adoption %`,
  `Avg Days Open (With CCR)`, `Days Saved per PR`, etc.).
- **1 M partition** reading from a `CsvFilePath` parameter via
  `Csv.Document(File.Contents(CsvFilePath), …)`.
- **1 expression** (`CsvFilePath`) — a Power Query text parameter the user
  sets when opening the template in Power BI Desktop.

## TMDL syntax rules

These were discovered during development and are critical for clean compiles:

- `Version.txt` must contain exactly `1.28` with **no trailing newline**.
  pbi-tools writes this verbatim (UTF-16 LE) into the OPC package, and PBI
  Desktop's version parser rejects `"1.28\n"`. Use `printf '1.28'` (not
  `echo`) when recreating the file.
- No blank or comment-only lines between TMDL object blocks.
- `database.tmdl` must start with `database <name>` (never `createOrReplace`).
- `model.tmdl` must start with `model Model`.
- Multi-line DAX and M expressions use triple-backtick blocks.
- `queryGroup` references must point to a defined group or be omitted entirely.
- Do not use `linguisticMetadata` with JSON content in culture files — the
  TMDL parser expects XML for that property.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Unknown action: 'extract'` | `extract` is unavailable in pbi-tools Core on Linux; only `compile` works. |
| `Unknown action: '--help'` | Container has no entrypoint. Always invoke `/app/pbi-tools/pbi-tools.core <action>`. |
| `TmdlFormatException: InvalidLineType: Empty` | Remove blank/comment lines between TMDL object blocks. |
| `Cannot resolve … QueryGroup` | Remove `queryGroup:` or define the group in the model. |
| `LinguisticMetadata … does not comply with Xml` | Remove `linguisticMetadata` from culture TMDL or use XML. |
| `no matching manifest for linux/arm64` | Add `--platform linux/amd64` to `docker run` / `docker pull`. |
| 403 on `docker pull` | Run `docker login ghcr.io` with a PAT that has `read:packages` scope. |
| `is not a valid .pbix file version number` | `Version.txt` has a trailing newline. Rewrite with `printf '1.28' > Version.txt`. |
| No visuals render / `visualContainers` undefined | Section folders under `Report/sections/` are missing or empty. Run `generate_report.py`. |

## Execution checklist

When the user invokes this skill:

1. Verify Docker Desktop is running (`docker info` should succeed).
2. Run `python3 powerbi/generate_report.py` unless the user says to skip.
3. Compile whichever variants were requested (default: both).
4. Show each compile's output to confirm `PBIT file written to:` appears.
5. Print file sizes and `file` type to confirm valid ZIP archives.
6. Remind the user that `.pbit` files are gitignored — they are build
   artifacts produced by CI or this local process.
