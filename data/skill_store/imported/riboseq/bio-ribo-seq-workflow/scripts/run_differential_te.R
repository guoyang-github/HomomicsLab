#!/usr/bin/env Rscript
# Differential translation efficiency analysis with DESeq2 interaction model
# Usage: Rscript scripts/run_differential_te.R [OUTDIR]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript scripts/run_differential_te.R [OUTDIR]")
}
outdir <- args[1]
library(DESeq2)

clean_names <- function(x) {
  x <- gsub(".sorted.bam$", "", x)
  x <- gsub("^.*/", "", x)
  return(x)
}

ribo <- read.delim(file.path(outdir, "ribo_counts.tsv"), comment.char = "#", row.names = 1)
ribo <- ribo[, - (1:5)]
rna <- read.delim(file.path(outdir, "rna_counts.tsv"), comment.char = "#", row.names = 1)
rna <- rna[, - (1:5)]

colnames(ribo) <- clean_names(colnames(ribo))
colnames(rna) <- clean_names(colnames(rna))

if (!setequal(colnames(ribo), colnames(rna))) {
  stop("Ribo-seq and RNA-seq sample names do not match after cleaning.")
}

common <- intersect(rownames(ribo), rownames(rna))
ribo <- ribo[common, ]
rna <- rna[common, ]

common_samples <- intersect(colnames(ribo), colnames(rna))
ribo <- ribo[, common_samples, drop = FALSE]
rna <- rna[, common_samples, drop = FALSE]

counts <- cbind(ribo, rna)

coldata_map <- read.delim(file.path(outdir, "sample_conditions.tsv"), header = FALSE, stringsAsFactors = FALSE)
conditions <- setNames(coldata_map[[2]], coldata_map[[1]])
condition_vec <- factor(rep(conditions[colnames(ribo)], 2))

if (any(is.na(condition_vec))) {
  stop("Some samples in the count matrix are missing from sample_conditions.tsv")
}
if (length(unique(condition_vec)) < 2) {
  stop("Need at least two distinct conditions for differential analysis.")
}
if (ncol(counts) < 2) {
  stop("Need at least two samples for DESeq2.")
}

coldata <- data.frame(
  condition = condition_vec,
  assay = factor(rep(c("ribo", "rna"), each = ncol(ribo))),
  row.names = colnames(counts)
)

dds <- DESeqDataSetFromMatrix(counts, coldata, ~ condition + assay + condition:assay)
dds <- DESeq(dds)

# Robustly extract the interaction contrast
rn <- resultsNames(dds)
interaction_candidates <- grep("condition.*assay|assay.*condition", rn, value = TRUE)

if (length(interaction_candidates) == 0) {
  # Fallback: the last coefficient is typically the interaction term
  # when using ~ condition + assay + condition:assay with 2 condition levels
  last_term <- rn[length(rn)]
  warning("No interaction term matched by pattern. Using last coefficient: ", last_term)
  interaction_name <- last_term
} else {
  interaction_name <- interaction_candidates[1]
}

# Verify this coefficient actually represents an interaction
if (!grepl("condition.*assay|assay.*condition", interaction_name)) {
  warning("Selected coefficient may not be the interaction term: ", interaction_name,
          ". Available coefficients: ", paste(rn, collapse = ", "))
}

res <- results(dds, name = interaction_name)
write.csv(as.data.frame(res), file.path(outdir, "deseq2_te_results.csv"))
