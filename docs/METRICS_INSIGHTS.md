# Metrics Insights Guide

This guide explains every metric collected and displayed in the PR Dashboard, why it matters, and how to interpret it when evaluating the impact of GitHub Copilot Code Review (CCR) on your engineering workflows.

---

## Dashboard Visuals

### Chart: Days PRs Stay Open (With/Without Copilot Code Review)

**What it shows:** Average number of days pull requests remain open before being merged or closed, grouped by month, split by whether Copilot Code Review was used.

**Why it matters:** PR cycle time is one of the strongest indicators of engineering velocity. Long-lived PRs increase merge conflict risk, delay feature delivery, and create context-switching overhead for authors and reviewers. A consistent reduction in days-open for CCR-reviewed PRs demonstrates that automated review accelerates the feedback loop — authors get initial feedback faster, address issues sooner, and merge with less back-and-forth.

**How to read it:**
- Compare the blue bars (With CCR) against the red bars (Without CCR) each month.
- A growing gap over time suggests increasing CCR effectiveness as teams adopt it.
- If the gap narrows, investigate whether PR complexity or team composition changed.

---

### Chart: Number of PRs (With/Without Copilot Code Review)

**What it shows:** Count of merged/closed pull requests per month, split by whether they received a Copilot Code Review.

**Why it matters:** This chart tracks CCR adoption momentum. Increasing blue bars relative to red bars shows the organization is progressively enabling and relying on automated code review. Flat or declining adoption may indicate configuration issues, team resistance, or a need for enablement.

**How to read it:**
- Look for the blue portion growing as a share of total PRs over time.
- Sudden drops in blue may indicate repository-level Copilot configuration changes.
- Use alongside the Adoption % KPI for a precise numeric trend.

---

## KPI Cards (Full Template)

### Total PRs

**Definition:** Total number of closed or merged pull requests in the dataset.

**DAX:** `COUNTROWS('pull_requests')`

**Why it matters:** Provides the baseline sample size for all other metrics. A small total may mean insights are not yet statistically significant. As a rule of thumb, aim for at least 100 PRs before drawing conclusions, and 500+ for high-confidence comparisons.

---

### CCR Adoption %

**Definition:** Percentage of pull requests that received at least one Copilot Code Review.

**DAX:** `DIVIDE([PRs With CCR], [Total PRs], 0) * 100`

**Why it matters:** Adoption rate is the leading indicator for CCR impact — you cannot measure time savings until a meaningful portion of PRs are being reviewed by Copilot. Tracking this metric helps identify:
- Whether CCR is enabled organization-wide or only in select repos.
- Which repositories or teams have not yet adopted.
- Progress toward an adoption target (e.g., 80% of PRs reviewed by CCR).

**Benchmarks:**
| Range | Interpretation |
|-------|---------------|
| < 20% | Early adoption — focus on enablement and configuration |
| 20–50% | Growing adoption — identify non-adopting repos |
| 50–80% | Strong adoption — start measuring impact on cycle time |
| > 80% | Mature adoption — focus on quality and time-savings trends |

---

### Avg Days Saved

**Definition:** The difference in average days-open between PRs without CCR and PRs with CCR.

**DAX:** `[Avg Days Without CCR] - [Avg Days With CCR]`

**Why it matters:** This is the headline impact metric. A positive value means PRs with Copilot Code Review are closing faster on average. Multiply by the number of CCR-reviewed PRs to estimate total engineering days recovered. For example, if Days Saved = 1.5 and you have 200 CCR-reviewed PRs per month, that represents 300 days of cycle time reduction per month.

**Caveats:**
- Correlation, not causation — teams that adopt CCR may also follow other best practices.
- Filter by repository or time range to control for confounding variables.
- Very small sample sizes can produce misleading values.

---

### Total Repos

**Definition:** Number of distinct repositories represented in the dataset.

**DAX:** `DISTINCTCOUNT('pull_requests'[repository])`

**Why it matters:** Shows the breadth of data coverage. If your organization has 50 repositories but only 10 appear in the dataset, you may need to adjust date ranges, check token permissions, or verify that the missing repos have PR activity. This metric also helps contextualize adoption — 80% adoption across 3 repos is different from 80% across 50.

---

## Supporting DAX Measures

### PRs With CCR / PRs Without CCR

**Definition:** Count of PRs where `has_copilot_review` is TRUE / FALSE.

**Why it matters:** The raw counts behind the adoption percentage. Useful when filtered by slicer — for example, selecting a single repository to see its CCR vs. non-CCR split.

---

### Avg Days With CCR / Avg Days Without CCR

**Definition:** Average of `days_open` for PRs with/without Copilot Code Review.

**Why it matters:** The individual averages behind the "Days Saved" calculation. Tracking each independently helps identify whether improvement is coming from CCR-reviewed PRs getting faster, non-CCR PRs getting slower, or both.

---

## Calculated Column: Review Type

**Definition:** A display-friendly label derived from `has_copilot_review`:
- `TRUE` → "With Copilot Code Review"
- `FALSE` → "Without Copilot Code Review"

**Used in:** Chart legends and series splits. This column drives the blue/red color coding throughout the dashboard.

---

## CSV Data Fields

The raw dataset contains 26 fields. Here is what each one captures and how it can be used for deeper analysis beyond the default dashboard visuals.

### Identity & Context

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `pr_number` | PR number within the repository | Unique identifier (with `repository`) for deduplication |
| `repository` | Full repository name (org/repo) | Slice metrics by repo to find outliers or team-level patterns |
| `title` | PR title text | Text analysis — keyword searches for feature vs. bugfix vs. chore |
| `author` | GitHub login of the PR author | Identify per-developer patterns; measure CCR impact by contributor |
| `labels` | Comma-separated label names | Filter by label (e.g., `bug`, `feature`, `hotfix`) for category-level analysis |

### Timestamps & Duration

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `created_at` | When the PR was opened (ISO 8601) | Time-series analysis, cohort grouping |
| `merged_at` | When the PR was merged (null if closed unmerged) | Calculate merge rate; filter to merged-only PRs |
| `closed_at` | When the PR was closed | Compare merged vs. closed-without-merge patterns |
| `days_open` | Calendar days from open to close/merge | Primary cycle-time metric; used in both charts |
| `month_year` | YYYY-MM format string | Pre-bucketed field for monthly trend charts |
| `first_response_hours` | Hours from PR open to first review | Measures reviewer engagement speed — are reviewers (human or Copilot) responding faster? |

### Copilot Code Review

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `has_copilot_review` | Whether any review came from `copilot-pull-request-reviewer` | The primary CCR indicator driving all dashboard splits |
| `copilot_review_count` | Number of Copilot review submissions | Distinguish single-pass CCR from multi-pass; correlate with cycle time |

### Review Activity

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `reviewer_count` | Total number of distinct reviewers (human + bot) | Correlate reviewer count with cycle time; identify under-reviewed PRs |
| `reviewers` | Semicolon-separated list of human reviewer logins | Network analysis — who reviews what; workload distribution |
| `review_decision` | Final review state: `APPROVED`, `CHANGES_REQUESTED`, or empty | Track approval rates; compare decision patterns with/without CCR |
| `comment_count` | Number of discussion comments | Proxy for review thoroughness or contentiousness |
| `merged_by` | GitHub login of the person who merged | Track merge authority patterns; identify bottlenecks |

### PR Size & Complexity

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `additions` | Lines of code added | Correlate PR size with cycle time; CCR may have more impact on larger PRs |
| `deletions` | Lines of code deleted | Combined with additions, gives net change and churn rate |
| `changed_files` | Number of files modified | File-count as a complexity proxy; large file counts often slow review |
| `commit_count` | Number of commits in the PR | High commit counts may indicate iterative development or review rework |

### Branch & State

| Field | Description | Analytical Use |
|-------|-------------|---------------|
| `state` | `MERGED` or `CLOSED` | Filter to merged-only for "successful" PRs; analyze abandonment rate |
| `is_draft` | Whether the PR was marked as draft | Drafts may skew cycle-time metrics; consider filtering them out |
| `base_branch` | Target branch (e.g., `main`, `develop`) | Segment by branch strategy; release branches may have different patterns |
| `head_branch` | Source branch name | Naming conventions can reveal PR purpose (e.g., `fix/`, `feat/`) |

---

## Analysis Tips

### Controlling for Confounders

CCR adoption does not happen in a vacuum. When interpreting "Days Saved":

1. **Filter by repository** — Some repos may have inherently faster cycles due to smaller PRs or more active reviewers.
2. **Filter by PR size** — Compare CCR impact on small PRs (< 100 lines) vs. large PRs (> 500 lines) separately.
3. **Filter by time period** — Ensure you are comparing similar timeframes, not a holiday month against a sprint month.
4. **Exclude drafts** — Draft PRs are often open for extended periods by design.

### Suggested Additional Visuals

The 26-column dataset supports analysis beyond the default dashboard. Consider adding:

| Visual | Fields | Insight |
|--------|--------|---------|
| Scatter plot | `additions + deletions` vs. `days_open`, color by `Review Type` | Does CCR help more on larger PRs? |
| Table | `repository`, `CCR Adoption %`, `Avg Days Saved` | Per-repo breakdown of impact |
| Line chart | `month_year` vs. `first_response_hours`, by `Review Type` | Is first-response time improving with CCR? |
| Bar chart | `author` vs. count, color by `Review Type` | Per-developer adoption tracking |
| Funnel | `APPROVED` vs. `CHANGES_REQUESTED` by `Review Type` | Does CCR reduce change-request rates? |

### Statistical Significance

For any comparison, consider the sample size:

| PRs per group | Confidence |
|---------------|------------|
| < 30 | Low — trends may be noise |
| 30–100 | Moderate — directional but not conclusive |
| 100–500 | Good — patterns are likely real |
| > 500 | High — suitable for executive reporting |

---

## Template Variants

| Template | File | Pages | Visuals |
|----------|------|-------|---------|
| **Full** | `dashboard-full.pbit` | 3 (Overview, Copilot Impact, PR Details) | 6 KPI cards, 2 clustered column charts, 1 donut chart, 1 line chart, 2 tables, 3 slicers |
| **Light** | `dashboard-light.pbit` | 1 (Dashboard) | 5 KPI cards, 2 comparison column charts, 1 line chart, 1 volume column chart |

Both templates include the complete TMDL data model (26 columns, 14 DAX
measures) and connect to CSV via a `CsvFilePath` parameter. The Light template
is ideal for quick presentations; the Full template provides interactive
filtering, detailed Copilot impact analysis, and a per-PR detail table with
slicers.
