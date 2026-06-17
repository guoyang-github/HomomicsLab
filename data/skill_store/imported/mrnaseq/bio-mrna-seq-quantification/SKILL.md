---
name: bio-mrna-seq-quantification
description: Gene and transcript quantification for bulk mRNA-seq. Covers alignment-based counting with featureCounts, STAR GeneCounts, and alignment-free pseudo-alignment with Salmon/kallisto, plus tximport summarization. Use after alignment or directly from FASTQ.
tool_type: mixed
primary_tool: featureCounts
---


Reference examples tested with: featureCounts 2.0.6+, STAR 2.7.11b+, Salmon 1.10+, kallisto 0.50+, tximport 1.28+

# mRNA-seq Quantification

## Overview

Generate gene-level count matrices from aligned BAMs or transcript-level abundances from FASTQ reads. This skill unifies alignment-based counting (featureCounts, STAR --quantMode) and alignment-free methods (Salmon, kallisto), including tximport integration.

## Quantification Strategy Selection

| Approach | Tool | Best For | Input |
|----------|------|----------|-------|
| **Alignment-based** | featureCounts / STAR GeneCounts | Need BAMs for downstream splicing, visualization, or QC | Sorted BAM + GTF |
| **Alignment-free** | Salmon / kallisto | Speed and lower compute; large cohorts | FASTQ + transcriptome index |

**Salmon vs kallisto**: Both are excellent. Salmon offers bias correction (`--gcBias`, `--seqBias`) and decoy-aware indexing out of the box. kallisto is slightly faster and has a simpler CLI. Choose based on ecosystem preference or existing pipelines.

**Rule of thumb**: Use alignment-based quantification if you need BAM files for splicing analysis (rMATS, IGV) or detailed QC. Use alignment-free (Salmon recommended) for standard DE workflows where speed matters.

---

## Alignment-Based: featureCounts

### Basic Usage

```bash
# Multiple samples -> single count matrix
featureCounts -a annotation.gtf -o counts.txt *.bam

# Paired-end: count fragments
featureCounts -p --countReadPairs -a annotation.gtf -o counts.txt *.bam

# Strict paired-end
featureCounts -p --countReadPairs -B -C -a annotation.gtf -o counts.txt *.bam
```

### Strandedness

```bash
# Unstranded (default)
featureCounts -s 0 -a annotation.gtf -o counts.txt *.bam

# Forward stranded
featureCounts -s 1 -a annotation.gtf -o counts.txt *.bam

# Reverse stranded (most common Illumina TruSeq)
featureCounts -s 2 -a annotation.gtf -o counts.txt *.bam
```

### Feature Types

```bash
# Gene level (default)
featureCounts -t exon -g gene_id -a annotation.gtf -o counts.txt *.bam

# Transcript level
featureCounts -t exon -g transcript_id -a annotation.gtf -o counts.txt *.bam
```

### Multi-Mapping and Overlaps

```bash
# Discard multi-mappers (default, recommended for DE)
featureCounts -a annotation.gtf -o counts.txt *.bam

# Fractional count for multi-mappers
featureCounts -M --fraction -a annotation.gtf -o counts.txt *.bam

# Count overlapping features with fractional allocation
featureCounts -O --fraction -a annotation.gtf -o counts.txt *.bam
```

### Extract Clean Count Matrix

**WARNING**: The `cut` approach below is fragile because `featureCounts` column positions change when options like `-J` (group-by) are used. Use the Python approach for robustness.

```bash
# Fragile: only valid for default featureCounts output with exactly 6 annotation columns.
# If you added -J or other options, column positions shift and this produces wrong data.
# cut -f1,7- counts.txt | tail -n +2 > count_matrix.txt
```

```python
import pandas as pd

counts = pd.read_csv('counts.txt', sep='\t', comment='#')
count_matrix = counts.set_index('Geneid')
# Drop annotation columns by name for robustness
count_matrix = count_matrix.drop(columns=['Chr', 'Start', 'End', 'Strand', 'Length'], errors='ignore')
count_matrix.columns = [c.replace('.bam', '').split('/')[-1] for c in count_matrix.columns]
count_matrix.to_csv('count_matrix.csv')
```

---

## Alignment-Based: STAR --quantMode GeneCounts

STAR can output gene counts directly during alignment (see `bio-mrna-seq-alignment`).

Output file: `sample_ReadsPerGene.out.tab`

Columns:
1. Gene ID
2. Unstranded
3. Forward strand
4. Reverse strand

---

## Alignment-Free: Salmon

### Build Index

```bash
# Decoy-aware index (recommended)
grep "^>" genome.fa | cut -d " " -f 1 | sed 's/>//g' > decoys.txt
cat transcripts.fa genome.fa > gentrome.fa
salmon index -t gentrome.fa -d decoys.txt -i salmon_index -p 8
```

### Quantify

```bash
# Paired-end
salmon quant -i salmon_index -l A \
    -1 sample_R1.fastq.gz -2 sample_R2.fastq.gz \
    -o sample_quant -p 8 --gcBias --seqBias

# Single-end: explicitly specify library type. Do NOT use -l A for single-end.
salmon quant -i salmon_index -l SR \
    -r sample.fastq.gz \
    -o sample_quant -p 8
```

### Batch Processing

```bash
for sample in sample1 sample2 sample3; do
    salmon quant -i salmon_index -l A \
        -1 ${sample}_R1.fastq.gz -2 ${sample}_R2.fastq.gz \
        -o ${sample}_quant -p 8 --gcBias --seqBias
done
```

### Combine Salmon Results (Python)

```python
import pandas as pd
from pathlib import Path

samples = ['sample1', 'sample2', 'sample3']
counts = pd.DataFrame({s: pd.read_csv(f'{s}_quant/quant.sf', sep='\t', index_col=0)['NumReads'] for s in samples})
tpm = pd.DataFrame({s: pd.read_csv(f'{s}_quant/quant.sf', sep='\t', index_col=0)['TPM'] for s in samples})

# Note: for DESeq2/edgeR, import via tximport (see below) rather than using raw NumReads directly,
# to properly account for transcript length differences across samples.
counts.to_csv('salmon_counts.csv')
tpm.to_csv('salmon_tpm.csv')
```

---

## Alignment-Free: kallisto

### Build Index

```bash
kallisto index -i kallisto_index transcripts.fa
```

### Quantify

```bash
# Paired-end
kallisto quant -i kallisto_index -o sample_quant \
    sample_R1.fastq.gz sample_R2.fastq.gz -t 8

# Single-end (must specify fragment length)
kallisto quant -i kallisto_index -o sample_quant \
    --single -l 200 -s 20 sample.fastq.gz -t 8

# With bootstraps for sleuth
kallisto quant -i kallisto_index -o sample_quant -b 100 \
    sample_R1.fastq.gz sample_R2.fastq.gz -t 8
```

---

## tximport (R)

Summarize transcript-level quantifications to gene-level counts for DESeq2/edgeR.

```r
library(tximport)

# tx2gene: a two-column data.frame mapping transcript_id to gene_id
# e.g., read from a GTF-derived TSV: tx2gene <- read.csv('tx2gene.tsv', sep='\t', col.names=c('tx', 'gene'))

# Salmon
files <- file.path('salmon_out', samples, 'quant.sf')
txi <- tximport(files, type = 'salmon', tx2gene = tx2gene)

# kallisto
files <- file.path('kallisto_out', samples, 'abundance.tsv')
txi <- tximport(files, type = 'kallisto', tx2gene = tx2gene)

# Access counts and abundance
counts <- txi$counts
abundance <- txi$abundance  # TPM-averaged
length <- txi$length
```

## tximeta (R) — Modern Best Practice

`tximeta` automatically imports Salmon/kallisto outputs, attaches transcript metadata, and verifies the reference version. It returns a `SummarizedExperiment` that can be summarized to gene level.

```r
library(tximeta)

# One-time setup: register the linked transcriptome so tximeta can verify the index
# makeLinkedTxome(indexDir='salmon_index', source='Ensembl', organism='Homo sapiens',
#                 release='110', genome='GRCh38', fasta='transcripts.fa', gtf='annotation.gtf')

coldata <- data.frame(
    names = samples,
    files = file.path('salmon_out', samples, 'quant.sf'),
    stringsAsFactors = FALSE
)

se <- tximeta(coldata)           # transcript-level SummarizedExperiment
gse <- summarizeToGene(se)       # gene-level SummarizedExperiment

counts <- assay(gse, 'counts')
abundance <- assay(gse, 'abundance')
```

## Quality Checks

- **featureCounts assignment rate** > 70%
- **Salmon mapping rate** > 70% (`grep "Mapping rate" logs/salmon_quant.log`)
- **Consistent library type** across Salmon samples
- **GTF reference matches genome version**

## Related Skills

- `bio-mrna-seq-alignment` - Generate input BAMs
- `bio-mrna-seq-count-prep` - Matrix ingest, ID mapping, metadata
- `bio-mrna-seq-pipeline` - End-to-end workflow
