#' irGSEA: Integrated Robust GSEA for Single-Cell Data
#'
#' Multi-method gene set enrichment analysis with RRA integration.
#' Combines AUCell, UCell, singscore, ssgsea, and ssGSEA2.
#'
#' @author Yang Guo
#' @date 2026-04-09
#' @version 2.0.0

#' Check Seurat version compatibility
#'
#' The underlying irGSEA package uses `slot` parameter internally,
#' which is incompatible with Seurat v5. This skill requires Seurat v4.
#'
#' @param obj Input object to check (if Seurat)
#' @param context Context string for error message
#' @noRd
.check_seurat_v4 <- function(obj, context = "irGSEA") {
  if (inherits(obj, "Seurat")) {
    if (!requireNamespace("SeuratObject", quietly = TRUE)) {
      stop("SeuratObject package required for Seurat version checking")
    }
    seurat_ver <- utils::packageVersion("SeuratObject")
    if (seurat_ver >= package_version("5.0.0")) {
      stop(sprintf(
        "[%s] Seurat v%s detected. This skill requires Seurat v4.x (< 5.0.0).\n",
        "The underlying irGSEA package uses 'slot' parameter internally, ",
        "which is incompatible with Seurat v5's 'layer' system.\n",
        "Please use a Seurat v4 environment, or extract the matrix manually:\n",
        "  expr_matrix <- Seurat::GetAssayData(seurat_obj, slot = 'counts')\n",
        "  results <- run_irgsea(expr_matrix, gene_sets = gene_sets)\n",
        context, seurat_ver
      ))
    }
  }
}

#' Run irGSEA Analysis
#'
#' Calculate enrichment scores using multiple methods and integrate with RRA.
#'
#' @param expr_matrix Expression matrix (genes x cells) or Seurat object
#' @param gene_sets Named list of gene sets
#' @param methods Vector of methods to use (default: c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"))
#' @param minGSSize Minimum gene set size (default: 10)
#' @param maxGSSize Maximum gene set size (default: 500)
#' @param ncores Number of cores for parallel processing (default: 1)
#' @param rra_integration Logical: integrate results with RRA (default: TRUE)
#'
#' @return List with results from each method and optionally RRA integrated scores
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Run irGSEA with all methods
#' results <- run_irgsea(
#'   expr_matrix = expr_matrix,
#'   gene_sets = gene_sets,
#'   methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2")
#' )
#'
#' # Access RRA integrated scores
#' rra_scores <- results$RRA
#'
#' # Access individual method scores
#' aucell_scores <- results$AUCell
#' }
run_irgsea <- function(
    expr_matrix,
    gene_sets,
    methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
    minGSSize = 10,
    maxGSSize = 500,
    ncores = 1,
    rra_integration = TRUE
) {
  # Check dependencies
  if (!requireNamespace("irGSEA", quietly = TRUE)) {
    stop("irGSEA package required. Install with: devtools::install_github('GitHUBZJY/irGSEA')")
  }

  library(irGSEA)

  # Check Seurat version compatibility
  .check_seurat_v4(expr_matrix, context = "run_irgsea")

  # Extract from Seurat if needed
  if (inherits(expr_matrix, "Seurat")) {
    message("Extracting expression matrix from Seurat object...")
    expr_matrix <- Seurat::GetAssayData(expr_matrix, slot = "counts")
  }

  # Validate gene_sets
  if (is.null(gene_sets) || length(gene_sets) == 0) {
    stop("gene_sets must be a non-empty list of gene sets")
  }

  # Filter gene sets by size
  gene_sets <- gene_sets[sapply(gene_sets, length) >= minGSSize]
  gene_sets <- gene_sets[sapply(gene_sets, length) <= maxGSSize]

  if (length(gene_sets) == 0) {
    stop("No valid gene sets after size filtering")
  }

  message(sprintf("Running irGSEA with %d gene sets using %d methods...",
                  length(gene_sets), length(methods)))

  # Run irGSEA scoring (geneSets -> geneset for irGSEA v2+)
  scores <- irGSEA::irGSEA.score(
    object = expr_matrix,
    geneset = gene_sets,
    method = methods,
    minGSSize = minGSSize,
    maxGSSize = maxGSSize,
    ncores = ncores
  )

  # RRA integration
  if (rra_integration && length(methods) > 1) {
    message("Running RRA integration...")

    # Prepare data for RRA
    score_list <- lapply(methods, function(m) {
      if (m %in% names(scores)) {
        return(scores[[m]])
      }
      return(NULL)
    })
    names(score_list) <- methods
    score_list <- score_list[!sapply(score_list, is.null)]

    if (length(score_list) >= 2) {
      rra_result <- irGSEA::irGSEA.integrate(
        object = score_list,
        method = "RRA"
      )
      scores$RRA <- rra_result
    }
  }

  message("irGSEA complete!")
  return(scores)
}


#' Internal: Extract scores from irGSEA assays to metadata
#' @keywords internal
extract_scores_internal <- function(seurat_obj, method = NULL) {
  # Detect which method assays were added
  all_methods <- c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2")
  assay_names <- names(seurat_obj@assays)
  added_methods <- all_methods[all_methods %in% assay_names]

  if (!is.null(method)) {
    added_methods <- added_methods[added_methods %in% method]
  }

  if (length(added_methods) == 0) {
    warning("No irGSEA method assays found in Seurat object")
    return(seurat_obj)
  }

  message(sprintf("Found %d method assays: %s", length(added_methods), paste(added_methods, collapse = ", ")))

  # Extract scores from each method assay to metadata
  for (method_name in added_methods) {
    assay_obj <- seurat_obj[[method_name]]

    # Get the data slot
    score_matrix <- as.matrix(Seurat::GetAssayData(assay_obj, slot = "data"))

    # score_matrix is genes (gene sets) x cells
    # Transpose to cells x gene_sets
    score_df <- as.data.frame(t(score_matrix))

    # Add prefix to column names
    colnames(score_df) <- paste0("irGSEA.", method_name, ".", colnames(score_df))

    # Add to metadata
    for (col in colnames(score_df)) {
      seurat_obj[[col]] <- score_df[[col]]
    }

    message(sprintf("  Added %d score columns for %s", ncol(score_df), method_name))
  }

  return(seurat_obj)
}


#' Run irGSEA with Seurat
#'
#' @param seurat_obj Seurat object
#' @param gene_sets Named list of gene sets (optional). If provided, uses custom = TRUE
#' @param slot Data slot/layer (default: "counts")
#' @param ... Additional arguments passed to irGSEA.score()
#'
#' @return Seurat object with irGSEA scores in metadata
#'
#' @export
run_irgsea_seurat <- function(
    seurat_obj,
    gene_sets = NULL,
    slot = "counts",
    ...
) {
  # Check dependencies
  if (!requireNamespace("irGSEA", quietly = TRUE)) {
    stop("irGSEA package required. Install with: devtools::install_github('GitHUBZJY/irGSEA')")
  }

  library(irGSEA)

  # Check Seurat version compatibility (irGSEA uses 'slot' internally)
  .check_seurat_v4(seurat_obj, context = "run_irgsea_seurat")

  # Auto-detect: if gene_sets provided, use custom = TRUE (custom gene sets)
  # If gene_sets is NULL, use MSigDB (default)
  if (!is.null(gene_sets)) {
    # Path 1: Custom gene sets (irGSEA v2+ requires custom = TRUE)
    message("Running irGSEA with custom gene sets (custom = TRUE)...")

    # Extract method from ... if provided
    extra_args <- list(...)
    method_arg <- extra_args[["method"]]

    seurat_obj <- irGSEA::irGSEA.score(
      object = seurat_obj,
      geneset = gene_sets,
      custom = TRUE,
      ...
    )

    # Extract scores from assays to metadata
    seurat_obj <- extract_scores_internal(seurat_obj, method = method_arg)

  } else {
    # Path 2: MSigDB gene sets (default behavior)
    message("Running irGSEA with MSigDB gene sets...")

    # irGSEA::irGSEA.score supports built-in MSigDB when geneset is not provided
    # Call directly with Seurat object to leverage built-in gene sets
    extra_args <- list(...)
    method_arg <- extra_args[["method"]]

    seurat_obj <- irGSEA::irGSEA.score(
      object = seurat_obj,
      ...
    )

    # Extract scores from assays to metadata
    seurat_obj <- extract_scores_internal(seurat_obj, method = method_arg)

    # Add scores to metadata
    for (method_name in names(results)) {
      score_df <- as.data.frame(results[[method_name]])
      colnames(score_df) <- paste0("irGSEA.", method_name, ".", colnames(score_df))

      for (col in colnames(score_df)) {
        seurat_obj[[col]] <- score_df[[col]]
      }

      message(sprintf("  Added %d score columns for %s", ncol(score_df), method_name))
    }
  }

  message("irGSEA complete! Scores added to metadata.")
  return(seurat_obj)
}


#' Differential Enrichment Analysis
#'
#' Perform differential enrichment analysis between groups.
#'
#' @param irgsea_results Results from run_irgsea()
#' @param group_vector Vector of group labels
#' @param method Which method scores to use (default: "RRA")
#' @param test Statistical test: "wilcoxon", "t.test", "DESeq2"
#'
#' @return DataFrame with differential enrichment results
#'
#' @export
differential_enrichment <- function(
    irgsea_results,
    group_vector,
    method = "RRA",
    test = "wilcoxon"
) {
  if (!method %in% names(irgsea_results)) {
    stop(sprintf("Method '%s' not found in results", method))
  }

  scores <- irgsea_results[[method]]

  # Ensure group_vector matches cells
  if (length(group_vector) != nrow(scores)) {
    stop("Length of group_vector must match number of cells")
  }

  groups <- unique(group_vector)
  if (length(groups) != 2) {
    stop("Differential enrichment requires exactly 2 groups")
  }

  results <- list()

  for (gene_set in colnames(scores)) {
    g1_scores <- scores[group_vector == groups[1], gene_set]
    g2_scores <- scores[group_vector == groups[2], gene_set]

    if (test == "wilcoxon") {
      test_result <- wilcox.test(g1_scores, g2_scores)
    } else if (test == "t.test") {
      test_result <- t.test(g1_scores, g2_scores)
    }

    results[[gene_set]] <- data.frame(
      gene_set = gene_set,
      group1 = groups[1],
      group2 = groups[2],
      group1_mean = mean(g1_scores),
      group2_mean = mean(g2_scores),
      log2FC = log2(mean(g1_scores) / mean(g2_scores)),
      pvalue = test_result$p.value
    )
  }

  result_df <- do.call(rbind, results)
  result_df$padj <- p.adjust(result_df$pvalue, method = "BH")

  return(result_df[order(result_df$pvalue), ])
}


#' Plot irGSEA Heatmap
#'
#' @param irgsea_results Results from run_irgsea()
#' @param method Which method to plot (default: "RRA")
#' @param group_vector Vector of group labels for annotation
#' @param top_n Number of top gene sets to show (default: 20)
#'
#' @return ComplexHeatmap object
#'
#' @export
plot_irgsea_heatmap <- function(
    irgsea_results,
    method = "RRA",
    group_vector = NULL,
    top_n = 20
) {
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap package required")
  }

  if (!method %in% names(irgsea_results)) {
    stop(sprintf("Method '%s' not found", method))
  }

  scores <- irgsea_results[[method]]

  # Select top gene sets by variance
  variances <- apply(scores, 2, var)
  top_sets <- names(sort(variances, decreasing = TRUE))[1:min(top_n, length(variances))]
  scores <- scores[, top_sets, drop = FALSE]

  # Create heatmap
  if (!is.null(group_vector)) {
    ha <- ComplexHeatmap::HeatmapAnnotation(
      Group = group_vector
    )
  } else {
    ha <- NULL
  }

  hm <- ComplexHeatmap::Heatmap(
    t(scores),
    name = "Score",
    top_annotation = ha,
    cluster_columns = TRUE,
    cluster_rows = TRUE,
    show_column_names = FALSE
  )

  return(hm)
}


#' Export irGSEA Results
#'
#' @param irgsea_results Results from run_irgsea()
#' @param output_dir Output directory
#' @param prefix File prefix
#'
#' @export
export_irgsea_results <- function(
    irgsea_results,
    output_dir,
    prefix = "irgsea"
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  for (method_name in names(irgsea_results)) {
    scores <- irgsea_results[[method_name]]
    write.csv(
      scores,
      file.path(output_dir, sprintf("%s_%s_scores.csv", prefix, method_name))
    )
  }

  message(sprintf("Results exported to %s", output_dir))
}


#' Extract irGSEA scores from assays to metadata
#'
#' Extract scores from irGSEA method assays and add them as metadata columns.
#' This is useful when you want to access scores for visualization or analysis.
#'
#' @param seurat_obj Seurat object with irGSEA assays (from run_irgsea_seurat)
#' @param method Which method to extract (default: "UCell")
#' @param prefix Prefix for metadata column names (default: method name)
#'
#' @return Seurat object with scores in metadata
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # After running irGSEA
#' seurat_obj <- run_irgsea_seurat(seurat_obj, gene_sets, methods = "UCell")
#'
#' # Extract UCell scores to metadata
#' seurat_obj <- extract_irgsea_scores(seurat_obj, method = "UCell")
#'
#' # Now scores are accessible as seurat_obj$UCell.GeneSetName
#' FeaturePlot(seurat_obj, features = "UCell.Mesenchymal")
#' }
extract_irgsea_scores <- function(
    seurat_obj,
    method = "UCell",
    prefix = NULL
) {
  if (is.null(prefix)) {
    prefix <- method
  }

  assay_names <- names(seurat_obj@assays)
  if (!method %in% assay_names) {
    stop(sprintf("Method assay '%s' not found. Run run_irgsea_seurat() first.", method))
  }

  assay_obj <- seurat_obj[[method]]

  # Extract scores from data slot
  score_matrix <- as.matrix(Seurat::GetAssayData(assay_obj, slot = "data"))

  # Transpose: genes x cells -> cells x genes
  score_df <- as.data.frame(t(score_matrix))

  # Add prefix to column names
  colnames(score_df) <- paste0(prefix, ".", colnames(score_df))

  # Add to metadata
  for (col in colnames(score_df)) {
    seurat_obj[[col]] <- score_df[[col]]
  }

  message(sprintf("Added %d score columns to metadata with prefix '%s'", ncol(score_df), prefix))
  return(seurat_obj)
}


#' Calculate EMT Score
#'
#' Calculate EMT (Epithelial-Mesenchymal Transition) score from
#' Mesenchymal and Epithelial signature scores.
#'
#' @param seurat_obj Seurat object with EMT scores in metadata
#' @param mesenchymal_col Column name for mesenchymal score
#' @param epithelial_col Column name for epithelial score
#' @param method Calculation method: "ratio" (M/E, recommended) or "difference" (M-E)
#' @param new_col_name Name for new EMT score column (default: "EMT_Score")
#'
#' @return Seurat object with EMT score in metadata
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # After extracting irGSEA scores
#' seurat_obj <- extract_irgsea_scores(seurat_obj, method = "UCell")
#'
#' # Calculate EMT score as M/E ratio (recommended)
#' seurat_obj <- calculate_emt_score(
#'   seurat_obj,
#'   mesenchymal_col = "UCell.Mesenchymal",
#'   epithelial_col = "UCell.Epithelial",
#'   method = "ratio"
#' )
#'
#' # Visualize
#' FeaturePlot(seurat_obj, features = "EMT_Score")
#' }
calculate_emt_score <- function(
    seurat_obj,
    mesenchymal_col,
    epithelial_col,
    method = c("ratio", "difference"),
    new_col_name = "EMT_Score"
) {
  method <- match.arg(method)

  # Check columns exist
  if (!mesenchymal_col %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("Column '%s' not found in metadata", mesenchymal_col))
  }
  if (!epithelial_col %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("Column '%s' not found in metadata", epithelial_col))
  }

  # Get scores
  mes_scores <- seurat_obj@meta.data[[mesenchymal_col]]
  epi_scores <- seurat_obj@meta.data[[epithelial_col]]

  # Calculate EMT score
  if (method == "ratio") {
    # M/E ratio: > 1 = mesenchymal-dominant, < 1 = epithelial-dominant
    emt_scores <- mes_scores / (epi_scores + 0.001)
    message("EMT Score = Mesenchymal / (Epithelial + 0.001)")
    message("> 1: Mesenchymal-dominant, < 1: Epithelial-dominant")
  } else {
    # M - E difference: positive = mesenchymal, negative = epithelial
    emt_scores <- mes_scores - epi_scores
    message("EMT Score = Mesenchymal - Epithelial")
    message("Positive: Mesenchymal-dominant, Negative: Epithelial-dominant")
  }

  seurat_obj[[new_col_name]] <- emt_scores

  message(sprintf("EMT scores added to metadata column '%s'", new_col_name))
  return(seurat_obj)
}
