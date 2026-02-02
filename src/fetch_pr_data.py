#!/usr/bin/env python3
"""
GitHub Pull Request Data Extractor

This script fetches pull request data from GitHub repositories and analyzes
whether Copilot Code Review (CCR) was used. It exports the data to CSV format
for analysis in Power BI or other visualization tools.

Features:
- Fetch PRs from a single repository or all repos in an organization
- Detect Copilot Code Review usage by examining review authors
- Calculate how long each PR was open
- Export data to CSV with all relevant metrics
- Filter by date range if needed

Usage:
    # Single repository
    python src/fetch_pr_data.py --owner myorg --repo myrepo
    
    # All repositories in organization
    python src/fetch_pr_data.py --owner myorg --all-repos
    
    # With date filtering
    python src/fetch_pr_data.py --owner myorg --all-repos --start-date 2025-01-01
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Any

import requests
from dotenv import load_dotenv


# ============================================================================
# GraphQL Queries
# ============================================================================

# GraphQL query to fetch pull requests and their reviews from a repository
# This query uses pagination to handle repositories with many PRs
GRAPHQL_QUERY = """
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
"""

# GraphQL query to list all repos in an organization
# Only includes repositories that have at least one PR
LIST_REPOS_QUERY = """
query ListOrgRepos($owner: String!, $cursor: String) {
  organization(login: $owner) {
    repositories(first: 100, after: $cursor) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        isPrivate
        pullRequests(states: [MERGED, CLOSED], first: 1) {
          totalCount
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
    Fetches pull request data from GitHub GraphQL API
    
    This class handles all interactions with the GitHub API, including:
    - Listing repositories in an organization
    - Fetching pull requests with their reviews
    - Handling pagination for large datasets
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
    
    def list_org_repositories(self, owner: str) -> List[str]:
        """
        List all repositories in an organization that have pull requests
        
        This method queries the GitHub API to find all repos in an org,
        then filters to only include those with at least one PR.
        
        Args:
            owner: GitHub organization name
            
        Returns:
            List of repository names (strings)
        """
        all_repos = []
        cursor = None
        
        print(f"Fetching repositories for organization: {owner}...")
        
        # Paginate through all repos in the organization
        while True:
            variables = {
                "owner": owner,
                "cursor": cursor
            }
            
            # Make GraphQL API request
            response = requests.post(
                self.api_url,
                json={"query": LIST_REPOS_QUERY, "variables": variables},
                headers=self.headers
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)
            
            data = response.json()
            
            # Check for GraphQL errors
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                sys.exit(1)
            
            org_data = data["data"]["organization"]
            if not org_data:
                print(f"Organization '{owner}' not found")
                sys.exit(1)
            
            repo_data = org_data["repositories"]
            repos = repo_data["nodes"]
            
            # Only include repos that have PRs (to avoid empty datasets)
            for repo in repos:
                pr_count = repo["pullRequests"]["totalCount"]
                if pr_count > 0:
                    all_repos.append(repo["name"])
            
            # Check if there are more pages to fetch
            page_info = repo_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            
            cursor = page_info["endCursor"]
        
        print(f"✓ Found {len(all_repos)} repositories with pull requests\n")
        return all_repos
    
    def fetch_pull_requests(self, owner: str, repo: str, 
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all pull requests from a repository with pagination
        
        Retrieves merged and closed PRs along with their reviews.
        Handles pagination automatically to get all PRs.
        
        Args:
            owner: GitHub organization or user name
            repo: Repository name
            start_date: Filter PRs created after this date (ISO format: YYYY-MM-DD)
            end_date: Filter PRs created before this date (ISO format: YYYY-MM-DD)
            
        Returns:
            List of pull request dictionaries containing PR and review data
        """
        all_prs = []
        cursor = None
        page = 1
        
        print(f"Fetching pull requests from {owner}/{repo}...")
        
        # Paginate through all PRs (100 per page)
        while True:
            variables = {
                "owner": owner,
                "repo": repo,
                "cursor": cursor
            }
            
            # Make GraphQL API request
            response = requests.post(
                self.api_url,
                json={"query": GRAPHQL_QUERY, "variables": variables},
                headers=self.headers
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)
            
            data = response.json()
            
            # Check for GraphQL errors
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                sys.exit(1)
            
            pr_data = data["data"]["repository"]["pullRequests"]
            prs = pr_data["nodes"]
            
            # Apply date filters if specified
            filtered_prs = self._filter_by_date(prs, start_date, end_date)
            all_prs.extend(filtered_prs)
            
            print(f"  Page {page}: Fetched {len(prs)} PRs ({len(filtered_prs)} after filtering)")
            
            # Check if there are more pages to fetch
            page_info = pr_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            
            cursor = page_info["endCursor"]
            page += 1
        
        print(f"✓ Total PRs fetched: {len(all_prs)}\n")
        return all_prs
    
    def _filter_by_date(self, prs: List[Dict], start_date: Optional[str], 
                       end_date: Optional[str]) -> List[Dict]:
        """
        Filter PRs by creation date
        
        Args:
            prs: List of PR dictionaries
            start_date: Include PRs created on or after this date (ISO format)
            end_date: Include PRs created on or before this date (ISO format)
            
        Returns:
            Filtered list of PRs
        """
        # If no filters specified, return all PRs
        if not start_date and not end_date:
            return prs
        
        filtered = []
        for pr in prs:
            # Parse PR creation date
            created = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
            
            # Check start date filter
            if start_date:
                start = datetime.fromisoformat(start_date)
                if created < start:
                    continue
            
            # Check end date filter
            if end_date:
                end = datetime.fromisoformat(end_date)
                if created > end:
                    continue
            
            filtered.append(pr)
        
        return filtered


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


def process_pull_requests(prs: List[Dict], repo_name: str) -> List[Dict[str, Any]]:
    """
    Process raw PR data and extract relevant fields for CSV export
    
    For each PR, this function:
    - Detects if Copilot Code Review was used
    - Calculates how long the PR was open
    - Extracts month-year for grouping
    - Counts total reviewers and Copilot reviews
    
    Args:
        prs: List of raw PR data from GraphQL
        repo_name: Full repository name (owner/repo) for the CSV
        
    Returns:
        List of processed PR records ready for CSV export
    """
    processed = []
    
    for pr in prs:
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
        
        # Build the output record
        record = {
            "pr_number": pr["number"],
            "repository": repo_name,
            "title": pr["title"],
            "created_at": pr["createdAt"],
            "merged_at": pr.get("mergedAt", ""),
            "closed_at": pr.get("closedAt", ""),
            "days_open": round(days, 2),  # Round to 2 decimal places
            "has_copilot_review": has_ccr,
            "month_year": month_year,
            "reviewer_count": len(reviews),
            "copilot_review_count": copilot_count
        }
        
        processed.append(record)
    
    return processed


# ============================================================================
# Export and Summary Functions
# ============================================================================

def export_to_csv(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Write processed PR data to CSV file
    
    Creates a CSV with the following columns:
    - pr_number: PR identifier
    - repository: Full repo name (owner/repo)
    - title: PR title
    - created_at: When PR was created (ISO 8601)
    - merged_at: When PR was merged (if applicable)
    - closed_at: When PR was closed (if applicable)
    - days_open: How long the PR was open
    - has_copilot_review: True if Copilot Code Review was used
    - month_year: Year-month for grouping (YYYY-MM)
    - reviewer_count: Total number of reviewers
    - copilot_review_count: Number of Copilot reviews
    
    Args:
        data: List of processed PR records
        output_path: File path for the CSV output
    """
    if not data:
        print("⚠ No data to export")
        return
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Define the column order for the CSV
    fieldnames = [
        "pr_number",
        "repository",
        "title",
        "created_at",
        "merged_at",
        "closed_at",
        "days_open",
        "has_copilot_review",
        "month_year",
        "reviewer_count",
        "copilot_review_count"
    ]
    
    # Write the CSV file
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
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
    3. Fetch pull request data (single repo or all org repos)
    4. Process and export data to CSV
    5. Display summary statistics
    
    Command line arguments:
        --owner: GitHub organization or user name
        --repo: Repository name (optional, if not provided scans all org repos)
        --all-repos: Scan all repositories in the organization
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
        description="Fetch GitHub PR data and export to CSV"
    )
    parser.add_argument(
        "--owner",
        default=os.getenv("GITHUB_OWNER"),
        help="GitHub organization or user name"
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPO"),
        help="Repository name (omit to scan all repos in org)"
    )
    parser.add_argument(
        "--all-repos",
        action="store_true",
        help="Fetch data from all repositories in the organization"
    )
    parser.add_argument(
        "--output",
        default="data/pull_requests.csv",
        help="Output CSV file path (default: data/pull_requests.csv)"
    )
    parser.add_argument(
        "--start-date",
        help="Filter PRs created after this date (ISO format: YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        help="Filter PRs created before this date (ISO format: YYYY-MM-DD)"
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
    
    # Initialize GitHub API client
    fetcher = GitHubPRFetcher(token)
    all_processed_data = []
    
    # Determine which repos to fetch data from
    if args.all_repos or not args.repo:
        # Scan all repositories in the organization
        repos = fetcher.list_org_repositories(args.owner)
        
        for i, repo in enumerate(repos, 1):
            print(f"\n[{i}/{len(repos)}] Processing {args.owner}/{repo}")
            try:
                # Fetch PRs for this repository
                prs = fetcher.fetch_pull_requests(
                    args.owner,
                    repo,
                    args.start_date,
                    args.end_date
                )
                
                # Process the PRs and add to dataset
                repo_full_name = f"{args.owner}/{repo}"
                processed = process_pull_requests(prs, repo_full_name)
                all_processed_data.extend(processed)
            except Exception as e:
                print(f"  ⚠ Error processing {repo}: {e}")
                continue  # Continue to next repo if one fails
    else:
        # Fetch from a single repository
        prs = fetcher.fetch_pull_requests(
            args.owner,
            args.repo,
            args.start_date,
            args.end_date
        )
        
        repo_full_name = f"{args.owner}/{args.repo}"
        all_processed_data = process_pull_requests(prs, repo_full_name)
    
    # Export all collected data to CSV
    export_to_csv(all_processed_data, args.output)
    
    # Display summary statistics
    print_summary(all_processed_data)


if __name__ == "__main__":
    main()
