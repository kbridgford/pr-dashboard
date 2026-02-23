# Pull Request Dashboard

Analyze pull request metrics comparing PRs with Copilot Code Review (CCR) versus those without.

Uses GitHub's GraphQL search API to efficiently query all PRs across an organization in a single search, avoiding the need to list and query each repository individually. This dramatically reduces API calls for large orgs.

## Setup

### 1. Prerequisites

- Python 3.11+ (using pyenv)
- GitHub Personal Access Token with `repo` scope
- Power BI Desktop (for visualization)

### 2. Install Python and Dependencies

```bash
# Set Python version
pyenv local 3.12.11

# Create virtual environment
pyenv exec python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure GitHub Access

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your GitHub Personal Access Token:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=your-repo-name
```

**Get a GitHub token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: `repo` (for private repos) or `public_repo` (for public only)
4. Copy the token

## Usage

### Fetch PR Data

Run the script to fetch data and generate CSV:

```bash
# Fetch all PRs across an organization (default)
python src/fetch_pr_data.py --owner myorg

# Fetch PRs from a single repository
python src/fetch_pr_data.py --owner myorg --repo myrepo

# Filter by date range
python src/fetch_pr_data.py --owner myorg --start-date 2025-01-01 --end-date 2025-12-31

# Custom output path
python src/fetch_pr_data.py --owner myorg --output data/custom.csv
```

> **Note:** GitHub search returns a maximum of 1,000 results per query. For large
> orgs exceeding this limit, the script automatically splits searches into monthly
> date ranges.

### Output

The script generates:
- `data/pull_requests.csv` - PR data with CCR status
- Console summary showing:
  - Total PRs analyzed
  - Count with/without CCR
  - Average days open comparison

### Load in Power BI

1. Open Power BI Desktop
2. Get Data → Text/CSV
3. Select `data/pull_requests.csv`
4. Transform data as needed
5. Create visualizations

## CSV Schema

| Column | Type | Description |
|--------|------|-------------|
| pr_number | Integer | PR number |
| repository | Text | Repository name |
| title | Text | PR title |
| created_at | DateTime | PR creation timestamp (ISO 8601) |
| merged_at | DateTime | PR merge timestamp (nullable) |
| closed_at | DateTime | PR close timestamp (nullable) |
| days_open | Decimal | Days PR was open |
| has_copilot_review | Boolean | true if CCR was used |
| month_year | Text | YYYY-MM format for grouping |
| reviewer_count | Integer | Total number of reviewers |
| copilot_review_count | Integer | Number of Copilot reviews |

## Dashboard Metrics

### Primary Visualization
- **Grouped bar chart**: Average days open by month
- **Blue bars**: PRs with Copilot Code Review
- **Red bars**: PRs without Copilot Code Review

### KPIs
- Average days saved with CCR
- % of PRs using CCR
- Total PRs analyzed

## Troubleshooting

### Authentication Errors
```
Error: GITHUB_TOKEN environment variable not set
```
**Solution**: Create `.env` file with valid GitHub token

### Rate Limiting
```
Error: HTTP 403
```
**Solution**: The script automatically retries after 60 seconds when rate-limited. GraphQL allows 5,000 points/hour.

### Over 1,000 Results
GitHub search limits results to 1,000 per query. The script handles this automatically by splitting into monthly date ranges. You can also use `--start-date` and `--end-date` to narrow your search.

### No Data Returned
**Check**:
- Organization name and owner are correct
- Token has access to the repositories
- Repositories have closed/merged PRs
- Search query syntax is valid (check console output for the generated query)

## Project Structure

```
pr-dashboard/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
├── .env.example             # Template for .env
├── src/
│   └── fetch_pr_data.py     # Data extraction script
├── data/
│   └── pull_requests.csv    # Generated CSV (gitignored)
└── powerbi/
    └── dashboard.pbix       # Power BI template (optional)
```

## License

MIT
