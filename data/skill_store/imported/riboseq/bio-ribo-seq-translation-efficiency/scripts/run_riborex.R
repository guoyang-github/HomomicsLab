#!/usr/bin/env Rscript
# Differential translation efficiency with riborex
# Usage: Rscript run_riborex.R [RIBO_COUNTS] [RNA_COUNTS] [CONDITIONS_CSV] [OUT_CSV]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("Usage: Rscript run_riborex.R [RIBO_COUNTS] [RNA_COUNTS] [CONDITIONS_CSV] [OUT_CSV]")
}
ribo_file <- args[1]
rna_file <- args[2]
cond_csv <- args[3]
out_csv <- args[4]

library(riborex)

ribo_counts <- read.delim(ribo_file, comment.char = '#', row.names = 1)
ribo_counts <- ribo_counts[, -(1:5)]

rna_counts <- read.delim(rna_file, comment.char = '#', row.names = 1)
rna_counts <- rna_counts[, -(1:5)]

common_genes <- intersect(rownames(ribo_counts), rownames(rna_counts))
ribo_counts <- ribo_counts[common_genes, ]
rna_counts <- rna_counts[common_genes, ]

if (!identical(colnames(ribo_counts), colnames(rna_counts))) {
  stop("Ribo-seq and RNA-seq column names do not match.")
}

cond_df <- read.csv(cond_csv, header = FALSE, stringsAsFactors = FALSE)
if (ncol(cond_df) >= 2) {
  condition <- factor(cond_df[[2]])
} else {
  condition <- factor(cond_df[[1]])
}

if (length(condition) != ncol(ribo_counts)) {
  stop("Condition vector length does not match number of samples.")
}
if (length(unique(condition)) < 2) {
  stop("Need at least two distinct conditions for differential analysis.")
}

sample_info <- data.frame(
  sample = colnames(ribo_counts),
  condition = condition
)

results <- riborex(
  rnaCntTable = rna_counts,
  riboCntTable = ribo_counts,
  rnaCond = sample_info$condition,
  riboCond = sample_info$condition
)

write.csv(results, out_csv)
