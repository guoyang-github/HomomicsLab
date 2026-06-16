#!/usr/bin/env Rscript
# Xtail differential translation analysis (requires paired Ribo-seq + RNA-seq)
# Usage: Rscript scripts/run_xtail.R [RNA_COUNTS] [RIBO_COUNTS] [CONDITIONS_CSV] [OUT_CSV]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("Usage: Rscript scripts/run_xtail.R [RNA_COUNTS] [RIBO_COUNTS] [CONDITIONS_CSV] [OUT_CSV]")
}
rna_file <- args[1]
ribo_file <- args[2]
cond_csv <- args[3]
out_csv <- args[4]

library(Xtail)

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

results <- xtail(rna, ribo, condition)
res_table <- resultsTable(results)
write.csv(res_table, out_csv)
