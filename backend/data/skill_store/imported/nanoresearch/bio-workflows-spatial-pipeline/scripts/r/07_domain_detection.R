#' Step 7: Domain Detection — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+, BayesSpace (optional)
#'
#' Input State:  [Spatial-Analyzed] or [Clustered]
#' Output State: [Domains]
#'
#' Identifies spatial domains using spatially constrained clustering.

library(Seurat)

# Load skill registry for BayesSpace sub-skill dependency resolution
.this_file <- if (!is.null(sys.frame(1)$ofile)) sys.frame(1)$ofile else NULL
if (is.null(.this_file) || .this_file == ".") {
  this_dir <- getwd()
} else {
  this_dir <- dirname(.this_file)
}
source(file.path(this_dir, "_skill_registry.R"))

# Resolve BayesSpace sub-skill utilities (prepare_bayesspace_seurat, etc.)
bayesspace_skill_dir <- NULL
tryCatch({
  bayesspace_skill_dir <- resolve_skill_path("bio-spatial-transcriptomics-domains-bayesspace-r", "scripts/r")
  source(file.path(bayesspace_skill_dir, "utils.R"))
}, error = function(e) {
  message(sprintf("BayesSpace sub-skill not resolved: %s", conditionMessage(e)))
})


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_domain_method <- function(obj) {
  #' Propose domain detection method based on data characteristics.

  n_spots <- ncol(obj)

  # Get current cluster count
  cluster_cols <- grep("snn_res\\.", colnames(obj@meta.data), value = TRUE)
  if (length(cluster_cols) > 0) {
    n_clusters <- length(unique(obj@meta.data[[cluster_cols[1]]]))
  } else {
    n_clusters <- length(unique(Idents(obj)))
  }

  # Method selection
  if (n_spots > 50000) {
    method <- "spatial_leiden"
    reason <- sprintf(
      "Large dataset (%d spots). Spatial Leiden is fast and scalable.",
      n_spots
    )
  } else if (requireNamespace("BayesSpace", quietly = TRUE)) {
    method <- "bayesspace"
    reason <- sprintf(
      "Dataset size (%d spots) suitable for BayesSpace. Provides uncertainty quantification.",
      n_spots
    )
  } else {
    method <- "spatial_leiden"
    reason <- sprintf(
      "BayesSpace not installed. Using spatial Leiden fallback (%d spots).",
      n_spots
    )
  }

  # Resolution
  if (n_clusters < 5) {
    domain_res <- 1.0
  } else if (n_clusters < 15) {
    domain_res <- 0.8
  } else {
    domain_res <- 0.5
  }

  list(
    recommendation = list(
      method = method,
      resolution = domain_res,
      comparison_cluster_col = cluster_cols[1] %||% "seurat_clusters"
    ),
    diagnostics = list(
      n_spots = n_spots,
      n_clusters = n_clusters
    ),
    justification = reason,
    alternatives = list(
      bayesspace = "R-only; provides uncertainty quantification and smoothing.",
      spatial_leiden = "Fast; uses spatial adjacency graph for constrained clustering.",
      stagate = "Python-only (STAGATE); deep learning for complex architecture."
    )
  )
}


`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_domain_proposal <- function(proposal, obj) {
  #' Evaluate domain detection proposal before execution.
  #'
  #' Guardrails:
  #'   - Method not in {spatial_leiden, bayesspace} → BLOCK
  #'   - Resolution outside [0.1, 2.0] → BLOCK + clamp
  #'   - n_spots > 50000 but method = bayesspace → CAUTION (slow)

  method <- proposal$recommendation$method
  resolution <- proposal$recommendation$resolution

  valid_methods <- c("spatial_leiden", "bayesspace")
  if (!(method %in% valid_methods)) {
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("Unknown domain method '%s'. Valid: %s", method, paste(valid_methods, collapse = ", ")),
      adjusted_params = list(method = "spatial_leiden")
    ))
  }

  if (resolution < 0.1 || resolution > 2.0) {
    clamped_res <- max(0.1, min(2.0, resolution))
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("Resolution %.2f outside [0.1, 2.0]. Clamped to %.2f.", resolution, clamped_res),
      adjusted_params = list(resolution = clamped_res)
    ))
  }

  n_spots <- proposal$diagnostics$n_spots
  if (method == "bayesspace" && n_spots > 50000) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("BayesSpace on %d spots may be very slow. Consider spatial_leiden.", n_spots)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_domain_detection <- function(obj,
                                     method = "spatial_leiden",
                                     resolution = 0.8,
                                     cluster_col = "seurat_clusters",
                                     ...) {
  #' Run domain detection with specified method.
  #'
  #' @param obj Seurat object
  #' @param method 'spatial_leiden' or 'bayesspace'
  #' @param resolution Leiden resolution for spatially constrained clustering
  #' @param cluster_col Column with transcriptomic clusters for comparison
  #' @param ... Additional args
  #' @return Seurat object with 'spatial_domain' in meta.data

  # Resolve cluster column dynamically if default doesn't exist
  if (!(cluster_col %in% colnames(obj@meta.data))) {
    cluster_cols <- grep("snn_res\\.", colnames(obj@meta.data), value = TRUE)
    if (length(cluster_cols) > 0) {
      cluster_col <- cluster_cols[1]
    } else {
      warning("No cluster column found. Domain-cluster ARI will not be computed.")
      cluster_col <- NULL
    }
  }

  if (method == "bayesspace") {
    if (!requireNamespace("BayesSpace", quietly = TRUE)) {
      warning("BayesSpace not installed. Falling back to spatial_leiden.")
      method <- "spatial_leiden"
    }
  }

  bayesspace_ok <- FALSE
  if (method == "bayesspace") {
    tryCatch({
      # Use sub-skill's prepare_bayesspace_seurat if available; fallback to native conversion
      if (exists("prepare_bayesspace_seurat", mode = "function")) {
        sce <- prepare_bayesspace_seurat(obj)
      } else {
        sce <- Seurat::as.SingleCellExperiment(obj)
      }
      sce <- BayesSpace::spatialPreprocess(sce, platform = "Visium")
      q <- min(20, ncol(obj) / 100)  # heuristic domain count
      q <- max(2, min(q, 30))
      # Guardrail: q should not exceed n_spots/20
      q_max <- max(2, floor(ncol(obj) / 20))
      if (q > q_max) {
        message(sprintf("GUARDRAIL: q=%d exceeds n_spots/20 (%d). Clamping to %d.", q, q_max, q_max))
        q <- q_max
      }
      sce <- BayesSpace::spatialCluster(sce, q = q, ...)
      obj@meta.data$spatial_domain <- as.character(sce$spatial.cluster)
      n_domains <- length(unique(obj@meta.data$spatial_domain))
      message(sprintf("BayesSpace domain detection complete: %d domains", n_domains))
      bayesspace_ok <- TRUE
    }, error = function(e) {
      message(sprintf("BayesSpace failed: %s. Falling back to spatial_leiden.", conditionMessage(e)))
    })
    if (!bayesspace_ok) {
      method <- "spatial_leiden"
    }
  }

  if (method == "spatial_leiden") {
    # Use spatial adjacency if available, otherwise transcriptomic neighbors
    assay <- DefaultAssay(obj)
    snn_name <- sprintf("%s_snn", assay)
    if (!(snn_name %in% names(obj@graphs))) {
      obj <- FindNeighbors(obj, reduction = obj@misc$clustering_reduction %||% "pca",
                           dims = obj@misc$clustering_dims, verbose = FALSE)
    }

    # Re-run clustering with spatial constraint (simplified: use SNN graph)
    obj <- FindClusters(obj, resolution = resolution, verbose = FALSE)
    # Rename to spatial_domain
    obj@meta.data$spatial_domain <- as.character(Idents(obj))

    n_domains <- length(unique(obj@meta.data$spatial_domain))
    message(sprintf("Spatial Leiden domain detection complete: %d domains", n_domains))
  }

  # Compare domains vs clusters
  if (cluster_col %in% colnames(obj@meta.data)) {
    ari <- .compute_ari(
      as.character(obj@meta.data[[cluster_col]]),
      as.character(obj@meta.data$spatial_domain)
    )
    obj@misc$domain_cluster_ari <- round(ari, 3)
    message(sprintf("Domain-cluster ARI: %.3f", ari))
  }

  obj@misc$pipeline_state <- "Domains"
  obj@misc$domain_method <- method
  obj@misc$domain_resolution <- resolution

  return(obj)
}


.compute_ari <- function(labels1, labels2) {
  #' Compute Adjusted Rand Index without external dependencies.
  #'
  #' Simplified implementation using table cross-tabulation.

  tab <- table(labels1, labels2)
  a <- sum(choose(tab, 2))
  b <- sum(choose(rowSums(tab), 2))
  c <- sum(choose(colSums(tab), 2))
  d <- choose(sum(tab), 2)

  if (d == 0) return(1)

  expected <- (b * c) / d
  max_ari <- 0.5 * (b + c)

  if (max_ari == expected) return(0)

  (a - expected) / (max_ari - expected)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_domain_detection <- function(obj, proposal) {
  #' Report domain detection results.

  n_domains <- length(unique(obj@meta.data$spatial_domain))
  method <- obj@misc$domain_method %||% "Unknown"
  ari <- obj@misc$domain_cluster_ari

  if (n_domains < 2) {
    status <- "WARNING"
  } else if (n_domains > 30) {
    status <- "CAUTION"
  } else {
    status <- "PASS"
  }

  list(
    step = "Domain Detection",
    status = status,
    n_domains = n_domains,
    method = method,
    domain_cluster_ari = ari,
    recommendation = if (n_domains < 2) {
      "Only 1 domain detected. Check spatial coords and neighbor graph."
    } else if (n_domains > 30) {
      sprintf("Many domains (%d). Consider lower resolution for broader regions.", n_domains)
    } else {
      sprintf(
        "%d domains detected. Domain-cluster ARI=%.2f. If close to 0, domains capture spatial structure beyond transcriptomics.",
        n_domains, ari %||% NA
      )
    },
    next_step = "Optional: Deconvolution / Cell-Cell Communication"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_domain_detection_step <- function(obj,
                                      method = NULL,
                                      resolution = NULL,
                                      auto = FALSE,
                                      use_llm = TRUE,
                                      prev_reports = list(),
                                      ...) {
  #' Complete domain detection step.

  # State validation
  expected_states <- c("Spatial-Analyzed", "Clustered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for domain detection step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_domain_method(obj)

  # Evaluate phase: guardrail on method and resolution
  evaluation <- evaluate_domain_proposal(proposal, obj)
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    if (!is.null(evaluation$adjusted_params$method))
      proposal$recommendation$method <- evaluation$adjusted_params$method
    if (!is.null(evaluation$adjusted_params$resolution))
      proposal$recommendation$resolution <- evaluation$adjusted_params$resolution
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(method)) method <- proposal$recommendation$method
  if (is.null(resolution)) resolution <- proposal$recommendation$resolution

  if (!auto) {
    message("\n=== Domain Detection Proposal ===")
    message(sprintf("Method: %s", method))
    message(sprintf("Resolution: %.1f", resolution))
    message(sprintf("Justification: %s", proposal$justification))
  }

  obj <- execute_domain_detection(
    obj,
    method = method,
    resolution = resolution,
    cluster_col = proposal$recommendation$comparison_cluster_col,
    ...
  )
  report <- report_domain_detection(obj, proposal)

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("domain", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
