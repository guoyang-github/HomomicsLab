#!/usr/bin/env python3
"""
arXiv Search Tool
A comprehensive Python tool for searching and retrieving preprints from arXiv.
Supports keyword search, author search, date filtering, category filtering, and more.

Note: This tool is focused exclusively on arXiv (physics, mathematics, computer science,
quantitative biology, statistics, finance, and electrical engineering preprints).
"""

import requests
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time
import sys
from xml.etree import ElementTree as ET
from urllib.parse import quote


class ArxivSearcher:
    """Efficient search interface for arXiv preprints."""

    BASE_URL = "https://export.arxiv.org/api/query"

    # Namespaces used in arXiv Atom feeds
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom"
    }

    # Valid arXiv categories
    CATEGORIES = [
        # Computer Science
        "cs.AI", "cs.CL", "cs.CC", "cs.CE", "cs.CG", "cs.CR", "cs.CV",
        "cs.CY", "cs.DB", "cs.DC", "cs.DL", "cs.DM", "cs.DS", "cs.ET",
        "cs.FL", "cs.GL", "cs.GR", "cs.GT", "cs.HC", "cs.IR", "cs.IT",
        "cs.LG", "cs.LO", "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE",
        "cs.NI", "cs.OH", "cs.OS", "cs.PF", "cs.PL", "cs.RO", "cs.SC",
        "cs.SD", "cs.SE", "cs.SI", "cs.SY",
        # Physics
        "physics.gen-ph", "physics.acc-ph", "physics.ao-ph", "physics.app-ph",
        "physics.atm-clus", "physics.atom-ph", "physics.bio-ph", "physics.chem-ph",
        "physics.class-ph", "physics.comp-ph", "physics.data-an", "physics.ed-ph",
        "physics.flu-dyn", "physics.geo-ph", "physics.hist-ph", "physics.ins-det",
        "physics.med-ph", "physics.optics", "physics.plasm-ph", "physics.pop-ph",
        "physics.soc-ph", "physics.space-ph",
        # Quantitative Biology
        "q-bio.BM", "q-bio.CB", "q-bio.GN", "q-bio.MN", "q-bio.NC",
        "q-bio.OT", "q-bio.PE", "q-bio.QM", "q-bio.SC", "q-bio.TO",
        # Mathematics
        "math.AG", "math.AT", "math.AP", "math.CT", "math.CA", "math.CO",
        "math.AC", "math.CV", "math.DG", "math.DS", "math.FA", "math.GM",
        "math.GN", "math.GT", "math.GR", "math.HO", "math.IT", "math.KT",
        "math.LO", "math.MP", "math.MG", "math.NT", "math.NA", "math.OA",
        "math.OC", "math.PR", "math.QA", "math.RT", "math.RA", "math.SP",
        "math.ST", "math.SG",
        # Statistics
        "stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH",
        # Electrical Engineering and Systems Science
        "eess.AS", "eess.IV", "eess.SP", "eess.SY",
        # Economics
        "econ.EM", "econ.GN", "econ.TH",
        # Quantitative Finance
        "q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF", "q-fin.PM",
        "q-fin.PR", "q-fin.RM", "q-fin.ST", "q-fin.TR"
    ]

    def __init__(self, verbose: bool = False):
        """Initialize the searcher."""
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ArXiv-Search-Tool/1.0'
        })

    def _log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def _make_request(self, params: Dict[str, Any]) -> Optional[ET.Element]:
        """Make an API request with error handling, rate limiting, and response validation.

        Args:
            params: Query parameters for the API request

        Returns:
            Parsed XML ElementTree root element, or None on error
        """
        self._log(f"Requesting: {self.BASE_URL} with params {params}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(
                    self.BASE_URL, params=params,
                    timeout=(10, 60)  # (connect_timeout, read_timeout)
                )
                response.raise_for_status()

                # Parse XML response
                root = ET.fromstring(response.content)

                # Check for error feed
                title_elem = root.find("atom:title", self.NAMESPACES)
                if title_elem is not None and title_elem.text == "Error":
                    summary_elem = root.find("atom:summary", self.NAMESPACES)
                    error_msg = summary_elem.text if summary_elem is not None else "Unknown error"
                    self._log(f"API Error: {error_msg}")
                    return None

                # Rate limiting - arXiv requires 3 seconds between requests
                time.sleep(3)

                return root

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                if status_code == 429:
                    wait_time = 5 * attempt
                    self._log(f"429 rate limit (attempt {attempt}/{max_retries}), waiting {wait_time}s...")
                    if attempt < max_retries:
                        time.sleep(wait_time)
                        continue
                    self._log("Error: arXiv API rate limit exceeded. Please wait a few minutes before trying again.")
                else:
                    self._log(f"HTTP Error {status_code}: {e}")
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                wait_time = 5 * attempt
                self._log(f"Connection error (attempt {attempt}/{max_retries}): {e}, waiting {wait_time}s...")
                if attempt < max_retries:
                    time.sleep(wait_time)
                    continue
                self._log(f"Error: Failed to connect to arXiv API after {max_retries} attempts.")
                return None

            except ET.ParseError as e:
                self._log(f"Error parsing XML: {e}")
                return None

            except requests.exceptions.RequestException as e:
                self._log(f"Error making request: {e}")
                return None

        return None

    def _parse_entries(self, root: ET.Element) -> List[Dict]:
        """Parse Atom feed entries into paper dictionaries.

        Args:
            root: XML root element of the Atom feed

        Returns:
            List of paper dictionaries
        """
        entries = []
        for entry in root.findall("atom:entry", self.NAMESPACES):
            paper = self._parse_entry(entry)
            if paper:
                entries.append(paper)
        return entries

    def _parse_entry(self, entry: ET.Element) -> Optional[Dict]:
        """Parse a single Atom entry into a paper dictionary.

        Args:
            entry: XML Element representing a single entry

        Returns:
            Paper dictionary, or None if parsing fails
        """
        try:
            # Extract arXiv ID from the id URL
            id_elem = entry.find("atom:id", self.NAMESPACES)
            arxiv_id = ""
            if id_elem is not None and id_elem.text:
                arxiv_id = id_elem.text.split("/")[-1]

            # Title
            title_elem = entry.find("atom:title", self.NAMESPACES)
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            # Summary (abstract)
            summary_elem = entry.find("atom:summary", self.NAMESPACES)
            abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""

            # Authors
            authors = []
            for author_elem in entry.findall("atom:author", self.NAMESPACES):
                name_elem = author_elem.find("atom:name", self.NAMESPACES)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # Published date
            published_elem = entry.find("atom:published", self.NAMESPACES)
            published = published_elem.text[:10] if published_elem is not None and published_elem.text else ""

            # Updated date
            updated_elem = entry.find("atom:updated", self.NAMESPACES)
            updated = updated_elem.text[:10] if updated_elem is not None and updated_elem.text else ""

            # Comment
            comment_elem = entry.find("arxiv:comment", self.NAMESPACES)
            comment = comment_elem.text if comment_elem is not None else ""

            # Primary category
            primary_cat_elem = entry.find("arxiv:primary_category", self.NAMESPACES)
            primary_category = primary_cat_elem.get("term", "") if primary_cat_elem is not None else ""

            # All categories (include primary category first)
            categories = []
            if primary_category:
                categories.append(primary_category)
            for cat_elem in entry.findall("atom:category", self.NAMESPACES):
                term = cat_elem.get("term", "")
                if term and term not in categories:
                    categories.append(term)

            # Links
            html_url = ""
            pdf_url = ""
            for link_elem in entry.findall("atom:link", self.NAMESPACES):
                rel = link_elem.get("rel", "")
                href = link_elem.get("href", "")
                link_title = link_elem.get("title", "")
                if rel == "alternate":
                    html_url = href
                elif link_title == "pdf":
                    pdf_url = href

            return {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": ", ".join(authors),
                "author_corresponding": "",
                "author_corresponding_institution": "",
                "date": published,
                "updated": updated,
                "version": "",
                "type": "",
                "license": "",
                "category": primary_category,
                "categories": categories,
                "abstract": abstract,
                "pdf_url": pdf_url,
                "html_url": html_url,
                "jatsxml": "",
                "comment": comment,
                "published": ""
            }
        except Exception as e:
            self._log(f"Error parsing entry: {e}")
            return None

    def _get_total_results(self, root: ET.Element) -> int:
        """Get total number of results from feed metadata.

        Args:
            root: XML root element

        Returns:
            Total number of results
        """
        total_elem = root.find("opensearch:totalResults", self.NAMESPACES)
        if total_elem is not None and total_elem.text:
            try:
                return int(total_elem.text)
            except ValueError:
                pass
        return 0

    def search_by_query(
        self,
        query: str,
        start: int = 0,
        max_results: int = 100,
        sort_by: str = "relevance",
        sort_order: str = "descending"
    ) -> List[Dict]:
        """Search for preprints using an arXiv query string.

        Args:
            query: arXiv search query (e.g., "ti:machine+learning")
            start: Offset for pagination
            max_results: Maximum results per request
            sort_by: Sort field (relevance, lastUpdatedDate, submittedDate)
            sort_order: Sort order (ascending, descending)

        Returns:
            List of preprint dictionaries
        """
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order
        }

        self._log(f"Searching arXiv with query: {query}")
        root = self._make_request(params)

        if root is not None:
            entries = self._parse_entries(root)
            self._log(f"Found {len(entries)} preprints")
            return entries

        return []

    def get_paper_details(self, arxiv_id: str) -> Dict:
        """Get detailed information about a specific paper by arXiv ID.

        Args:
            arxiv_id: The arXiv ID of the paper (e.g., '2401.12345')

        Returns:
            Dictionary with paper details
        """
        # Clean arXiv ID if full URL was provided
        if 'arxiv.org' in arxiv_id:
            arxiv_id = arxiv_id.split("/")[-1]

        self._log(f"Fetching details for arXiv ID: {arxiv_id}")
        params = {"id_list": arxiv_id}

        root = self._make_request(params)

        if root is not None:
            entries = self._parse_entries(root)
            if entries:
                return entries[0]

        return {}

    def search_by_keywords(
        self,
        keywords: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        search_fields: List[str] = ["title", "abstract"],
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """Search for papers containing specific keywords.

        Args:
            keywords: List of keywords to search for
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            category: Optional category filter (e.g., 'cs.LG')
            search_fields: Fields to search in (title, abstract, authors)
            max_results: Maximum number of results to return (default: no limit)

        Returns:
            List of matching preprints
        """
        # Build search query
        query_parts = []

        # Build keyword query
        keyword_clauses = []
        for keyword in keywords:
            escaped = keyword.replace('"', '')
            # Use quoted phrases for multi-word terms, unquoted for single words
            # Unquoted single words ensure case-insensitive matching
            if " " in escaped:
                term = f'"{escaped}"'
            else:
                term = escaped
            field_clauses = []
            for field in search_fields:
                if field == "title":
                    field_clauses.append(f"ti:{term}")
                elif field == "abstract":
                    field_clauses.append(f"abs:{term}")
                elif field == "authors":
                    field_clauses.append(f"au:{term}")
            if field_clauses:
                keyword_clauses.append(" OR ".join(field_clauses))

        if keyword_clauses:
            query_parts.append(" AND ".join(f"({kc})" for kc in keyword_clauses))

        # Add category filter
        if category:
            query_parts.append(f"cat:{category}")

        query = " AND ".join(query_parts) if query_parts else "all:*"

        self._log(f"Searching for keywords: {keywords} with query: {query}")

        # Request more results than needed to account for client-side date filtering
        per_page = 100
        # If date filter is active, fetch extra to compensate for filtered-out papers
        has_date_filter = start_date is not None or end_date is not None
        fetch_limit = (max_results * 5 if max_results else 1000) if has_date_filter else (max_results if max_results else 1000)

        all_papers = []
        current_start = 0

        while current_start < fetch_limit:
            batch_size = min(per_page, fetch_limit - current_start)
            papers = self.search_by_query(
                query=query,
                start=current_start,
                max_results=batch_size,
                sort_by="submittedDate",
                sort_order="descending"
            )

            if not papers:
                break

            # Filter by date range if specified
            for paper in papers:
                if start_date and paper.get("date", "") < start_date:
                    continue
                if end_date and paper.get("date", "") > end_date:
                    continue
                all_papers.append(paper)
                if max_results is not None and len(all_papers) >= max_results:
                    break

            if max_results is not None and len(all_papers) >= max_results:
                break

            current_start += batch_size

            # Stop if we got fewer results than requested (reached end)
            if len(papers) < batch_size:
                break

        self._log(f"Found {len(all_papers)} papers matching keywords after date filtering")
        return all_papers[:max_results] if max_results else all_papers

    def search_by_author(
        self,
        author_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """Search for papers by author name.

        Args:
            author_name: Author name to search for
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            max_results: Maximum number of results to return (default: no limit)

        Returns:
            List of matching preprints
        """
        # Use unquoted author name for case-insensitive matching
        query = f"au:{author_name.replace(' ', '+')}"

        self._log(f"Searching for author: {author_name}")

        # Request more results than needed to account for client-side date filtering
        per_page = 100
        has_date_filter = start_date is not None or end_date is not None
        fetch_limit = (max_results * 5 if max_results else 1000) if has_date_filter else (max_results if max_results else 1000)

        all_papers = []
        current_start = 0

        while current_start < fetch_limit:
            batch_size = min(per_page, fetch_limit - current_start)
            papers = self.search_by_query(
                query=query,
                start=current_start,
                max_results=batch_size,
                sort_by="submittedDate",
                sort_order="descending"
            )

            if not papers:
                break

            # Filter by date range if specified
            for paper in papers:
                if start_date and paper.get("date", "") < start_date:
                    continue
                if end_date and paper.get("date", "") > end_date:
                    continue
                all_papers.append(paper)
                if max_results is not None and len(all_papers) >= max_results:
                    break

            if max_results is not None and len(all_papers) >= max_results:
                break

            current_start += batch_size

            if len(papers) < batch_size:
                break

        self._log(f"Found {len(all_papers)} papers by {author_name} after date filtering")
        return all_papers[:max_results] if max_results else all_papers

    def download_pdf(self, arxiv_id: str, output_path: str) -> bool:
        """Download the PDF of a paper.

        Args:
            arxiv_id: The arXiv ID of the paper
            output_path: Path where PDF should be saved

        Returns:
            True if download successful, False otherwise
        """
        # Clean arXiv ID
        if 'arxiv.org' in arxiv_id:
            arxiv_id = arxiv_id.split("/")[-1]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        self._log(f"Downloading PDF from: {pdf_url}")

        try:
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            self._log(f"PDF saved to: {output_path}")
            # Respect rate limit after download
            time.sleep(3)
            return True
        except Exception as e:
            self._log(f"Error downloading PDF: {e}")
            return False

    def format_result(self, paper: Dict, include_abstract: bool = True) -> Dict:
        """Format a paper result with standardized fields.

        Args:
            paper: Raw paper dictionary from API
            include_abstract: Whether to include the abstract

        Returns:
            Formatted paper dictionary
        """
        result = {
            "arxiv_id": paper.get("arxiv_id", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "author_corresponding": paper.get("author_corresponding", ""),
            "author_corresponding_institution": paper.get("author_corresponding_institution", ""),
            "date": paper.get("date", ""),
            "updated": paper.get("updated", ""),
            "version": paper.get("version", ""),
            "type": paper.get("type", ""),
            "license": paper.get("license", ""),
            "category": paper.get("category", ""),
            "categories": paper.get("categories", []),
            "jatsxml": paper.get("jatsxml", ""),
            "comment": paper.get("comment", ""),
            "published": paper.get("published", "")
        }

        if include_abstract:
            result["abstract"] = paper.get("abstract", "")

        # Ensure URLs are present
        arxiv_id = result["arxiv_id"]
        if arxiv_id:
            result["pdf_url"] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            result["html_url"] = f"https://arxiv.org/abs/{arxiv_id}"

        return result


def main():
    """Command-line interface for arXiv search."""
    parser = argparse.ArgumentParser(
        description="Search arXiv preprints efficiently",
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
    search_group.add_argument("--id",
                            help="Get details for specific arXiv ID")

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
                            choices=ArxivSearcher.CATEGORIES,
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
                            help="Download PDF to specified path (requires --id)")
    output_group.add_argument("--limit", type=int,
                            help="Limit number of results")

    args = parser.parse_args()

    # Initialize searcher
    searcher = ArxivSearcher(verbose=args.verbose)

    # Handle date range
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if args.days_back:
        start_date = (datetime.now() - timedelta(days=args.days_back)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # Execute search based on arguments
    results = []

    if args.download_pdf:
        if not args.id:
            print("Error: --id required with --download-pdf", file=sys.stderr)
            return 1

        success = searcher.download_pdf(args.id, args.download_pdf)
        return 0 if success else 1

    elif args.id:
        # Get specific paper by arXiv ID
        paper = searcher.get_paper_details(args.id)
        if paper:
            results = [paper]

    elif args.author:
        # Search by author
        results = searcher.search_by_author(
            args.author, start_date, end_date, args.limit
        )

    elif args.keywords:
        # Search by keywords
        # Only apply date filter if user explicitly specified one
        kw_start = start_date if (args.start_date or args.days_back) else None
        kw_end = end_date if (args.start_date or args.days_back or args.end_date) else None

        results = searcher.search_by_keywords(
            args.keywords, kw_start, kw_end,
            args.category, args.search_fields, args.limit
        )

    else:
        # Date range search (search all in category or all papers)
        query = f"cat:{args.category}" if args.category else "all:*"

        per_page = 100
        total_limit = args.limit if args.limit else 1000
        current_start = 0

        while current_start < total_limit:
            batch_size = min(per_page, total_limit - current_start)
            papers = searcher.search_by_query(
                query=query,
                start=current_start,
                max_results=batch_size,
                sort_by="submittedDate",
                sort_order="descending"
            )

            if not papers:
                break

            for paper in papers:
                if start_date and paper.get("date", "") < start_date:
                    continue
                if end_date and paper.get("date", "") > end_date:
                    continue
                results.append(paper)
                if args.limit and len(results) >= args.limit:
                    break

            if args.limit and len(results) >= args.limit:
                break

            current_start += batch_size
            if len(papers) < batch_size:
                break

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
            "id": args.id,
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
