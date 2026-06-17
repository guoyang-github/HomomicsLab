#!/usr/bin/env python3
"""
bioRxiv Search Tool
A comprehensive Python tool for searching and retrieving preprints from bioRxiv.
Supports keyword search, author search, date filtering, category filtering, and more.

Note: This tool is focused exclusively on bioRxiv (life sciences preprints).
"""

import requests
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time
import sys
from urllib.parse import quote


class BioRxivSearcher:
    """Efficient search interface for bioRxiv preprints."""

    BASE_URL = "https://api.biorxiv.org"

    # Valid bioRxiv categories
    CATEGORIES = [
        "animal-behavior-and-cognition", "biochemistry", "bioengineering",
        "bioinformatics", "biophysics", "cancer-biology", "cell-biology",
        "clinical-trials", "developmental-biology", "ecology", "epidemiology",
        "evolutionary-biology", "genetics", "genomics", "immunology",
        "microbiology", "molecular-biology", "neuroscience", "paleontology",
        "pathology", "pharmacology-and-toxicology", "physiology",
        "plant-biology", "scientific-communication-and-education",
        "synthetic-biology", "systems-biology", "zoology"
    ]

    def __init__(self, verbose: bool = False):
        """Initialize the searcher."""
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BioRxiv-Search-Tool/1.0'
        })

    def _log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request with error handling, rate limiting, and response validation."""
        url = f"{self.BASE_URL}/{endpoint}"
        self._log(f"Requesting: {url}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Validate content type before parsing JSON
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                self._log(f"Unexpected content type: {content_type}")
                return {
                    "messages": [{"status": "error", "message": f"Unexpected content type: {content_type}"}],
                    "collection": []
                }

            data = response.json()

            # Validate response structure
            if not isinstance(data, dict):
                self._log(f"Invalid response format: expected dict, got {type(data).__name__}")
                return {
                    "messages": [{"status": "error", "message": f"Invalid response format: {type(data).__name__}"}],
                    "collection": []
                }

            # Rate limiting - be respectful to the API
            time.sleep(0.5)

            return data
        except requests.exceptions.JSONDecodeError as e:
            self._log(f"Error decoding JSON: {e}")
            return {"messages": [{"status": "error", "message": f"Invalid JSON response: {e}"}], "collection": []}
        except requests.exceptions.RequestException as e:
            self._log(f"Error making request: {e}")
            return {"messages": [{"status": "error", "message": str(e)}], "collection": []}

    def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for preprints within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            category: Optional category filter (e.g., 'neuroscience')

        Returns:
            List of preprint dictionaries
        """
        self._log(f"Searching bioRxiv from {start_date} to {end_date}")

        if category:
            endpoint = f"details/biorxiv/{start_date}/{end_date}/{category}"
        else:
            endpoint = f"details/biorxiv/{start_date}/{end_date}"

        data = self._make_request(endpoint)

        if "collection" in data:
            self._log(f"Found {len(data['collection'])} preprints")
            return data["collection"]

        return []

    def search_by_interval(
        self,
        interval: str = "1",
        cursor: int = 0,
        format: str = "json"
    ) -> Dict:
        """
        Retrieve preprints from a specific time interval.

        Args:
            interval: Number of days back to search
            cursor: Pagination cursor (0 for first page, then use returned cursor)
            format: Response format ('json' or 'xml')

        Returns:
            Dictionary with collection and pagination info
        """
        endpoint = f"pubs/biorxiv/{interval}/{cursor}/{format}"
        return self._make_request(endpoint)

    def get_paper_details(self, doi: str) -> Dict:
        """
        Get detailed information about a specific paper by DOI.

        Args:
            doi: The DOI of the paper (e.g., '10.1101/2021.01.01.123456')

        Returns:
            Dictionary with paper details
        """
        # Clean DOI if full URL was provided
        if 'doi.org' in doi:
            doi = doi.split('doi.org/')[-1]

        self._log(f"Fetching details for DOI: {doi}")
        endpoint = f"details/biorxiv/{doi}"

        data = self._make_request(endpoint)

        if "collection" in data and len(data["collection"]) > 0:
            return data["collection"][0]

        return {}

    def _chunked_date_search(
        self,
        start_date: str,
        end_date: str,
        category: Optional[str] = None,
        chunk_days: int = 30,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for preprints across a date range in small chunks to avoid
        excessive memory use and API load.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            category: Optional category filter
            chunk_days: Days per chunk (default: 30)
            max_results: Stop after fetching this many results (default: no limit)
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        all_papers = []
        current = start

        while current <= end:
            if max_results is not None and len(all_papers) >= max_results:
                self._log(f"Reached max_results limit ({max_results}), stopping early")
                break

            chunk_end = min(current + timedelta(days=chunk_days - 1), end)
            chunk_start_str = current.strftime("%Y-%m-%d")
            chunk_end_str = chunk_end.strftime("%Y-%m-%d")
            self._log(f"Fetching chunk {chunk_start_str} to {chunk_end_str}")
            papers = self.search_by_date_range(chunk_start_str, chunk_end_str, category)
            all_papers.extend(papers)
            current = chunk_end + timedelta(days=1)

        if max_results is not None:
            return all_papers[:max_results]
        return all_papers

    def search_by_author(
        self,
        author_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for papers by author name.

        Args:
            author_name: Author name to search for
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            max_results: Maximum number of results to return (default: no limit)

        Returns:
            List of matching preprints
        """
        # If no date range specified, search last 3 years
        if not start_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")

        self._log(f"Searching for author: {author_name}")

        # Get papers in chunked date ranges to limit memory and API load
        papers = self._chunked_date_search(start_date, end_date, max_results=max_results)

        # Filter by author name (case-insensitive)
        author_lower = author_name.lower()
        matching_papers = []

        for paper in papers:
            authors = paper.get("authors", "")
            if author_lower in authors.lower():
                matching_papers.append(paper)
                if max_results is not None and len(matching_papers) >= max_results:
                    break

        self._log(f"Found {len(matching_papers)} papers by {author_name}")
        return matching_papers

    def search_by_keywords(
        self,
        keywords: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        search_fields: List[str] = ["title", "abstract"],
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for papers containing specific keywords.

        Args:
            keywords: List of keywords to search for
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            category: Optional category filter
            search_fields: Fields to search in (title, abstract, authors)
            max_results: Maximum number of results to return (default: no limit)

        Returns:
            List of matching preprints
        """
        # If no date range specified, search last year
        if not start_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        self._log(f"Searching for keywords: {keywords}")

        # Get papers in chunked date ranges to limit memory and API load
        papers = self._chunked_date_search(start_date, end_date, category, max_results=max_results)

        # Filter by keywords
        matching_papers = []
        keywords_lower = [k.lower() for k in keywords]

        for paper in papers:
            # Build search text from specified fields
            search_text = ""
            for field in search_fields:
                if field in paper:
                    search_text += " " + str(paper[field]).lower()

            # Check if any keyword matches
            if any(keyword in search_text for keyword in keywords_lower):
                matching_papers.append(paper)
                if max_results is not None and len(matching_papers) >= max_results:
                    break

        self._log(f"Found {len(matching_papers)} papers matching keywords")
        return matching_papers

    def download_pdf(self, doi: str, output_path: str, version: str = "") -> bool:
        """
        Download the PDF of a paper.

        Args:
            doi: The DOI of the paper
            output_path: Path where PDF should be saved
            version: Paper version (default: latest)

        Returns:
            True if download successful, False otherwise
        """
        # Clean DOI
        if 'doi.org' in doi:
            doi = doi.split('doi.org/')[-1]

        # Use provided version or default to v1
        ver = version if version else "1"
        pdf_url = f"https://www.biorxiv.org/content/{doi}v{ver}.full.pdf"

        self._log(f"Downloading PDF from: {pdf_url}")

        try:
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            self._log(f"PDF saved to: {output_path}")
            return True
        except Exception as e:
            self._log(f"Error downloading PDF: {e}")
            return False

    def format_result(self, paper: Dict, include_abstract: bool = True) -> Dict:
        """
        Format a paper result with standardized fields.

        Args:
            paper: Raw paper dictionary from API
            include_abstract: Whether to include the abstract

        Returns:
            Formatted paper dictionary
        """
        result = {
            "doi": paper.get("doi", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "author_corresponding": paper.get("author_corresponding", ""),
            "author_corresponding_institution": paper.get("author_corresponding_institution", ""),
            "date": paper.get("date", ""),
            "version": paper.get("version", ""),
            "type": paper.get("type", ""),
            "license": paper.get("license", ""),
            "category": paper.get("category", ""),
            "jatsxml": paper.get("jatsxml", ""),
            "published": paper.get("published", "")
        }

        if include_abstract:
            result["abstract"] = paper.get("abstract", "")

        # Add PDF and HTML URLs
        if result["doi"]:
            result["pdf_url"] = f"https://www.biorxiv.org/content/{result['doi']}v{result['version']}.full.pdf"
            result["html_url"] = f"https://www.biorxiv.org/content/{result['doi']}v{result['version']}"

        return result


def main():
    """Command-line interface for bioRxiv search."""
    parser = argparse.ArgumentParser(
        description="Search bioRxiv preprints efficiently",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")

    # Search type arguments
    search_group = parser.add_argument_group("Search options")
    search_group.add_argument("--keywords", "-k", nargs="+",
                            help="Keywords to search for")
    search_group.add_argument("--author", "-a",
                            help="Author name to search for")
    search_group.add_argument("--doi",
                            help="Get details for specific DOI")

    # Date range arguments
    date_group = parser.add_argument_group("Date range options")
    date_group.add_argument("--start-date",
                          help="Start date (YYYY-MM-DD)")
    date_group.add_argument("--end-date",
                          help="End date (YYYY-MM-DD)")
    date_group.add_argument("--days-back", type=int,
                          help="Search N days back from today")

    # Filter arguments
    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument("--category", "-c",
                            choices=BioRxivSearcher.CATEGORIES,
                            help="Filter by category")
    filter_group.add_argument("--search-fields", nargs="+",
                            default=["title", "abstract"],
                            choices=["title", "abstract", "authors"],
                            help="Fields to search in for keywords")

    # Output arguments
    output_group = parser.add_argument_group("Output options")
    output_group.add_argument("--output", "-o",
                            help="Output file (default: stdout)")
    output_group.add_argument("--include-abstract", action="store_true",
                            default=True, help="Include abstracts in output")
    output_group.add_argument("--download-pdf",
                            help="Download PDF to specified path (requires --doi)")
    output_group.add_argument("--limit", type=int,
                            help="Limit number of results")

    args = parser.parse_args()

    # Initialize searcher
    searcher = BioRxivSearcher(verbose=args.verbose)

    # Handle date range
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if args.days_back:
        start_date = (datetime.now() - timedelta(days=args.days_back)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # Execute search based on arguments
    results = []

    if args.download_pdf:
        if not args.doi:
            print("Error: --doi required with --download-pdf", file=sys.stderr)
            return 1

        success = searcher.download_pdf(args.doi, args.download_pdf)
        return 0 if success else 1

    elif args.doi:
        # Get specific paper by DOI
        paper = searcher.get_paper_details(args.doi)
        if paper:
            results = [paper]

    elif args.author:
        # Search by author
        results = searcher.search_by_author(
            args.author, start_date, end_date
        )

    elif args.keywords:
        # Search by keywords
        if not start_date:
            print("Error: --start-date or --days-back required for keyword search",
                  file=sys.stderr)
            return 1

        results = searcher.search_by_keywords(
            args.keywords, start_date, end_date,
            args.category, args.search_fields
        )

    else:
        # Date range search
        if not start_date:
            print("Error: Must specify search criteria (--keywords, --author, or --doi)",
                  file=sys.stderr)
            return 1

        results = searcher.search_by_date_range(
            start_date, end_date, args.category
        )

    # Apply limit
    if args.limit:
        results = results[:args.limit]

    # Format results
    formatted_results = [
        searcher.format_result(paper, args.include_abstract)
        for paper in results
    ]

    # Output results
    output_data = {
        "query": {
            "keywords": args.keywords,
            "author": args.author,
            "doi": args.doi,
            "start_date": start_date,
            "end_date": end_date,
            "category": args.category
        },
        "result_count": len(formatted_results),
        "results": formatted_results
    }

    output_json = json.dumps(output_data, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
