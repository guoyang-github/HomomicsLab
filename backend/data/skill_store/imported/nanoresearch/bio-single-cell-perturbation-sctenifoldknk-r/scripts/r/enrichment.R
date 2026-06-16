#' Enrichment Analysis Functions for scTenifoldKnk Results
#'
#' This module provides functions for pathway and functional enrichment analysis
#' of differentially regulated genes from scTenifoldKnk knockdown experiments.
#'
#' @author Based on scTenifoldKnk manuscript analysis
#' @references Osorio et al. (2020). Systematic characterization of gene knockdown
#'   perturbations in single-cell data. bioRxiv.

#' Run Enrichment Analysis on Knockdown Results
#'
#' Performs pathway enrichment analysis on significantly affected genes
#' from scTenifoldKnk results using enrichR and fgsea.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param databases Character vector. Enrichment databases to query.
#'   Default: c("KEGG_2019_Human", "GO_Biological_Process_2018",
#'   "GO_Cellular_Component_2018", "GO_Molecular_Function_2018").
#' @param p_cutoff Numeric. P-value cutoff for significant genes (default: 0.05).
#' @param fdr_threshold Numeric. FDR threshold for enriched terms (default: 0.05).
#' @param use_zscore Logical. Whether to use Z-scores for GSEA (default: TRUE).
#'   If FALSE, uses fold changes.
#' @param max_categories Integer. Maximum categories to return per database (default: 50).
#' @param organism Character. Either "human" or "mouse" (default: "human").
#'
#' @return List containing:
#'   \item{enrichr}{Results from enrichR analysis}
#'   \item{fgsea}{Results from fgsea analysis (if available)}
#'   \item{sig_genes}{Vector of significant gene symbols}
#'   \item{summary}{Summary statistics}
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#'
#' # Basic enrichment
#' enrichment <- run_enrichment_analysis(result)
#'
#' # Custom databases
#' enrichment <- run_enrichment_analysis(
#'   result,
#'   databases = c("KEGG_2019_Human", "Reactome_2016"),
#'   organism = "human"
#' )
#' }
#'
#' @export
run_enrichment_analysis <- function(
    result,
    databases = c(
      "KEGG_2019_Human",
      "GO_Biological_Process_2018",
      "GO_Cellular_Component_2018",
      "GO_Molecular_Function_2018",
      "BioPlanet_2019",
      "WikiPathways_2019_Human",
      "Reactome_2016"
    ),
    p_cutoff = 0.05,
    fdr_threshold = 0.05,
    use_zscore = TRUE,
    max_categories = 50,
    organism = "human"
) {
  # Check required packages
  if (!requireNamespace("enrichR", quietly = TRUE)) {
    stop("Package 'enrichR' is required. Install with: install.packages('enrichR')")
  }

  # Adjust databases for organism
  if (organism == "mouse") {
    databases <- gsub("Human", "Mouse", databases)
    databases <- gsub("_Human", "_Mouse", databases)
  }

  # Extract significant genes
  dr <- result$diffRegulation
  sig_genes <- dr$gene[dr$p.adj < p_cutoff]

  if (length(sig_genes) == 0) {
    warning("No significant genes found at p_cutoff = ", p_cutoff)
    return(list(
      enrichr = NULL,
      fgsea = NULL,
      sig_genes = character(0),
      summary = list(n_sig_genes = 0, n_enriched = 0)
    ))
  }

  message(sprintf("Running enrichment on %d significant genes...", length(sig_genes)))

  # Run enrichR
  enrichr_results <- list()

  tryCatch({
    enrichr_output <- enrichR::enrichr(sig_genes, databases)

    # Process results for each database
    for (db_name in names(enrichr_output)) {
      df <- enrichr_output[[db_name]]

      if (!is.null(df) && nrow(df) > 0) {
        # Filter by FDR
        df <- df[df$Adjusted.P.value < fdr_threshold, ]

        if (nrow(df) > 0) {
          # Clean up term names
          df$Term <- sapply(strsplit(df$Term, ""), function(X) {
            X[1] <- toupper(X[1])
            X <- paste0(X, collapse = "")
            X <- gsub("\\([[:print:]]+\\)|Homo[[:print:]]+|WP[[:digit:]]+", "", X)
            X <- gsub("'s", "", X)
            X <- unlist(strsplit(X, ","))[1]
            X <- gsub("[[:blank:]]$", "", X)
            return(X)
          })

          # Remove duplicates
          df <- df[!duplicated(toupper(df$Term)), ]

          # Limit to max categories
          if (nrow(df) > max_categories) {
            df <- df[seq_len(max_categories), ]
          }

          enrichr_results[[db_name]] <- df
        }
      }
    }
  }, error = function(e) {
    warning("enrichR analysis failed: ", conditionMessage(e))
  })

  # Run fgsea if available
  fgsea_results <- NULL

  if (requireNamespace("fgsea", quietly = TRUE)) {
    tryCatch({
      # Prepare gene list
      gene_list <- if (use_zscore) dr$Z else dr$FC
      names(gene_list) <- toupper(dr$gene)
      gene_list <- gene_list[!is.na(gene_list)]
      gene_list <- sort(gene_list, decreasing = TRUE)

      # Load pathways
      pathways <- list()

      for (db in databases) {
        tryCatch({
          # Try to fetch from Enrichr
          url <- sprintf(
            "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=%s",
            db
          )
          gmt_lines <- readLines(url, warn = FALSE)

          for (line in gmt_lines) {
            parts <- strsplit(line, "\t")[[1]]
            pathway_name <- parts[1]
            genes <- parts[-c(1, 2)]
            pathways[[pathway_name]] <- genes
          }
        }, error = function(e) {
          message("Could not load database: ", db)
        })
      }

      if (length(pathways) > 0) {
        # Run fgsea
        set.seed(1)
        fgsea_results <- fgsea::fgseaMultilevel(
          pathways = pathways,
          stats = gene_list,
          sampleSize = 101
        )

        # Filter and sort
        fgsea_results <- fgsea_results[fgsea_results$padj < fdr_threshold, ]
        fgsea_results <- fgsea_results[order(-fgsea_results$NES), ]

        # Format leading edge
        fgsea_results$leadingEdge <- sapply(
          fgsea_results$leadingEdge,
          function(x) paste0(x, collapse = ";")
        )
      }
    }, error = function(e) {
      warning("fgsea analysis failed: ", conditionMessage(e))
    })
  }

  # Compile summary
  n_enriched <- sum(sapply(enrichr_results, nrow))

  summary <- list(
    n_sig_genes = length(sig_genes),
    n_databases = length(databases),
    n_enriched_terms = n_enriched,
    databases_queried = databases,
    p_cutoff = p_cutoff,
    fdr_threshold = fdr_threshold
  )

  return(list(
    enrichr = enrichr_results,
    fgsea = fgsea_results,
    sig_genes = sig_genes,
    summary = summary
  ))
}

#' Plot Enrichment Results
#'
#' Creates visualization of enrichment analysis results.
#'
#' @param enrichment List. Output from run_enrichment_analysis().
#' @param database Character. Which database to plot (default: first available).
#' @param n_terms Integer. Number of top terms to show (default: 15).
#' @param plot_type Character. Type of plot: "bar", "dot", or "lollipop" (default: "bar").
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width in inches (default: 10).
#' @param height Numeric. Plot height in inches (default: 8).
#'
#' @return ggplot object (invisibly if save_path provided).
#'
#' @examples
#' \dontrun{
#' enrichment <- run_enrichment_analysis(result)
#' plot_enrichment(enrichment, database = "KEGG_2019_Human")
#' }
#'
#' @export
plot_enrichment <- function(
    enrichment,
    database = NULL,
    n_terms = 15,
    plot_type = "bar",
    save_path = NULL,
    width = 10,
    height = 8
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Package 'ggplot2' is required for plotting")
  }

  # Get database to plot
  if (is.null(database)) {
    available_dbs <- names(enrichment$enrichr)
    if (length(available_dbs) == 0) {
      stop("No enrichment results available to plot")
    }
    database <- available_dbs[1]
  }

  df <- enrichment$enrichr[[database]]

  if (is.null(df) || nrow(df) == 0) {
    stop("No enrichment results for database: ", database)
  }

  # Limit to top n_terms
  if (nrow(df) > n_terms) {
    df <- df[seq_len(n_terms), ]
  }

  # Create plot
  if (plot_type == "bar") {
    p <- ggplot2::ggplot(df, ggplot2::aes(
      x = reorder(Term, -Adjusted.P.value),
      y = -log10(Adjusted.P.value)
    )) +
      ggplot2::geom_bar(stat = "identity", fill = "steelblue") +
      ggplot2::coord_flip() +
      ggplot2::labs(
        title = paste("Enriched Pathways -", database),
        x = "Pathway",
        y = "-log10(FDR)"
      ) +
      ggplot2::theme_minimal() +
      ggplot2::theme(
        axis.text.y = ggplot2::element_text(size = 10),
        plot.title = ggplot2::element_text(face = "bold")
      )

  } else if (plot_type == "dot") {
    # Parse gene counts
    df$GeneCount <- sapply(strsplit(df$Genes, ";"), length)

    p <- ggplot2::ggplot(df, ggplot2::aes(
      x = GeneCount,
      y = reorder(Term, -Adjusted.P.value),
      size = GeneCount,
      color = -log10(Adjusted.P.value)
    )) +
      ggplot2::geom_point() +
      ggplot2::scale_color_gradient(low = "blue", high = "red") +
      ggplot2::labs(
        title = paste("Enriched Pathways -", database),
        x = "Gene Count",
        y = "Pathway",
        color = "-log10(FDR)",
        size = "Genes"
      ) +
      ggplot2::theme_minimal() +
      ggplot2::theme(plot.title = ggplot2::element_text(face = "bold"))

  } else if (plot_type == "lollipop") {
    p <- ggplot2::ggplot(df, ggplot2::aes(
      x = reorder(Term, -Adjusted.P.value),
      y = -log10(Adjusted.P.value)
    )) +
      ggplot2::geom_segment(ggplot2::aes(
        x = Term,
        xend = Term,
        y = 0,
        yend = -log10(Adjusted.P.value)
      ), color = "grey50") +
      ggplot2::geom_point(color = "steelblue", size = 4) +
      ggplot2::coord_flip() +
      ggplot2::labs(
        title = paste("Enriched Pathways -", database),
        x = "Pathway",
        y = "-log10(FDR)"
      ) +
      ggplot2::theme_minimal() +
      ggplot2::theme(
        axis.text.y = ggplot2::element_text(size = 10),
        plot.title = ggplot2::element_text(face = "bold")
      )
  } else {
    stop("plot_type must be 'bar', 'dot', or 'lollipop'")
  }

  # Save if path provided
  if (!is.null(save_path)) {
    ggplot2::ggsave(save_path, p, width = width, height = height, dpi = 300)
    message("Plot saved to: ", save_path)
    invisible(p)
  } else {
    return(p)
  }
}

#' Compare Enrichment Across Multiple Knockdowns
#'
#' Compares pathway enrichment results from multiple gene knockdowns.
#'
#' @param enrichment_list Named list of enrichment results.
#' @param database Character. Database to compare (default: "KEGG_2019_Human").
#'
#' @return List containing overlap statistics and comparison plots.
#'
#' @examples
#' \dontrun{
#' results <- run_multiple_knockdowns(counts, c("POU5F1", "SOX2", "NANOG"))
#' enrichments <- lapply(results, run_enrichment_analysis)
#' comparison <- compare_enrichment(enrichments)
#' }
#'
#' @export
compare_enrichment <- function(
    enrichment_list,
    database = "KEGG_2019_Human"
) {
  # Extract pathways for each knockdown
  pathways_per_kd <- lapply(enrichment_list, function(e) {
    if (is.null(e$enrichr[[database]])) {
      return(character(0))
    }
    e$enrichr[[database]]$Term
  })

  # Find common pathways
  all_pathways <- unique(unlist(pathways_per_kd))

  if (length(all_pathways) == 0) {
    warning("No pathways found for database: ", database)
    return(NULL)
  }

  # Create overlap matrix
  n <- length(pathways_per_kd)
  overlap_matrix <- matrix(0, n, n)
  rownames(overlap_matrix) <- colnames(overlap_matrix) <- names(pathways_per_kd)

  for (i in seq_len(n)) {
    for (j in seq_len(n)) {
      if (i == j) {
        overlap_matrix[i, j] <- length(pathways_per_kd[[i]])
      } else {
        overlap_matrix[i, j] <- length(
          intersect(pathways_per_kd[[i]], pathways_per_kd[[j]])
        )
      }
    }
  }

  # Find shared pathways
  if (n > 1) {
    shared_pathways <- Reduce(intersect, pathways_per_kd)
  } else {
    shared_pathways <- pathways_per_kd[[1]]
  }

  return(list(
    overlap_matrix = overlap_matrix,
    shared_pathways = shared_pathways,
    all_pathways = all_pathways,
    n_pathways = sapply(pathways_per_kd, length)
  ))
}
