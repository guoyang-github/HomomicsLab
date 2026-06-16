---
name: bio-mrna-seq-ppi
description: Protein-protein interaction (PPI) network analysis for bulk mRNA-seq gene lists. Covers STRING database queries, network construction, visualization, and omicverse pyPPI integration. Use for exploring molecular interactions among DE genes.
tool_type: mixed
primary_tool: STRINGdb
---


Reference examples tested with: STRINGdb 2.16+, omicverse 1.6+

# mRNA-seq PPI Analysis

## Overview

Query protein-protein interaction networks from STRING and visualize interactions among differentially expressed gene sets.

## Tool Selection

| Tool | Best For | Notes |
|------|----------|-------|
| **STRINGdb (R)** | Full functionality; interactive network plots; predicted neighbor expansion | R-only; requires mapping gene symbols to STRING IDs |
| **omicverse pyPPI (Python)** | Python-only workflows; integration with scanpy/omicverse | Simpler API; node coloring by DE direction built-in |

**Rule of thumb**: Use STRINGdb in R for publication-quality network visualization and advanced features. Use omicverse only when constrained to a Python environment.

## R: STRINGdb

```r
library(STRINGdb)

string_db <- STRINGdb$new(version='11.5', species=9606, score_threshold=400)

# Map gene symbols to STRING IDs
sig_df <- data.frame(gene = sig_genes)
mapped <- string_db$map(sig_df, 'gene', removeUnmappedRows=TRUE)

# Get interactions
interactions <- string_db$get_interactions(mapped$STRING_id)

# Plot network
string_db$plot_network(mapped$STRING_id)
```

## Python: omicverse pyPPI

```python
import omicverse as ov

# gene_list: list of differentially expressed gene symbols from your DE analysis
# e.g., gene_list = ['TP53', 'BRCA1', 'EGFR', 'MYC']
gene_list = sig_genes.tolist()  # or however you extract from your DE results

# Optional: map each gene to a category (e.g., up/down regulated) for coloring
gene_type_dict = {g: 'up' if g in up_genes else 'down' for g in gene_list}
gene_color_dict = {'up': '#FF0000', 'down': '#0000FF'}

# Query STRING interactions
interactions = ov.bulk.string_interaction(gene_list, species_id=9606)

# Build and plot PPI network
ppi = ov.bulk.pyPPI(
    gene=gene_list,
    gene_type_dict=gene_type_dict,
    gene_color_dict=gene_color_dict,
    species=9606
)
ppi.interaction_analysis()
ppi.plot_network()
```

## Species IDs

| Species | NCBI Taxonomy ID |
|---------|------------------|
| Human | 9606 |
| Mouse | 10090 |
| Rat | 10116 |
| Yeast | 4932 |
| Zebrafish | 7955 |

## Tips

- Ensure gene symbols match the target species exactly
- Use `score_threshold` to filter interaction confidence (default 400 = medium)
- Add predicted neighbors with `ppi.interaction_analysis(add_nodes=5)` to expand the network

## Related Skills

- `bio-mrna-seq-differential-expression` - Generate gene lists
- `bio-mrna-seq-pathway-enrichment` - Functional context
- `bio-mrna-seq-pipeline` - End-to-end workflow
