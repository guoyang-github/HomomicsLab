#' Example: Load multiple spatial samples from a SampleSheet with Seurat
#' Reference: Seurat 5.0+ | Verify API if version differs

# Source the spatial data I/O module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "samplesheet.R"))

message("=== Loading Spatial Samples from SampleSheet ===\n")

# Load all samples and merge into a single Seurat object
obj <- load_from_samplesheet("samplesheet.csv", merge = TRUE)

print(obj)
cat("Samples:\n")
print(table(obj$sample_id))

if ("batch" %in% colnames(obj@meta.data)) {
  cat("Batches:\n")
  print(table(obj$batch))
}

# Access spatial coordinates
coords <- GetTissueCoordinates(obj)
message(sprintf("Spatial coordinates: %d spots x %d dims", nrow(coords), ncol(coords)))

# Save
saveRDS(obj, "spatial_merged.rds")
message("\nSaved to: spatial_merged.rds")

# --- Alternative: load as list for per-sample QC ---
# obj_list <- load_from_samplesheet("samplesheet.csv", merge = FALSE)
# for (nm in names(obj_list)) {
#   cat(nm, ":", ncol(obj_list[[nm]]), "spots\n")
# }
