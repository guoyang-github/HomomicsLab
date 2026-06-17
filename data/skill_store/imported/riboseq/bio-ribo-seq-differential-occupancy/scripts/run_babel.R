#!/usr/bin/env Rscript
# Babel differential translation analysis
# Usage: Rscript scripts/run_babel.R [RNA_COUNTS] [RIBO_COUNTS] [CONDITIONS_CSV] [OUT_CSV]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("Usage: Rscript scripts/run_babel.R [RNA_COUNTS] [RIBO_COUNTS] [CONDITIONS_CSV] [OUT_CSV]")
}
rna_file <- args[1]
ribo_file <- args[2]
cond_csv <- args[3]
out_csv <- args[4]

library(Babel)

ribo <- read.delim(ribo_file, comment.char = "#", row.names = 1)
ribo <- ribo[, -(1:5)]

rna <- read.delim(rna_file, comment.char = "#", row.names = 1)
rna <- rna[, -(1:5)]

common_genes <- intersect(rownames(ribo), rownames(rna))
ribo <- ribo[common_genes, ]
rna <- rna[common_genes, ]

if (!identical(colnames(ribo), colnames(rna))) {
  stop("Ribo-seq and RNA-seq column names do not match.")
}

cond_df <- read.csv(cond_csv, header = FALSE, stringsAsFactors = FALSE)
if (ncol(cond_df) >= 2) {
  condition <- cond_df[[2]]
} else {
  condition <- cond_df[[1]]
}

if (length(condition) != ncol(ribo)) {
  stop("Condition vector length (", length(condition), ") does not match number of samples (", ncol(ribo), ").")
}

babel_results <- babel(ribo_counts = ribo, rna_counts = rna, conditions = condition)
write.csv(babel_results, out_csv)
