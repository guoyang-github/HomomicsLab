---
name: bio-mrna-seq-count-prep
description: Prepare raw count matrices for downstream analysis. Covers ingestion from featureCounts/Salmon/kallisto, gene ID mapping (Ensembl to symbol), metadata alignment, low-count filtering, and AnnData/DESeq2 object creation. Use after quantification and before DE analysis.
tool_type: mixed
primary_tool: pandas
---


Reference examples tested with: pandas 2.0+, mygene 3.2+, biomaRt 2.58+, anndata 0.10+, pyreadr 0.5+

# mRNA-seq Count Matrix Preparation

## Overview

Transform raw quantification outputs into a clean, analysis-ready count matrix with aligned metadata and mapped gene identifiers.

---

## 1. Ingest Count Matrices

### From featureCounts

```python
import pandas as pd

fc = pd.read_csv('featurecounts.txt', sep='\t', comment='#')
counts = fc.set_index('Geneid')
# Drop annotation columns (Chr, Start, End, Strand, Length) by name
counts = counts.drop(columns=['Chr', 'Start', 'End', 'Strand', 'Length'], errors='ignore')
counts.columns = [c.replace('.bam', '').split('/')[-1] for c in counts.columns]
```

### From Salmon

```python
from pathlib import Path

samples = ['sample1', 'sample2', 'sample3']
counts = pd.DataFrame({
    s: pd.read_csv(f'{s}_quant/quant.sf', sep='\t', index_col=0)['NumReads']
    for s in samples
})
```

### From kallisto

```python
counts = pd.DataFrame({
    s: pd.read_csv(f'{s}_quant/abundance.tsv', sep='\t', index_col=0)['est_counts']
    for s in samples
})
```

### From R tximport RDS

```python
import pyreadr
result = pyreadr.read_r('txi.rds')
txi = result[None]
counts = pd.DataFrame(txi['counts'])
```

---

## Modern Alternative: tximeta (R)

For Salmon/kallisto outputs, `tximeta` (Bioconductor) is the modern successor to `tximport`. It automatically attaches transcript and gene metadata (including biotype and chromosome) and ensures reference version consistency.

```r
library(tximeta)

# Create a linked transcriptome once (requires matching GTF/FASTA)
# makeLinkedTxome(indexDir='salmon_index', source='Ensembl', organism='Homo sapiens',
#                 release='110', genome='GRCh38', fasta='transcripts.fa', gtf='annotation.gtf')

coldata <- data.frame(
    names = samples,
    files = file.path(samples, 'quant.sf'),
    stringsAsFactors = FALSE
)

se <- tximeta(coldata)
gse <- summarizeToGene(se)  # returns a SummarizedExperiment with counts, abundance, length

counts <- assay(gse, 'counts')
```

---

## Tool Selection for ID Mapping

| Method | Best For | Key Trait |
|--------|----------|-----------|
| **org.Hs.eg.db** | Offline R workflows; stable, reproducible pipelines | No internet required; Ensembl-to-SYMBOL mapping is version-locked to the installed package |
| **biomaRt** | R workflows needing the latest Ensembl annotations | Online query to current Ensembl release; always up-to-date |
| **mygene** | Python workflows; cross-database queries | Online; supports many ID types (Ensembl, RefSeq, UniProt, etc.) and species |

**Rule of thumb**: Use `org.Hs.eg.db` for reproducible pipelines where reference version stability matters. Use `biomaRt` when you need the absolute latest annotations. Use `mygene` only when working in Python.

---

## 2. Gene ID Mapping

### Python: mygene

```python
import mygene

def map_count_matrix_ids(counts, from_type='ensembl.gene', to_type='symbol', species='human'):
    mg = mygene.MyGeneInfo()
    clean_ids = [g.split('.')[0] for g in counts.index]
    results = mg.querymany(clean_ids, scopes=from_type, fields=to_type, species=species)
    mapping = {r['query']: r.get(to_type, r['query']) for r in results if to_type in r}
    new_index = [mapping.get(g.split('.')[0], g) for g in counts.index]
    counts_mapped = counts.copy()
    counts_mapped.index = new_index
    # Sum duplicates
    counts_mapped = counts_mapped.groupby(counts_mapped.index).sum()
    return counts_mapped

# Usage
counts = map_count_matrix_ids(counts, 'ensembl.gene', 'symbol')
```

### R: biomaRt

```r
library(biomaRt)
ensembl <- useEnsembl(biomart='genes', dataset='hsapiens_gene_ensembl')

clean_ids <- gsub('\\..*', '', rownames(counts))
mapping <- getBM(
    attributes=c('ensembl_gene_id', 'hgnc_symbol'),
    filters='ensembl_gene_id',
    values=clean_ids,
    mart=ensembl
)

# Merge and aggregate duplicates
counts$gene_id <- clean_ids
merged <- merge(counts, mapping, by.x='gene_id', by.y='ensembl_gene_id', all.x=TRUE)
# Fill missing symbols with Ensembl ID to avoid NA rownames
merged$hgnc_symbol <- ifelse(is.na(merged$hgnc_symbol) | merged$hgnc_symbol == '',
                             merged$gene_id, merged$hgnc_symbol)
rownames(merged) <- merged$hgnc_symbol
merged$hgnc_symbol <- NULL
merged$gene_id <- NULL
# Aggregate duplicate symbols using rowsum (more robust than aggregate)
counts_mapped <- t(rowsum(t(merged), group=rownames(merged)))
```

### R: org.Hs.eg.db

```r
library(org.Hs.eg.db)
library(dplyr)
library(tibble)

symbols <- mapIds(org.Hs.eg.db, keys=rownames(counts), keytype='ENSEMBL', column='SYMBOL', multiVals='first')
rownames(counts) <- ifelse(is.na(symbols), rownames(counts), symbols)
counts <- counts %>%
    rownames_to_column("gene") %>%
    group_by(gene) %>%
    summarise(across(everything(), sum), .groups="drop") %>%
    column_to_rownames("gene")
```

---

## 3. Metadata Alignment

```python
import pandas as pd

metadata = pd.read_csv('metadata.csv', index_col=0)

# Find common samples
common_samples = counts.columns.intersection(metadata.index)
counts = counts[common_samples]
metadata = metadata.loc[common_samples]

# Assert alignment
assert all(counts.columns == metadata.index)
```

### Flexible Name Matching

```python
def fuzzy_match_samples(counts, metadata):
    count_cols = counts.columns.tolist()
    meta_idx = metadata.index.tolist()
    if set(count_cols) == set(meta_idx):
        counts = counts[meta_idx]
        return counts, metadata
    transformations = [
        lambda x: x.replace('_', '-'),
        lambda x: x.replace('-', '_'),
        lambda x: x.split('_')[0],
        lambda x: x.replace('.bam', ''),
        lambda x: x.upper(),
        lambda x: x.lower(),
    ]
    for transform in transformations:
        transformed = {transform(c): c for c in count_cols}
        matches = {m: transformed[transform(m)] for m in meta_idx if transform(m) in transformed}
        if len(matches) == len(meta_idx):
            counts = counts[[matches[m] for m in meta_idx]]
            return counts, metadata
    raise ValueError('Could not match sample names')
```

---

## 4. Filter Low-Count Genes

```python
# CPM-based filtering (best practice): keep genes with CPM > 0.5 in at least 3 samples
import numpy as np

lib_sizes = counts.sum(axis=0)
cpm = counts.div(lib_sizes, axis=1) * 1e6
expressed = (cpm > 0.5).sum(axis=1) >= 3
counts_filtered = counts.loc[expressed]
```

```r
# R equivalent using edgeR
dge <- edgeR::DGEList(counts=counts)
keep <- edgeR::filterByExpr(dge)
counts_filtered <- counts[keep, ]
```

---

## 5. Create Analysis Objects

### DESeq2 (R)

```r
library(DESeq2)

dds <- DESeqDataSetFromMatrix(
    countData = as.matrix(counts_filtered),
    colData = metadata,
    design = ~ condition
)
```

### edgeR (R)

```r
library(edgeR)
y <- DGEList(counts=as.matrix(counts_filtered), group=metadata$condition)
y$samples <- cbind(y$samples, metadata)
```

### AnnData (Python)

```python
import anndata as ad

adata = ad.AnnData(X=counts_filtered.T)
adata.obs = metadata
adata.write_h5ad('prepared_counts.h5ad')
```

---

## Validation Checklist

- [ ] Count matrix shape: genes x samples
- [ ] Sample names in counts match metadata index exactly
- [ ] Gene IDs mapped consistently (Ensembl or Symbol, not mixed)
- [ ] Low-expression genes filtered
- [ ] No negative or NA values in count matrix

## Related Skills

- `bio-mrna-seq-quantification` - Generate raw counts
- `bio-mrna-seq-qc-exploratory` - Visualize prepared matrix
- `bio-mrna-seq-differential-expression` - Downstream DE analysis
- `bio-mrna-seq-pipeline` - End-to-end workflow
