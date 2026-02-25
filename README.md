# Pull Request Dashboard

Analyze pull request metrics comparing PRs with and without GitHub Copilot Code Review (CCR). Generates a CSV dataset that powers a Power BI dashboard showing impact on PR cycle time.

Uses GitHub's GraphQL search API to query all PRs across an organization in a single search, automatically splitting into monthly date chunks for orgs with >1,000 PRs.

## Architecture

```
GitHub GraphQL API  →  Python Script  →  CSV  →  Power BI Dashboard
                          ↓
                    Cloud Storage (optional)
                    Azure Blob / S3 / SharePoint
                          ↓
                    Power BI Scheduled Refresh
```

## Quick Start

Download the latest release from the [Releases page](https://github.com/kbridgford/pr-dashboard/releases), or clone the repo:

```bash
# 1. Clone and set up
git clone https://github.com/kbridgford/pr-dashboard.git
cd pr-dashboard

# 2. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# 5. Fetch PR data for your org
python src/fetch_pr_data.py --owner your-org

# 6. Open data/pull_requests.csv in Power BI Desktop
```

---

## Setup

### Prerequisites

- Python 3.11+
- GitHub Personal Access Token with `repo` scope (used by the Python scripts — not needed for Power BI)
- Power BI Desktop (for visualization — no token required)

### Install Dependencies

```bash
# Using pyenv (recommended)
pyenv local 3.12.11
pyenv exec python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# For cloud upload support (optional)
pip install azure-storage-blob  # Azure Blob Storage
pip install boto3               # AWS S3
```

### Configure GitHub Access

The GitHub token is used **only by the Python scripts** (`src/fetch_pr_data.py`
and `src/upload_data.py`) to query the GitHub API. Power BI reads from the
generated CSV and does not need a token.

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=your-repo-name   # optional — default for --repo flag
```

`GITHUB_REPO` is optional. It provides a default for the `--repo` CLI flag so
you don't have to pass it every time. Most users fetch org-wide (`--owner`
only) and don't need it.

You can also set `GITHUB_TOKEN` as an environment variable instead of using
`.env` — the scripts check both.

**Get a token:** [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → select `repo` scope.

---

## Usage

### Fetch PR Data

```bash
# All closed PRs across an organization
python src/fetch_pr_data.py --owner myorg

# Single repository
python src/fetch_pr_data.py --owner myorg --repo myrepo

# Date range filter
python src/fetch_pr_data.py --owner myorg --start-date 2025-01-01 --end-date 2025-06-30

# Custom output path
python src/fetch_pr_data.py --owner myorg --output data/custom.csv
```

> **Note:** GitHub search limits results to 1,000 per query. The script automatically
> splits into monthly date ranges when this limit is reached.

### Incremental Updates (Merge-and-Replace)

Use `--merge` to fetch recent PRs and upsert them into your existing CSV. This avoids re-fetching your entire history on every run:

```bash
# Fetch last 30 days and merge into existing data
python src/fetch_pr_data.py --owner myorg --start-date 2026-01-25 --merge

# Same, but save a timestamped snapshot before overwriting
python src/fetch_pr_data.py --owner myorg --start-date 2026-01-25 --merge --snapshot
```

**How it works:**
- Loads existing `data/pull_requests.csv`
- Fetches new PRs from GitHub (scoped by `--start-date`)
- Upserts by `(pr_number, repository)` — new data wins, so PRs that were open last week but merged this week get updated
- Writes the deduplicated result back to the same file
- `--snapshot` saves a backup at `data/snapshots/pull_requests_YYYY-MM-DD.csv` before overwriting

### Upload / Download Cloud Storage

```bash
# Upload to Azure Blob Storage
python src/upload_data.py --provider azure --file data/pull_requests.csv

# Download from Azure (before a merge run)
python src/upload_data.py --provider azure --download --file data/pull_requests.csv

# Upload to AWS S3
python src/upload_data.py --provider s3 --file data/pull_requests.csv

# Download from S3
python src/upload_data.py --provider s3 --download --file data/pull_requests.csv
```

**Full merge-and-replace cycle (manual):**
```bash
# 1. Download existing data from cloud
python src/upload_data.py --provider azure --download --file data/pull_requests.csv

# 2. Fetch recent PRs and merge
python src/fetch_pr_data.py --owner myorg --start-date 2026-01-25 --merge --snapshot

# 3. Upload merged result back to cloud
python src/upload_data.py --provider azure --file data/pull_requests.csv
```

See [Cloud Storage Setup](#cloud-storage) for configuration details.

### Use the Pre-Built Power BI Templates

Download `dashboard-full.pbit` or `dashboard-light.pbit` from the
[latest release](https://github.com/kbridgford/pr-dashboard/releases).
Open in Power BI Desktop, point it at your CSV, and the dashboard is ready.

| Template | Pages | Visuals |
|----------|-------|---------|
| **Full** | 3 (Overview, Copilot Impact, PR Details) | 6 cards, 4 charts, 1 donut, 2 tables, 3 slicers |
| **Light** | 1 (Dashboard) | 5 cards, 4 charts |

### Build Templates from Source

The `.pbit` files are compiled from PbixProj source folders using
[pbi-tools](https://pbi.tools) in Docker. See the
[build skill](.github/skills/build-pbi-reports/SKILL.md) for the full
procedure, or run:

```bash
python3 powerbi/generate_report.py

docker run --rm --platform linux/amd64 \
  -v "$PWD":/workspace -w /workspace \
  ghcr.io/pbi-tools/pbi-tools-core:latest \
  /app/pbi-tools/pbi-tools.core compile \
    -folder powerbi/pbixproj-full \
    -format PBIT \
    -outPath /workspace/powerbi/dashboard-full.pbit \
    -overwrite
```

CI also builds templates on every push — see
[build-pbit.yml](.github/workflows/build-pbit.yml).

### Customize the Dashboard

See [powerbi/POWER_BI_SETUP.md](powerbi/POWER_BI_SETUP.md) for manual
construction instructions including data connections, DAX measures, visual
specifications, and cloud data source options.

---

## Automated Data Refresh

A GitHub Actions workflow runs weekly using the merge-and-replace pattern:
1. Downloads existing CSV from cloud storage
2. Fetches PRs from the last 30 days
3. Merges new data into existing (upsert, no duplicates)
4. Uploads the deduplicated CSV back to cloud storage

### Setup

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Add secret: `GITHUB_TOKEN_PAT` (your GitHub PAT with `repo` scope)
3. Set `STORAGE_PROVIDER` in the workflow to `azure`, `s3`, or `none`
4. Add provider secrets as needed:
   - Azure: `AZURE_STORAGE_CONNECTION_STRING`
   - S3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`

The workflow runs every Monday at 6:00 AM UTC and can also be triggered manually.

### Manual Trigger

1. Go to **Actions** → **Refresh PR Data**
2. Click **Run workflow**
3. Optionally override: org name, start date, end date
4. Check **Full refresh** to ignore existing data and re-fetch everything

### Workflow File

See [.github/workflows/refresh-data.yml](.github/workflows/refresh-data.yml)

---

## Cloud Storage

### Azure Blob Storage

Set these environment variables:

```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_CONTAINER_NAME=pr-dashboard          # default
AZURE_BLOB_NAME=pull_requests.csv          # default
```

In Power BI: **Get Data** → **Azure Blob Storage** → enter storage account name.

### AWS S3

```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=pr-dashboard                 # default
AWS_S3_KEY=pull_requests.csv               # default
AWS_REGION=us-east-1                       # default
```

### SharePoint Online (Recommended for Microsoft 365 Customers)

Upload the CSV to a SharePoint document library manually or via Power Automate. Power BI can connect natively and supports scheduled refresh without a gateway.

---

## CSV Schema

| Column | Type | Description |
|--------|------|-------------|
| `pr_number` | Integer | PR number |
| `repository` | Text | Repository name (org/repo) |
| `title` | Text | PR title |
| `author` | Text | GitHub login of PR author |
| `created_at` | DateTime | PR creation timestamp (ISO 8601) |
| `merged_at` | DateTime | PR merge timestamp (nullable) |
| `closed_at` | DateTime | PR close timestamp (nullable) |
| `state` | Text | `MERGED` or `CLOSED` |
| `is_draft` | Boolean | `True` if PR was a draft |
| `days_open` | Decimal | Days PR was open |
| `has_copilot_review` | Boolean | `True` if CCR was used |
| `month_year` | Text | YYYY-MM format for grouping |
| `reviewer_count` | Integer | Total number of reviewers |
| `copilot_review_count` | Integer | Number of Copilot reviews |
| `reviewers` | Text | Semicolon-separated human reviewer logins |
| `merged_by` | Text | GitHub login of who merged the PR |
| `additions` | Integer | Lines added |
| `deletions` | Integer | Lines deleted |
| `changed_files` | Integer | Number of files changed |
| `commit_count` | Integer | Number of commits in the PR |
| `comment_count` | Integer | Number of discussion comments |
| `review_decision` | Text | `APPROVED`, `CHANGES_REQUESTED`, or empty |
| `labels` | Text | Comma-separated label names |
| `base_branch` | Text | Target branch (e.g., main) |
| `head_branch` | Text | Source branch name |
| `first_response_hours` | Decimal | Hours from PR open to first review |

---

## Dashboard Metrics

For a detailed explanation of every metric, its business impact, interpretation guidance, and analysis tips, see the **[Metrics Insights Guide](docs/METRICS_INSIGHTS.md)**.

### Charts
- **Average Days Open by Month** — Clustered bar chart comparing with/without CCR
- **PR Count by Month** — Clustered bar chart showing adoption over time

### KPI Cards
- Total PRs analyzed
- Copilot adoption rate (%)
- Average days saved with CCR
- Total repositories

### Colors

Charts use the default Power BI theme (`CY25SU12`) which auto-assigns colors
from the palette. The first two series in comparison charts typically render as:
- **Blue** (`#118DFF`): first series (e.g., With Copilot Code Review)
- **Dark Blue** (`#12239E`): second series (e.g., Without Copilot Code Review)

---

## Troubleshooting

### Authentication Errors
```
Error: GITHUB_TOKEN environment variable not set
```
Create `.env` file or `export GITHUB_TOKEN="ghp_..."`.

### Rate Limiting
```
Error: HTTP 403
```
The script automatically retries after 60 seconds. GraphQL allows 5,000 points/hour.

### Over 1,000 Results
Handled automatically — the script splits searches into monthly date ranges.

### No Data Returned
- Verify organization name is correct
- Ensure token has access to the repositories
- Check that repositories have closed/merged PRs
- Review the console output for the generated search query

---

## Project Structure

```
pr-dashboard/
├── README.md                              # This file
├── COPILOT_PROMPT.md                      # Original agent prompt
├── requirements.txt                       # Python dependencies
├── .env.example                           # Template for .env
├── .gitignore                             # Git ignore rules
│
├── docs/
│   └── METRICS_INSIGHTS.md                # Metric definitions & analysis guide
│
├── .github/
│   ├── copilot-instructions.md            # Copilot custom instructions
│   ├── skills/
│   │   └── build-pbi-reports/SKILL.md     # Agent skill: compile .pbit templates
│   └── workflows/
│       ├── build-pbit.yml                 # CI: compile .pbit from PbixProj source
│       ├── release.yml                    # CD: attach .pbit to GitHub Releases
│       └── refresh-data.yml               # Weekly automated data refresh
│
├── src/
│   ├── fetch_pr_data.py                   # Data extraction (GraphQL search API)
│   └── upload_data.py                     # Cloud upload (Azure Blob / S3)
│
├── data/
│   ├── pull_requests.csv                  # Generated CSV (gitignored)
│   └── sample.csv                         # Sample data for previewing
│
└── powerbi/
    ├── POWER_BI_SETUP.md                  # Power BI dashboard build guide
    ├── generate_report.py                 # Generates Report section JSON for PbixProj
    ├── blank_template.pbit                # Reference blank template from PBI Desktop
    ├── pbixproj-full/                     # PbixProj source — full 3-page dashboard
    │   ├── .pbixproj.json
    │   ├── Version.txt
    │   ├── Model/                         # TMDL data model (26 cols, 14 measures)
    │   ├── Report/                        # Report layout & section visuals
    │   └── StaticResources/               # Theme JSON
    └── pbixproj-light/                    # PbixProj source — light 1-page dashboard
        └── (same structure, single page)
```

## License

MIT
