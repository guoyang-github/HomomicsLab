# ScType Cell Type Annotation for Seurat Objects
# Adapted from: https://github.com/IanevskiAleksandr/sc-type
# License: GNU General Public License v3.0

#' @title Run ScType Annotation
#' @description Main function to run ScType cell type annotation on a Seurat object
#' @param seurat_obj Seurat object
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to extract data from (default: "data", options: "counts", "data", "scale.data")
#' @param tissue Tissue type from built-in database. If NULL, auto-detection is performed.
#' @param marker_file Path to custom marker Excel file (optional)
#' @param marker_list Custom marker list with gs_positive and gs_negative (optional)
#' @param db_source Built-in database to use: "full" or "short" (default: "full")
#' @param cluster_col Column in metadata containing cluster IDs (default: "seurat_clusters")
#' @param score_threshold Minimum score threshold for cell type assignment. If NULL, uses ncells/4.
#' @param return_scores Return full score matrix (default: FALSE)
#' @param plot_results Generate UMAP plot with annotations (default: FALSE)
#' @param output_col Column name for output annotations (default: "sctype_cell_type")
#' @return Seurat object with sctype annotations added to metadata
#' @export
run_sctype_annotation <- function(
    seurat_obj,
    assay = "RNA",
    slot = "data",
    tissue = NULL,
    marker_file = NULL,
    marker_list = NULL,
    db_source = "full",
    cluster_col = "seurat_clusters",
    score_threshold = NULL,
    return_scores = FALSE,
    plot_results = FALSE,
    output_col = "sctype_cell_type"
) {
    # Validate inputs
    if (!inherits(seurat_obj, "Seurat")) {
        stop("Input must be a Seurat object")
    }

    if (!requireNamespace("Seurat", quietly = TRUE)) {
        stop("Please install Seurat: install.packages('Seurat')")
    }

    if (!requireNamespace("openxlsx", quietly = TRUE)) {
        stop("Please install openxlsx: install.packages('openxlsx')")
    }

    if (!requireNamespace("dplyr", quietly = TRUE)) {
        stop("Please install dplyr: install.packages('dplyr')")
    }

    # Get script directory for sourcing dependencies
    script_dir <- tryCatch(dirname(sys.frame(1)$ofile), error = function(e) NULL)
    if (is.null(script_dir) || script_dir == "" || script_dir == ".") {
        # Try to find scripts relative to working directory
        possible_paths <- c(
            file.path(getwd(), "scripts", "r"),
            file.path(getwd(), "..", "scripts", "r"),
            file.path(getwd(), "..", "..", "scripts", "r"),
            getwd()
        )
        for (path in possible_paths) {
            if (file.exists(file.path(path, "gene_sets_prepare.R"))) {
                script_dir <- path
                break
            }
        }
        if (is.null(script_dir) || script_dir == "" || script_dir == ".") {
            script_dir <- getwd()
        }
    }

    # Source core functions
    source(file.path(script_dir, "gene_sets_prepare.R"))
    source(file.path(script_dir, "sctype_score.R"))

    # Determine marker source
    if (!is.null(marker_list)) {
        # Use provided marker list directly
        gs_list <- marker_list
        message("Using custom marker list")
    } else if (!is.null(marker_file)) {
        # Use custom marker file
        if (!file.exists(marker_file)) {
            stop(paste("Marker file not found:", marker_file))
        }
        if (is.null(tissue)) {
            stop("Tissue type must be specified when using custom marker file")
        }
        gs_list <- gene_sets_prepare(marker_file, tissue)
        message(paste("Using custom marker file for tissue:", tissue))
    } else {
        # Use built-in database
        if (!db_source %in% c("full", "short")) {
            stop(sprintf("db_source must be 'full' or 'short', got '%s'", db_source))
        }
        db_file <- file.path(script_dir, "..", "..", "assets", "markers",
                            ifelse(db_source == "short", "ScTypeDB_short.xlsx", "ScTypeDB_full.xlsx"))
        db_file <- normalizePath(db_file, mustWork = FALSE)

        if (!file.exists(db_file)) {
            stop(paste("Built-in database not found:", db_file))
        }

        # Auto-detect tissue if not specified
        if (is.null(tissue)) {
            message("Tissue type not specified, running auto-detection...")
            source(file.path(script_dir, "auto_detect_tissue.R"))
            tissue_guess <- auto_detect_tissue_type(
                path_to_db_file = db_file,
                seuratObject = seurat_obj,
                scaled = (slot == "scale.data"),
                assay = assay
            )
            tissue <- tissue_guess$tissue[1]
            message(paste("Auto-detected tissue:", tissue))
        }

        gs_list <- gene_sets_prepare(db_file, tissue)
        message(paste("Using built-in database (", db_source, ") for tissue:", tissue))
    }

    # Extract expression matrix based on Seurat version
    # Reliable v5 detection: check if assay inherits "Assay5"
    seurat_v5 <- inherits(seurat_obj[[assay]], "Assay5")
    message(paste("Detected Seurat", ifelse(seurat_v5, "v5", "v4")))

    # v5 compatible layer access using LayerData() or GetAssayData()
    if (seurat_v5) {
        layer_name <- switch(slot,
            "counts" = "counts",
            "data" = "data",
            "scale.data" = "scale.data",
            stop("Invalid slot specified")
        )
        expr_matrix <- as.matrix(SeuratObject::LayerData(seurat_obj, assay = assay, layer = layer_name))
    } else {
        expr_matrix <- as.matrix(Seurat::GetAssayData(seurat_obj, assay = assay, slot = slot))
    }

    # Run ScType scoring
    message("Running ScType scoring...")
    es.max <- sctype_score(
        scRNAseqData = expr_matrix,
        scaled = (slot == "scale.data"),
        gs = gs_list$gs_positive,
        gs2 = gs_list$gs_negative
    )

    # Get clusters
    if (!cluster_col %in% colnames(seurat_obj[[]])) {
        stop(paste("Cluster column not found:", cluster_col))
    }

    clusters <- unique(seurat_obj@meta.data[[cluster_col]])

    # Calculate per-cluster scores
    cL_results <- do.call("rbind", lapply(clusters, function(cl) {
        cells_in_cluster <- rownames(seurat_obj@meta.data[seurat_obj@meta.data[[cluster_col]] == cl, ])
        es.max.cl <- sort(rowSums(es.max[, cells_in_cluster, drop = FALSE]), decreasing = TRUE)
        ncells <- sum(seurat_obj@meta.data[[cluster_col]] == cl)
        head(data.frame(
            cluster = cl,
            type = names(es.max.cl),
            scores = es.max.cl,
            ncells = ncells
        ), 10)
    }))

    # Get top cell type per cluster
    sctype_scores <- cL_results %>%
        dplyr::group_by(cluster) %>%
        dplyr::slice_max(order_by = scores, n = 1, with_ties = FALSE)

    # Apply score threshold
    if (is.null(score_threshold)) {
        sctype_scores$type[as.numeric(as.character(sctype_scores$scores)) <
                          sctype_scores$ncells / 4] <- "Unknown"
    } else {
        sctype_scores$type[sctype_scores$scores < score_threshold] <- "Unknown"
    }

    # Add annotations to Seurat object
    seurat_obj@meta.data[[output_col]] <- "Unknown"
    for (j in unique(sctype_scores$cluster)) {
        cl_type <- sctype_scores[sctype_scores$cluster == j, ]
        seurat_obj@meta.data[[output_col]][seurat_obj@meta.data[[cluster_col]] == j] <-
            as.character(cl_type$type[1])
    }

    # Store scores in metadata if requested
    if (return_scores) {
        seurat_obj@misc[[paste0(output_col, "_scores")]] <- es.max
        seurat_obj@misc[[paste0(output_col, "_cluster_scores")]] <- cL_results
    }

    # Plot if requested
    if (plot_results) {
        if ("umap" %in% names(seurat_obj@reductions)) {
            p <- Seurat::DimPlot(seurat_obj, reduction = "umap", group.by = output_col,
                                label = TRUE, repel = TRUE)
            print(p)
        } else {
            warning("UMAP not found in reductions, skipping plot")
        }
    }

    message("ScType annotation complete!")
    message(paste("Cell types identified:", paste(unique(seurat_obj@meta.data[[output_col]]), collapse = ", ")))

    return(seurat_obj)
}

#' @title Get Available Tissues
#' @description Get list of available tissue types from built-in database
#' @param db_source Database source: "full" or "short"
#' @return Vector of tissue type names
#' @export
get_available_tissues <- function(db_source = "full") {
    # Search for database file in likely locations
    possible_paths <- c(
        file.path(getwd(), "assets", "markers"),
        file.path(getwd(), "..", "assets", "markers"),
        file.path(getwd(), "..", "..", "assets", "markers")
    )
    
    db_filename <- ifelse(db_source == "short", "ScTypeDB_short.xlsx", "ScTypeDB_full.xlsx")
    db_file <- NULL
    
    for (path in possible_paths) {
        candidate <- file.path(path, db_filename)
        if (file.exists(candidate)) {
            db_file <- candidate
            break
        }
    }
    
    if (is.null(db_file)) {
        # Fallback: try system.file if installed as a package
        db_file <- system.file("assets", "markers", db_filename, package = "sctype")
    }

    if (!requireNamespace("openxlsx", quietly = TRUE)) {
        stop("Please install openxlsx")
    }

    cell_markers <- openxlsx::read.xlsx(db_file)
    return(unique(cell_markers$tissueType))
}

#' @title Create Custom Marker List
#' @description Create a marker list object from user-defined markers
#' @param positive_markers Named list of positive marker genes per cell type
#' @param negative_markers Named list of negative marker genes per cell type (optional)
#' @return Marker list compatible with run_sctype_annotation
#' @export
create_marker_list <- function(positive_markers, negative_markers = NULL) {
    if (is.null(negative_markers)) {
        negative_markers <- lapply(names(positive_markers), function(x) character(0))
        names(negative_markers) <- names(positive_markers)
    }

    return(list(
        gs_positive = positive_markers,
        gs_negative = negative_markers
    ))
}
