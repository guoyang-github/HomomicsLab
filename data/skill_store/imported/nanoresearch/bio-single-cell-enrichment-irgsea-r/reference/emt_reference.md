# EMT Gene Sets Reference for irGSEA

This file provides ready-to-use EMT (Epithelial-Mesenchymal Transition) gene sets for the `bio-single-cell-enrichment-irgsea-r` skill.

## How to Use

Source these gene sets into your R script and pass them to `run_irgsea_seurat()` or `run_irgsea()`:

```r
source("reference/emt_reference.R")  # if saved as R script
# or copy the list below into your script

seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = emt_gene_sets,
  slot = "counts",
  method = c("AUCell", "UCell"),
  rra_integration = TRUE
)

seurat_obj <- calculate_emt_score(
  seurat_obj,
  mesenchymal_col = "irGSEA.UCell.Mesenchymal",
  epithelial_col = "irGSEA.UCell.Epithelial",
  method = "ratio",
  new_col_name = "EMT_Score"
)
```

## Complete EMT Gene Sets

```r
emt_gene_sets <- list(
  # Epithelial markers
  Epithelial = c(
    'CDH1', 'EPCAM', 'KRT8', 'KRT18', 'KRT19', 'OCLN', 'CLDN3', 'CLDN4',
    'CLDN7', 'TJP1', 'TJP2', 'TJP3', 'CGN', 'MARVELD2', 'CRB3', 'DSP',
    'PKP1', 'PKP2', 'PKP3', 'JUP', 'CTNNB1', 'ALCAM', 'CEACAM1', 'CEACAM5',
    'CEACAM6', 'MUC1', 'MUC4', 'MUC16', 'CD24', 'HES1', 'PARD3', 'PARD6A',
    'PARD6B', 'AMOT', 'AMOTL1', 'AMOTL2', 'INADL', 'MPP5', 'PALS1', 'CRUMBS3',
    'LLGL1', 'LLGL2', 'SCRIB', 'DLG1', 'DLG2', 'DLG3', 'DLG4', 'DLG5'
  ),

  # Mesenchymal markers
  Mesenchymal = c(
    'CDH2', 'VIM', 'FN1', 'SNAI1', 'SNAI2', 'TWIST1', 'ZEB1', 'ZEB2',
    'MMP2', 'MMP3', 'MMP9', 'SERPINE1', 'ACTA2', 'TAGLN', 'TGFB1',
    'TGFBR1', 'TGFBR2', 'SMAD2', 'SMAD3', 'COL1A1', 'COL1A2', 'COL3A1',
    'COL5A1', 'FAP', 'THY1', 'VCAN', 'TNC', 'POSTN', 'WNT5A', 'WNT5B',
    'AXL', 'LOXL2', 'LOXL3', 'ITGA5', 'ITGAV', 'ITGB1', 'CD44', 'EMP3',
    'GADD45B', 'ID2', 'ID3', 'RHOC', 'ROCK1', 'RAC1', 'CDC42', 'PAK1',
    'LIMK1', 'CFL1', 'DSTN', 'TPM1', 'TPM2', 'MYL9', 'MYH9', 'PRKCA',
    'MARCKS', 'PPP1R12A', 'CALD1', 'MYLK', 'FLNA', 'FLNB'
  ),

  # Core EMT transcription factors
  EMT_TFs = c(
    "SNAI1", "SNAI2", "ZEB1", "ZEB2", "TWIST1", "TWIST2"
  ),

  # MSigDB Hallmark EMT gene set (for reference)
  EMT_Hallmark = c(
    'CTNNB1', 'GSK3B', 'MYC', 'SNAI1', 'SNAI2', 'TWIST1', 'ZEB1', 'ZEB2',
    'VIM', 'CDH2', 'FN1', 'MMP2', 'MMP9', 'SERPINE1', 'SPARC', 'TGFBR1',
    'TGFBR2', 'TGFB1', 'TGFB2', 'EGF', 'EGFR', 'PDGFRB', 'FGFR1', 'IGF1R',
    'WNT5A', 'WNT5B', 'AXL', 'LOXL2', 'LOXL3', 'ITGA5', 'ITGAV', 'COL1A1',
    'COL1A2', 'COL3A1', 'COL5A1', 'FAP', 'THY1', 'VCAN', 'TNC', 'POSTN',
    'MMP3', 'MMP10', 'MMP13', 'MMP14', 'MMP16', 'LAMB3', 'LAMC2', 'LAMA3',
    'TIMP1', 'TIMP2', 'ITGA2', 'ITGA3', 'ITGB1', 'CD44', 'EMP3', 'GADD45B',
    'TGIF1', 'ID2', 'ID3', 'FGF2', 'IGFBP3', 'IGFBP4', 'IGFBP5', 'VEGFA',
    'VEGFC', 'ANGPTL4', 'RHOC', 'ROCK1', 'RAC1', 'CDC42', 'PAK1', 'LIMK1',
    'CFL1', 'DSTN', 'ACTA2', 'TAGLN', 'TPM1', 'TPM2', 'MYL9', 'MYH9',
    'PRKCA', 'MARCKS', 'PPP1R12A', 'CALD1', 'MYLK', 'FLNA', 'FLNB', 'PALLD',
    'MYO10', 'ENAH', 'ARPC1B', 'ARPC2', 'ARPC3', 'ARPC4', 'ARPC5', 'WAS',
    'WASL', 'CYFIP1', 'ABI1', 'NCKAP1', 'HSPC300', 'BRK1'
  )
)
```

## Notes

- `EMT_TFs` is usually analyzed separately, not mixed into the `EMT_score` calculation.
- `EMT_score` is typically computed as `Mesenchymal / (Epithelial + 0.001)` using the `calculate_emt_score()` helper.
- `EMT_Hallmark` is a mixed E + M signature from MSigDB and measures overall EMT-associated gene expression.
