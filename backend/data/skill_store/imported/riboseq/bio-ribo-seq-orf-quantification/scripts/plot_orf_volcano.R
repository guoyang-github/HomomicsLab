#!/usr/bin/env Rscript
# Volcano plot for differential ORF expression
# Usage: Rscript scripts/plot_orf_volcano.R [DESEQ2_RESULTS_CSV] [OUT_PDF]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript scripts/plot_orf_volcano.R [DESEQ2_RESULTS_CSV] [OUT_PDF]")
}
res_csv <- args[1]
out_pdf <- args[2]

library(ggplot2)

df <- read.csv(res_csv, row.names = 1)
df$significant <- ifelse(is.na(df$padj), FALSE, df$padj < 0.05 & abs(df$log2FoldChange) > 1)

p <- ggplot(df, aes(x = log2FoldChange, y = -log10(pvalue), color = significant)) +
  geom_point(alpha = 0.5) +
  scale_color_manual(values = c('grey', 'red')) +
  theme_minimal() +
  labs(title = 'Differential ORF Expression',
       x = 'log2 Fold Change',
       y = '-log10 p-value')

ggsave(out_pdf, p, width = 6, height = 5)
