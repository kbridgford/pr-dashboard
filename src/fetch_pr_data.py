#!/usr/bin/env python3
"""
GitHub Pull Request Data Extractor

This script fetches pull request data from GitHub repositories and analyzes
whether Copilot Code Review (CCR) was used. It exports the data to CSV format
for analysis in Power BI or other visualization tools.

Uses GitHub's GraphQL search API to efficiently query all PRs across an
organization in a single search, avoiding the need to list and query each
repository individually. This dramatically reduces API calls for large orgs.

Features:
- Search for PRs across an entire organization with a single query
- Automatically handles the 1,000 result search limit by splitting into
  monthly date ranges
- Detect Copilot Code Review usage by examining review authors
- Calculate how long each PR was open
- Export data to CSV with all relevant metrics
- Filter by date range

Usage:
    # All repositories in an organization (default)
    python src/fetch_pr_data.py --owner myorg

    # Single repository
    python src/fetch_pr_data.py --owner myorg --repo myrepo

    # With date filtering
    python src/fetch_pr_data.py --owner myorg --start-date 2025-01-01 --end-date 2025-12-31

    # Custom output path
    python src/fetch_pr_data.py --owner myorg --output data/my_results.csv

Requirements:
    - Python 3.11+
    - GitHub Personal Access Token with 'repo' scope
    - pip install requests python-dotenv
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

import requests
from dotenv import load_dotenv


# ============================================================================
# GraphQL Queries
# ============================================================================

# GraphQL search query to find pull requests across an entire organization
# or a single repository. Uses GitHub's search API for efficiency.
#
# Key advantages over per-repo queries:
#   - Single query covers all repos in an org (no need to list repos first)
#   - Date filtering is handled server-side via search qualifiers
#   - Dramatically fewer API calls for large organizations
#
# Note: GitHub search returns a maximum of 1,000 results per query.
# For datasets exceeding this limit, the script automatically splits
# searches into monthly date ranges to stay under the limit.
SEARCH_PRS_QUERY = """
query SearchPullRequests($query: String!, $cursor: String) {
  search(query: $query, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        number
        title
        createdAt
        mergedAt
        closedAt
        state
        isDraft
        additions
        deletions
        changedFiles
        baseRefName
        headRefName
        reviewDecision
        author {
          login
        }
        mergedBy {
          login
        }
        repository {
          nameWithOwner
        }
        commits {
          totalCount
        }
        comments {
          totalCount
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
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
"""


# ============================================================================
# Main Fetcher Class
# ============================================================================

class GitHubPRFetcher:
    """
    Fetches pull request data from GitHub using the GraphQL search API

    This class handles all interactions with the GitHub API, including:
    - Searching for PRs across an entire org or single repo
    - Handling pagination (100 PRs per page)
    - Automatic date-range chunking when results exceed 1,000
    - Rate limit awareness with automatic retry
    """

    def __init__(self, token: str):
        """
        Initialize the fetcher with GitHub authentication

        Args:
            token: GitHub Personal Access Token with 'repo' scope
        """
        self.token = token
        self.api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _execute_graphql(self, query: str, variables: Dict) -> Dict:
        """
        Execute a GraphQL query against the GitHub API

        Handles HTTP errors, GraphQL errors, and rate limiting with
        automatic retry after a cooldown period.

        Args:
            query: GraphQL query string
            variables: Query variables dictionary

        Returns:
            Parsed JSON response from the API

        Raises:
            SystemExit: On non-recoverable API errors
        """
        response = requests.post(
            self.api_url,
            json={"query": query, "variables": variables},
            headers=self.headers
        )

        # Handle rate limiting - wait and retry
        if response.status_code == 403 and "rate limit" in response.text.lower():
            print("  ⚠ Rate limit hit, waiting 60 seconds...")
            time.sleep(60)
            return self._execute_graphql(query, variables)

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            sys.exit(1)

        data = response.json()

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            sys.exit(1)

        return data

    def _build_search_query(self, owner: str, repo: Optional[str] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> str:
        """
        Build a GitHub search query string for finding pull requests

        Examples of generated queries:
            "is:pr is:closed org:myorg"
            "is:pr is:closed repo:myorg/myrepo"
            "is:pr is:closed org:myorg created:2025-01-01..2025-06-30"

        Args:
            owner: GitHub organization or user name
            repo: Optional repository name (searches all org repos if omitted)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Search query string for the GitHub API
        """
        # Start with PR type and closed state (includes merged PRs)
        parts = ["is:pr", "is:closed"]

        # Scope to org or specific repo
        if repo:
            parts.append(f"repo:{owner}/{repo}")
        else:
            parts.append(f"org:{owner}")

        # Add date range filter using GitHub search syntax
        if start_date and end_date:
            parts.append(f"created:{start_date}..{end_date}")
        elif start_date:
            parts.append(f"created:>={start_date}")
        elif end_date:
            parts.append(f"created:<={end_date}")

        return " ".join(parts)

    def _search_page(self, query_string: str, cursor: Optional[str] = None) -> Dict:
        """
        Execute a single page of search results

        Args:
            query_string: GitHub search query
            cursor: Pagination cursor for the next page

        Returns:
            The 'search' portion of the GraphQL response
        """
        variables: Dict[str, Any] = {"query": query_string, "cursor": cursor}
        data = self._execute_graphql(SEARCH_PRS_QUERY, variables)
        return data["data"]["search"]

    def search_pull_requests(self, owner: str, repo: Optional[str] = None,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> List[Dict]:
        """
        Search for pull requests across an organization or single repository

        Uses GitHub's search API to find all closed/merged PRs matching the
        criteria. If results exceed 1,000 (GitHub's search limit), the query
        is automatically split into monthly date ranges.

        Args:
            owner: GitHub organization or user name
            repo: Optional repository name (searches all org repos if omitted)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            List of pull request dictionaries with review data
        """
        query_string = self._build_search_query(owner, repo, start_date, end_date)
        scope = f"{owner}/{repo}" if repo else f"{owner} (all repos)"
        print(f"Searching for PRs in {scope}...")
        print(f"  Query: {query_string}")

        # First page - check total count
        search_data = self._search_page(query_string)
        total_count = search_data["issueCount"]
        print(f"  Found {total_count} matching PRs")

        # If over 1,000 results, split into monthly date ranges
        if total_count > 1000:
            print("  ⚠ Over 1,000 results - splitting into monthly chunks...")
            return self._search_by_date_chunks(owner, repo, start_date, end_date)

        # Collect all results with pagination
        all_prs = []
        page = 1
        cursor = None

        # Process results starting with the first page we already fetched
        while True:
            if page > 1:
                search_data = self._search_page(query_string, cursor)

            # Filter out non-PullRequest nodes (search can return mixed types)
            prs = [n for n in search_data["nodes"] if n and n.get("number")]
            all_prs.extend(prs)

            print(f"  Page {page}: {len(prs)} PRs (total so far: {len(all_prs)})")

            page_info = search_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break

            cursor = page_info["endCursor"]
            page += 1

        print(f"✓ Total PRs fetched: {len(all_prs)}\n")
        return all_prs

    def _search_by_date_chunks(self, owner: str, repo: Optional[str] = None,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> List[Dict]:
        """
        Handle large result sets by splitting search into monthly date ranges

        GitHub search returns a maximum of 1,000 results. This method works
        around that limit by searching one month at a time and combining results.

        Args:
            owner: GitHub organization or user name
            repo: Optional repository name
            start_date: Start of date range (defaults to 2 years ago)
            end_date: End of date range (defaults to today)

        Returns:
            Combined list of PR dictionaries from all monthly chunks
        """
        # Default date range if not specified
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        # Generate monthly date ranges
        ranges = self._generate_monthly_ranges(start_date, end_date)
        all_prs = []

        for i, (chunk_start, chunk_end) in enumerate(ranges, 1):
            print(f"\n  Chunk [{i}/{len(ranges)}]: {chunk_start} to {chunk_end}")

            query_string = self._build_search_query(owner, repo, chunk_start, chunk_end)
            cursor = None
            page = 1

            while True:
                search_data = self._search_page(query_string, cursor)

                if page == 1:
                    chunk_total = search_data["issueCount"]
                    print(f"    {chunk_total} PRs in this period")

                    if chunk_total > 1000:
                        print("    ⚠ Still over 1,000 in this month - some results may be truncated")

                prs = [n for n in search_data["nodes"] if n and n.get("number")]
                all_prs.extend(prs)

                page_info = search_data["pageInfo"]
                if not page_info["hasNextPage"]:
                    break

                cursor = page_info["endCursor"]
                page += 1

        print(f"\n✓ Total PRs fetched across all chunks: {len(all_prs)}\n")
        return all_prs

    def _generate_monthly_ranges(self, start_date: str, end_date: str) -> List[tuple]:
        """
        Generate a list of (start, end) date pairs for each month in the range

        Args:
            start_date: Range start in YYYY-MM-DD format
            end_date: Range end in YYYY-MM-DD format

        Returns:
            List of (start_date, end_date) string tuples, one per month
        """
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        ranges = []

        while current <= end:
            # Calculate last day of current month
            if current.month == 12:
                month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

            # Cap at the overall end date
            if month_end > end:
                month_end = end

            ranges.append((
                current.strftime("%Y-%m-%d"),
                month_end.strftime("%Y-%m-%d")
            ))

            # Move to first day of next month
            current = month_end + timedelta(days=1)

        return ranges


# ============================================================================
# Helper Functions for Copilot Detection
# ============================================================================

def has_copilot_review(reviews: List[Dict]) -> bool:
    """
    Check if any review is from Copilot Code Review

    Copilot reviews are identified by checking if the reviewer's
    login contains "copilot" (case-insensitive).

    Args:
        reviews: List of review dictionaries from GraphQL response

    Returns:
        True if at least one review is from Copilot, False otherwise
    """
    if not reviews:
        return False

    for review in reviews:
        author = review.get("author")
        if author and author.get("login"):
            login = author["login"].lower()
            # Check if "copilot" appears in the reviewer's username
            if "copilot" in login:
                return True

    return False


def count_copilot_reviews(reviews: List[Dict]) -> int:
    """
    Count how many reviews are from Copilot

    Args:
        reviews: List of review dictionaries

    Returns:
        Number of Copilot reviews (integer)
    """
    if not reviews:
        return 0

    count = 0
    for review in reviews:
        author = review.get("author")
        if author and author.get("login"):
            login = author["login"].lower()
            if "copilot" in login:
                count += 1

    return count


# ============================================================================
# Data Processing Functions
# ============================================================================

def calculate_days_open(created_at: str, merged_at: Optional[str],
                       closed_at: Optional[str]) -> float:
    """
    Calculate how many days a pull request was open

    The "end time" is determined by:
    1. merged_at timestamp if the PR was merged
    2. closed_at timestamp if the PR was closed without merging
    3. Current time if the PR is still open

    Args:
        created_at: PR creation timestamp (ISO 8601 format)
        merged_at: PR merge timestamp (ISO 8601 format, nullable)
        closed_at: PR close timestamp (ISO 8601 format, nullable)

    Returns:
        Number of days as a decimal (e.g., 2.5 days)
    """
    # Parse the creation timestamp
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    # Determine the end time: prefer merged_at, then closed_at, then now
    end_time_str = merged_at if merged_at else closed_at

    if not end_time_str:
        # PR is still open - use current time
        end_time = datetime.now(created.tzinfo)
    else:
        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))

    # Calculate difference and convert to days
    delta = end_time - created
    return delta.total_seconds() / 86400  # 86400 seconds in a day


def process_pull_requests(prs: List[Dict]) -> List[Dict[str, Any]]:
    """
    Process raw PR data from search results and extract relevant fields for CSV

    For each PR, this function:
    - Extracts the repository name from the PR's repository field
    - Detects if Copilot Code Review was used
    - Calculates how long the PR was open
    - Extracts month-year for grouping
    - Counts total reviewers and Copilot reviews

    Args:
        prs: List of raw PR data from GraphQL search results

    Returns:
        List of processed PR records ready for CSV export
    """
    processed = []

    for pr in prs:
        # Extract repository name from the search result
        repo_name = pr.get("repository", {}).get("nameWithOwner", "unknown")

        # Extract reviews from the PR
        reviews = pr.get("reviews", {}).get("nodes", [])

        # Calculate key metrics
        has_ccr = has_copilot_review(reviews)
        copilot_count = count_copilot_reviews(reviews)
        days = calculate_days_open(
            pr["createdAt"],
            pr.get("mergedAt"),
            pr.get("closedAt")
        )

        # Extract month-year for grouping in dashboard (e.g., "2025-08")
        created = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
        month_year = created.strftime("%Y-%m")

        # Extract human reviewers (exclude bots/copilot)
        human_reviewers = list(set(
            r["author"]["login"] for r in reviews
            if r.get("author") and r["author"].get("login")
            and "copilot" not in r["author"]["login"].lower()
            and "[bot]" not in r["author"]["login"].lower()
        ))

        # Calculate first response time (hours from PR open to first review)
        first_response_hours = None
        if reviews:
            review_times = [
                datetime.fromisoformat(r["submittedAt"].replace("Z", "+00:00"))
                for r in reviews if r.get("submittedAt")
            ]
            if review_times:
                earliest_review = min(review_times)
                first_response_hours = round(
                    (earliest_review - created).total_seconds() / 3600, 2
                )

        # Extract labels as comma-separated string
        labels = ", ".join(
            l["name"] for l in pr.get("labels", {}).get("nodes", [])
        )

        # Build the output record
        record = {
            "pr_number": pr["number"],
            "repository": repo_name,
            "title": pr["title"],
            "author": pr.get("author", {}).get("login", "") if pr.get("author") else "",
            "created_at": pr["createdAt"],
            "merged_at": pr.get("mergedAt", ""),
            "closed_at": pr.get("closedAt", ""),
            "state": pr.get("state", ""),
            "is_draft": pr.get("isDraft", False),
            "days_open": round(days, 2),
            "has_copilot_review": has_ccr,
            "month_year": month_year,
            "reviewer_count": len(reviews),
            "copilot_review_count": copilot_count,
            "reviewers": "; ".join(human_reviewers),
            "merged_by": pr.get("mergedBy", {}).get("login", "") if pr.get("mergedBy") else "",
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "changed_files": pr.get("changedFiles", 0),
            "commit_count": pr.get("commits", {}).get("totalCount", 0),
            "comment_count": pr.get("comments", {}).get("totalCount", 0),
            "review_decision": pr.get("reviewDecision", "") or "",
            "labels": labels,
            "base_branch": pr.get("baseRefName", ""),
            "head_branch": pr.get("headRefName", ""),
            "first_response_hours": first_response_hours if first_response_hours is not None else ""
        }

        processed.append(record)

    return processed


# ============================================================================
# Merge and Deduplication Functions
# ============================================================================

# CSV column order — used by both load and export
CSV_FIELDNAMES = [
    "pr_number",
    "repository",
    "title",
    "author",
    "created_at",
    "merged_at",
    "closed_at",
    "state",
    "is_draft",
    "days_open",
    "has_copilot_review",
    "month_year",
    "reviewer_count",
    "copilot_review_count",
    "reviewers",
    "merged_by",
    "additions",
    "deletions",
    "changed_files",
    "commit_count",
    "comment_count",
    "review_decision",
    "labels",
    "base_branch",
    "head_branch",
    "first_response_hours"
]


def load_existing_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load existing PR data from a CSV file

    Reads the CSV and converts numeric/boolean fields back to their
    proper Python types so they can be merged with freshly fetched data.

    Args:
        csv_path: Path to the existing CSV file

    Returns:
        List of PR records as dictionaries, or empty list if file missing
    """
    if not os.path.exists(csv_path):
        return []

    records = []
    with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert types to match freshly processed data
            row["pr_number"] = int(row.get("pr_number", 0))
            row["days_open"] = float(row.get("days_open", 0))
            row["has_copilot_review"] = row.get("has_copilot_review", "False") == "True"
            row["is_draft"] = row.get("is_draft", "False") == "True"
            row["reviewer_count"] = int(row.get("reviewer_count", 0))
            row["copilot_review_count"] = int(row.get("copilot_review_count", 0))
            row["additions"] = int(row.get("additions", 0))
            row["deletions"] = int(row.get("deletions", 0))
            row["changed_files"] = int(row.get("changed_files", 0))
            row["commit_count"] = int(row.get("commit_count", 0))
            row["comment_count"] = int(row.get("comment_count", 0))
            # first_response_hours may be empty string
            frh = row.get("first_response_hours", "")
            row["first_response_hours"] = float(frh) if frh else ""
            records.append(row)

    print(f"✓ Loaded {len(records)} existing PRs from {csv_path}")
    return records


def merge_data(
    existing: List[Dict[str, Any]],
    new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge new PR data into existing data, deduplicating by (pr_number, repository)

    For PRs that appear in both datasets, the new data wins — this handles
    cases where a PR was previously fetched as OPEN but has since been
    MERGED or received new reviews.

    Args:
        existing: Previously collected PR records
        new: Freshly fetched PR records

    Returns:
        Deduplicated merged list sorted by created_at descending
    """
    # Build a dict keyed by (pr_number, repository) — existing first, then
    # overwrite with new data so fresh results always win
    merged = {}
    for record in existing:
        key = (record["pr_number"], record["repository"])
        merged[key] = record

    updated = 0
    added = 0
    for record in new:
        key = (record["pr_number"], record["repository"])
        if key in merged:
            updated += 1
        else:
            added += 1
        merged[key] = record

    # Sort by created_at descending (newest first)
    result = sorted(
        merged.values(),
        key=lambda r: r.get("created_at", ""),
        reverse=True
    )

    print(f"✓ Merge complete: {added} new, {updated} updated, {len(result)} total")
    return result


def save_snapshot(csv_path: str) -> Optional[str]:
    """
    Save a timestamped snapshot of the existing CSV before overwriting

    Snapshots are saved alongside the original file in a 'snapshots'
    subdirectory with a date-stamped filename.

    Args:
        csv_path: Path to the existing CSV file

    Returns:
        Path to the snapshot file, or None if no existing file to snapshot
    """
    if not os.path.exists(csv_path):
        return None

    import shutil
    snapshot_dir = os.path.join(os.path.dirname(csv_path), "snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    base = os.path.splitext(os.path.basename(csv_path))[0]
    snapshot_path = os.path.join(snapshot_dir, f"{base}_{timestamp}.csv")

    shutil.copy2(csv_path, snapshot_path)
    print(f"✓ Snapshot saved: {snapshot_path}")
    return snapshot_path


# ============================================================================
# Export and Summary Functions
# ============================================================================

def export_to_csv(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Write processed PR data to CSV file

    Creates a CSV with columns for PR metadata, timing, review info,
    size metrics, and Copilot Code Review detection.

    Args:
        data: List of processed PR records
        output_path: File path for the CSV output
    """
    if not data:
        print("⚠ No data to export")
        return

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write the CSV file
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()  # Write column headers
        writer.writerows(data)  # Write all PR records

    print(f"✓ Data exported to: {output_path}")


def print_summary(data: List[Dict[str, Any]]) -> None:
    """
    Display summary statistics about the exported data

    Shows:
    - Total number of PRs analyzed
    - Number and percentage with Copilot Code Review
    - Average days open for PRs with/without CCR
    - Days saved (or lost) when using CCR
    - Date range of the data

    Args:
        data: List of processed PR records
    """
    if not data:
        return

    # Count PRs with and without Copilot Code Review
    total = len(data)
    with_ccr = sum(1 for pr in data if pr["has_copilot_review"])
    without_ccr = total - with_ccr

    # Calculate average days open for each group
    avg_days_with = sum(pr["days_open"] for pr in data if pr["has_copilot_review"]) / with_ccr if with_ccr > 0 else 0
    avg_days_without = sum(pr["days_open"] for pr in data if not pr["has_copilot_review"]) / without_ccr if without_ccr > 0 else 0

    # Determine date range of the data
    dates = [datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")) for pr in data]
    min_date = min(dates).strftime("%Y-%m-%d")
    max_date = max(dates).strftime("%Y-%m-%d")

    # Print formatted summary
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(f"Total PRs:              {total}")
    print(f"  With Copilot Review:  {with_ccr} ({with_ccr/total*100:.1f}%)")
    print(f"  Without CCR:          {without_ccr} ({without_ccr/total*100:.1f}%)")
    print()
    print(f"Average Days Open:")
    print(f"  With Copilot Review:  {avg_days_with:.2f} days")
    print(f"  Without CCR:          {avg_days_without:.2f} days")
    if with_ccr > 0 and without_ccr > 0:
        # Calculate and show the time difference
        diff = avg_days_without - avg_days_with
        print(f"  Difference:           {diff:.2f} days ({'faster' if diff > 0 else 'slower'} with CCR)")
    print()
    print(f"Date Range:             {min_date} to {max_date}")
    print("="*60 + "\n")


# ============================================================================
# Main Program
# ============================================================================

def main():
    """
    Main entry point for the script

    Parses command line arguments and executes the PR data extraction workflow:
    1. Load configuration from environment and CLI arguments
    2. Connect to GitHub API with authentication
    3. Search for pull requests (entire org or single repo)
    4. Process and export data to CSV
    5. Display summary statistics

    Command line arguments:
        --owner: GitHub organization or user name
        --repo: Repository name (optional - omit to search all org repos)
        --start-date: Filter PRs created after this date (YYYY-MM-DD)
        --end-date: Filter PRs created before this date (YYYY-MM-DD)
        --output: CSV output file path (default: data/pull_requests.csv)

    Environment variables (via .env file):
        GITHUB_TOKEN: GitHub Personal Access Token (required)
        GITHUB_OWNER: Default organization/user name
        GITHUB_REPO: Default repository name
    """
    # Load environment variables from .env file
    load_dotenv()

    # Set up command line argument parser
    parser = argparse.ArgumentParser(
        description="Fetch GitHub PR data and export to CSV for Copilot Code Review analysis"
    )
    parser.add_argument(
        "--owner",
        default=os.getenv("GITHUB_OWNER"),
        help="GitHub organization or user name"
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPO"),
        help="Repository name (omit to search all repos in org)"
    )
    parser.add_argument(
        "--output",
        default="data/pull_requests.csv",
        help="Output CSV file path (default: data/pull_requests.csv)"
    )
    parser.add_argument(
        "--start-date",
        help="Filter PRs created after this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        help="Filter PRs created before this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge new results into existing CSV (upsert by pr_number + repository)"
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Save a timestamped backup before overwriting (used with --merge)"
    )

    args = parser.parse_args()

    # Validate required arguments
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Create a .env file or export GITHUB_TOKEN=your_token")
        sys.exit(1)

    if not args.owner:
        print("Error: --owner is required")
        print("Set it via CLI argument or GITHUB_OWNER in .env")
        sys.exit(1)

    # Initialize GitHub API client and search for PRs
    fetcher = GitHubPRFetcher(token)

    prs = fetcher.search_pull_requests(
        args.owner,
        repo=args.repo,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # Process raw PR data and export to CSV
    all_processed_data = process_pull_requests(prs)

    # Merge with existing data if --merge flag is set
    if args.merge:
        # Optionally save a snapshot before overwriting
        if args.snapshot:
            save_snapshot(args.output)

        existing_data = load_existing_csv(args.output)
        all_processed_data = merge_data(existing_data, all_processed_data)

    export_to_csv(all_processed_data, args.output)

    # Display summary statistics
    print_summary(all_processed_data)


if __name__ == "__main__":
    main()
