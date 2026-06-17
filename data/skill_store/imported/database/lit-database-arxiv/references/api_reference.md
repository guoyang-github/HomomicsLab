# arXiv API Reference

## Overview

The arXiv API provides programmatic access to preprint metadata from the arXiv server. The API returns Atom/XML-formatted data with comprehensive metadata about scientific preprints across physics, mathematics, computer science, quantitative biology, statistics, finance, and electrical engineering.

## Base URL

```
http://export.arxiv.org/api/query
```

## Rate Limiting

arXiv enforces strict rate limits. Be respectful:
- **Maximum 3 requests per second** (minimum 3 seconds between requests)
- Do not make concurrent requests
- Use appropriate User-Agent headers
- Cache results when possible
- For bulk data collection, consider using the arXiv bulk data dumps instead

## API Endpoints

### 1. Search Query

Search for preprints using the arXiv query syntax.

**Endpoint:**
```
GET /api/query
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search_query` | string | No | Search query using arXiv query syntax |
| `id_list` | string | No | Comma-separated list of arXiv IDs |
| `start` | integer | No | Offset for pagination (default: 0) |
| `max_results` | integer | No | Maximum results per request (default: 10, max: 30000) |
| `sortBy` | string | No | Sort field: `relevance`, `lastUpdatedDate`, `submittedDate` (default: `relevance`) |
| `sortOrder` | string | No | Sort order: `ascending`, `descending` (default: `descending`) |

**Note:** At least one of `search_query` or `id_list` must be provided.

**Example:**
```
GET http://export.arxiv.org/api/query?search_query=ti:machine+learning&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending
```

**Response (Atom/XML):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <link href="http://arxiv.org/api/query?search_query=ti:machine+learning&amp;start=0&amp;max_results=10" rel="self" type="application/atom+xml"/>
  <title type="html">ArXiv Query: ti:machine learning</title>
  <id>http://arxiv.org/api/cHxbiOdZaP56ODnBPIenZhzgNQg</id>
  <updated>2024-01-15T00:00:00Z</updated>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">15000</opensearch:totalResults>
  <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
  <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">10</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.12345</id>
    <updated>2024-03-20T00:00:00Z</updated>
    <published>2024-01-15T00:00:00Z</published>
    <title>Example Paper Title</title>
    <summary>Full abstract text...</summary>
    <author>
      <name>Smith, John</name>
    </author>
    <author>
      <name>Doe, Jane</name>
    </author>
    <arxiv:comment xmlns:arxiv="http://arxiv.org/schemas/atom">12 pages, 5 figures</arxiv:comment>
    <link href="http://arxiv.org/abs/2401.12345" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.12345.pdf" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="stat.ML" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
```

### 2. Paper Details by ID

Retrieve details for specific papers by arXiv ID.

**Endpoint:**
```
GET /api/query?id_list={id1},{id2},...
```

**Parameters:**
- `id_list`: Comma-separated list of arXiv IDs (e.g., `2401.12345,2402.67890`)

**Example:**
```
GET http://export.arxiv.org/api/query?id_list=2401.12345
```

## Query Syntax

arXiv supports a rich query syntax for the `search_query` parameter:

### Field Prefixes

| Prefix | Field | Example |
|--------|-------|---------|
| `ti:` | Title | `ti:machine learning` |
| `au:` | Author | `au:Smith` |
| `abs:` | Abstract | `abs:neural network` |
| `co:` | Comment | `co:supplementary` |
| `jr:` | Journal Reference | `jr:Nature` |
| `cat:` | Subject Category | `cat:cs.LG` |
| `rn:` | Report Number | `rn:arXiv:2401.12345` |
| `id:` | arXiv ID | `id:2401.12345` |
| `all:` | All fields | `all:machine learning` |

### Boolean Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both terms must match | `ti:machine AND ti:learning` |
| `OR` | Either term may match | `cat:cs.LG OR cat:cs.AI` |
| `ANDNOT` | Exclude term | `ti:machine ANDNOT ti:robot` |

**Complex Example:**
```
search_query=ti:transformer+AND+abs:attention+AND+cat:cs.CL
```

### Grouping

Use parentheses to group queries:
```
search_query=(ti:machine+OR+abs:deep)+AND+cat:cs.LG
```

### Wildcards

- `*` matches any sequence of characters: `au:Sm*` matches Smith, Smyth, etc.
- `?` matches a single character

## Valid Categories

### Computer Science

| Code | Name |
|------|------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language |
| `cs.CC` | Computational Complexity |
| `cs.CE` | Computational Engineering, Finance, and Science |
| `cs.CG` | Computational Geometry |
| `cs.CR` | Cryptography and Security |
| `cs.CV` | Computer Vision and Pattern Recognition |
| `cs.CY` | Computers and Society |
| `cs.DB` | Databases |
| `cs.DC` | Distributed, Parallel, and Cluster Computing |
| `cs.DL` | Digital Libraries |
| `cs.DM` | Discrete Mathematics |
| `cs.DS` | Data Structures and Algorithms |
| `cs.ET` | Emerging Technologies |
| `cs.FL` | Formal Languages and Automata Theory |
| `cs.GL` | General Literature |
| `cs.GR` | Graphics |
| `cs.GT` | Computer Science and Game Theory |
| `cs.HC` | Human-Computer Interaction |
| `cs.IR` | Information Retrieval |
| `cs.IT` | Information Theory |
| `cs.LG` | Machine Learning |
| `cs.LO` | Logic in Computer Science |
| `cs.MA` | Multiagent Systems |
| `cs.MM` | Multimedia |
| `cs.MS` | Mathematical Software |
| `cs.NA` | Numerical Analysis |
| `cs.NE` | Neural and Evolutionary Computing |
| `cs.NI` | Networking and Internet Architecture |
| `cs.OH` | Other Computer Science |
| `cs.OS` | Operating Systems |
| `cs.PF` | Performance |
| `cs.PL` | Programming Languages |
| `cs.RO` | Robotics |
| `cs.SC` | Symbolic Computation |
| `cs.SD` | Sound |
| `cs.SE` | Software Engineering |
| `cs.SI` | Social and Information Networks |
| `cs.SY` | Systems and Control |

### Physics

| Code | Name |
|------|------|
| `physics.gen-ph` | General Physics |
| `physics.acc-ph` | Accelerator Physics |
| `physics.ao-ph` | Atmospheric and Oceanic Physics |
| `physics.app-ph` | Applied Physics |
| `physics.atm-clus` | Atomic and Molecular Clusters |
| `physics.atom-ph` | Atomic Physics |
| `physics.bio-ph` | Biological Physics |
| `physics.chem-ph` | Chemical Physics |
| `physics.class-ph` | Classical Physics |
| `physics.comp-ph` | Computational Physics |
| `physics.data-an` | Data Analysis, Statistics and Probability |
| `physics.ed-ph` | Physics Education |
| `physics.flu-dyn` | Fluid Dynamics |
| `physics.geo-ph` | Geophysics |
| `physics.hist-ph` | History and Philosophy of Physics |
| `physics.ins-det` | Instrumentation and Detectors |
| `physics.med-ph` | Medical Physics |
| `physics.optics` | Optics |
| `physics.plasm-ph` | Plasma Physics |
| `physics.pop-ph` | Popular Physics |
| `physics.soc-ph` | Physics and Society |
| `physics.space-ph` | Space Physics |

### Quantitative Biology

| Code | Name |
|------|------|
| `q-bio.BM` | Biomolecules |
| `q-bio.CB` | Cell Behavior |
| `q-bio.GN` | Genomics |
| `q-bio.MN` | Molecular Networks |
| `q-bio.NC` | Neurons and Cognition |
| `q-bio.OT` | Other Quantitative Biology |
| `q-bio.PE` | Populations and Evolution |
| `q-bio.QM` | Quantitative Methods |
| `q-bio.SC` | Subcellular Processes |
| `q-bio.TO` | Tissues and Organs |

### Mathematics

| Code | Name |
|------|------|
| `math.AG` | Algebraic Geometry |
| `math.AT` | Algebraic Topology |
| `math.AP` | Analysis of PDEs |
| `math.CT` | Category Theory |
| `math.CA` | Classical Analysis and ODEs |
| `math.CO` | Combinatorics |
| `math.AC` | Commutative Algebra |
| `math.CV` | Complex Variables |
| `math.DG` | Differential Geometry |
| `math.DS` | Dynamical Systems |
| `math.FA` | Functional Analysis |
| `math.GM` | General Mathematics |
| `math.GN` | General Topology |
| `math.GT` | Geometric Topology |
| `math.GR` | Group Theory |
| `math.HO` | History and Overview |
| `math.IT` | Information Theory |
| `math.KT` | K-Theory and Homology |
| `math.LO` | Logic |
| `math.MP` | Mathematical Physics |
| `math.MG` | Metric Geometry |
| `math.NT` | Number Theory |
| `math.NA` | Numerical Analysis |
| `math.OA` | Operator Algebras |
| `math.OC` | Optimization and Control |
| `math.PR` | Probability |
| `math.QA` | Quantum Algebra |
| `math.RT` | Representation Theory |
| `math.RA` | Rings and Algebras |
| `math.SP` | Spectral Theory |
| `math.ST` | Statistics Theory |
| `math.SG` | Symplectic Geometry |

### Statistics

| Code | Name |
|------|------|
| `stat.AP` | Applications |
| `stat.CO` | Computation |
| `stat.ME` | Methodology |
| `stat.ML` | Machine Learning |
| `stat.OT` | Other Statistics |
| `stat.TH` | Statistics Theory |

### Electrical Engineering and Systems Science

| Code | Name |
|------|------|
| `eess.AS` | Audio and Speech Processing |
| `eess.IV` | Image and Video Processing |
| `eess.SP` | Signal Processing |
| `eess.SY` | Systems and Control |

### Economics

| Code | Name |
|------|------|
| `econ.EM` | Econometrics |
| `econ.GN` | General Economics |
| `econ.TH` | Theoretical Economics |

### Quantitative Finance

| Code | Name |
|------|------|
| `q-fin.CP` | Computational Finance |
| `q-fin.EC` | Economics |
| `q-fin.GN` | General Finance |
| `q-fin.MF` | Mathematical Finance |
| `q-fin.PM` | Portfolio Management |
| `q-fin.PR` | Pricing of Securities |
| `q-fin.RM` | Risk Management |
| `q-fin.ST` | Statistical Finance |
| `q-fin.TR` | Trading and Market Microstructure |

## Paper Metadata Fields

Each paper entry contains:

| Field | Description | XML Path |
|-------|-------------|----------|
| `id` | arXiv URL | `entry/id` |
| `title` | Paper title | `entry/title` |
| `summary` | Abstract | `entry/summary` |
| `author` | Authors | `entry/author/name` (multiple) |
| `published` | Submission date | `entry/published` |
| `updated` | Last update date | `entry/updated` |
| `arxiv:comment` | Author comments | `entry/arxiv:comment` |
| `arxiv:primary_category` | Main category | `entry/arxiv:primary_category/@term` |
| `category` | Categories | `entry/category/@term` (multiple) |
| `link[@rel='alternate']` | HTML abstract URL | `entry/link[@rel='alternate']/@href` |
| `link[@title='pdf']` | PDF URL | `entry/link[@title='pdf']/@href` |

## Downloading Full Papers

### PDF Download

PDFs can be downloaded directly:

```
https://arxiv.org/pdf/{arxiv_id}.pdf
```

Example:
```
https://arxiv.org/pdf/2401.12345.pdf
```

### HTML Version

```
https://arxiv.org/abs/{arxiv_id}
```

### Source Download

```
https://arxiv.org/e-print/{arxiv_id}
```

### Versioned PDF

For a specific version:
```
https://arxiv.org/pdf/2401.12345v1.pdf
```

## Common Search Patterns

### Author Search

```
search_query=au:Smith
```

**With date filtering** (client-side after fetching):
1. Search by author
2. Filter by `published` date

### Keyword Search

**In title only:**
```
search_query=ti:machine+learning
```

**In title or abstract:**
```
search_query=ti:machine+learning+OR+abs:machine+learning
```

**With category filter:**
```
search_query=(ti:machine+OR+abs:machine)+AND+cat:cs.LG
```

### Recent Papers by Category

```
search_query=cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=50
```

### Pagination

```
# First page
search_query=cat:cs.LG&start=0&max_results=100

# Second page
search_query=cat:cs.LG&start=100&max_results=100

# Third page
search_query=cat:cs.LG&start=200&max_results=100
```

## Error Handling

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (invalid query syntax)
- `404`: Resource not found
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Server error

### Common Errors

**Rate Limiting:**
If you receive a 429 status code, wait at least 3 seconds before making another request.

**Invalid Query:**
```xml
<feed>
  <title>Error</title>
  <summary>Incorrect id format for...</summary>
</feed>
```

**No Results:**
An empty feed with `opensearch:totalResults` of 0.

## Best Practices

1. **Cache results**: Store retrieved papers to avoid repeated API calls
2. **Use appropriate max_results**: Start with 10-100, increase as needed
3. **Filter by category**: Reduces data transfer and processing time
4. **Batch processing**: When downloading multiple PDFs, add 3-second delays between requests
5. **Error handling**: Always check response status and handle errors gracefully
6. **Respect rate limits**: 3 seconds between requests is mandatory
7. **Use pagination**: For large result sets, fetch in batches of 100
8. **Prefer id_list for known papers**: More efficient than search queries

## Python Usage Example

```python
from arxiv_search import ArxivSearcher

searcher = ArxivSearcher(verbose=True)

# Search by keywords
papers = searcher.search_by_keywords(
    keywords=["transformer", "attention"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    category="cs.CL"
)

# Search by author
papers = searcher.search_by_author(
    author_name="Geoffrey Hinton",
    start_date="2023-01-01",
    end_date="2024-12-31"
)

# Get specific paper
paper = searcher.get_paper_details("2401.12345")

# Download PDF
searcher.download_pdf("2401.12345", "paper.pdf")
```

## External Resources

- arXiv homepage: https://arxiv.org/
- arXiv API documentation: https://arxiv.org/help/api/
- arXiv API user manual: https://arxiv.org/help/api/user-manual
- arXiv search tips: https://arxiv.org/help/search
