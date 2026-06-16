# Utility Functions for PROGENy
# =============================
#
# Helper functions for data validation, result processing, and analysis utilities.

#' Get assay data with cross-version Seurat compatibility
#'
#' Detects Seurat v4/v5 and uses slot= (v4) or layer= (v5) accordingly.
#'
#' @param seurat_obj Seurat object
#' @param assay Assay name (optional, uses default if NULL)
#' @return Assay data matrix
#' @export
get_assay_data_compat <- function(seurat_obj, assay = NULL) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  seurat_ver <- utils::packageVersion("SeuratObject")
  is_v5 <- seurat_ver >= package_version("5.0.0")
  if (is_v5) {
    if (is.null(assay)) {
      return(Seurat::GetAssayData(seurat_obj, layer = "data"))
    } else {
      return(Seurat::GetAssayData(seurat_obj, assay = assay, layer = "data"))
    }
  } else {
    if (is.null(assay)) {
      return(Seurat::GetAssayData(seurat_obj, slot = "data"))
    } else {
      return(Seurat::GetAssayData(seurat_obj, assay = assay, slot = "data"))
    }
  }
}

#' Validate gene names in data against PROGENy model
#'
#' @param gene_names Character vector of gene names
#' @param organism Organism: "Human" or "Mouse"
#' @param top Number of top genes to check (default: 100)
#' @return List with overlap statistics
#' @export
validate_gene_overlap <- function(gene_names, organism = "Human", top = 100) {
  if (!requireNamespace("progeny", quietly = TRUE)) {
    stop("progeny package required")
  }

  model <- progeny::getModel(organism = organism, top = top)
  model_genes <- rownames(model)

  overlap <- intersect(gene_names, model_genes)
  missing <- setdiff(model_genes, gene_names)
  data_only <- setdiff(gene_names, model_genes)

  result <- list(
    n_input_genes = length(gene_names),
    n_model_genes = length(model_genes),
    n_overlap = length(overlap),
    overlap_fraction = length(overlap) / length(model_genes),
    n_missing = length(missing),
    n_data_only = length(data_only),
    overlap_genes = overlap,
    missing_genes = missing
  )

  return(result)
}

#' Print overlap statistics
#'
#' @param overlap_result Result from validate_gene_overlap
#' @export
print_overlap_stats <- function(overlap_result) {
  cat("Gene Overlap Statistics:\n")
  cat("  Input genes:", overlap_result$n_input_genes, "\n")
  cat("  Model genes:", overlap_result$n_model_genes, "\n")
  cat("  Overlap:", overlap_result$n_overlap,
      sprintf("(%.1f%%)\n", overlap_result$overlap_fraction * 100))
  cat("  Missing from input:", overlap_result$n_missing, "\n")
  cat("  In input only:", overlap_result$n_data_only, "\n")

  if (overlap_result$overlap_fraction < 0.5) {
    warning("Low gene overlap! Check gene naming convention (HGNC/MGI symbols required)")
  }
}

#' Get pathway activity summary statistics
#'
#' @param scores Matrix or data frame of pathway scores
#' @return Data frame with summary statistics per pathway
#' @export
get_pathway_summary_stats <- function(scores) {
  if (inherits(scores, "Seurat")) {
    if (!"progeny" %in% names(scores@assays)) {
      stop("No progeny assay found")
    }
    scores <- t(as.matrix(get_assay_data_compat(scores, assay = "progeny")))
  }

  scores <- as.matrix(scores)

  stats <- data.frame(
    pathway = colnames(scores),
    mean = apply(scores, 2, mean, na.rm = TRUE),
    median = apply(scores, 2, median, na.rm = TRUE),
    sd = apply(scores, 2, sd, na.rm = TRUE),
    min = apply(scores, 2, min, na.rm = TRUE),
    max = apply(scores, 2, max, na.rm = TRUE),
    q25 = apply(scores, 2, quantile, 0.25, na.rm = TRUE),
    q75 = apply(scores, 2, quantile, 0.75, na.rm = TRUE)
  )

  return(stats)
}

#' Identify cells with extreme pathway activity
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param pathway Pathway name
#' @param quantile_threshold Quantile for extreme values (default: 0.95)
#' @param tail Which tail: "high", "low", or "both" (default: "both")
#' @return Vector of cell names
#' @export
get_extreme_pathway_cells <- function(
    seurat_obj,
    pathway,
    quantile_threshold = 0.95,
    tail = "both"
) {
  if (!"progeny" %in% names(seurat_obj@assays)) {
    stop("No progeny assay found")
  }

  scores <- as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny"))

  if (!pathway %in% rownames(scores)) {
    stop("Pathway '", pathway, "' not found")
  }

  pathway_scores <- scores[pathway, ]

  if (tail %in% c("high", "both")) {
    high_threshold <- quantile(pathway_scores, quantile_threshold)
    high_cells <- names(pathway_scores)[pathway_scores >= high_threshold]
  } else {
    high_cells <- character(0)
  }

  if (tail %in% c("low", "both")) {
    low_threshold <- quantile(pathway_scores, 1 - quantile_threshold)
    low_cells <- names(pathway_scores)[pathway_scores <= low_threshold]
  } else {
    low_cells <- character(0)
  }

  return(unique(c(high_cells, low_cells)))
}

#' Compare pathway activities between two conditions
#'
#' @param scores Matrix of pathway scores
#' @param metadata Data frame with condition information
#' @param condition_col Column name for condition
#' @param condition1 First condition value
#' @param condition2 Second condition value
#' @param method Statistical test: "t.test" or "wilcox" (default: "wilcox")
#' @return Data frame with comparison results
#' @export
compare_pathway_conditions <- function(
    scores,
    metadata,
    condition_col,
    condition1,
    condition2,
    method = "wilcox"
) {
  # Subset to conditions of interest
  keep <- metadata[[condition_col]] %in% c(condition1, condition2)
  scores_sub <- scores[keep, ]
  cond <- metadata[[condition_col]][keep]

  results <- data.frame(
    pathway = colnames(scores),
    mean1 = NA,
    mean2 = NA,
    diff = NA,
    statistic = NA,
    p_value = NA
  )

  for (i in seq_along(results$pathway)) {
    pathway <- results$pathway[i]
    vals1 <- scores_sub[cond == condition1, pathway]
    vals2 <- scores_sub[cond == condition2, pathway]

    results$mean1[i] <- mean(vals1)
    results$mean2[i] <- mean(vals2)
    results$diff[i] <- results$mean1[i] - results$mean2[i]

    if (method == "t.test") {
      test <- t.test(vals1, vals2)
    } else {
      test <- wilcox.test(vals1, vals2)
    }

    results$statistic[i] <- as.numeric(test$statistic)
    results$p_value[i] <- test$p.value
  }

  results$adj_p_value <- p.adjust(results$p_value, method = "BH")

  return(results)
}

#' Merge PROGENy results back to original Seurat object
#'
#' @param original Original Seurat object
#' @param progeny_result Seurat object with progeny assay
#' @return Merged Seurat object
#' @export
merge_progeny_results <- function(original, progeny_result) {
  if (!"progeny" %in% names(progeny_result@assays)) {
    stop("No progeny assay in result object")
  }

  original[["progeny"]] <- progeny_result[["progeny"]]
  message("PROGENy assay added to original object")

  return(original)
}

#' Export pathway scores to various formats
#'
#' @param scores Matrix or data frame of scores
#' @param output_file Output file path
#' @param format Output format: "csv", "tsv", "rds" (default: "csv")
#' @return Invisible NULL
#' @export
export_pathway_scores <- function(
    scores,
    output_file,
    format = "csv"
) {
  if (inherits(scores, "Seurat")) {
    scores <- t(as.matrix(get_assay_data_compat(scores, assay = "progeny")))
  }

  format <- tolower(format)
  if (format == "csv") {
    write.csv(scores, output_file, row.names = TRUE)
  } else if (format == "tsv") {
    write.table(scores, output_file, sep = "\t", row.names = TRUE)
  } else if (format == "rds") {
    saveRDS(scores, output_file)
  } else {
    stop("Unknown format: ", format)
  }

  return(invisible(NULL))
}

#' Create summary report of PROGENy analysis
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param output_file Output file path (optional)
#' @return Summary string
#' @export
create_progeny_report <- function(seurat_obj, output_file = NULL) {
  if (!"progeny" %in% names(seurat_obj@assays)) {
    stop("No progeny assay found")
  }

  # Get summary stats
  stats <- get_pathway_summary_stats(seurat_obj)

  report <- c(
    "PROGENy Analysis Report",
    "======================",
    "",
    paste("Number of cells:", ncol(seurat_obj)),
    paste("Number of pathways:", nrow(seurat_obj[["progeny"]])),
    "",
    "Pathway Summary Statistics:",
    capture.output(print(stats)),
    "",
    "Top 3 Most Active Pathways (by mean):",
    capture.output(print(head(stats[order(-stats$mean), ], 3))),
    "",
    "Most Variable Pathways (by SD):",
    capture.output(print(head(stats[order(-stats$sd), ], 3)))
  )

  report_text <- paste(report, collapse = "\n")

  if (!is.null(output_file)) {
    writeLines(report_text, output_file)
    message("Report saved to ", output_file)
  }

  cat(report_text, "\n")
  return(invisible(report_text))
}

#' Check if required packages are installed
#'
#' @return Logical indicating whether all packages are available
#' @export
check_progeny_dependencies <- function() {
  required <- c("progeny", "Seurat", "ggplot2", "pheatmap")
  missing <- character(0)

  for (pkg in required) {
    if (!requireNamespace(pkg, quietly = TRUE)) {
      missing <- c(missing, pkg)
    }
  }

  optional <- c("ggridges", "dplyr")
  missing_opt <- character(0)

  for (pkg in optional) {
    if (!requireNamespace(pkg, quietly = TRUE)) {
      missing_opt <- c(missing_opt, pkg)
    }
  }

  if (length(missing) > 0) {
    warning("Missing required packages: ", paste(missing, collapse = ", "))
    return(FALSE)
  }

  if (length(missing_opt) > 0) {
    message("Optional packages not installed: ", paste(missing_opt, collapse = ", "))
  }

  message("All required packages available")
  return(TRUE)
}

#' Get recommended top parameter based on data characteristics
#'
#' @param n_cells Number of cells
#' @param organism Organism
#' @return Recommended top value
#' @export
recommend_top_parameter <- function(n_cells, organism = "Human") {
  if (n_cells < 100) {
    return(500)  # Small dataset, use more genes
  } else if (n_cells < 1000) {
    return(200)  # Medium dataset
  } else {
    return(100)  # Large dataset, standard parameter
  }
}
