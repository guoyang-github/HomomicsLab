# SPOTlight Utility Functions
#
# Helper functions for SPOTlight deconvolution workflow.

#' Validate SPOTlight Input Data
#'
#' Check that input data meets requirements for SPOTlight analysis.
#'
#' @param spatial_counts Gene expression matrix for spatial data
#' @param reference_counts Gene expression matrix for reference scRNA-seq
#' @param cell_types Named vector of cell type labels
#' @param marker_genes List of marker genes (optional)
#'
#' @return Logical indicating if data is valid
#'
#' @export
validate_spotlight_data <- function(spatial_counts, reference_counts, cell_types, marker_genes = NULL) {
    errors <- c()

    # Check dimensions
    if (ncol(reference_counts) != length(cell_types)) {
        errors <- c(errors, "Number of cells in reference_counts must match length of cell_types")
    }

    # Check for empty matrices
    if (nrow(spatial_counts) == 0 || ncol(spatial_counts) == 0) {
        errors <- c(errors, "spatial_counts is empty")
    }

    if (nrow(reference_counts) == 0 || ncol(reference_counts) == 0) {
        errors <- c(errors, "reference_counts is empty")
    }

    # Check for NA values
    if (any(is.na(spatial_counts))) {
        errors <- c(errors, "spatial_counts contains NA values")
    }

    if (any(is.na(reference_counts))) {
        errors <- c(errors, "reference_counts contains NA values")
    }

    # Check marker genes if provided
    if (!is.null(marker_genes)) {
        if (!is.list(marker_genes)) {
            errors <- c(errors, "marker_genes must be a list")
        } else {
            all_markers <- unlist(marker_genes)
            missing_in_spatial <- setdiff(all_markers, rownames(spatial_counts))
            missing_in_ref <- setdiff(all_markers, rownames(reference_counts))

            if (length(missing_in_spatial) > 0) {
                warning(sprintf("%d marker genes not found in spatial data", length(missing_in_spatial)))
            }
            if (length(missing_in_ref) > 0) {
                warning(sprintf("%d marker genes not found in reference data", length(missing_in_ref)))
            }
        }
    }

    # Print validation results
    if (length(errors) > 0) {
        cat("Validation FAILED:\n")
        for (err in errors) {
            cat("  -", err, "\n")
        }
        return(FALSE)
    } else {
        cat("Validation PASSED\n")
        cat(sprintf("  Spatial: %d genes x %d spots\n", nrow(spatial_counts), ncol(spatial_counts)))
        cat(sprintf("  Reference: %d genes x %d cells\n", nrow(reference_counts), ncol(reference_counts)))
        cat(sprintf("  Cell types: %s\n", paste(unique(cell_types), collapse = ", ")))
        return(TRUE)
    }
}


#' Extract Top Marker Genes
#'
#' Extract top marker genes from Seurat FindAllMarkers output.
#'
#' @param markers Data frame from FindAllMarkers
#' @param n_top Number of top markers per cell type (default: 20)
#' @param min_avg_log2FC Minimum log2 fold change (default: 0.5)
#' @param max_padj Maximum adjusted p-value (default: 0.05)
#'
#' @return Named list of marker genes per cluster
#'
#' @export
extract_top_markers <- function(markers, n_top = 20, min_avg_log2FC = 0.5, max_padj = 0.05) {
    # Filter markers
    filtered <- markers[markers$avg_log2FC >= min_avg_log2FC &
                        markers$p_val_adj <= max_padj, ]

    # Get top markers per cluster
    marker_list <- list()
    for (cluster in unique(filtered$cluster)) {
        cluster_markers <- filtered[filtered$cluster == cluster, ]
        cluster_markers <- cluster_markers[order(-cluster_markers$avg_log2FC), ]
        marker_list[[as.character(cluster)]] <- head(cluster_markers$gene, n_top)
    }

    return(marker_list)
}


#' Prepare Seurat Data for SPOTlight
#'
#' Extract expression matrix and cell type labels from Seurat object.
#'
#' @param seurat_obj Seurat object
#' @param cell_type_col Column name with cell type annotations
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to use (default: "counts")
#'
#' @return List with counts matrix and cell type vector
#'
#' @export
prepare_seurat_for_spotlight <- function(seurat_obj, cell_type_col, assay = "RNA", slot = "counts") {
    # Check if column exists
    if (!cell_type_col %in% colnames(seurat_obj@meta.data)) {
        stop(sprintf("Column '%s' not found in Seurat object metadata", cell_type_col))
    }

    # Extract counts
    if (packageVersion("SeuratObject") >= "5.0.0") {
        counts <- GetAssayData(seurat_obj, assay = assay, layer = slot)
    } else {
        counts <- GetAssayData(seurat_obj, assay = assay, slot = slot)
    }

    # Extract cell types
    cell_types <- setNames(seurat_obj@meta.data[[cell_type_col]], colnames(seurat_obj))

    cat(sprintf("Prepared data: %d genes x %d cells\n", nrow(counts), ncol(counts)))
    cat(sprintf("Cell types: %s\n", paste(unique(cell_types), collapse = ", ")))

    return(list(counts = counts, cell_types = cell_types))
}


#' Filter Low Quality Spots
#'
#' Remove spots with too few counts or genes.
#'
#' @param spatial_counts Gene expression matrix
#' @param min_counts Minimum counts per spot (default: 100)
#' @param min_genes Minimum genes per spot (default: 50)
#'
#' @return Filtered expression matrix
#'
#' @export
filter_low_quality_spots <- function(spatial_counts, min_counts = 100, min_genes = 50) {
    # Calculate metrics
    spot_counts <- colSums(spatial_counts)
    spot_genes <- colSums(spatial_counts > 0)

    # Filter
    keep <- spot_counts >= min_counts & spot_genes >= min_genes

    cat(sprintf("Filtering spots: %d -> %d\n", ncol(spatial_counts), sum(keep)))
    cat(sprintf("  Removed %d low-quality spots\n", sum(!keep)))

    return(spatial_counts[, keep, drop = FALSE])
}


#' Print SPOTlight Results Summary
#'
#' Print a summary of SPOTlight deconvolution results.
#'
#' @param spotlight_results Results from run_spotlight
#'
#' @export
print_spotlight_summary <- function(spotlight_results) {
    cat("SPOTlight Deconvolution Results\n")
    cat("================================\n\n")

    proportions <- spotlight_results$proportions

    cat(sprintf("Spots analyzed: %d\n", nrow(proportions)))
    cat(sprintf("Cell types: %d\n", ncol(proportions)))
    cat(sprintf("Cell types: %s\n\n", paste(colnames(proportions), collapse = ", ")))

    # Calculate average proportions
    avg_props <- colMeans(proportions)
    cat("Average proportions:\n")
    for (ct in names(avg_props)) {
        cat(sprintf("  %s: %.2f%%\n", ct, avg_props[ct] * 100))
    }

    # Find dominant cell type per spot
    dominant <- apply(proportions, 1, function(x) names(x)[which.max(x)])
    dominant_table <- table(dominant)
    cat("\nDominant cell type per spot:\n")
    for (ct in names(dominant_table)) {
        cat(sprintf("  %s: %d spots (%.1f%%)\n", ct, dominant_table[ct],
                    100 * dominant_table[ct] / length(dominant)))
    }
}
