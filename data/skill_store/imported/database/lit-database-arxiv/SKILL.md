---
name: lit-database-arxiv
description: Efficient database search tool for arXiv preprint server. Use this skill when searching for preprints in physics, mathematics, computer science, quantitative biology, finance, statistics, and electrical engineering by keywords, authors, date ranges, or categories, retrieving paper metadata, downloading PDFs, or conducting literature reviews.
---

# arXiv Database

## Overview

This skill provides efficient Python-based tools for searching and retrieving preprints from the arXiv database. It enables comprehensive searches by keywords, authors, date ranges, and categories, returning structured JSON metadata that includes titles, abstracts, arXiv IDs, and citation information. The skill also supports PDF downloads for full-text analysis.

## When to Use This Skill

Use this skill when:
- Searching for recent preprints in physics, mathematics, computer science, or quantitative biology
- Tracking publications by particular authors
- Conducting systematic literature reviews
- Analyzing research trends over time periods
- Retrieving metadata for citation management
- Downloading preprint PDFs for analysis
- Filtering papers by arXiv subject categories

## Core Search Capabilities

### 1. Keyword Search

Search for preprints containing specific keywords in titles, abstracts, or author lists.

**Basic Usage:**
```python
python scripts/arxiv_search.py \
  --keywords "neural networks" "deep learning" \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output results.json
```

**With Category Filter:**
```python
python scripts/arxiv_search.py \
  --keywords "transformer" "attention mechanism" \
  --days-back 180 \
  --category cs.CL \
  --output recent_nlp.json
```

**Search Fields:**
By default, keywords are searched in both title and abstract. Customize with `--search-fields`:
```python
python scripts/arxiv_search.py \
  --keywords "GPT" \
  --search-fields title \
  --days-back 365
```

### 2. Author Search

Find all papers by a specific author within a date range.

**Basic Usage:**
```python
python scripts/arxiv_search.py \
  --author "Yann LeCun" \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --output lecun_papers.json
```

**Recent Publications:**
```python
# Last year by default if no dates specified
python scripts/arxiv_search.py \
  --author "Geoffrey Hinton" \
  --output hinton_recent.json
```

### 3. Date Range Search

Retrieve all preprints posted within a specific date range.

**Basic Usage:**
```python
python scripts/arxiv_search.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --output january_2024.json
```

**With Category Filter:**
```python
python scripts/arxiv_search.py \
  --start-date 2024-06-01 \
  --end-date 2024-06-30 \
  --category physics.gen-ph \
  --output physics_june.json
```

**Days Back Shortcut:**
```python
# Last 30 days
python scripts/arxiv_search.py \
  --days-back 30 \
  --output last_month.json
```

### 4. Paper Details by arXiv ID

Retrieve detailed metadata for a specific preprint.

**Basic Usage:**
```python
python scripts/arxiv_search.py \
  --id "2401.12345" \
  --output paper_details.json
```

**Full URLs Accepted:**
```python
python scripts/arxiv_search.py \
  --id "https://arxiv.org/abs/2401.12345"
```

### 5. PDF Downloads

Download the full-text PDF of any preprint.

**Basic Usage:**
```python
python scripts/arxiv_search.py \
  --id "2401.12345" \
  --download-pdf paper.pdf
```

**Batch Processing:**
For multiple PDFs, extract arXiv IDs from a search result JSON and download each paper:
```python
import json
from arxiv_search import ArxivSearcher

# Load search results
with open('results.json') as f:
    data = json.load(f)

searcher = ArxivSearcher(verbose=True)

# Download each paper
for i, paper in enumerate(data['results'][:10]):  # First 10 papers
    arxiv_id = paper['arxiv_id']
    searcher.download_pdf(arxiv_id, f"papers/paper_{i+1}.pdf")
```

## Valid Categories

Filter searches by arXiv subject categories:

**Computer Science:**
- `cs.AI` - Artificial Intelligence
- `cs.CL` - Computation and Language (NLP)
- `cs.CV` - Computer Vision and Pattern Recognition
- `cs.DB` - Databases
- `cs.DC` - Distributed, Parallel, and Cluster Computing
- `cs.DS` - Data Structures and Algorithms
- `cs.GT` - Computer Science and Game Theory
- `cs.HC` - Human-Computer Interaction
- `cs.IR` - Information Retrieval
- `cs.LG` - Machine Learning
- `cs.NE` - Neural and Evolutionary Computing
- `cs.RO` - Robotics
- `cs.SE` - Software Engineering

**Physics:**
- `physics.gen-ph` - General Physics
- `physics.bio-ph` - Biological Physics
- `physics.chem-ph` - Chemical Physics
- `physics.comp-ph` - Computational Physics
- `physics.data-an` - Data Analysis, Statistics and Probability
- `physics.med-ph` - Medical Physics
- `physics.soc-ph` - Physics and Society

**Quantitative Biology:**
- `q-bio.BM` - Biomolecules
- `q-bio.CB` - Cell Behavior
- `q-bio.GN` - Genomics
- `q-bio.MN` - Molecular Networks
- `q-bio.NC` - Neurons and Cognition
- `q-bio.OT` - Other Quantitative Biology
- `q-bio.PE` - Populations and Evolution
- `q-bio.QM` - Quantitative Methods
- `q-bio.SC` - Subcellular Processes
- `q-bio.TO` - Tissues and Organs

**Mathematics:**
- `math.AG` - Algebraic Geometry
- `math.AP` - Analysis of PDEs
- `math.AT` - Algebraic Topology
- `math.CO` - Combinatorics
- `math.CT` - Category Theory
- `math.DG` - Differential Geometry
- `math.DS` - Dynamical Systems
- `math.FA` - Functional Analysis
- `math.GM` - General Mathematics
- `math.GT` - Geometric Topology
- `math.IT` - Information Theory
- `math.LO` - Logic
- `math.MP` - Mathematical Physics
- `math.NA` - Numerical Analysis
- `math.NT` - Number Theory
- `math.OA` - Operator Algebras
- `math.OC` - Optimization and Control
- `math.PR` - Probability
- `math.QA` - Quantum Algebra
- `math.RA` - Rings and Algebras
- `math.RT` - Representation Theory
- `math.SP` - Spectral Theory
- `math.ST` - Statistics Theory

**Statistics:**
- `stat.AP` - Applications
- `stat.CO` - Computation
- `stat.ME` - Methodology
- `stat.ML` - Machine Learning
- `stat.OT` - Other Statistics
- `stat.TH` - Statistics Theory

**Electrical Engineering and Systems Science:**
- `eess.AS` - Audio and Speech Processing
- `eess.IV` - Image and Video Processing
- `eess.SP` - Signal Processing
- `eess.SY` - Systems and Control

**Economics:**
- `econ.EM` - Econometrics
- `econ.GN` - General Economics
- `econ.TH` - Theoretical Economics

## Output Format

All searches return structured JSON with the following format:

```json
{
  "query": {
    "keywords": ["neural networks"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "category": "cs.LG"
  },
  "result_count": 42,
  "results": [
    {
      "arxiv_id": "2401.12345",
      "title": "Paper Title Here",
      "authors": "Smith J, Doe J, Johnson A",
      "author_corresponding": "",
      "author_corresponding_institution": "",
      "date": "2024-01-15",
      "updated": "2024-03-20",
      "version": "",
      "type": "",
      "license": "",
      "category": "cs.LG",
      "categories": ["cs.LG", "cs.AI", "stat.ML"],
      "abstract": "Full abstract text...",
      "pdf_url": "https://arxiv.org/pdf/2401.12345.pdf",
      "html_url": "https://arxiv.org/abs/2401.12345",
      "jatsxml": "",
      "comment": "12 pages, 5 figures",
      "published": ""
    }
  ]
}
```

## Common Usage Patterns

### Literature Review Workflow

1. **Broad keyword search:**
```python
python scripts/arxiv_search.py \
  --keywords "diffusion model" "generative AI" \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --category cs.LG \
  --output diffusion_papers.json
```

2. **Extract and review results:**
```python
import json

with open('diffusion_papers.json') as f:
    data = json.load(f)

print(f"Found {data['result_count']} papers")

for paper in data['results'][:5]:
    print(f"\nTitle: {paper['title']}")
    print(f"Authors: {paper['authors']}")
    print(f"Date: {paper['date']}")
    print(f"arXiv ID: {paper['arxiv_id']}")
```

3. **Download selected papers:**
```python
from arxiv_search import ArxivSearcher

searcher = ArxivSearcher()
selected_ids = ["2401.12345", "2402.67890"]

for arxiv_id in selected_ids:
    searcher.download_pdf(arxiv_id, f"papers/{arxiv_id}.pdf")
```

### Trend Analysis

Track research trends by analyzing publication frequencies over time:

```python
python scripts/arxiv_search.py \
  --keywords "large language model" \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --category cs.CL \
  --output llm_trends.json
```

Then analyze the temporal distribution in the results.

### Author Tracking

Monitor specific researchers' preprints:

```python
# Track multiple authors
authors = ["Yoshua Bengio", "Yann LeCun"]

for author in authors:
    python scripts/arxiv_search.py \
      --author "{author}" \
      --days-back 365 \
      --output "{author.replace(' ', '_')}_papers.json"
```

## Python API Usage

For more complex workflows, import and use the `ArxivSearcher` class directly:

```python
from scripts.arxiv_search import ArxivSearcher

# Initialize
searcher = ArxivSearcher(verbose=True)

# Multiple search operations
keywords_papers = searcher.search_by_keywords(
    keywords=["transformer", "attention"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    category="cs.CL"
)

author_papers = searcher.search_by_author(
    author_name="Geoffrey Hinton",
    start_date="2023-01-01",
    end_date="2024-12-31"
)

# Get specific paper details
paper = searcher.get_paper_details("2401.12345")

# Download PDF
success = searcher.download_pdf(
    arxiv_id="2401.12345",
    output_path="paper.pdf"
)

# Format results consistently
formatted = searcher.format_result(paper, include_abstract=True)
```

## Best Practices

1. **Use appropriate date ranges**: Smaller date ranges return faster. For keyword searches over long periods, consider splitting into multiple queries.

2. **Filter by category**: When possible, use `--category` to reduce data transfer and improve search precision.

3. **Respect rate limits**: The script includes automatic delays (3 seconds between requests, per arXiv policy). For large-scale data collection, add additional delays.

4. **Cache results**: Save search results to JSON files to avoid repeated API calls.

5. **Handle pagination**: arXiv returns results in batches. For large result sets, the script handles pagination automatically.

6. **Handle errors gracefully**: Check the `result_count` in output JSON. Empty results may indicate date range issues or API connectivity problems.

7. **Verbose mode for debugging**: Use `--verbose` flag to see detailed logging of API requests and responses.

## Advanced Features

### Custom Date Range Logic

```python
from datetime import datetime, timedelta

# Last quarter
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

python scripts/arxiv_search.py \
  --start-date {start_date.strftime('%Y-%m-%d')} \
  --end-date {end_date.strftime('%Y-%m-%d')}
```

### Result Limiting

Limit the number of results returned:

```python
python scripts/arxiv_search.py \
  --keywords "quantum computing" \
  --days-back 30 \
  --limit 50 \
  --output quantum_top50.json
```

### Exclude Abstracts for Speed

When only metadata is needed:

```python
# Note: Abstract inclusion is controlled in Python API
from scripts.arxiv_search import ArxivSearcher

searcher = ArxivSearcher()
papers = searcher.search_by_keywords(keywords=["AI"], days_back=30)
formatted = [searcher.format_result(p, include_abstract=False) for p in papers]
```

### Multi-Category Search

Search across multiple categories:

```python
from scripts.arxiv_search import ArxivSearcher

searcher = ArxivSearcher()

# Search in both CS and quantitative biology
cs_papers = searcher.search_by_keywords(
    keywords=["protein folding"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    category="cs.LG"
)

qbio_papers = searcher.search_by_keywords(
    keywords=["protein folding"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    category="q-bio.BM"
)
```

## Programmatic Integration

Integrate search results into downstream analysis pipelines:

```python
import json
import pandas as pd

# Load results
with open('results.json') as f:
    data = json.load(f)

# Convert to DataFrame for analysis
df = pd.DataFrame(data['results'])

# Analyze
print(f"Total papers: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"\nTop authors by paper count:")
print(df['authors'].str.split(',').explode().str.strip().value_counts().head(10))

# Filter and export
recent = df[df['date'] >= '2024-06-01']
recent.to_csv('recent_papers.csv', index=False)
```

## Testing the Skill

To verify that the arXiv database skill is working correctly, run the comprehensive test suite.

**Prerequisites:**
```bash
uv pip install requests
```

**Run tests:**
```bash
python tests/test_lit_database_arxiv.py
```

The test suite validates:
- **Initialization**: ArxivSearcher class instantiation
- **Query Search**: Retrieving papers via search queries
- **Category Filtering**: Filtering papers by arXiv categories
- **Keyword Search**: Finding papers containing specific keywords
- **ID Lookup**: Retrieving specific papers by arXiv ID
- **Result Formatting**: Proper formatting of paper metadata
- **Author Search**: Finding papers by author name

**Expected Output:**
```
📄 arXiv Database Search Skill Test Suite
======================================================================

🧪 Test 1: Initialization
✅ ArxivSearcher initialized successfully

🧪 Test 2: Query Search
✅ Found 10 papers matching query
   First paper: Novel Approach to...

[... additional tests ...]

======================================================================
📊 Test Summary
======================================================================
✅ PASS: Initialization
✅ PASS: Query Search
✅ PASS: Category Filtering
✅ PASS: Keyword Search
✅ PASS: ID Lookup
✅ PASS: Result Formatting
✅ PASS: Author Search
======================================================================
Results: 7/7 tests passed (100%)
======================================================================

🎉 All tests passed! The arXiv database skill is working correctly.
```

**Note:** Some tests may show warnings if no papers are found in specific date ranges or categories. This is normal and does not indicate a failure.

## Reference Documentation

For detailed API specifications, endpoint documentation, and response schemas, refer to:
- `references/api_reference.md` - Complete arXiv API documentation

The reference file includes:
- Full API endpoint specifications
- Response format details (Atom/XML)
- Error handling patterns
- Rate limiting guidelines
- Advanced search patterns and query syntax
