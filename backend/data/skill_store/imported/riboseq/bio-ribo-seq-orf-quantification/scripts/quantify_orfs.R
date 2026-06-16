#!/usr/bin/env Rscript
# ORF quantification from Ribo-seq BAMs
# Usage: Rscript scripts/quantify_orfs.R [GTF] [BAM_DIR] [OUTDIR]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript scripts/quantify_orfs.R [GTF] [BAM_DIR] [OUTDIR]")
}
gtf <- args[1]
bam_dir <- args[2]
outdir <- args[3]

library(GenomicFeatures)
library(GenomicAlignments)
library(DESeq2)

txdb <- makeTxDbFromGFF(gtf, format = "gtf")
cds <- cdsBy(txdb, by = 'tx', use.names = TRUE)

samples <- list.files(bam_dir, pattern = '\\.sorted\\.bam$', full.names = FALSE)
samples <- gsub('\\.sorted\\.bam$', '', samples)

if (length(samples) == 0) {
  stop("No BAM files found in ", bam_dir)
}

orf_count_matrix <- sapply(samples, function(s) {
  bam <- file.path(bam_dir, paste0(s, '.sorted.bam'))
  if (!file.exists(bam)) {
    stop("BAM file not found: ", bam)
  }
  ribo <- readGAlignments(bam, param = ScanBamParam(what = c("qname")))
  countOverlaps(cds, ribo, ignore.strand = FALSE)
})

rownames(orf_count_matrix) <- names(cds)
write.table(orf_count_matrix, file.path(outdir, 'orf_counts.tsv'), sep = '\t', quote = FALSE)

# Read sample metadata if available, otherwise treat all as one group
metadata_file <- file.path(bam_dir, "..", "sample_conditions.tsv")
if (file.exists(metadata_file)) {
  meta <- read.delim(metadata_file, header = FALSE, stringsAsFactors = FALSE)
  cond_map <- setNames(meta[[2]], meta[[1]])
  conditions <- factor(cond_map[samples])
  if (any(is.na(conditions))) {
    conditions <- factor(samples)
  }
} else {
  conditions <- factor(rep("single_group", length(samples)))
}

coldata <- data.frame(
  condition = conditions,
  row.names = samples
)

if (ncol(orf_count_matrix) >= 2 && length(unique(coldata$condition)) >= 2) {
  dds <- DESeqDataSetFromMatrix(orf_count_matrix, coldata, ~ condition)
  dds <- DESeq(dds)
  res <- results(dds)
  write.csv(as.data.frame(res), file.path(outdir, 'orf_deseq2_results.csv'))
}
