#' scMetabolism Analysis for Single-Cell Data
#'
#' A comprehensive wrapper for scMetabolism package to quantify metabolic pathway
#' activities in single-cell RNA-seq data using multiple scoring methods.
#'
#' @author Yang Guo
#' @date 2026-04-03
#' @version 1.1.0

#' Run scMetabolism Analysis on Seurat Object
#'
#' Main function to run scMetabolism analysis on a Seurat object.
#' Supports multiple scoring methods and metabolic pathway databases.
#'
#' @param seurat_obj Seurat object
#' @param method Scoring method: "VISION", "AUCell", "ssGSEA", or "GSVA" (default: "VISION")
#' @param metabolism.type Pathway database: "KEGG" or "REACTOME" (default: "KEGG")
#' @param imputation Whether to perform data imputation before scoring (default: FALSE)
#' @param ncores Number of cores for parallel computation (default: 4)
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to extract data from: "counts" or "data" (default: "counts")
#' @param min.cells Minimum cells threshold (default: 10)
#' @param min.feature Minimum features threshold (default: 10)
#' @param output_assay Name for output assay (default: "METABOLISM")
#' @param return_matrix Whether to return metabolism matrix separately (default: TRUE)
#'
#' @return Seurat object with metabolism scores added as an assay
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic usage with VISION method (default)
#' seurat_obj <- run_scmetabolism(seurat_obj, method = "VISION")
#'
#' # Using AUCell method with REACTOME database
#' seurat_obj <- run_scmetabolism(
#'   seurat_obj,
#'   method = "AUCell",
#'   metabolism.type = "REACTOME",
#'   ncores = 8
#' )
#'
#' # With imputation (for sparse data)
#' seurat_obj <- run_scmetabolism(seurat_obj, imputation = TRUE)
#' }
run_scmetabolism <- function(
    seurat_obj,
    method = "VISION",
    metabolism.type = "KEGG",
    imputation = FALSE,
    ncores = 4,
    assay = "RNA",
    slot = "counts",
    min.cells = 10,
    min.feature = 10,
    output_assay = "METABOLISM",
    return_matrix = TRUE
) {
  # Validate inputs
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Please install Seurat: install.packages('Seurat')")
  }

  if (!requireNamespace("scMetabolism", quietly = TRUE)) {
    stop("Please install scMetabolism: devtools::install_github('wu-yc/scMetabolism')")
  }

  # Validate method
  valid_methods <- c("VISION", "AUCell", "ssGSEA", "GSVA")
  method <- toupper(method)
  if (!method %in% valid_methods) {
    stop(sprintf("Invalid method '%s'. Choose from: %s",
                 method, paste(valid_methods, collapse = ", ")))
  }

  # Validate metabolism type
  valid_dbs <- c("KEGG", "REACTOME")
  metabolism.type <- toupper(metabolism.type)
  if (!metabolism.type %in% valid_dbs) {
    stop(sprintf("Invalid metabolism.type '%s'. Choose from: %s",
                 metabolism.type, paste(valid_dbs, collapse = ", ")))
  }

  # Check if assay exists
  if (!assay %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found in Seurat object. Available assays: %s",
                 assay, paste(names(seurat_obj@assays), collapse = ", ")))
  }

  message(sprintf("Running scMetabolism with %s method and %s database...",
                  method, metabolism.type))
  message(sprintf("Using assay: %s, slot: %s", assay, slot))

  # Extract counts based on Seurat version
  seurat_v5 <- packageVersion("SeuratObject") >= "5.0.0"

  if (seurat_v5) {
    counts <- switch(slot,
      "counts" = Seurat::GetAssayData(seurat_obj, assay = assay, layer = "counts"),
      "data" = Seurat::GetAssayData(seurat_obj, assay = assay, layer = "data"),
      stop("Invalid slot specified. Use 'counts' or 'data'")
    )
  } else {
    counts <- switch(slot,
      "counts" = Seurat::GetAssayData(seurat_obj, assay = assay, slot = "counts"),
      "data" = Seurat::GetAssayData(seurat_obj, assay = assay, slot = "data"),
      stop("Invalid slot specified. Use 'counts' or 'data'")
    )
  }

  # Check for empty matrix
  if (sum(counts) == 0) {
    stop("Count matrix is empty (all zeros)")
  }

  # Run scMetabolism
  library(scMetabolism)

  metabolism_matrix <- sc.metabolism(
    countexp = as.data.frame(as.matrix(counts)),
    method = method,
    imputation = imputation,
    ncores = ncores,
    metabolism.type = metabolism.type
  )

  # Add to Seurat object
  seurat_obj[[output_assay]] <- Seurat::CreateAssayObject(data = as.matrix(metabolism_matrix))

  # Store metadata
  seurat_obj@misc[["scmetabolism_params"]] <- list(
    method = method,
    metabolism.type = metabolism.type,
    imputation = imputation,
    ncores = ncores,
    timestamp = Sys.time()
  )

  message(sprintf("scMetabolism analysis complete! Added assay '%s'", output_assay))
  message(sprintf("Pathways analyzed: %d", nrow(metabolism_matrix)))

  if (return_matrix) {
    return(list(
      seurat_obj = seurat_obj,
      metabolism_matrix = metabolism_matrix
    ))
  }

  return(seurat_obj)
}


#' Run scMetabolism on Raw Count Matrix
#'
#' Run scMetabolism analysis directly on a count matrix without Seurat.
#' Useful for custom workflows or non-Seurat data.
#'
#' @param countexp Data frame or matrix of UMI counts (genes x cells)
#' @param method Scoring method: "VISION", "AUCell", "ssGSEA", or "GSVA" (default: "VISION")
#' @param metabolism.type Pathway database: "KEGG" or "REACTOME" (default: "KEGG")
#' @param imputation Whether to perform data imputation (default: FALSE)
#' @param ncores Number of cores for parallel computation (default: 4)
#' @param min.cells Minimum cells threshold (default: 10)
#' @param min.feature Minimum features threshold (default: 10)
#'
#' @return Data frame with metabolism pathway scores (pathways x cells)
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Run on raw count matrix
#' metabolism_scores <- run_scmetabolism_matrix(
#'   countexp = raw_counts,
#'   method = "AUCell",
#'   metabolism.type = "KEGG"
#' )
#' }
run_scmetabolism_matrix <- function(
    countexp,
    method = "VISION",
    metabolism.type = "KEGG",
    imputation = FALSE,
    ncores = 4,
    min.cells = 10,
    min.feature = 10
) {
  # Validate input
  if (!is.data.frame(countexp) && !is.matrix(countexp)) {
    stop("countexp must be a data frame or matrix")
  }

  if (!requireNamespace("scMetabolism", quietly = TRUE)) {
    stop("Please install scMetabolism: devtools::install_github('wu-yc/scMetabolism')")
  }

  # Validate parameters
  valid_methods <- c("VISION", "AUCell", "ssGSEA", "GSVA")
  method <- toupper(method)
  if (!method %in% valid_methods) {
    stop(sprintf("Invalid method '%s'. Choose from: %s",
                 method, paste(valid_methods, collapse = ", ")))
  }

  valid_dbs <- c("KEGG", "REACTOME")
  metabolism.type <- toupper(metabolism.type)
  if (!metabolism.type %in% valid_dbs) {
    stop(sprintf("Invalid metabolism.type '%s'. Choose from: %s",
                 metabolism.type, paste(valid_dbs, collapse = ", ")))
  }

  message(sprintf("Running scMetabolism on raw matrix with %s method...", method))

  # Run scMetabolism
  library(scMetabolism)

  metabolism_matrix <- sc.metabolism(
    countexp = as.data.frame(countexp),
    method = method,
    imputation = imputation,
    ncores = ncores,
    metabolism.type = metabolism.type
  )

  message(sprintf("Analysis complete! %d pathways x %d cells",
                  nrow(metabolism_matrix), ncol(metabolism_matrix)))

  return(metabolism_matrix)
}


#' Get Available Metabolic Pathways
#'
#' Retrieve the list of metabolic pathways available in KEGG or REACTOME database.
#'
#' @param database Pathway database: "KEGG" or "REACTOME" (default: "KEGG")
#'
#' @return Character vector of pathway names
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Get KEGG pathways
#' kegg_pathways <- get_metabolic_pathways("KEGG")
#'
#' # Get REACTOME pathways
#' reactome_pathways <- get_metabolic_pathways("REACTOME")
#' }
get_metabolic_pathways <- function(database = "KEGG") {
  if (!requireNamespace("GSEABase", quietly = TRUE)) {
    stop("Please install GSEABase: BiocManager::install('GSEABase')")
  }

  if (!requireNamespace("scMetabolism", quietly = TRUE)) {
    stop("Please install scMetabolism")
  }

  # Get GMT file path
  database <- toupper(database)
  if (database == "KEGG") {
    gmt_file <- system.file("data", "KEGG_metabolism_nc.gmt", package = "scMetabolism")
  } else if (database == "REACTOME") {
    gmt_file <- system.file("data", "REACTOME_metabolism.gmt", package = "scMetabolism")
  } else {
    stop("Database must be 'KEGG' or 'REACTOME'")
  }

  if (!file.exists(gmt_file)) {
    stop(sprintf("GMT file not found: %s", gmt_file))
  }

  # Read GMT file
  gene_sets <- GSEABase::getGmt(gmt_file)
  pathways <- sapply(gene_sets, function(x) x@setName)

  return(pathways)
}


#' Extract Metabolism Scores
#'
#' Extract metabolism scores from Seurat object as a data frame.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param pathways Optional vector of pathway names to extract (default: all)
#'
#' @return Data frame with metabolism scores (pathways x cells)
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Extract all metabolism scores
#' scores <- extract_metabolism_scores(seurat_obj)
#'
#' # Extract specific pathways
#' glycolysis_scores <- extract_metabolism_scores(
#'   seurat_obj,
#'   pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)")
#' )
#' }
extract_metabolism_scores <- function(
    seurat_obj,
    assay = "METABOLISM",
    pathways = NULL
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!assay %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found. Available: %s",
                 assay, paste(names(seurat_obj@assays), collapse = ", ")))
  }

  # Extract scores based on Seurat version
  seurat_v5 <- packageVersion("SeuratObject") >= "5.0.0"

  if (seurat_v5) {
    scores <- as.data.frame(Seurat::GetAssayData(seurat_obj, assay = assay, layer = "data"))
  } else {
    scores <- as.data.frame(seurat_obj[[assay]]@data)
  }

  # Subset pathways if specified
  if (!is.null(pathways)) {
    missing <- setdiff(pathways, rownames(scores))
    if (length(missing) > 0) {
      warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    }
    pathways <- intersect(pathways, rownames(scores))
    scores <- scores[pathways, , drop = FALSE]
  }

  return(scores)
}


#' Compare Metabolism Between Groups
#'
#' Compare metabolic pathway activities between cell groups.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param group.by Column in metadata for grouping (default: "ident")
#' @param pathways Vector of pathways to compare (default: top 10 variable)
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param test Statistical test: "wilcox" or "t.test" (default: "wilcox")
#'
#' @return Data frame with comparison statistics
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Compare metabolism between conditions
#' results <- compare_metabolism(
#'   seurat_obj,
#'   group.by = "condition",
#'   pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation")
#' )
#' }
compare_metabolism <- function(
    seurat_obj,
    group.by = "ident",
    pathways = NULL,
    assay = "METABOLISM",
    test = "wilcox"
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- seurat_obj@active.ident
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- seurat_obj@meta.data[[group.by]]
  }

  # Extract scores
  scores <- extract_metabolism_scores(seurat_obj, assay = assay, pathways = pathways)

  # Calculate statistics per group
  results <- list()
  all_groups <- unique(groups)

  for (pathway in rownames(scores)) {
    pathway_scores <- as.numeric(scores[pathway, ])

    group_stats <- lapply(all_groups, function(g) {
      idx <- groups == g
      list(
        mean = mean(pathway_scores[idx], na.rm = TRUE),
        sd = sd(pathway_scores[idx], na.rm = TRUE),
        median = median(pathway_scores[idx], na.rm = TRUE),
        n = sum(idx)
      )
    })
    names(group_stats) <- all_groups

    results[[pathway]] <- group_stats
  }

  # Convert to data frame
  result_df <- do.call(rbind, lapply(names(results), function(p) {
    data.frame(
      pathway = p,
      group = all_groups,
      mean = sapply(results[[p]], function(x) x$mean),
      sd = sapply(results[[p]], function(x) x$sd),
      median = sapply(results[[p]], function(x) x$median),
      n = sapply(results[[p]], function(x) x$n),
      stringsAsFactors = FALSE
    )
  }))

  return(result_df)
}


#' Export scMetabolism Results
#'
#' Export metabolism scores and parameters to files.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param output_dir Output directory path
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param prefix Prefix for output files (default: "scmetabolism")
#'
#' @export
#'
#' @examples
#' \dontrun{
#' export_scmetabolism_results(seurat_obj, "./output", prefix = "sample1")
#' }
export_scmetabolism_results <- function(
    seurat_obj,
    output_dir,
    assay = "METABOLISM",
    prefix = "scmetabolism"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  }

  # Extract scores
  scores <- extract_metabolism_scores(seurat_obj, assay = assay)

  # Export scores
  scores_file <- file.path(output_dir, sprintf("%s_scores.csv", prefix))
  write.csv(scores, scores_file)
  message(sprintf("Scores saved to: %s", scores_file))

  # Export metadata if available
  if ("scmetabolism_params" %in% names(seurat_obj@misc)) {
    params_file <- file.path(output_dir, sprintf("%s_params.txt", prefix))
    params <- seurat_obj@misc$scmetabolism_params
    writeLines(
      c("scMetabolism Parameters:",
        sprintf("  Method: %s", params$method),
        sprintf("  Database: %s", params$metabolism.type),
        sprintf("  Imputation: %s", params$imputation),
        sprintf("  Cores: %d", params$ncores),
        sprintf("  Timestamp: %s", params$timestamp)),
      params_file
    )
    message(sprintf("Parameters saved to: %s", params_file))
  }

  # Export mean scores per group
  if ("ident" %in% names(seurat_obj@active.ident) || length(seurat_obj@active.ident) > 0) {
    mean_scores <- compare_metabolism(seurat_obj, assay = assay)
    mean_file <- file.path(output_dir, sprintf("%s_mean_by_group.csv", prefix))
    write.csv(mean_scores, mean_file, row.names = FALSE)
    message(sprintf("Mean scores saved to: %s", mean_file))
  }

  message("Export complete!")
}


#' Get Top Variable Pathways
#'
#' Identify the most variable metabolic pathways across cells.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param n_top Number of top pathways to return (default: 10)
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#'
#' @return Character vector of pathway names
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Get top 20 variable pathways
#' top_pathways <- get_top_variable_pathways(seurat_obj, n_top = 20)
#' }
get_top_variable_pathways <- function(
    seurat_obj,
    n_top = 10,
    assay = "METABOLISM"
) {
  scores <- extract_metabolism_scores(seurat_obj, assay = assay)

  # Calculate variance for each pathway
  variances <- apply(scores, 1, var, na.rm = TRUE)

  # Get top pathways
  top_pathways <- names(sort(variances, decreasing = TRUE))[1:min(n_top, length(variances))]

  return(top_pathways)
}
