# Power BI Dashboard Setup Guide

This guide walks you through creating the Copilot Code Review dashboard in Power BI Desktop. The finished dashboard will have two bar charts and KPI cards, matching the reference template.

## Quick Start

1. Open Power BI Desktop
2. **Get Data** → **Text/CSV** → select `data/pull_requests.csv` (or `data/sample.csv` to preview)
3. Follow the steps below to transform the data & build visuals

---

## Step 1: Load and Transform Data

### Connect to the CSV

1. **Home** → **Get Data** → **Text/CSV**
2. Browse to `data/pull_requests.csv`
3. In the preview dialog, click **Transform Data** (opens Power Query Editor)

### Data Type Transformations

In Power Query Editor, set column types:

| Column | Set Type To |
|--------|------------|
| `pr_number` | Whole Number |
| `created_at` | Date/Time/Timezone |
| `merged_at` | Date/Time/Timezone |
| `closed_at` | Date/Time/Timezone |
| `days_open` | Decimal Number |
| `has_copilot_review` | True/False |
| `reviewer_count` | Whole Number |
| `copilot_review_count` | Whole Number |

### Add a Display Column

In Power Query, add a custom column for chart legends:

1. **Add Column** → **Custom Column**
2. Name: `Review Type`
3. Formula:
   ```
   if [has_copilot_review] = true then "With Copilot Code Review" else "Without Copilot Code Review"
   ```
4. Click **Close & Apply**

---

## Step 2: Create DAX Measures

Switch to **Model** view or the **Data** pane and create these measures:

### Total PRs
```dax
Total PRs = COUNTROWS('pull_requests')
```

### PRs With Copilot Review
```dax
PRs With CCR = CALCULATE(
    COUNTROWS('pull_requests'),
    'pull_requests'[has_copilot_review] = TRUE
)
```

### PRs Without Copilot Review
```dax
PRs Without CCR = CALCULATE(
    COUNTROWS('pull_requests'),
    'pull_requests'[has_copilot_review] = FALSE
)
```

### Copilot Adoption Rate
```dax
CCR Adoption % = DIVIDE([PRs With CCR], [Total PRs], 0) * 100
```

### Average Days Open (With CCR)
```dax
Avg Days With CCR = CALCULATE(
    AVERAGE('pull_requests'[days_open]),
    'pull_requests'[has_copilot_review] = TRUE
)
```

### Average Days Open (Without CCR)
```dax
Avg Days Without CCR = CALCULATE(
    AVERAGE('pull_requests'[days_open]),
    'pull_requests'[has_copilot_review] = FALSE
)
```

### Days Saved
```dax
Days Saved = [Avg Days Without CCR] - [Avg Days With CCR]
```

### Total Repositories
```dax
Total Repos = DISTINCTCOUNT('pull_requests'[repository])
```

---

## Step 3: Build the Dashboard

### Page Layout

Create a single report page named **"Copilot Code Review Impact"**.

### Color Theme

| Element | Color |
|---------|-------|
| Without CCR (red) | `#C0504D` |
| With CCR (blue) | `#4F81BD` |
| Background | White |
| Text | `#333333` |

---

### KPI Cards (Top Row)

Add four **Card** visuals across the top of the page:

| Card | Value | Format |
|------|-------|--------|
| Total PRs | `[Total PRs]` | Whole number |
| Copilot Adoption | `[CCR Adoption %]` | One decimal + "%" suffix |
| Avg Days Saved | `[Days Saved]` | One decimal + " days" suffix |
| Repositories | `[Total Repos]` | Whole number |

---

### Visual 1: Number of Days PRs Stay Open

**Type:** Clustered Bar Chart

| Field | Value |
|-------|-------|
| X-axis | `month_year` |
| Y-axis | Average of `days_open` |
| Legend | `Review Type` |

**Formatting:**
- Title: "Number of Days Most Pull Requests Stay Open (With/Without Copilot Code Review)"
- Legend position: Top right
- Colors: Blue = With CCR, Red = Without CCR
- Sort X-axis ascending (chronological)
- Data labels: On

---

### Visual 2: Number of PRs With/Without CCR

**Type:** Clustered Bar Chart

| Field | Value |
|-------|-------|
| X-axis | `month_year` |
| Y-axis | Count of `pr_number` |
| Legend | `Review Type` |

**Formatting:**
- Title: "Number of Pull Requests With/Without Copilot Code Review"
- Legend position: Top right
- Colors: Blue = With CCR (Reviewed), Red = Without CCR (Not Reviewed)
- Sort X-axis ascending (chronological)
- Data labels: On

---

### Slicers (Optional Sidebar)

Add filter slicers for interactivity:

| Slicer | Field | Style |
|--------|-------|-------|
| Date Range | `month_year` | Dropdown or between |
| Repository | `repository` | Dropdown (multi-select) |

---

## Step 4: Connect to Cloud Data (Optional)

### Azure Blob Storage

If using Azure Blob Storage to host the CSV:

1. **Get Data** → **Azure** → **Azure Blob Storage**
2. Enter your storage account name
3. Sign in with your Azure credentials
4. Navigate to the `pr-dashboard` container
5. Select `pull_requests.csv`
6. Set up **Scheduled Refresh** in Power BI Service

### SharePoint Online

If using SharePoint to host the CSV:

1. **Get Data** → **SharePoint folder**
2. Enter your SharePoint site URL
3. Navigate to the folder containing `pull_requests.csv`
4. Filter and select the file
5. Power BI Service can auto-refresh from SharePoint

### AWS S3

If using AWS S3:

1. **Get Data** → **Web**
2. Enter the public S3 URL or use a pre-signed URL
3. Note: Scheduled refresh requires Power BI Gateway

---

## Step 5: Save as Template

To share this dashboard as a reusable template:

1. **File** → **Export** → **Power BI template (.pbit)**
2. Add a description: "Copilot Code Review Impact Dashboard"
3. Save as `powerbi/dashboard.pbit`

When customers open the `.pbit` file, they'll be prompted to enter their data source path.

---

## Step 6: Publish (Optional)

1. **Home** → **Publish**
2. Select a Power BI workspace
3. Configure **Scheduled Refresh** (Settings → Datasets → Scheduled Refresh)
4. Set refresh frequency (e.g., weekly on Monday)
5. Share the dashboard with stakeholders
