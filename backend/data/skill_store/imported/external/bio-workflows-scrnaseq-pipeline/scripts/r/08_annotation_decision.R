#' Step 8: Cell Type Annotation Decision — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: ScType, SingleR, Seurat 5.0+
#'
#' Input State:  [Clustered] + markers
#' Output State: [Annotated]
#'
#' Recommends annotation method based on data characteristics.

library(Seurat)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x

# Load skill registry for dependency resolution
this_dir <- dirname(sys.frame(1)$ofile)
if (is.null(this_dir) || this_dir == ".") {
  this_dir <- getwd()
}
source(file.path(this_dir, "_skill_registry.R"))


# ---------------------------------------------------------------------------
# ScType tissue coverage check
# ---------------------------------------------------------------------------

.sctype_covered_tissues <- c(
  "immune", "blood", "pbmc", "lymph", "spleen", "thymus", "tonsil",
  "brain", "neuron", "nervous", "cortex", "hippocampus", "cerebellum",
  "liver", "lung", "kidney", "pancreas", "intestine", "gut", "colon",
  "heart", "skin", "eye", "muscle", "bone", "cartilage",
  "placenta", "embryo", "fetal", "adipose",
  "bladder", "uterus", "ovary", "testis", "prostate", "breast",
  "thyroid", "adrenal", "pituitary", "esophagus", "stomach"
)

.sctype_tissue_available <- function(tissue) {
  #' Check whether ScType has a marker database for the given tissue.
  if (is.null(tissue)) return(FALSE)
  tissue_clean <- tolower(gsub(" tissue| cells| cell", "", tissue))
  # Exact match
  if (tissue_clean %in% .sctype_covered_tissues) return(TRUE)
  # Partial match: e.g. "pancreatic" matches "pancreas", "cancer" matches nothing
  for (t in .sctype_covered_tissues) {
    if (grepl(t, tissue_clean, fixed = TRUE) || grepl(tissue_clean, t, fixed = TRUE)) {
      return(TRUE)
    }
  }
  FALSE
}


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend annotation method
# ---------------------------------------------------------------------------

propose_annotation_method <- function(obj, tissue_hint = NULL) {
  #' Propose cell type annotation method based on data.
  #'
  #' @param obj Seurat object [Clustered]
  #' @param tissue_hint Optional tissue type hint from user
  #' @return Recommendation list

  n_cells <- ncol(obj)
  has_markers <- !is.null(obj@misc$markers) && nrow(obj@misc$markers) > 0
  sctype_ok <- .sctype_tissue_available(tissue_hint)

  # Decision logic
  if (!is.null(tissue_hint) && sctype_ok) {
    # Tissue known and covered by ScType database
    method <- "ScType"
    reason <- sprintf(
      "Tissue type provided ('%s'). ScType has a curated marker database for this tissue.",
      tissue_hint
    )
  } else if (!is.null(tissue_hint) && !sctype_ok) {
    # Tissue known but NOT in ScType database — fallback to SingleR
    method <- "SingleR"
    reason <- sprintf(
      "Tissue type provided ('%s') but ScType has no marker database for it. Using SingleR with general reference (HPCA). Results may be less precise; consider manual curation with known markers.",
      tissue_hint
    )
  } else if (n_cells > 10000) {
    # Large dataset: SingleR is faster
    method <- "SingleR"
    reason <- sprintf(
      "Large dataset (%d cells). SingleR is reference-based and scales well. Consider providing tissue type for better accuracy.",
      n_cells
    )
  } else if (has_markers) {
    # Medium dataset with good markers: ScType default
    method <- "ScType"
    reason <- paste(
      "Medium dataset with detected markers. ScType marker-based annotation",
      "provides interpretable results with confidence scores."
    )
  } else {
    # Fallback
    method <- "SingleR"
    reason <- "Default to SingleR for quick reference-based annotation."
  }

  list(
    recommendation = list(
      method = method,
      tissue = tissue_hint,
      requires_markers = (method == "ScType")
    ),
    diagnostics = list(
      n_cells = n_cells,
      n_clusters = length(unique(Idents(obj))),
      has_markers = has_markers,
      sctype_available = sctype_ok
    ),
    justification = reason,
    alternatives = list(
      ScType = "Best when tissue type is known and in database. Uses curated marker databases.",
      SingleR = "Best for quick annotation or tissues not in ScType database. Reference-based.",
      Manual = "Use when automated methods fail or for novel populations."
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_annotation_proposal <- function(proposal, obj) {
  #' Evaluate annotation proposal before execution.
  #'
  #' Guardrails:
  #'   - Method = ScType but tissue not covered → CAUTION
  #'   - Method = ScType but no markers detected → CAUTION
  #'   - No clusters found → BLOCK

  rec <- proposal$recommendation
  method <- rec$method

  n_clusters <- length(unique(Idents(obj)))
  if (n_clusters < 2) {
    return(list(
      verdict = "BLOCK",
      adjusted = FALSE,
      reason = sprintf("Only %d cluster found. Annotation requires at least 2 clusters.", n_clusters)
    ))
  }

  if (method == "ScType" && !proposal$diagnostics$has_markers) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = "ScType selected but no markers detected in the dataset. Results may be unreliable; consider SingleR or manual annotation."
    ))
  }

  if (method == "ScType" && !proposal$diagnostics$sctype_available) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf(
        "Tissue '%s' not in ScType database. Consider SingleR or manual annotation.",
        rec$tissue %||% "unknown"
      )
    ))
  }

  if (method == "SingleR" && n_clusters > 50) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Very high cluster count (%d). SingleR may be slow; consider downsampling.", n_clusters)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Annotation methods
# ---------------------------------------------------------------------------

execute_sctype_annotation <- function(obj, tissue = "Immune system", ...) {
  #' Run ScType annotation.
  #' Delegates to bio-single-cell-annotation-sctype-r skill via the skill registry.

  # Validate tissue is in coverage list
  if (!.sctype_tissue_available(tissue)) {
    stop(paste0(
      "ScType has no marker database for tissue '", tissue, "'. ",
      "Supported tissues: ", paste(.sctype_covered_tissues, collapse = ", "), ". ",
      "Use method='SingleR' for general reference-based annotation, ",
      "or method='Manual' with known markers."
    ))
  }

  sctype_dir <- resolve_skill_path("bio-single-cell-annotation-sctype-r", "scripts")
  source(file.path(sctype_dir, "sctype_annotation.R"))

  obj <- tryCatch(
    run_sctype_annotation(obj, tissue = tissue, ...),
    error = function(e) {
      stop(
        "ScType annotation failed for tissue '", tissue, "': ", conditionMessage(e), "\n",
        "Possible causes:\n",
        "  1. Tissue not in ScType database\n",
        "  2. Missing required markers in the dataset\n",
        "  3. bio-single-cell-annotation-sctype-r skill not available\n",
        "Fallback: use method='SingleR' or method='Manual'."
      )
    }
  )

  obj@misc$annotation_method <- "ScType"
  obj@misc$pipeline_state <- "Annotated"

  return(obj)
}


execute_singler_annotation <- function(obj, ref = NULL, tissue = NULL, ...) {
  #' Run SingleR annotation.
  #' Uses SingleR + celldex directly (lightweight wrapper, no external skill dependency).

  library(SingleR)

  if (is.null(ref)) {
    library(celldex)
    # Select reference based on tissue type
    if (!is.null(tissue)) {
      tissue_lower <- tolower(tissue)
      if (grepl("immune|blood|pbmc|lymph", tissue_lower)) {
        ref <- celldex::MonacoImmuneData()
      } else if (grepl("brain|neuron|nerv", tissue_lower)) {
        ref <- celldex::HumanPrimaryCellAtlasData()
      } else if (grepl("liver|lung|kidney|pancrea|intestine|gut", tissue_lower)) {
        ref <- celldex::BlueprintEncodeData()
      } else {
        ref <- celldex::HumanPrimaryCellAtlasData()
      }
    } else {
      ref <- celldex::MonacoImmuneData()
    }
  }

  pred <- SingleR(test = as.SingleCellExperiment(obj),
                  ref = ref,
                  labels = ref$label.main,
                  ...)

  obj$cell_type <- pred$labels
  obj$cell_type_score <- apply(pred$scores, 1, max)

  obj@misc$annotation_method <- "SingleR"
  obj@misc$pipeline_state <- "Annotated"

  return(obj)
}


execute_manual_annotation <- function(obj, cluster_annotations) {
  #' Apply manual cluster-to-cell-type mapping.
  #'
  #' @param cluster_annotations Named vector: cluster_id -> cell_type

  obj$cell_type <- cluster_annotations[as.character(Idents(obj))]
  obj@misc$annotation_method <- "Manual"
  obj@misc$pipeline_state <- "Annotated"

  return(obj)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_annotation <- function(obj) {
  #' Report annotation results.

  method <- obj@misc$annotation_method %||% "Unknown"
  cell_types <- table(obj$cell_type)

  n_unassigned <- sum(is.na(obj$cell_type) | obj$cell_type == "Unknown")
  pct_assigned <- (1 - n_unassigned / ncol(obj)) * 100

  status <- if (pct_assigned < 50) {
    "WARNING"
  } else if (pct_assigned < 80) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "Cell Type Annotation",
    status = status,
    method = method,
    n_cell_types = length(unique(obj$cell_type)),
    pct_assigned = round(pct_assigned, 1),
    cell_type_table = cell_types,
    recommendation = if (status == "WARNING") {
      "<50% cells assigned. Try different annotation method or provide tissue-specific markers."
    } else if (status == "CAUTION") {
      "Partial assignment. Review unassigned clusters; may need manual curation."
    } else {
      "Good assignment rate. Pipeline complete."
    },
    next_step = "Pipeline complete. Optional: downstream analysis (differential expression, pathway analysis, etc.)"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_annotation_step <- function(obj, method = NULL, tissue = NULL,
                                 cluster_annotations = NULL, auto = FALSE, use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete annotation step.
  #'
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @return List(obj, report, proposal, llm_report)

  # State validation
  expected_states <- c("Clustered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for annotation step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_annotation_method(obj, tissue_hint = tissue)

  # Evaluate phase: guardrail on annotation feasibility
  evaluation <- evaluate_annotation_proposal(proposal, obj)
  if (evaluation$verdict == "BLOCK") {
    stop(evaluation$reason)
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(method)) {
    method <- proposal$recommendation$method
  }

  if (!auto) {
    message("\n=== Annotation Proposal ===")
    message(sprintf("Recommended method: %s", method))
    message(sprintf("Justification: %s", proposal$justification))
    if (!is.null(tissue)) {
      message(sprintf("Tissue: %s", tissue))
    }
  }

  if (method == "ScType") {
    tissue_use <- tissue %||% proposal$recommendation$tissue %||% "Immune system"
    obj <- execute_sctype_annotation(obj, tissue = tissue_use, ...)
  } else if (method == "SingleR") {
    obj <- execute_singler_annotation(obj, tissue = tissue, ...)
  } else if (method == "Manual") {
    if (is.null(cluster_annotations)) {
      stop("Manual annotation requires cluster_annotations parameter")
    }
    obj <- execute_manual_annotation(obj, cluster_annotations)
  } else {
    stop("Unknown annotation method: ", method)
  }

  report <- report_annotation(obj)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("annotation", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
