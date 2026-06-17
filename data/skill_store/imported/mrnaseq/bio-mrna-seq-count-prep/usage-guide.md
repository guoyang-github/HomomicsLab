# Usage Guide: bio-mrna-seq-count-prep

## When to Use
Use this skill immediately after quantification to clean, align, and filter the raw count matrix before exploratory QC and differential expression.

## Inputs
- Raw count matrix (from featureCounts, Salmon, kallisto, or tximport)
- Sample metadata CSV/TSV (sample IDs as row index, conditions/batch as columns)
- Optional: gene ID mapping table (e.g., Ensembl → gene symbol)

## Outputs
- Clean, filtered count matrix (CSV/TSV or `.h5ad`)
- Metadata matched to count matrix samples
- DESeq2 `DESeqDataSet` or edgeR `DGEList` (optional)

## Quick Start
1. **Ingest** the count matrix from your quantifier.
2. **Prefer `tximeta`** for Salmon/kallisto outputs in R — it imports counts and attaches gene metadata automatically.
3. **Map gene IDs** (e.g., Ensembl → symbol) using `mygene` (Python) or `biomaRt` (R).
4. **Align metadata** — ensure sample names in metadata match count matrix columns exactly.
5. **Filter** low-expression genes: keep genes with CPM > 0.5 in at least 3 samples.
6. **Export** as CSV or convert to `DESeqDataSet` / `AnnData`.

## Tips
- **Sum duplicates** after ID mapping if multiple Ensembl IDs map to the same symbol.
- **Metadata alignment is critical** — mismatched sample names are the #1 cause of DE errors.
- **Do not normalize yet** — DESeq2/edgeR need raw counts.

## Workflow Position
**Upstream**: `bio-mrna-seq-quantification`  
**Downstream**: `bio-mrna-seq-qc-exploratory` or `bio-mrna-seq-differential-expression`
