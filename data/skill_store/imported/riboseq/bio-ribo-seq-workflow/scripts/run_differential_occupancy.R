#!/usr/bin/env Rscript
# Differential ribosome occupancy analysis with DESeq2 (Ribo-seq only)
# Usage: Rscript scripts/run_differential_occupancy.R [OUTDIR]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript scripts/run_differential_occupancy.R [OUTDIR]")
}
outdir <- args[1]
library(DESeq2)

clean_names <- function(x) {
  x <- gsub(".sorted.bam$", "", x)
  x <- gsub("^.*/", "", x)
  return(x)
}

counts <- read.delim(file.path(outdir, "ribo_counts.tsv"), comment.char = "#", row.names = 1)
counts <- counts[, - (1:5)]
colnames(counts) <- clean_names(colnames(counts))

coldata_map <- read.delim(file.path(outdir, "sample_conditions.tsv"), header = FALSE, stringsAsFactors = FALSE)
conditions <- setNames(coldata_map[[2]], coldata_map[[1]])

if (!all(colnames(counts) %in% names(conditions))) {
  stop("Some samples in the count matrix are missing from sample_conditions.tsv")
}

condition_vec <- factor(conditions[colnames(counts)])
if (any(is.na(condition_vec))) {
  stop("Condition mapping produced NAs. Check sample_conditions.tsv.")
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
write.csv(as.data.frame(res), file.path(outdir, "deseq2_occupancy_results.csv"))
