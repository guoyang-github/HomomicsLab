#!/usr/bin/env Rscript
# Differential Expression Analysis with DESeq2
# Designed for Nextflow: single-sample/task execution, parameterized I/O

suppressPackageStartupMessages({
    library(DESeq2)
    library(ggplot2)
})

# --- Parse command line arguments ---
args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag) {
    idx <- which(args == flag)
    if (length(idx) == 0 || idx == length(args)) {
        stop(paste("Missing required argument:", flag))
    }
    return(args[idx + 1])
}

input_file <- get_arg("--input")
outprefix  <- get_arg("--outprefix")

# --- Validate inputs ---
if (!file.exists(input_file)) {
    stop(paste("Input file not found:", input_file))
}

# --- Load and process data ---
counts <- read.csv(input_file, row.names = 1)

# Example: simple DESeq2 workflow (adapt to your actual design)
coldata <- data.frame(
    condition = factor(rep(c("treated", "control"), length.out = ncol(counts))),
    row.names = colnames(counts)
)

dds <- DESeqDataSetFromMatrix(
    countData = counts,
    colData   = coldata,
    design    = ~ condition
)

dds <- DESeq(dds)
res <- results(dds)

# --- Write outputs with prefix for uniqueness ---
write.csv(as.data.frame(res), file = paste0(outprefix, ".results.csv"))

pdf(paste0(outprefix, ".plots.pdf"))
plotMA(res, main = paste("MA Plot:", outprefix))
dev.off()

message("DESeq2 analysis complete for: ", outprefix)
