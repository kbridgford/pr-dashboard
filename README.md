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
- GitHub Personal Access Token with `repo` scope
- Power BI Desktop (for visualization)

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

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=your-repo-name
```

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

### Upload to Cloud Storage (Optional)

```bash
# Azure Blob Storage
python src/upload_data.py --provider azure --file data/pull_requests.csv

# AWS S3
python src/upload_data.py --provider s3 --file data/pull_requests.csv
```

See [Cloud Storage Setup](#cloud-storage) for configuration details.

### Build the Power BI Dashboard

See [powerbi/SETUP_GUIDE.md](powerbi/SETUP_GUIDE.md) for step-by-step instructions including:
- Data connection (local CSV, Azure Blob, SharePoint)
- DAX measures for KPIs
- Visual specifications (bar charts, cards, slicers)
- Template export

---

## Automated Data Refresh

A GitHub Actions workflow runs weekly to keep data current.

### Setup

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Add secret: `GITHUB_TOKEN_PAT` (your GitHub PAT with `repo` scope)
3. Optionally add: `AZURE_STORAGE_CONNECTION_STRING` for cloud upload

The workflow runs every Monday at 6:00 AM UTC and can also be triggered manually.

### Manual Trigger

1. Go to **Actions** → **Refresh PR Data**
2. Click **Run workflow**
3. Optionally override: org name, start date, end date

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

### Charts
- **Average Days Open by Month** — Clustered bar chart comparing with/without CCR
- **PR Count by Month** — Clustered bar chart showing adoption over time

### KPI Cards
- Total PRs analyzed
- Copilot adoption rate (%)
- Average days saved with CCR
- Total repositories

### Colors
- **Blue** (`#4F81BD`): With Copilot Code Review
- **Red** (`#C0504D`): Without Copilot Code Review

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
├── requirements.txt                       # Python dependencies
├── .env.example                           # Template for .env
├── .gitignore                             # Git ignore rules
├── COPILOT_PROMPT.md                      # Original agent prompt
│
├── .github/
│   └── workflows/
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
    └── SETUP_GUIDE.md                     # Power BI dashboard build guide
```

## License

MIT
