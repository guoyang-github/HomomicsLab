# Differential Occupancy - Usage Guide

## Overview

Detect differential ribosome occupancy using Ribo-seq counts alone (DESeq2) or paired with RNA-seq (Xtail / Babel).

## Prerequisites

```r
BiocManager::install(c('DESeq2', 'Xtail', 'Babel'))
```

```bash
conda install -c bioconda subread
```

## Quick Start

Tell your AI agent:
- "Find genes with differential ribosome occupancy"
- "Run Xtail on my Ribo-seq and RNA-seq counts"
- "Compare ribosome density between conditions without RNA-seq"

## Example Prompts

### Differential Occupancy

> "Run DESeq2 on my Ribo-seq count matrix"

> "Which genes show increased ribosome occupancy in treatment?"

> "Filter significant differential occupancy genes (padj < 0.05)"

### Xtail / Babel

> "Run Xtail to detect differential translation"

> "Use Babel for TE analysis with my paired data"

> "Compare DESeq2 occupancy vs Xtail TE results"

## What the Agent Will Do

1. Build or load CDS-level Ribo-seq count matrices
2. Run DESeq2 for simple differential occupancy (Ribo-seq only)
3. Optionally load RNA-seq counts and run Xtail / Babel
4. Extract and annotate significant genes
5. Export results tables

## Tips

- **DESeq2** alone tests differential occupancy (includes transcription + translation)
- **Xtail / Babel** separates translational from transcriptional changes
- Ensure Ribo-seq and RNA-seq matrices have identical gene and sample ordering
- Use CDS counts for Ribo-seq and full transcript counts for RNA-seq
