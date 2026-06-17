# Example: Load multiple samples from a SampleSheet with Seurat

source("../scripts/r/samplesheet.R")

# Load all samples and merge into a single Seurat object
obj <- load_from_samplesheet("samplesheet.csv", merge = TRUE)

print(obj)
cat("Samples:\n")
print(table(obj$sample_id))

if ("batch" %in% colnames(obj@meta.data)) {
  cat("Batches:\n")
  print(table(obj$batch))
}

# Save merged
saveRDS(obj, "merged.rds")

# --- Alternative: load as list for per-sample QC ---
# obj_list <- load_from_samplesheet("samplesheet.csv", merge = FALSE)
# for (nm in names(obj_list)) {
#   cat(nm, ":", ncol(obj_list[[nm]]), "cells\n")
# }
