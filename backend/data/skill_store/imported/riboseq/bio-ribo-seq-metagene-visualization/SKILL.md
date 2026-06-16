---
name: bio-ribo-seq-metagene-visualization
description: Generate publication-quality metagene plots, frame distributions, heatmaps, and IGV snapshots from Ribo-seq data. Use for QC figures and manuscript reporting.
tool_type: mixed
primary_tool: matplotlib
---

## Version Compatibility

Reference examples tested with: matplotlib 3.8+, numpy 1.26+, pysam 0.22+, scipy 1.12+, plastid 0.6+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Metagene and Genome Visualization

**"Create metagene plots and genome snapshots for my Ribo-seq data"** → Generate publication-quality figures including metagene profiles around start/stop codons, reading frame distributions, gene-body heatmaps, and IGV batch snapshots.

## Output Directory Structure

```
results/08_visualization/
├── metagene_start_codon.pdf
├── metagene_stop_codon.pdf
├── frame_distribution.pdf
├── genebody_heatmap.pdf
└── igv_snapshots/
    └── gene_xyz.png
```

## Concept: What Metagene Plots Show

A **metagene plot** aggregates ribosome density across thousands of genes aligned at a common landmark (e.g., start codon or stop codon). It reveals:
- A sharp peak ~12–15 nt upstream of the start codon: the **P-site**
- 3-nt periodicity: evidence of active translation
- Read-length stratification: different footprint sizes correspond to different ribosome states

### Gene-Body Binning for Heatmaps

Because transcripts vary in length, gene-body coverage must be **rescaled to a common coordinate system** before heatmap visualization. This is done by dividing the CDS into `N` equal-sized bins and averaging reads within each bin:

```python
import numpy as np

def bin_counts(counts, bins=50):
    '''Rescale a 1-D coverage array into equal-sized bins.'''
    if len(counts) < bins:
        return None
    # Method 1: linear interpolation (smooth but loses nucleotide resolution)
    x_old = np.linspace(0, 1, len(counts))
    x_new = np.linspace(0, 1, bins)
    return np.interp(x_new, x_old, counts)

    # Method 2: true binning (preserves local structure)
    split = np.array_split(counts, bins)
    return np.array([s.mean() for s in split])
```

- **Interpolation** is useful for smooth heatmaps but blurs small features.
- **Array-split binning** (`np.array_split`) preserves local peaks but can look noisier for short genes.

## Step 1: Metagene Plot Around Start Codon

```bash
python scripts/plot_metagene_start.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --out results/08_visualization/metagene_start_codon.pdf
```

## Step 2: Frame Distribution Plot

```bash
python scripts/plot_frame_distribution.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --out results/08_visualization/frame_distribution.pdf
```

## Step 3: Gene-Body Heatmap

```bash
python scripts/plot_genebody_heatmap.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --gtf results/00_index/annotation_clean.gtf \
  --n-genes 100 \
  --out results/08_visualization/genebody_heatmap.pdf
```

## Step 4: IGV Batch Snapshots

```bash
bash scripts/batch_igv_snapshots.sh \
  results/00_index/genome.fa \
  genes_of_interest.bed \
  results/02_ribo_preprocessing \
  results/08_visualization/igv_snapshots
```

Then run the generated batch script:
```bash
xvfb-run igv.sh -b results/08_visualization/igv_snapshots/igv_batch.txt
```

## Related Skills

- bio-ribo-seq-ribosome-periodicity - Provides P-site offsets required for all plots
- bio-ribo-seq-riboseq-preprocessing - Provides aligned BAM files
- bio-ribo-seq-qc-reporting - Consumes some of these figures for summary reports
