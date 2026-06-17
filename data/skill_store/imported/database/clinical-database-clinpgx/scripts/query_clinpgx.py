#!/usr/bin/env python3
"""
ClinPGx API Query Helper Script

Provides ready-to-use functions for querying pharmacogenomics data via
the ClinPGx public REST API. ClinPGx is a curated pharmacogenomics
knowledgebase integrating CPIC, DPWG, FDA, EMA, PMDA, HCSC, and
peer-reviewed literature.

ClinPGx API: https://api.clinpgx.org/v1
Rate limit: be respectful, add delays for batch queries
Terms: https://www.clinpgx.org/page/policies
"""

import requests
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# API Configuration
BASE_URL = "https://api.clinpgx.org/v1"
RATE_LIMIT_DELAY = 0.5  # 500ms delay between requests


def _rate_limited_get(url: str, params: Optional[Dict] = None,
                       delay: float = RATE_LIMIT_DELAY) -> requests.Response:
    """Make a GET request with rate limiting."""
    time.sleep(delay)
    response = requests.get(url, params=params, timeout=10)
    return response


def safe_api_call(url: str, params: Optional[Dict] = None,
                  max_retries: int = 3) -> Optional[Any]:
    """
    Make API call with error handling and exponential backoff retry.

    Args:
        url: API endpoint URL
        params: Query parameters
        max_retries: Maximum number of retry attempts

    Returns:
        JSON response data or None on failure
    """
    for attempt in range(max_retries):
        try:
            response = _rate_limited_get(url, params, delay=0.1)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limit exceeded. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            elif response.status_code == 404:
                print(f"Resource not found: {url}")
                return None
            else:
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                print(f"Failed after {max_retries} attempts")
                return None
            time.sleep(1)

    return None


def cached_query(cache_file: str, query_func, *args, **kwargs) -> Any:
    """
    Cache API results to avoid repeated queries.

    Args:
        cache_file: Path to cache file
        query_func: Function to call if cache miss
        *args, **kwargs: Arguments to pass to query_func

    Returns:
        Cached or freshly queried data
    """
    cache_path = Path(cache_file)

    if cache_path.exists():
        print(f"Loading from cache: {cache_file}")
        with open(cache_path) as f:
            return json.load(f)

    print("Cache miss. Querying API...")
    result = query_func(*args, **kwargs)

    if result is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Cached to: {cache_file}")

    return result


def _get_gene_id(gene_symbol: str) -> Optional[str]:
    """Search for a gene by symbol and return its ClinPGx accession ID."""
    url = f"{BASE_URL}/data/gene"
    params = {"symbol": gene_symbol}
    data = safe_api_call(url, params)
    if data and 'data' in data:
        for gene in data['data']:
            if gene.get('symbol', '').upper() == gene_symbol.upper():
                return gene.get('id')
    return None


def _get_chemical_id(chemical_name: str) -> Optional[str]:
    """Search for a chemical by name and return its ClinPGx accession ID."""
    url = f"{BASE_URL}/data/chemical"
    params = {"name": chemical_name}
    data = safe_api_call(url, params)
    if data and 'data' in data:
        for chem in data['data']:
            if chem.get('name', '').lower() == chemical_name.lower():
                return chem.get('id')
    return None


# Core Query Functions

def get_gene_info(gene_symbol: str) -> Optional[Dict]:
    """
    Retrieve detailed information about a pharmacogene.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2D6", "TPMT")

    Returns:
        Gene information dictionary
    """
    gene_id = _get_gene_id(gene_symbol)
    if not gene_id:
        print(f"Gene not found: {gene_symbol}")
        return None

    url = f"{BASE_URL}/data/gene/{gene_id}"
    data = safe_api_call(url)
    if data and 'data' in data:
        return data['data']
    return data


def get_chemical_info(name: str) -> Optional[List[Dict]]:
    """
    Search for chemical/drug information by name.

    Args:
        name: Chemical/drug name (e.g., "warfarin", "codeine")

    Returns:
        List of matching chemicals
    """
    url = f"{BASE_URL}/data/chemical"
    params = {"name": name}
    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def get_gene_drug_pairs(gene: Optional[str] = None,
                        drug: Optional[str] = None) -> Optional[List[Dict]]:
    """
    Query gene-drug interaction pairs via clinical annotations.

    Args:
        gene: Gene symbol (optional)
        drug: Drug name (optional)

    Returns:
        List of gene-drug pairs with clinical annotations
    """
    url = f"{BASE_URL}/data/clinicalAnnotation"
    params: Dict[str, str] = {"view": "base"}
    if gene:
        params["location.genes.symbol"] = gene
    if drug:
        params["relatedChemicals.name"] = drug

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def get_guideline_annotations(
    source: Optional[str] = None,
    gene_id: Optional[str] = None,
    chemical_id: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Retrieve clinical practice guideline annotations.

    Args:
        source: Guideline source - 'cpic', 'dpwg', or 'pro' (optional)
        gene_id: ClinPGx gene accession ID (optional)
        chemical_id: ClinPGx chemical accession ID (optional)

    Returns:
        List of guideline annotations
    """
    url = f"{BASE_URL}/data/guidelineAnnotation"
    params: Dict[str, str] = {"view": "base"}
    if source:
        params["source"] = source
    if gene_id:
        params["relatedGenes.accessionId"] = gene_id
    if chemical_id:
        params["relatedChemicals.accessionId"] = chemical_id

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def get_clinical_annotations(
    gene: Optional[str] = None,
    drug: Optional[str] = None,
    evidence_level: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Retrieve curated clinical annotations for gene-drug interactions.

    Args:
        gene: Gene symbol (optional)
        drug: Drug name (optional)
        evidence_level: Filter by evidence level (1A, 1B, 2A, 2B, 3, 4)

    Returns:
        List of clinical annotations
    """
    url = f"{BASE_URL}/data/clinicalAnnotation"
    params: Dict[str, str] = {"view": "base"}
    if gene:
        params["location.genes.symbol"] = gene
    if drug:
        params["relatedChemicals.name"] = drug

    data = safe_api_call(url, params)
    if not data or 'data' not in data:
        return data

    annotations = data['data']
    if evidence_level:
        annotations = [
            a for a in annotations
            if (a.get('levelOfEvidence', {}).get('term')
                if isinstance(a.get('levelOfEvidence'), dict)
                else a.get('levelOfEvidence', '')) == evidence_level
        ]
    return annotations


def get_drug_labels(
    drug: Optional[str] = None,
    source: Optional[str] = None,
    gene: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Retrieve pharmacogenomic drug label information.

    Args:
        drug: Drug/chemical name (optional)
        source: Regulatory source - 'fda', 'ema', 'pmda', or 'hcsc' (optional)
        gene: Gene symbol (optional)

    Returns:
        List of drug labels with PGx information
    """
    url = f"{BASE_URL}/data/label"
    params: Dict[str, str] = {"view": "base"}
    if drug:
        params["relatedChemicals.name"] = drug
    if source:
        params["source"] = source
    if gene:
        params["relatedGenes.symbol"] = gene

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def search_variants(rsid: Optional[str] = None,
                    gene: Optional[str] = None) -> Optional[Any]:
    """
    Search for genetic variants by rsID or gene.

    Args:
        rsid: dbSNP rsID (e.g., "rs4244285")
        gene: Gene symbol to filter by (uses variantAnnotation endpoint)

    Returns:
        Variant information or list of variants
    """
    if rsid:
        url = f"{BASE_URL}/data/variant/"
        params: Dict[str, str] = {"symbol": rsid}
        data = safe_api_call(url, params)
        if data and 'data' in data:
            return data['data']
        return data

    if gene:
        # Use variantAnnotation endpoint for gene-based variant lookup
        url = f"{BASE_URL}/data/variantAnnotation"
        params = {"location.genes.symbol": gene}
        data = safe_api_call(url, params)
        if data and 'data' in data:
            return data['data']
        return data

    return None


def get_variant_annotations(
    gene: Optional[str] = None,
    rsid: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Retrieve variant annotations for a gene or specific variant.

    Args:
        gene: Gene symbol (optional)
        rsid: Variant rsID/fingerprint (optional)

    Returns:
        List of variant annotations
    """
    url = f"{BASE_URL}/data/variantAnnotation"
    params: Dict[str, str] = {"view": "base"}
    if gene:
        params["location.genes.symbol"] = gene
    if rsid:
        params["location.fingerprint"] = rsid

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def get_pathway_info(pathway_id: Optional[str] = None,
                     name: Optional[str] = None) -> Optional[Any]:
    """
    Retrieve pharmacokinetic/pharmacodynamic pathway information.

    Args:
        pathway_id: ClinPGx pathway ID (optional)
        name: Pathway name to search (optional)

    Returns:
        Pathway information or list of pathways
    """
    if pathway_id:
        url = f"{BASE_URL}/data/pathway/{pathway_id}"
        data = safe_api_call(url)
        if data and 'data' in data:
            return data['data']
        return data

    url = f"{BASE_URL}/data/pathway"
    params: Dict[str, str] = {}
    if name:
        params["name"] = name

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


# Report Endpoints

def get_pair_connections(
    first_id: str,
    second_id: str,
    result_type: str = "clinicalAnnotation"
) -> Optional[Any]:
    """
    Find connections between two objects via the report/pair endpoint.

    Args:
        first_id: First object ClinPGx ID (PA# or numeric)
        second_id: Second object ClinPGx ID (PA# or numeric)
        result_type: Type of connecting objects (variantAnnotation,
                     clinicalAnnotation, literatureAnnotation,
                     multilinkAnnotation, pathway, guidelineAnnotation,
                     label, vip, vipVariant)

    Returns:
        List of connecting objects
    """
    url = f"{BASE_URL}/report/pair/{first_id}/{second_id}/{result_type}"
    data = safe_api_call(url)
    if data and 'data' in data:
        return data['data']
    return data


def get_connected_objects(
    obj_id: str,
    obj_type: str
) -> Optional[Any]:
    """
    Get all connected objects of a given type for an entity.

    Args:
        obj_id: Object ClinPGx ID
        obj_type: Type of connected objects to search for

    Returns:
        List of connected objects
    """
    url = f"{BASE_URL}/report/connectedObjects/{obj_id}/{obj_type}"
    data = safe_api_call(url)
    if data and 'data' in data:
        return data['data']
    return data


def get_variant_frequency(rsid: str) -> Optional[Any]:
    """
    Query variant frequency data by rsID.

    Args:
        rsid: Variant rsID (e.g., "rs4244285")

    Returns:
        Variant frequency data
    """
    url = f"{BASE_URL}/report/variantFrequency"
    params = {"fp": rsid}
    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


def get_literature_by_pmid(pmid: str) -> Optional[Any]:
    """
    Look up ClinPGx literature records by PubMed ID.

    Args:
        pmid: PubMed ID

    Returns:
        Literature record data
    """
    url = f"{BASE_URL}/report/literatureId/{pmid}"
    data = safe_api_call(url)
    if data and 'data' in data:
        return data['data']
    return data


def get_cross_references(
    obj_type: str,
    acc_id: str,
    resource: Optional[str] = None
) -> Optional[Any]:
    """
    Get cross-references for an object.

    Args:
        obj_type: Type of object (e.g., 'Gene', 'Chemical')
        acc_id: Object accession ID
        resource: External resource name (optional)

    Returns:
        List of cross-references
    """
    url = f"{BASE_URL}/report/crossReference"
    params: Dict[str, str] = {"type": obj_type, "accId": acc_id}
    if resource:
        params["resource"] = resource

    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


# Data Connection Queries

def get_data_connections(
    obj1_type: str,
    obj1_id: str,
    obj2_type: str,
    obj2_id: str
) -> Optional[Any]:
    """
    Query direct connections between two objects.

    Args:
        obj1_type: Type of first object (e.g., 'Gene', 'Chemical')
        obj1_id: ID of first object
        obj2_type: Type of second object
        obj2_id: ID of second object

    Returns:
        Connection data
    """
    url = f"{BASE_URL}/data/connection"
    params = {
        "object1Type": obj1_type,
        "object1Id": obj1_id,
        "object2Type": obj2_type,
        "object2Id": obj2_id
    }
    data = safe_api_call(url, params)
    if data and 'data' in data:
        return data['data']
    return data


# Utility Functions

def export_to_dataframe(data: List[Dict], output_file: Optional[str] = None):
    """
    Convert API results to pandas DataFrame for analysis.

    Args:
        data: List of dictionaries from API
        output_file: Optional CSV output file path

    Returns:
        pandas DataFrame
    """
    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed. Install with: pip install pandas")
        return None

    df = pd.DataFrame(data)

    if output_file:
        df.to_csv(output_file, index=False)
        print(f"Data exported to: {output_file}")

    return df


def batch_gene_query(gene_list: List[str], delay: float = 0.5) -> Dict[str, Dict]:
    """
    Query multiple genes in batch with rate limiting.

    Args:
        gene_list: List of gene symbols
        delay: Delay between requests (default 0.5s)

    Returns:
        Dictionary mapping gene symbols to gene data
    """
    results = {}
    print(f"Querying {len(gene_list)} genes with {delay}s delay between requests...")

    for gene in gene_list:
        print(f"Fetching: {gene}")
        data = get_gene_info(gene)
        if data:
            results[gene] = data
        time.sleep(delay)

    print(f"Completed: {len(results)}/{len(gene_list)} successful")
    return results


def find_actionable_gene_drug_pairs() -> Optional[List[Dict]]:
    """
    Find clinically actionable gene-drug pairs (level 1A/1B).

    Returns:
        List of actionable gene-drug pairs from clinical annotations
    """
    url = f"{BASE_URL}/data/clinicalAnnotation"
    params = {"view": "base"}
    data = safe_api_call(url, params)
    if not data or 'data' not in data:
        return data

    actionable = []
    for ann in data['data']:
        level = ann.get('levelOfEvidence', {})
        level_term = level.get('term', '') if isinstance(level, dict) else str(level)
        if level_term.startswith('1'):
            actionable.append(ann)
    return actionable


# Example Usage
if __name__ == "__main__":
    print("ClinPGx API Query Examples\n")

    # Example 1: Get gene information
    print("=" * 60)
    print("Example 1: Get CYP2D6 gene information")
    print("=" * 60)
    cyp2d6 = get_gene_info("CYP2D6")
    if cyp2d6:
        print(f"Gene: {cyp2d6.get('symbol')}")
        print(f"Name: {cyp2d6.get('name')}")
        print(f"ID: {cyp2d6.get('id')}")
        print()

    # Example 2: Search for a chemical
    print("=" * 60)
    print("Example 2: Search for warfarin")
    print("=" * 60)
    warfarin = get_chemical_info("warfarin")
    if warfarin:
        for chem in warfarin[:1]:
            print(f"Chemical: {chem.get('name')}")
            print(f"ID: {chem.get('id')}")
        print()

    # Example 3: Get gene-drug clinical annotations
    print("=" * 60)
    print("Example 3: Get CYP2C19-clopidogrel clinical annotations")
    print("=" * 60)
    pair = get_gene_drug_pairs(gene="CYP2C19", drug="clopidogrel")
    if pair:
        print(f"Found {len(pair)} clinical annotation(s)")
        if len(pair) > 0:
            ann = pair[0]
            gene = ann.get('location', {}).get('genes', [{}])[0].get('symbol', 'N/A')
            related_chemicals = ann.get('relatedChemicals', [])
            drug = related_chemicals[0].get('name', 'N/A') if related_chemicals else 'N/A'
            level = ann.get('levelOfEvidence', 'N/A')
            level_str = level.get('term', 'N/A') if isinstance(level, dict) else level
            print(f"  {gene} + {drug}: Level {level_str}")
        print()

    # Example 4: Get guideline annotations
    print("=" * 60)
    print("Example 4: Get CPIC guideline annotations for CYP2D6")
    print("=" * 60)
    guidelines = get_guideline_annotations(source="cpic", gene_id="PA128")
    if guidelines:
        print(f"Found {len(guidelines)} guideline annotation(s)")
        for g in guidelines[:2]:
            print(f"  - {g.get('name')}")
    else:
        print("No guideline annotations found")
    print()

    # Example 5: Get clinical annotations for a gene
    print("=" * 60)
    print("Example 5: Get CYP2D6 clinical annotations")
    print("=" * 60)
    annotations = get_clinical_annotations(gene="CYP2D6")
    if annotations:
        print(f"Found {len(annotations)} annotation(s)")
        for ann in annotations[:3]:
            gene = ann.get('location', {}).get('genes', [{}])[0].get('symbol', 'N/A')
            related_chemicals = ann.get('relatedChemicals', [])
            drug = related_chemicals[0].get('name', 'N/A') if related_chemicals else 'N/A'
            level = ann.get('levelOfEvidence', 'N/A')
            level_str = level.get('term', 'N/A') if isinstance(level, dict) else level
            print(f"  - {gene} + {drug}: Level {level_str}")
        print()

    # Example 6: Search for a variant
    print("=" * 60)
    print("Example 6: Search for variant rs4244285")
    print("=" * 60)
    variant = search_variants(rsid="rs4244285")
    if variant:
        if isinstance(variant, list):
            for v in variant[:1]:
                print(f"Variant: {v.get('symbol')}")
                print(f"Type: {v.get('type')}")
        else:
            print(f"Variant: {variant.get('symbol')}")
    print()

    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
