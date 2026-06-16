#!/usr/bin/env Rscript
# DESeq2 differential ribosome occupancy analysis (Ribo-seq only)
# Usage: Rscript scripts/run_deseq2_occupancy.R [COUNTS_FILE] [OUT_CSV] [CONDITIONS_TSV]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript scripts/run_deseq2_occupancy.R [COUNTS_FILE] [OUT_CSV] [CONDITIONS_TSV]")
}
counts_file <- args[1]
out_csv <- args[2]
cond_tsv <- args[3]

library(DESeq2)

counts <- read.delim(counts_file, comment.char = "#", row.names = 1)
counts <- counts[, -(1:5)]

coldata_map <- read.delim(cond_tsv, header = FALSE, stringsAsFactors = FALSE)
conditions <- setNames(coldata_map[[2]], coldata_map[[1]])

if (!all(colnames(counts) %in% names(conditions))) {
  stop("Some samples in the count matrix are missing from conditions file.")
}

condition_vec <- factor(conditions[colnames(counts)])
if (any(is.na(condition_vec))) {
  stop("Condition mapping produced NAs. Check conditions file.")
}
if (length(unique(condition_vec)) < 2) {
  stop("Need at least two distinct conditions for differential analysis.")
}
if (ncol(counts) < 2) {
  stop("Need at least two samples for DESeq2.")
}

coldata <- data.frame(
  condition = condition_vec,
  row.names = colnames(counts)
)

dds <- DESeqDataSetFromMatrix(counts, coldata, ~ condition)
dds <- DESeq(dds)
res <- results(dds)

write.csv(as.data.frame(res), out_csv)
