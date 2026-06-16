# Usage Guide: bio-mrna-seq-ppi

## When to Use
Use this skill after differential expression analysis to explore physical interactions among your significant genes and build publication-ready protein-protein interaction networks.

## Inputs
- Gene list (symbols or Entrez IDs) from DE results or a co-expression module
- Target species (human, mouse, yeast, etc.)

## Outputs
- PPI edge table with combined STRING scores
- Network visualization (static or interactive)
- Extended networks with predicted neighbors

## Quick Start
### R: STRINGdb
```r
string_db <- STRINGdb$new(version='11.5', species=9606, score_threshold=400)
mapped <- string_db$map(sig_genes, 'gene', removeUnmappedRows=TRUE)
string_db$plot_network(mapped$STRING_id)
```

### Python: omicverse
```python
interactions = ov.bulk.string_interaction(gene_list, species_id=9606)
ppi = ov.bulk.pyPPI(gene=gene_list, gene_type_dict=types, gene_color_dict=colors, species=9606)
ppi.interaction_analysis()
ppi.plot_network()
```

## Tips
- **Score threshold 400** = medium confidence; increase to 700 for high-confidence only.
- Use `add_nodes` to expand the network with predicted interactors.
- Color nodes by DE direction or functional category for clearer biological stories.

## Workflow Position
**Upstream**: `bio-mrna-seq-differential-expression` or `bio-mrna-seq-wgcna`  
**Downstream**: Publication figures, hypothesis generation
