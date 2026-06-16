#!/usr/bin/env Rscript
# Differential TE using DESeq2 interaction model
# Usage: Rscript deseq2_interaction_te.R [RIBO_COUNTS] [RNA_COUNTS] [CONDITIONS_CSV] [OUT_CSV]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("Usage: Rscript deseq2_interaction_te.R [RIBO_COUNTS] [RNA_COUNTS] [CONDITIONS_CSV] [OUT_CSV]")
}
ribo_file <- args[1]
rna_file <- args[2]
cond_csv <- args[3]
out_csv <- args[4]

library(DESeq2)

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

counts <- cbind(ribo_counts, rna_counts)
n_ribo <- ncol(ribo_counts)
n_rna <- ncol(rna_counts)

coldata <- data.frame(
  condition = condition,
  assay = factor(rep(c("ribo", "rna"), c(n_ribo, n_rna))),
  row.names = colnames(counts)
)

dds <- DESeqDataSetFromMatrix(
  countData = counts,
  colData = coldata,
  design = ~ condition + assay + condition:assay
)

dds <- DESeq(dds)

# Robustly extract the interaction contrast
available_names <- resultsNames(dds)
interaction_name <- grep("condition.*assay", available_names, value = TRUE)[1]
if (is.na(interaction_name) || nchar(interaction_name) == 0) {
  interaction_name <- available_names[length(available_names)]
}

res_te <- results(dds, name = interaction_name)
write.csv(as.data.frame(res_te), out_csv)
