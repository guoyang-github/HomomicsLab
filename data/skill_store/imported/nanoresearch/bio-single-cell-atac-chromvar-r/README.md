# bio-single-cell-atac-chromvar-r

Single-cell ATAC-seq TF motif deviation analysis using chromVAR.

## Description

chromVAR is an R package for analyzing chromatin accessibility variation across single cells at transcription factor binding motifs. This skill provides wrapper functions and comprehensive documentation for running chromVAR analysis on scATAC-seq data.

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Run complete analysis
results <- run_chromvar(
  rse = your_rse_object,
  motifs = "jaspar2020",
  genome = "BSgenome.Hsapiens.UCSC.hg38"
)

# View top variable motifs
head(results$variability[order(results$variability$variability, decreasing = TRUE), ])
```

## Files

- `SKILL.md` - Comprehensive documentation
- `usage-guide.md` - Detailed usage guide
- `scripts/r/core_analysis.R` - Core analysis functions
- `scripts/r/visualization.R` - Visualization functions
- `scripts/r/utils.R` - Utility functions
- `examples/minimal_example.R` - Minimal example
- `examples/advanced_example.R` - Advanced example
- `tests/test_chromvar.R` - Unit tests

## Installation

```r
BiocManager::install("chromVAR")
BiocManager::install(c("motifmatchr", "JASPAR2020", "BSgenome.Hsapiens.UCSC.hg38"))
```

## Key Features

- Create chromVAR objects from count matrices and peak coordinates
- Filter peaks and correct for GC bias
- Match TF motifs from JASPAR database
- Compute motif accessibility deviations
- Identify variable TF motifs across cells
- Visualize results with heatmaps and dimensionality reduction plots
- Export results and generate reports

## References

1. Schep et al. (2017). chromVAR: inferring transcription-factor-associated accessibility from single-cell epigenomic data. *Nature Methods*.
2. chromVAR documentation: https://greenleaflab.github.io/chromVAR/
