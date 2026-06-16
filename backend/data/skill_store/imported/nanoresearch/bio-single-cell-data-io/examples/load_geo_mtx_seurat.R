# Example: Load GEO merged MTX + metadata CSV with Seurat

source("../scripts/r/geo_loaders.R")

# GEO pattern: one MTX directory for all cells,
# metadata CSV maps each barcode to its sample
obj <- load_geo_mtx_merged(
  mtx_dir = "GSE12345/",
  metadata_csv = "GSE12345_cell_metadata.csv",
  sample_col = "sample"
)

print(obj)
cat("Samples:\n")
print(table(obj$sample))

# The metadata CSV can contain additional columns (condition, batch, etc.)
# They are automatically added to obj@meta.data
cat("Metadata columns:\n")
print(colnames(obj@meta.data))

saveRDS(obj, "geo_loaded.rds")
