# Build a Pull Request Dashboard in Power BI

## Objective

Build a Power BI dashboard that compares the average number of days pull requests stay open when **Copilot Code Review (CCR) is enabled** versus when it is **not enabled**.

---

## Architecture

```
GitHub GraphQL API → Python Script → CSV Files → Power BI Dashboard
```

1. **Python script** fetches data from GitHub API
2. **CSV files** store the extracted data
3. **Power BI** loads from CSV for visualization

---

## Data Extraction Script

Create a Python script that:
1. Connects to GitHub GraphQL API (`https://api.github.com/graphql`)
2. Fetches all pull requests and their reviews
3. Processes the data and exports to CSV

### Authentication
- Use a GitHub Personal Access Token (PAT) with `repo` scope
- Load from environment variable `GITHUB_TOKEN`

### GraphQL Query to Use

```graphql
query GetPullRequestsWithReviews($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 100, after: $cursor, states: [MERGED, CLOSED]) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        createdAt
        mergedAt
        closedAt
        reviews(first: 50) {
          nodes {
            author {
              login
            }
            state
            submittedAt
          }
        }
      }
    }
  }
}
```

### Script Requirements
- Use `requests` library for API calls
- Handle pagination (loop while `hasNextPage` is true)
- Calculate `days_open` in the script
- Determine `has_copilot_review` flag
- Export to CSV with proper date formatting

---

## How to Identify Copilot Code Review

A pull request has CCR enabled if **any review** meets this criteria:
- `review.author.login` contains `"copilot"` (case-insensitive)

**Logic:**
```python
has_copilot_review = any("copilot" in (r.get("author", {}).get("login", "") or "").lower() 
                         for r in reviews)
```

---

## Calculations (in Python Script)

### Days Open
```python
end_date = merged_at if merged_at else closed_at
days_open = (end_date - created_at).total_seconds() / 86400
```
- Use `merged_at` if available, otherwise use `closed_at`
- Convert to decimal days

### Month-Year Grouping
```python
month_year = created_at.strftime("%Y-%m")
```

---

## CSV Output Format

### File: `data/pull_requests.csv`

| Column | Type | Description |
|--------|------|-------------|
| pr_number | Integer | PR identifier |
| repository | Text | Repository name |
| title | Text | PR title |
| created_at | DateTime | ISO format |
| merged_at | DateTime | ISO format (nullable) |
| closed_at | DateTime | ISO format (nullable) |
| days_open | Decimal | Calculated duration |
| has_copilot_review | Boolean | true/false |
| month_year | Text | YYYY-MM format |
| reviewer_count | Integer | Total reviewers |
| copilot_review_count | Integer | Copilot reviews |

---

## Power BI Setup

### 1. Data Connection
- Use **Text/CSV Connector** to load `data/pull_requests.csv`
- Set up **scheduled refresh** or manual refresh after running script

### 2. Power Query Transformations
- Parse date columns as DateTime
- Convert `has_copilot_review` to Boolean
- Create calculated columns if needed

### 3. Visualizations

**Primary Chart: Grouped Bar Chart**
- X-axis: Month-Year
- Y-axis: Average of days_open
- Legend: has_copilot_review (With CCR = Blue, Without CCR = Red)
- Show data labels on bars
- Title: "Number of Days Most Pull Requests Stay Open (With/Without Copilot Code Review)"

**Additional Elements:**
- KPI card: Average days saved with CCR
- Slicer: Date range filter
- Slicer: Repository filter (if multiple repos)

---

## File Structure to Generate

```
pr-dashboard/
├── README.md                       # Setup and usage instructions
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── src/
│   └── fetch_pr_data.py            # Main data extraction script
├── data/
│   └── .gitkeep                    # CSV output directory
└── powerbi/
    └── pr_dashboard.pbix           # Power BI template (optional)
```

---

## Python Script Requirements

### Dependencies (requirements.txt)
```
requests>=2.28.0
python-dotenv>=1.0.0
```

### Python Environment Setup (pyenv)
```bash
# Set Python version for project
pyenv local 3.12.11

# Create virtual environment
pyenv exec python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Script Features
1. Load config from environment variables or CLI args
2. Authenticate with GitHub PAT
3. Paginate through all PRs in repository
4. Process reviews to detect Copilot
5. Calculate metrics (days_open, etc.)
6. Export to CSV with headers
7. Print summary statistics

### CLI Usage
```bash
# Set environment variables
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# Run script
python src/fetch_pr_data.py --owner "myorg" --repo "myrepo" --output "data/pull_requests.csv"
```

---

## Configuration Parameters

The script should support these parameters (via CLI or env vars):
- `GITHUB_TOKEN` - Personal Access Token (required)
- `--owner` - Organization or user name
- `--repo` - Repository name
- `--output` - Output CSV path (default: `data/pull_requests.csv`)
- `--start-date` - Filter PRs created after this date (optional)
- `--end-date` - Filter PRs created before this date (optional)

---

## Expected Output

When complete:

### From Python Script
- CSV file with all PR data
- Console output showing:
  - Total PRs fetched
  - PRs with CCR vs without
  - Date range covered

### From Power BI Dashboard
1. A grouped bar chart comparing average days open by month
2. Blue bars for PRs WITH Copilot Code Review
3. Red bars for PRs WITHOUT Copilot Code Review
4. Clear trend visualization over 6+ months

---

## Technical Notes

- GitHub GraphQL rate limit: 5,000 points/hour
- Handle pagination for repositories with >100 PRs
- Script should be idempotent (can re-run safely)
- CSV should overwrite on each run (or append with dedup)
- Use ISO 8601 date format in CSV for Power BI compatibility
