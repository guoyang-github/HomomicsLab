# Metagene Visualization - Usage Guide

## Overview

Generate publication-quality metagene plots, frame distributions, gene-body heatmaps, and IGV snapshots from Ribo-seq alignments.

## Prerequisites

```bash
pip install plastid matplotlib numpy pysam
```

Optional for IGV snapshots:
```bash
# Download IGV and run in batch mode with xvfb-run
```

## Quick Start

Tell your AI agent:
- "Create a metagene plot around start codons"
- "Plot reading frame distribution for my Ribo-seq data"
- "Generate a gene-body ribosome occupancy heatmap"
- "Create IGV snapshots for my top differential genes"

## Example Prompts

### Metagene Plots

> "Plot metagene profile around start codons with frame coloring"

> "Create stop codon metagene plots for all samples"

### Frame and Heatmap

> "Show the reading frame distribution in CDS"

> "Generate a normalized gene-body heatmap for top 100 genes"

### IGV Snapshots

> "Batch generate IGV snapshots for genes of interest"

> "Create genome browser images for differentially occupied genes"

## What the Agent Will Do

1. Load BAM files with P-site offset correction
2. Compute metagene profiles around start/stop codons
3. Calculate frame distributions and gene-body occupancy
4. Generate heatmaps sorted by peak position
5. Optionally write IGV batch scripts for genome snapshots

## Tips

- **Frame 0 enrichment** at start codons is the hallmark of good Ribo-seq
- Use **P-site offsets** from periodicity analysis for accurate positioning
- Gene-body heatmaps look best when sorted by peak position
- IGV snapshots require BAM index files (.bai) and a reference genome
