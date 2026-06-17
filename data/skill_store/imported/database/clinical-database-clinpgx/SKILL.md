---
name: clinical-database-clinpgx
description: "Query ClinPGx for pharmacogenomics data. Access clinical annotations, CPIC/DPWG guidelines, drug labels, pathways, gene-drug interactions, variant frequencies, and connected data for precision medicine and genotype-guided dosing decisions."
---

# ClinPGx Pharmacogenomics Database

## Overview

ClinPGx is a curated pharmacogenomics knowledgebase providing structured clinical annotations linking genetic variation to drug response, dosing guidelines, and drug labels. It integrates data from CPIC, DPWG, FDA, EMA, PMDA, HCSC, and peer-reviewed literature, serving as a clinical decision-support resource for pharmacogenomic implementation.

Use this skill when working with:
- Gene-drug interactions and clinical annotations
- CPIC and DPWG dosing guidelines
- Pharmacogenomic drug labels (FDA, EMA, PMDA, HCSC)
- Star allele interpretation and metabolizer phenotypes
- Drug-gene variant associations
- Variant frequency queries

**Key resources:**
- ClinPGx website: https://www.clinpgx.org/
- ClinPGx API: https://api.clinpgx.org/v1
- CPIC guidelines: https://cpicpgx.org/

## When to Use This Skill

This skill should be used when:

- **Gene-drug interactions**: Querying how genetic variants affect drug metabolism, efficacy, or toxicity
- **CPIC/DPWG guidelines**: Accessing evidence-based clinical practice guidelines for pharmacogenetics
- **Allele information**: Interpreting star allele function and phenotype data
- **Drug labels**: Exploring pharmacogenomic drug labeling from regulatory agencies
- **Clinical decision support**: Using curated annotations for genotype interpretation
- **Precision medicine**: Implementing pharmacogenomic testing in clinical practice
- **Drug metabolism**: Understanding CYP450 and other pharmacogene functions
- **Personalized dosing**: Finding genotype-guided dosing recommendations
- **Adverse drug reactions**: Identifying genetic risk factors for drug toxicity

## Installation and Setup

### Python API Access

The ClinPGx REST API provides programmatic access to all database resources. Basic setup:

```bash
uv pip install requests
```

### API Endpoint

```python
BASE_URL = "https://api.clinpgx.org/v1"
```

**Rate Limits**:
- Be respectful; add ~0.5s delay between requests for batch queries
- Excessive requests may result in HTTP 429 (Too Many Requests)

**Authentication**: Not required for basic access

**Data License**: See https://www.clinpgx.org/page/policies

## Core Capabilities

### 1. Gene Queries

**Retrieve gene information** including function and pharmacogenomic significance:

```python
import requests

# Get gene details (search by symbol first, then fetch by ID)
response = requests.get(
    "https://api.clinpgx.org/v1/data/gene",
    params={"symbol": "CYP2D6"},
    timeout=10
)
genes = response.json()['data']
gene_id = genes[0]['id']  # e.g., PA128
response = requests.get(f"https://api.clinpgx.org/v1/data/gene/{gene_id}", timeout=10)
gene_data = response.json()['data']
```

**Key pharmacogenes**:
- **CYP450 enzymes**: CYP2D6, CYP2C19, CYP2C9, CYP3A4, CYP3A5
- **Transporters**: SLCO1B1, ABCB1, ABCG2
- **Other metabolizers**: TPMT, DPYD, NUDT15, UGT1A1
- **Receptors**: OPRM1, HTR2A, ADRB1
- **HLA genes**: HLA-B, HLA-A

### 2. Drug and Chemical Queries

**Retrieve drug/chemical information** including pharmacogenomic annotations:

```python
# Get chemical details
response = requests.get(
    "https://api.clinpgx.org/v1/data/chemical/PA448515",  # Warfarin
    timeout=10
)
drug_data = response.json()['data']

# Search chemicals by name
response = requests.get(
    "https://api.clinpgx.org/v1/data/chemical",
    params={"name": "warfarin"},
    timeout=10
)
drugs = response.json()['data']
```

**Drug categories with pharmacogenomic significance**:
- Anticoagulants (warfarin, clopidogrel)
- Antidepressants (SSRIs, TCAs)
- Immunosuppressants (tacrolimus, azathioprine)
- Oncology drugs (5-fluorouracil, irinotecan, tamoxifen)
- Cardiovascular drugs (statins, beta-blockers)
- Pain medications (codeine, tramadol)
- Antivirals (abacavir)

### 3. Clinical Annotations

**Access curated gene-drug relationships** with evidence levels:

```python
# Get clinical annotations for a gene-drug pair
response = requests.get(
    "https://api.clinpgx.org/v1/data/clinicalAnnotation",
    params={
        "view": "base",
        "location.genes.symbol": "CYP2D6",
        "relatedChemicals.name": "codeine"
    },
    timeout=10
)
annotations = response.json()['data']

# Get all annotations for a gene
response = requests.get(
    "https://api.clinpgx.org/v1/data/clinicalAnnotation",
    params={"view": "base", "location.genes.symbol": "CYP2C19"},
    timeout=10
)
all_annotations = response.json()['data']

# Filter by evidence level
response = requests.get(
    "https://api.clinpgx.org/v1/data/clinicalAnnotation",
    params={
        "view": "base",
        "levelOfEvidence.term": "1A"
    },
    timeout=10
)
high_evidence = response.json()['data']
```

**Evidence levels** (from highest to lowest):
- **Level 1A**: High-quality evidence, CPIC/FDA/DPWG guidelines
- **Level 1B**: High-quality evidence, not yet guideline
- **Level 2A**: Moderate evidence from well-designed studies
- **Level 2B**: Moderate evidence with some limitations
- **Level 3**: Limited evidence
- **Level 4**: Case reports or weak evidence

**Clinical annotation sources**:
- CPIC (Clinical Pharmacogenetics Implementation Consortium)
- DPWG (Dutch Pharmacogenetics Working Group)
- FDA (Food and Drug Administration) labels
- Peer-reviewed literature summary annotations

### 4. Guideline Annotations

**Access clinical practice guidelines** directly via the dedicated endpoint:

```python
# Get CPIC guidelines for a gene-drug pair
response = requests.get(
    "https://api.clinpgx.org/v1/data/guidelineAnnotation",
    params={
        "view": "base",
        "source": "cpic",
        "relatedGenes.accessionId": "PA128"  # CYP2D6
    },
    timeout=10
)
guidelines = response.json()['data']

# Get all DPWG guidelines
response = requests.get(
    "https://api.clinpgx.org/v1/data/guidelineAnnotation",
    params={"view": "base", "source": "dpwg"},
    timeout=10
)
dpwg_guidelines = response.json()['data']
```

**Guideline sources**:
- `cpic`: Clinical Pharmacogenetics Implementation Consortium
- `dpwg`: Dutch Pharmacogenetics Working Group
- `pro`: Professional guidelines

**Guideline components**:
- Gene-drug pairs covered
- Clinical recommendations by phenotype
- Evidence levels and strength ratings
- Supporting literature
- Implementation considerations

**Example guideline pairs**:
- CYP2D6-codeine (avoid in ultra-rapid metabolizers)
- CYP2C19-clopidogrel (alternative therapy for poor metabolizers)
- TPMT-azathioprine (dose reduction for intermediate/poor metabolizers)
- DPYD-fluoropyrimidines (dose adjustment based on activity)
- HLA-B*57:01-abacavir (avoid if positive)

### 5. Variant Information

**Query variants by rsID**:

```python
# Get variants by rsID
response = requests.get(
    "https://api.clinpgx.org/v1/data/variant/",
    params={"symbol": "rs4244285"},
    timeout=10
)
variant_data = response.json()['data']
```

**Variant data includes**:
- rsID and genomic coordinates
- Gene and functional consequence
- Allele associations
- Clinical significance
- Population frequencies
- Literature references

### 6. Variant Annotations

**Access clinical annotations for specific genetic variants**:

```python
# Get variant annotations by gene or variant fingerprint
response = requests.get(
    "https://api.clinpgx.org/v1/data/variantAnnotation",
    params={
        "relatedChemicals.name": "warfarin",
        "location.genes.symbol": "VKORC1"
    },
    timeout=10
)
annotations = response.json()['data']

# Get variant annotations by rsID
response = requests.get(
    "https://api.clinpgx.org/v1/data/variantAnnotation",
    params={"location.fingerprint": "rs4244285"},
    timeout=10
)
variant_anns = response.json()['data']
```

### 7. Drug Labels

**Access pharmacogenomic information from drug labels**:

```python
# Get drug labels with PGx information
response = requests.get(
    "https://api.clinpgx.org/v1/data/label",
    params={"relatedChemicals.name": "warfarin"},
    timeout=10
)
labels = response.json()['data']

# Filter by regulatory source
response = requests.get(
    "https://api.clinpgx.org/v1/data/label",
    params={"source": "FDA"},
    timeout=10
)
fda_labels = response.json()['data']
```

**Label sources**:
- `fda`: U.S. Food and Drug Administration
- `ema`: European Medicines Agency
- `pmda`: Pharmaceuticals and Medical Devices Agency (Japan)
- `hcsc`: Health Canada / Santé Canada

**Label information includes**:
- Testing recommendations
- Dosing guidance by genotype
- Warnings and precautions
- Biomarker information
- Regulatory source

### 8. Pathways

**Explore pharmacokinetic and pharmacodynamic pathways**:

```python
# Get pathway information
response = requests.get(
    "https://api.clinpgx.org/v1/data/pathway/PA146123006",  # Warfarin pathway
    timeout=10
)
pathway_data = response.json()['data']

# Search pathways by name
response = requests.get(
    "https://api.clinpgx.org/v1/data/pathway",
    params={"name": "warfarin"},
    timeout=10
)
pathways = response.json()['data']
```

**Pathway diagrams** show:
- Drug metabolism steps
- Enzymes and transporters involved
- Gene variants affecting each step
- Downstream effects on efficacy/toxicity
- Interactions with other pathways

### 9. Report Endpoints

**Use helper queries for connected data**:

```python
# Find connections between two objects
response = requests.get(
    "https://api.clinpgx.org/v1/report/pair/PA128/PA448515/clinicalAnnotation",
    timeout=10
)
connections = response.json()['data']

# Get connected objects for an entity
response = requests.get(
    "https://api.clinpgx.org/v1/report/connectedObjects/PA128/clinicalAnnotation",
    timeout=10
)
connected = response.json()['data']

# Query variant frequency by rsID
response = requests.get(
    "https://api.clinpgx.org/v1/report/variantFrequency",
    params={"fp": "rs4244285"},
    timeout=10
)
freq_data = response.json()['data']

# Look up literature by PMID
response = requests.get(
    "https://api.clinpgx.org/v1/report/literatureId/19512959",
    timeout=10
)
lit_data = response.json()['data']
```

**Report endpoint types**:
- `/report/pair/{id1}/{id2}/{resultType}` - Find connections between two objects (resultType: variantAnnotation, clinicalAnnotation, literatureAnnotation, multilinkAnnotation, pathway, guidelineAnnotation, label, vip, vipVariant)
- `/report/connectedObjects/{id}/{type}` - Get all connected objects of a given type
- `/report/variantFrequency` - Query variant frequencies
- `/report/literatureId/{pmid}` - Look up literature by PubMed ID
- `/report/crossReference` - Get cross-references for an object
- `/report/stats` - Get database statistics

### 10. Data Connections

**Query relationships between entities**:

```python
# Find connections between a gene and a chemical
response = requests.get(
    "https://api.clinpgx.org/v1/data/connection",
    params={
        "object1Type": "Gene",
        "object1Id": "PA128",
        "object2Type": "Chemical",
        "object2Id": "PA448515"
    },
    timeout=10
)
connections = response.json()['data']
```

## Query Workflow

### Workflow 1: Clinical Decision Support for Drug Prescription

1. **Identify patient genotype** for relevant pharmacogenes.
2. **Query clinical annotations** for the medication of interest:
   ```python
   response = requests.get(
       "https://api.clinpgx.org/v1/data/clinicalAnnotation",
       params={
           "view": "base",
           "location.genes.symbol": "CYP2C19",
           "relatedChemicals.name": "clopidogrel"
       },
       timeout=10
   )
   annotations = response.json()['data']
   ```
3. **Retrieve guideline annotations** for dosing recommendations:
   ```python
   response = requests.get(
       "https://api.clinpgx.org/v1/data/guidelineAnnotation",
       params={
           "view": "base",
           "source": "cpic",
           "relatedGenes.accessionId": "PA124"  # CYP2C19
       },
       timeout=10
   )
   guidelines = response.json()['data']
   ```
4. **Check drug label** for regulatory guidance.

### Workflow 2: Gene Panel Analysis

1. **Get list of pharmacogenes** in clinical panel:
   ```python
   pgx_panel = ["CYP2C19", "CYP2D6", "CYP2C9", "TPMT", "DPYD", "SLCO1B1"]
   ```
2. **For each gene, retrieve clinical annotations**:
   ```python
   all_annotations = {}
   for gene in pgx_panel:
       response = requests.get(
           "https://api.clinpgx.org/v1/data/clinicalAnnotation",
           params={"view": "base", "location.genes.symbol": gene},
           timeout=10
       )
       all_annotations[gene] = response.json()['data']
   ```
3. **Filter for guideline-level evidence**:
   ```python
   for gene, anns in all_annotations.items():
       for ann in anns:
           level = ann.get('levelOfEvidence', {})
           level_term = level.get('term', '') if isinstance(level, dict) else str(level)
           if level_term.startswith('1'):
               related_chemicals = ann.get('relatedChemicals', [])
               drug = related_chemicals[0].get('name', 'Unknown') if related_chemicals else 'Unknown'
               print(f"{gene} - {drug}: {level_term}")
   ```
4. **Generate patient report** with actionable findings.

### Workflow 3: Drug Safety Assessment

1. **Query drug for PGx associations**:
   ```python
   response = requests.get(
       "https://api.clinpgx.org/v1/data/chemical",
       params={"name": "abacavir"},
       timeout=10
   )
   drug_info = response.json()['data']
   ```
2. **Get clinical annotations**:
   ```python
   response = requests.get(
       "https://api.clinpgx.org/v1/data/clinicalAnnotation",
       params={"view": "base", "relatedChemicals.name": "abacavir"},
       timeout=10
   )
   annotations = response.json()['data']
   ```
3. **Check for HLA associations** and toxicity risk:
   ```python
   for ann in annotations:
       genes = [g.get('symbol', '') for g in ann.get('location', {}).get('genes', [])]
       if any('HLA' in g for g in genes):
           print(f"Toxicity risk annotation found: {ann.get('phenotypes', [])}")
   ```
4. **Retrieve screening recommendations** from guidelines and labels.

### Workflow 4: Star Allele Interpretation

ClinPGx and CPIC define activity scores for CYP star alleles:

```python
CYP2D6_ACTIVITY = {
    '*1': 1.0,   # Normal
    '*2': 1.0,   # Normal
    '*3': 0.0,   # No function
    '*4': 0.0,   # No function
    '*5': 0.0,   # Gene deletion
    '*10': 0.25, # Decreased function
    '*17': 0.5,  # Decreased function
    '*41': 0.5,  # Decreased function
}

def get_metabolizer_status(score):
    if score == 0:
        return 'Poor Metabolizer (PM)'
    elif score <= 1.25:
        return 'Intermediate Metabolizer (IM)'
    elif score <= 2.25:
        return 'Normal Metabolizer (NM)'
    else:
        return 'Ultrarapid Metabolizer (UM)'

score = CYP2D6_ACTIVITY.get('*1', 1.0) + CYP2D6_ACTIVITY.get('*4', 0.0)
print(get_metabolizer_status(score))
```

### Workflow 5: Literature Evidence Review

1. **Search for gene-drug clinical annotations**:
   ```python
   response = requests.get(
       "https://api.clinpgx.org/v1/data/clinicalAnnotation",
       params={
           "view": "base",
           "location.genes.symbol": "TPMT",
           "relatedChemicals.name": "azathioprine"
       },
       timeout=10
   )
   annotations = response.json()['data']
   ```
2. **Filter by evidence level**:
   ```python
   def get_level(ann):
       level = ann.get('levelOfEvidence', {})
       return level.get('term', '') if isinstance(level, dict) else str(level)

   high_quality = [a for a in annotations
                   if get_level(a) in ['1A', '1B', '2A']]
   ```
3. **Extract PMIDs** and retrieve full references:
   ```python
   pmids = [a.get('pmid') for a in high_quality if a.get('pmid')]
   ```

## Rate Limiting and Best Practices

### Rate Limit Compliance

```python
import time

def rate_limited_request(url, params=None, delay=0.5):
    """Make API request with rate limiting"""
    response = requests.get(url, params=params, timeout=10)
    time.sleep(delay)
    return response

# Use in loops
genes = ["CYP2D6", "CYP2C19", "CYP2C9"]
for gene in genes:
    response = rate_limited_request(
        f"https://api.clinpgx.org/v1/data/gene/{gene}"
    )
    data = response.json()
```

### Error Handling

```python
def safe_api_call(url, params=None, max_retries=3):
    """API call with error handling and retries"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
```

### Caching Results

```python
import json
from pathlib import Path

def cached_query(cache_file, api_func, *args, **kwargs):
    """Cache API results to avoid repeated queries"""
    cache_path = Path(cache_file)

    if cache_path.exists():
        with open(cache_file) as f:
            return json.load(f)

    result = api_func(*args, **kwargs)

    with open(cache_file, 'w') as f:
        json.dump(result, f, indent=2)

    return result
```

## Resources

### scripts/query_clinpgx.py

Python script with ready-to-use functions for common queries:

- `get_gene_info(gene_symbol)` - Retrieve gene details (searches by symbol, fetches by ID)
- `get_chemical_info(name)` - Get chemical/drug information
- `get_gene_drug_pairs(gene, drug)` - Query gene-drug clinical annotations
- `get_guideline_annotations(source, gene_id, chemical_id)` - Query guideline annotations (CPIC/DPWG/pro)
- `get_clinical_annotations(gene, drug, evidence_level)` - Query clinical annotations with optional evidence filtering
- `get_drug_labels(drug, source)` - Retrieve pharmacogenomic drug labels (FDA/EMA/PMDA/HCSC)
- `search_variants(rsid)` - Search by variant rsID
- `get_variant_annotations(gene, rsid)` - Get variant annotations
- `get_pathway_info(pathway_id, name)` - Retrieve pathway information
- `get_pair_connections(first_id, second_id, result_type)` - Find connections between two objects
- `get_connected_objects(obj_id, obj_type)` - Get connected objects
- `get_variant_frequency(rsid)` - Query variant frequency
- `get_literature_by_pmid(pmid)` - Look up literature by PubMed ID
- `export_to_dataframe(data)` - Convert results to pandas DataFrame

Consult this script for implementation examples with proper rate limiting and error handling.

### references/api_reference.md

Comprehensive API documentation including:

- Complete endpoint listing with parameters
- Request/response format specifications
- Example queries for each endpoint
- Filter operators and search patterns
- Data schema definitions
- Rate limiting details
- Troubleshooting common errors

## Important Notes

### Data Sources and Integration

ClinPGx consolidates multiple authoritative sources:
- **CPIC**: Evidence-based clinical implementation guidelines
- **DPWG**: Dutch Pharmacogenetics Working Group guidelines
- **FDA/EMA/PMDA/HCSC labels**: Regulatory pharmacogenomic information
- **Peer-reviewed literature**: Curated clinical annotations

### Clinical Implementation Considerations

- **Evidence levels**: Always check evidence strength before clinical application
- **Population differences**: Allele frequencies vary significantly across populations
- **Phenoconversion**: Consider drug-drug interactions that affect enzyme activity
- **Multi-gene effects**: Some drugs affected by multiple pharmacogenes
- **Non-genetic factors**: Age, organ function, drug interactions also affect response
- **Testing limitations**: Not all clinically relevant alleles detected by all assays

### Data Updates

- ClinPGx continuously updates with new evidence and guidelines
- Check publication dates for clinical annotations
- Monitor ClinPGx website for announcements
- CPIC guidelines updated as new evidence emerges

### API Stability

- ClinPGx API endpoints are relatively stable
- Parameters and response formats subject to modification
- Consider version pinning for production applications
- Test API changes in development before production deployment

## Common Use Cases

### Pre-emptive Pharmacogenomic Testing

Query all clinically actionable gene-drug pairs to guide panel selection:

```python
response = requests.get(
    "https://api.clinpgx.org/v1/data/clinicalAnnotation",
    params={"view": "base"},
    timeout=10
)
all_annotations = response.json()['data']
actionable_pairs = [
    a for a in all_annotations
    if (a.get('levelOfEvidence', {}).get('term', '') if isinstance(a.get('levelOfEvidence'), dict) else str(a.get('levelOfEvidence', ''))).startswith('1')
]
```

### Medication Therapy Management

Review patient medications against known genotypes:

```python
patient_genes = {"CYP2C19": "*1/*2", "CYP2D6": "*1/*1", "SLCO1B1": "*1/*5"}
medications = ["clopidogrel", "simvastatin", "escitalopram"]

for med in medications:
    for gene in patient_genes:
        response = requests.get(
            "https://api.clinpgx.org/v1/data/clinicalAnnotation",
            params={
                "view": "base",
                "location.genes.symbol": gene,
                "relatedChemicals.name": med
            },
            timeout=10
        )
        annotations = response.json()['data']
```

### Clinical Trial Eligibility

Screen for pharmacogenomic contraindications:

```python
# Check for HLA-B*57:01 before abacavir trial
response = requests.get(
    "https://api.clinpgx.org/v1/data/clinicalAnnotation",
    params={
        "view": "base",
        "location.genes.symbol": "HLA-B",
        "relatedChemicals.name": "abacavir"
    },
    timeout=10
)
annotations = response.json()['data']
```

## Additional Resources

- **ClinPGx website**: https://www.clinpgx.org/
- **CPIC website**: https://cpicpgx.org/
- **PharmVar**: https://www.pharmvar.org/
- **ClinGen**: https://clinicalgenome.org/
- **FDA Table of Pharmacogenomic Biomarkers**: https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling
