# Core Analysis Functions for PROGENy
# ===================================
#
# This script provides wrapper functions for PROGENy pathway activity inference
# from single-cell RNA-seq data.
#
# NOTE: The underlying progeny package uses 'slot' parameter internally,
# which is incompatible with Seurat v5. This wrapper extracts the expression
# matrix manually for all Seurat objects to ensure cross-version compatibility.

#' Check input data for PROGENy analysis
#'
#' @param data Input data object (Seurat, matrix, or data.frame)
#' @return Logical indicating whether data is valid
#' @export
check_progeny_input <- function(data) {
  if (is.null(data)) {
    stop("Input data is NULL")
  }

  if (inherits(data, "Seurat")) {
    if (!requireNamespace("Seurat", quietly = TRUE)) {
      stop("Seurat package required for Seurat objects")
    }
    message("Input type: Seurat object")
    message("Default assay: ", Seurat::DefaultAssay(data))
    return(TRUE)
  } else if (is.matrix(data) || is.data.frame(data)) {
    message("Input type: Matrix/Data frame")
    message("Dimensions: ", nrow(data), " genes x ", ncol(data), " samples")
    return(TRUE)
  } else if (inherits(data, "SingleCellExperiment")) {
    message("Input type: SingleCellExperiment")
    return(TRUE)
  } else {
    stop("Unsupported input type: ", class(data))
  }
}

#' Run PROGENy pathway activity inference
#'
#' Wrapper around progeny::progeny() with cross-version Seurat support.
#' For Seurat objects, extracts the expression matrix manually and re-adds
#' the result as a new assay, avoiding internal 'slot' parameter issues.
#'
#' @param data Input data (Seurat, matrix, or data.frame)
#' @param organism Organism: "Human" or "Mouse"
#' @param top Number of top responsive genes per pathway (default: 100)
#' @param scale Logical: scale pathway scores (default: FALSE for single-cell)
#' @param perm Number of permutations for significance (default: 1, no permutations)
#' @param assay_name For Seurat: which assay to use (default: "RNA")
#' @param return_assay For Seurat: return as new assay (default: TRUE)
#' @param verbose Logical: print gene usage info (default: TRUE)
#' @param ... Additional arguments passed to progeny()
#' @return Pathway activity scores or Seurat object with progeny assay
#' @export
run_progeny <- function(
    data,
    organism = "Human",
    top = 100,
    scale = FALSE,
    perm = 1,
    assay_name = "RNA",
    return_assay = TRUE,
    verbose = TRUE,
    ...
) {
  if (!requireNamespace("progeny", quietly = TRUE)) {
    stop("progeny package not installed. Run: BiocManager::install('progeny')")
  }

  # Check input
  check_progeny_input(data)

  # Validate parameters
  if (!organism %in% c("Human", "Mouse")) {
    stop("organism must be 'Human' or 'Mouse'")
  }

  if (top < 1 || top > 1000) {
    stop("top must be between 1 and 1000")
  }

  message("Running PROGENy with parameters:")
  message("  Organism: ", organism)
  message("  Top genes per pathway: ", top)
  message("  Scale scores: ", scale)
  message("  Permutations: ", perm)

  if (inherits(data, "Seurat")) {
    if (!requireNamespace("Seurat", quietly = TRUE)) {
      stop("Seurat package required for Seurat objects")
    }

    # Extract expression matrix manually for cross-version compatibility
    seurat_ver <- utils::packageVersion("SeuratObject")
    is_v5 <- seurat_ver >= package_version("5.0.0")

    if (is_v5) {
      expr_matrix <- as.matrix(Seurat::GetAssayData(data, assay = assay_name, layer = "data"))
    } else {
      expr_matrix <- as.matrix(get_assay_data_compat(data, assay = assay_name))
    }

    result <- progeny::progeny(
      expr_matrix,
      scale = scale,
      organism = organism,
      top = top,
      perm = perm,
      verbose = verbose,
      ...
    )

    if (return_assay) {
      data[["progeny"]] <- Seurat::CreateAssayObject(data = t(result))
      message("PROGENy scores added as 'progeny' assay")
      return(data)
    } else {
      message("PROGENy analysis complete. Result dimensions: ",
              nrow(result), " samples x ", ncol(result), " pathways")
      return(result)
    }
  } else if (inherits(data, "SingleCellExperiment")) {
    if (!requireNamespace("SummarizedExperiment", quietly = TRUE)) {
      stop("SummarizedExperiment package required for SingleCellExperiment objects")
    }
    if (!"counts" %in% names(SummarizedExperiment::assays(data))) {
      stop("No 'counts' assay found in SingleCellExperiment")
    }
    expr_matrix <- as.matrix(SummarizedExperiment::assay(data, "counts"))
    result <- progeny::progeny(
      expr_matrix,
      scale = scale,
      organism = organism,
      top = top,
      perm = perm,
      verbose = verbose,
      ...
    )
    message("PROGENy analysis complete. Result dimensions: ",
            nrow(result), " samples x ", ncol(result), " pathways")
    return(result)
  } else {
    # Non-Seurat input: pass through directly
    # Convert sparse matrices to dense (native progeny does not accept dgCMatrix)
    if (inherits(data, "dgCMatrix") || inherits(data, "sparseMatrix")) {
      data <- as.matrix(data)
    }
    result <- progeny::progeny(
      data,
      scale = scale,
      organism = organism,
      top = top,
      perm = perm,
      verbose = verbose,
      ...
    )
    message("PROGENy analysis complete. Result dimensions: ",
            nrow(result), " samples x ", ncol(result), " pathways")
    return(result)
  }
}

#' Run PROGENy with permutation-based significance testing
#'
#' @param data Input data (matrix or data.frame). Genes must be in rows.
#' @param organism Organism: "Human" or "Mouse"
#' @param top Number of top responsive genes per pathway (default: 100)
#' @param perm Number of permutations (default: 10000)
#' @param z_scores Return z-scores instead of normalized scores (default: TRUE)
#' @param get_nulldist Return null distributions (default: FALSE)
#' @param verbose Logical: print progress (default: TRUE)
#' @return Matrix of pathway scores, or list with scores and null distributions
#'   if get_nulldist = TRUE.
#' @export
run_progeny_permutation <- function(
    data,
    organism = "Human",
    top = 100,
    perm = 10000,
    scale = FALSE,
    z_scores = TRUE,
    get_nulldist = FALSE,
    verbose = TRUE
) {
  if (!requireNamespace("progeny", quietly = TRUE)) {
    stop("progeny package not installed")
  }

  # Convert data.frame to matrix with gene names as rownames
  if (is.data.frame(data)) {
    has_meaningful_rownames <- !is.null(rownames(data)) &&
      !all(grepl("^[0-9]+$", rownames(data)))
    if (has_meaningful_rownames) {
      data <- as.matrix(data)
    } else {
      if (ncol(data) < 2) {
        stop("Data frame must have at least 2 columns if row names are not gene symbols")
      }
      gene_names <- as.character(data[, 1])
      data <- as.matrix(data[, -1])
      rownames(data) <- gene_names
    }
  }

  if (inherits(data, "Seurat")) {
    stop("Seurat objects are not supported by run_progeny_permutation. ",
         "Extract expression matrix first with GetAssayData().")
  }

  if (inherits(data, "dgCMatrix") || inherits(data, "sparseMatrix")) {
    data <- as.matrix(data)
  }

  message("Running PROGENy with ", perm, " permutations...")
  message("This may take some time for large datasets")

  result <- progeny::progeny(
    data,
    scale = scale,
    organism = organism,
    top = top,
    perm = perm,
    verbose = verbose,
    z_scores = z_scores,
    get_nulldist = get_nulldist
  )

  message("Permutation analysis complete")

  return(result)
}

#' Get pathway model information
#'
#' @param organism Organism: "Human" or "Mouse"
#' @param top Number of top genes per pathway (default: 100)
#' @return Data frame with model information
#' @export
get_progeny_model_info <- function(organism = "Human", top = 100) {
  if (!requireNamespace("progeny", quietly = TRUE)) {
    stop("progeny package not installed")
  }

  model <- progeny::getModel(organism = organism, top = top)

  # Calculate statistics per pathway
  pathway_stats <- apply(model, 2, function(x) {
    non_zero <- x[x != 0]
    n_genes <- length(non_zero)
    if (n_genes == 0) {
      c(n_genes = 0, mean_weight = NA_real_, sd_weight = NA_real_,
        min_weight = NA_real_, max_weight = NA_real_)
    } else {
      c(
        n_genes = n_genes,
        mean_weight = mean(non_zero),
        sd_weight = ifelse(n_genes > 1, sd(non_zero), NA_real_),
        min_weight = min(non_zero),
        max_weight = max(non_zero)
      )
    }
  })

  result <- as.data.frame(t(pathway_stats))
  result$pathway <- rownames(result)
  rownames(result) <- NULL

  return(result[, c("pathway", "n_genes", "mean_weight", "sd_weight",
                    "min_weight", "max_weight")])
}

#' Get list of available pathways
#'
#' @param organism Organism: "Human" or "Mouse"
#' @param top Number of top genes per pathway (default: 100)
#' @return Character vector of pathway names
#' @export
list_progeny_pathways <- function(organism = "Human", top = 100) {
  model <- get_progeny_model_info(organism = organism, top = top)
  return(model$pathway)
}

#' Add PROGENy scores to Seurat object metadata
#'
#' @param seurat_obj Seurat object
#' @param progeny_scores Matrix of PROGENy scores (optional, will run if not provided)
#' @param prefix Prefix for column names (default: "PROGENy_")
#' @return Seurat object with pathway scores in metadata
#' @export
add_progeny_to_metadata <- function(
    seurat_obj,
    progeny_scores = NULL,
    prefix = "PROGENy_"
) {
  if (is.null(progeny_scores)) {
    if (!("progeny" %in% names(seurat_obj@assays))) {
      stop("No progeny scores found. Run run_progeny() first or provide scores.")
    }
    progeny_scores <- t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny")))
  }

  # Add each pathway as metadata column
  for (pathway in colnames(progeny_scores)) {
    col_name <- paste0(prefix, pathway)
    seurat_obj[[col_name]] <- progeny_scores[, pathway]
  }

  message("Added ", ncol(progeny_scores), " pathway scores to metadata")
  return(seurat_obj)
}

#' Calculate differential pathway activity between groups
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param group.by Metadata column defining groups (default: active.ident)
#' @param assay Assay to use (default: "progeny")
#' @param only.pos Only return positive markers (default: FALSE)
#' @param min.pct Minimum fraction of cells (default: 0)
#' @param logfc.threshold Log fold change threshold (default: 0)
#' @return Data frame with differential pathway markers
#' @export
find_pathway_markers <- function(
    seurat_obj,
    group.by = NULL,
    assay = "progeny",
    only.pos = FALSE,
    min.pct = 0,
    logfc.threshold = 0
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!(assay %in% names(seurat_obj@assays))) {
    stop("Assay '", assay, "' not found. Run run_progeny() first.")
  }

  markers <- Seurat::FindAllMarkers(
    seurat_obj,
    group.by = group.by,
    only.pos = only.pos,
    min.pct = min.pct,
    logfc.threshold = logfc.threshold,
    assay = assay
  )

  # Rename gene column to pathway for clarity
  if ("gene" %in% colnames(markers)) {
    markers$pathway <- markers$gene
    markers$gene <- NULL
  }

  return(markers)
}

#' Calculate average pathway activity by group
#'
#' @param seurat_obj Seurat object with progeny assay or metadata
#' @param group.by Metadata column for grouping
#' @param use_metadata Use metadata columns instead of assay (default: FALSE)
#' @param prefix Prefix for metadata columns (default: "PROGENy_")
#' @return Data frame with average pathway activities
#' @export
average_pathway_activity <- function(
    seurat_obj,
    group.by,
    use_metadata = FALSE,
    prefix = "PROGENy_"
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (use_metadata) {
    # Get pathway columns from metadata
    pathway_cols <- grep(paste0("^", prefix), colnames(seurat_obj@meta.data), value = TRUE)
    if (length(pathway_cols) == 0) {
      stop("No pathway columns found in metadata with prefix '", prefix, "'")
    }

    scores <- seurat_obj@meta.data[, c(group.by, pathway_cols)]
    colnames(scores) <- gsub(paste0("^", prefix), "", colnames(scores))
  } else {
    if (!("progeny" %in% names(seurat_obj@assays))) {
      stop("No progeny assay found. Run run_progeny() first.")
    }

    scores <- as.data.frame(t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny"))))
    scores[[group.by]] <- seurat_obj[[group.by, drop = TRUE]]
  }

  # Calculate means by group
  score_cols <- setdiff(colnames(scores), group.by)
  result <- stats::aggregate(
    x = scores[, score_cols, drop = FALSE],
    by = list(group = scores[[group.by]]),
    FUN = mean
  )
  colnames(result)[1] <- group.by

  return(result)
}

#' Export PROGENy results
#'
#' @param seurat_obj Seurat object with progeny results
#' @param output_dir Output directory (default: "./progeny_results")
#' @param prefix Prefix for output files (default: "progeny")
#' @param export_scores Export pathway scores (default: TRUE)
#' @param export_metadata Export metadata with pathway scores (default: TRUE)
#' @return Invisible NULL
#' @export
export_progeny_results <- function(
    seurat_obj,
    output_dir = "./progeny_results",
    prefix = "progeny",
    export_scores = TRUE,
    export_metadata = TRUE
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Export pathway scores
  if (export_scores && ("progeny" %in% names(seurat_obj@assays))) {
    scores <- as.data.frame(t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny"))))
    scores$cell_id <- rownames(scores)

    tryCatch({
      write.csv(
        scores,
        file = file.path(output_dir, paste0(prefix, "_scores.csv")),
        row.names = FALSE
      )
      message("Exported pathway scores to ", output_dir)
    }, error = function(e) {
      stop("Failed to write scores CSV: ", e$message)
    })
  }

  # Export metadata
  if (export_metadata) {
    # Get pathway columns from metadata if they exist
    pathway_pattern <- "^PROGENy_"
    pathway_cols <- grep(pathway_pattern, colnames(seurat_obj@meta.data), value = TRUE)

    if (length(pathway_cols) > 0) {
      metadata <- seurat_obj@meta.data[, pathway_cols, drop = FALSE]
      metadata$cell_id <- rownames(metadata)

      tryCatch({
        write.csv(
          metadata,
          file = file.path(output_dir, paste0(prefix, "_metadata.csv")),
          row.names = FALSE
        )
        message("Exported pathway metadata to ", output_dir)
      }, error = function(e) {
        stop("Failed to write metadata CSV: ", e$message)
      })
    }
  }

  message("Export complete")
  return(invisible(NULL))
}
