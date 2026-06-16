#' Example: Load GEO Visium data (h5 + spatial.tar.gz) with Seurat
#' Reference: Seurat 5.0+ | Verify API if version differs

# Source the spatial data I/O module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "geo_loaders.R"))

message("=== Loading GEO Visium Data ===\n")

# GEO often provides Visium data as separate h5 and spatial.tar.gz files
# This function auto-restructures them into standard Space Ranger format

obj <- load_geo_visium(
  data.dir = "GSE12345/PA08/",
  sample_id = "PA08",
  slice = "slice1"
)

print(obj)
cat("Sample ID:", unique(obj$sample_id), "\n")

# Access spatial coordinates and images
coords <- GetTissueCoordinates(obj)
message(sprintf("Spatial coordinates: %d spots", nrow(coords)))

# Save
saveRDS(obj, "geo_visium_loaded.rds")
message("\nSaved to: geo_visium_loaded.rds")
