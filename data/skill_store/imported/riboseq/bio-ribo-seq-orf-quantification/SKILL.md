---
name: bio-ribo-seq-orf-quantification
description: Quantify ORF-level translation from Ribo-seq data using ORFik and DESeq2. Use when measuring expression of detected ORFs or comparing ORF translation across conditions.
tool_type: mixed
primary_tool: ORFik
---

## Version Compatibility

Reference examples tested with: ORFik 1.24+ (Bioconductor 3.18+), DESeq2 1.42+, GenomicFeatures 1.54+

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# ORF Quantification

**"Quantify translation at detected ORFs"** → Measure ribosome occupancy per ORF, normalize counts, and perform differential ORF expression analysis using ORFik and DESeq2.

## Output Directory Structure

```
results/06_orf_quantification/
├── orf_counts.tsv
├── orf_fpkm.tsv
├── orf_deseq2_results.csv
└── plots/
    └── orf_volcano.pdf
```

## Concept: ORF-Level Quantification

Gene-level translation analysis averages ribosome occupancy across all ORFs on a transcript. However, many transcripts contain **multiple translated ORFs** (e.g., upstream ORFs, downstream ORFs, or novel ORFs in non-coding RNAs). ORF-level quantification isolates the signal for each individual open reading frame.

### How Counts Are Assigned

1. **Annotation parsing**: `makeTxDbFromGFF()` builds a transcript database from the GTF.
2. **CDS extraction**: `cdsBy(txdb, by='tx')` returns the genomic coordinates of every CDS per transcript.
3. **Counting**: `countOverlaps(cds, ribo_reads)` counts how many Ribo-seq reads overlap each ORF.

```r
library(GenomicFeatures)
library(GenomicAlignments)

txdb <- makeTxDbFromGFF('annotation.gtf', format = 'gtf')
cds_list <- cdsBy(txdb, by = 'tx', use.names = TRUE)
reads <- readGAlignments('sample.sorted.bam')
orf_counts <- countOverlaps(cds_list, reads, ignore.strand = FALSE)
```

### P-site Correction

For maximum accuracy, reads should be shifted to the **P-site** before counting. A read spanning multiple codons should be counted at the codon where the ribosome active site resides, not at the 5' end of the footprint. In practice, many pipelines apply the length-specific offset and then count 1 nt per read (the inferred P-site position) rather than the full alignment span.

### ORF-Level Normalization

Like gene-level analysis, raw counts must be normalized by ORF length and library depth:

```
RPK  = counts / (ORF_length_kb)
FPKM = RPK / (sum(RPK) / 1e6)
TPM  = (counts / ORF_length_kb) / (sum(counts / length_kb) / 1e6)
```

### Differential ORF Expression

`DESeq2` is run on the ORF count matrix just as it would be on a gene count matrix. Because different ORFs on the same transcript share the same mRNA pool, a significant result indicates that the **ribosome loading ratio** for that specific ORF has changed—evidence of **differential ORF usage**.

## Step 1: Build ORF Count Matrix

```bash
Rscript scripts/quantify_orfs.R \
  results/00_index/annotation_clean.gtf \
  results/02_ribo_preprocessing \
  results/06_orf_quantification
```

## Step 2: Differential ORF Expression

```bash
Rscript -e "
library(DESeq2)
orf_counts <- read.delim('results/06_orf_quantification/orf_counts.tsv', row.names = 1)
coldata <- data.frame(
  condition = factor(c('control', 'control', 'treatment', 'treatment')),
  row.names = colnames(orf_counts)
)
dds <- DESeqDataSetFromMatrix(orf_counts, coldata, ~ condition)
dds <- DESeq(dds)
write.csv(as.data.frame(results(dds)), 'results/06_orf_quantification/orf_deseq2_results.csv')
"
```

## Step 3: Merge with ORF Detection Results

```r
ribocode <- read.delim('results/05_orf_detection/sample1_ORF_result.txt')
ribocode$orf_id <- paste(ribocode$transcript_id, ribocode$ORF_type, sep = '_')
res <- read.csv('results/06_orf_quantification/orf_deseq2_results.csv', row.names = 1)
merged <- merge(ribocode, res, by.x = 'transcript_id', by.y = 'row.names', all.x = TRUE)
write.csv(merged, 'results/06_orf_quantification/orf_annotated_results.csv', row.names = FALSE)
```

## Step 4: Volcano Plot

```bash
Rscript scripts/plot_orf_volcano.R \
  results/06_orf_quantification/orf_deseq2_results.csv \
  results/06_orf_quantification/plots/orf_volcano.pdf
```

## Related Skills

- bio-ribo-seq-orf-detection - Provides detected ORF coordinates and annotations
- bio-ribo-seq-ribosome-periodicity - Provides P-site offsets for corrected quantification
- bio-ribo-seq-differential-occupancy - General DESeq2 patterns (gene-level)
