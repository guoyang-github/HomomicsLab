# Core Analysis Functions for miloR
# ================================
#
# Wrapper functions for differential abundance analysis using miloR
# Reference: Dann et al., Nature Biotechnology 2021

library(miloR)
library(SingleCellExperiment)
library(edgeR)

#' Check miloR dependencies
#'
#' @return TRUE if all dependencies are installed
#' @export
check_milor_dependencies <- function() {
  required <- c("miloR", "SingleCellExperiment", "edgeR", "limma")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning("Missing packages: ", paste(missing, collapse = ", "))
    return(FALSE)
  }
  return(TRUE)
}

#' Validate input data for miloR analysis
#'
#' @param x SingleCellExperiment or matrix object
#' @param sample_col Column name for sample IDs in colData
#' @param condition_col Column name for condition in colData
#' @return List with validation results
#' @export
validate_milor_input <- function(x, sample_col = "sample_id", condition_col = NULL) {
  if (!is(x, "SingleCellExperiment") && !is.matrix(x)) {
    stop("Input must be SingleCellExperiment or matrix")
  }

  if (is(x, "SingleCellExperiment")) {
    if (!sample_col %in% colnames(colData(x))) {
      stop(sprintf("Sample column '%s' not found in colData", sample_col))
    }

    if (!is.null(condition_col) && !condition_col %in% colnames(colData(x))) {
      stop(sprintf("Condition column '%s' not found in colData", condition_col))
    }

    # Check for reduced dimensions
    if (length(reducedDimNames(x)) == 0 && !"logcounts" %in% assayNames(x)) {
      stop("Input must have reducedDims or logcounts assay for PCA computation")
    }
  }

  list(valid = TRUE, type = class(x)[1])
}

#' Create Milo object from SingleCellExperiment
#'
#' @param x SingleCellExperiment object
#' @return Milo object
#' @export
create_milo_object <- function(x) {
  if (!is(x, "SingleCellExperiment")) {
    stop("Input must be SingleCellExperiment")
  }

  milo_obj <- Milo(x)
  message("Created Milo object with ", ncol(milo_obj), " cells")
  return(milo_obj)
}

#' Build kNN graph for Milo object
#'
#' @param x Milo object
#' @param k Number of nearest neighbors (default: 30)
#' @param d Number of dimensions for PCA (default: 30)
#' @param reduced_dims Name of reduced dimension slot to use (default: "PCA")
#' @param get.distance Whether to compute distances (default: FALSE)
#' @return Milo object with graph slot populated
#' @export
build_milo_graph <- function(x, k = 30, d = 30, reduced_dims = "PCA",
                             get.distance = FALSE) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  message("Building kNN graph with k=", k, "...")
  x <- buildGraph(x, k = k, d = d, reduced.dim = reduced_dims,
                  get.distance = get.distance)
  message("Graph construction complete")
  return(x)
}

#' Define neighborhoods on kNN graph
#'
#' @param x Milo object with graph
#' @param prop Proportion of cells to sample (default: 0.1)
#' @param k Number of nearest neighbors (default: 30)
#' @param d Number of dimensions (default: 30)
#' @param refined Use refined sampling (default: TRUE)
#' @param reduced_dims Name of reduced dimension slot (default: "PCA")
#' @param refinement_scheme Refinement scheme (default: "reduced_dim")
#' @param seed Random seed for reproducibility (default: NULL)
#' @return Milo object with neighborhoods defined
#' @export
make_milo_neighborhoods <- function(x, prop = 0.1, k = 30, d = 30,
                                    refined = TRUE, reduced_dims = "PCA",
                                    refinement_scheme = "reduced_dim",
                                    seed = NULL) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  if (!is.null(seed)) {
    set.seed(seed)
  }

  message("Defining neighborhoods (prop=", prop, ", refined=", refined, ")...")
  x <- makeNhoods(x, prop = prop, k = k, d = d, refined = refined,
                  reduced_dims = reduced_dims, refinement_scheme = refinement_scheme)

  n_nhoods <- ncol(nhoods(x))
  message("Created ", n_nhoods, " neighborhoods")
  return(x)
}

#' Calculate neighborhood distances for spatial FDR
#'
#' @param x Milo object with neighborhoods
#' @param d Number of dimensions (default: 30)
#' @param reduced.dim Name of reduced dimension slot (default: "PCA")
#' @param use.assay Assay to use if reduced.dim not available (default: "logcounts")
#' @return Milo object with nhoodDistances slot populated
#' @export
calc_milo_distances <- function(x, d = 30, reduced.dim = "PCA",
                                use.assay = "logcounts") {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  message("Calculating neighborhood distances...")
  x <- calcNhoodDistance(x, d = d, reduced.dim = reduced.dim, use.assay = use.assay)
  message("Distance calculation complete")
  return(x)
}

#' Count cells in neighborhoods
#'
#' @param x Milo object
#' @param sample_col Column name for sample IDs
#' @param meta.data Data frame with sample metadata (optional)
#' @return Milo object with nhoodCounts slot populated
#' @export
count_milo_cells <- function(x, sample_col = "sample_id", meta.data = NULL) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  if (is.null(meta.data)) {
    meta.data <- as.data.frame(colData(x))
  }

  message("Counting cells per neighborhood per sample...")
  x <- countCells(x, samples = sample_col, meta.data = meta.data)

  n_counts <- ncol(nhoodCounts(x))
  message("Counted cells across ", n_counts, " samples")
  return(x)
}

#' Test differential abundance of neighborhoods
#'
#' @param x Milo object with nhoodCounts
#' @param design Formula for experimental design
#' @param design.df Data frame with design matrix
#' @param fdr.weighting Method for spatial FDR (default: "k-distance")
#' @param min.mean Minimum mean counts threshold (default: 0)
#' @param norm.method Normalization method (default: "TMM")
#' @param model.contrasts Contrast matrix for testing (optional)
#' @param robust Use robust estimation (default: TRUE)
#' @return Data frame with DA test results
#' @export
test_milo_da <- function(x, design, design.df,
                         fdr.weighting = c("k-distance", "neighbour-distance",
                                           "max", "graph-overlap", "none"),
                         min.mean = 0, norm.method = "TMM",
                         model.contrasts = NULL, robust = TRUE) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  fdr.weighting <- match.arg(fdr.weighting)

  message("Testing differential abundance...")
  message("  Design: ", deparse(design))
  message("  FDR weighting: ", fdr.weighting)

  da_results <- testNhoods(x, design = design, design.df = design.df,
                           fdr.weighting = fdr.weighting, min.mean = min.mean,
                           norm.method = norm.method,
                           model.contrasts = model.contrasts, robust = robust)

  n_sig <- sum(da_results$SpatialFDR < 0.1, na.rm = TRUE)
  message("Found ", n_sig, " significant DA neighborhoods (FDR < 0.1)")

  return(da_results)
}

#' Run complete miloR pipeline
#'
#' @param x SingleCellExperiment or Milo object
#' @param sample_col Column name for sample IDs
#' @param condition_col Column name for condition
#' @param design Formula for experimental design
#' @param design.df Data frame with design matrix (optional, auto-generated if NULL)
#' @param k k for kNN graph (default: 30)
#' @param d Number of dimensions (default: 30)
#' @param prop Proportion for neighborhood sampling (default: 0.1)
#' @param refined Use refined sampling (default: TRUE)
#' @param reduced_dims Name of reduced dimension (default: "PCA")
#' @param fdr.weighting Spatial FDR method (default: "k-distance")
#' @param norm.method Normalization method (default: "TMM")
#' @param calc.distances Calculate neighborhood distances (default: TRUE)
#' @param verbose Print progress messages (default: TRUE)
#' @param seed Random seed (default: NULL)
#' @return List containing milo object, DA results, and design info
#' @export
run_milo_pipeline <- function(x, sample_col = "sample_id", condition_col,
                              design, design.df = NULL,
                              k = 30, d = 30, prop = 0.1, refined = TRUE,
                              reduced_dims = "PCA",
                              fdr.weighting = "k-distance",
                              norm.method = "TMM",
                              calc.distances = TRUE,
                              verbose = TRUE, seed = NULL) {

  if (verbose) message("=== miloR Differential Abundance Pipeline ===")

  # Step 1: Create Milo object if needed
  if (is(x, "SingleCellExperiment") && !is(x, "Milo")) {
    if (verbose) message("\n[Step 1] Creating Milo object...")
    x <- create_milo_object(x)
  } else if (!is(x, "Milo")) {
    stop("Input must be SingleCellExperiment or Milo object")
  }

  # Step 2: Build graph
  if (verbose) message("\n[Step 2] Building kNN graph...")
  x <- build_milo_graph(x, k = k, d = d, reduced_dims = reduced_dims)

  # Step 3: Make neighborhoods
  if (verbose) message("\n[Step 3] Defining neighborhoods...")
  x <- make_milo_neighborhoods(x, prop = prop, k = k, d = d, refined = refined,
                               reduced_dims = reduced_dims, seed = seed)

  # Step 4: Calculate distances (optional but recommended)
  if (calc.distances) {
    if (verbose) message("\n[Step 4] Calculating neighborhood distances...")
    x <- calc_milo_distances(x, d = d, reduced.dim = reduced.dim)
  }

  # Step 5: Count cells
  if (verbose) message("\n[Step 5] Counting cells in neighborhoods...")
  x <- count_milo_cells(x, sample_col = sample_col)

  # Step 6: Create design.df if not provided
  if (is.null(design.df)) {
    if (verbose) message("\n[Step 6] Creating design matrix...")
    design.df <- unique(data.frame(
      sample_id = colData(x)[[sample_col]],
      condition = colData(x)[[condition_col]]
    ))
    colnames(design.df) <- c(sample_col, condition_col)
    rownames(design.df) <- design.df[[sample_col]]
  }

  # Step 7: Test DA
  if (verbose) message("\n[Step 7] Testing differential abundance...")
  da_results <- test_milo_da(x, design = design, design.df = design.df,
                             fdr.weighting = fdr.weighting, norm.method = norm.method)

  if (verbose) message("\n=== Pipeline Complete ===")

  list(
    milo = x,
    da_results = da_results,
    design = design,
    design.df = design.df,
    params = list(k = k, d = d, prop = prop, refined = refined)
  )
}

#' Group overlapping DA neighborhoods
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param da.fdr FDR threshold for DA neighborhoods (default: 0.1)
#' @param overlap Minimum cell overlap for merging (default: 1)
#' @param max.lfc.delta Maximum logFC difference for merging (default: NULL)
#' @param merge.discord Allow merging discordant signs (default: FALSE)
#' @param compute.new Force recomputing adjacency (default: FALSE)
#' @return Data frame with NhoodGroup column added
#' @export
group_milo_neighborhoods <- function(x, da.res, da.fdr = 0.1, overlap = 1,
                                     max.lfc.delta = NULL, merge.discord = FALSE,
                                     compute.new = FALSE) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  message("Grouping DA neighborhoods...")
  da.res <- groupNhoods(x, da.res = da.res, da.fdr = da.fdr, overlap = overlap,
                        max.lfc.delta = max.lfc.delta, merge.discord = merge.discord,
                        compute.new = compute.new)

  n_groups <- length(unique(na.omit(da.res$NhoodGroup)))
  message("Grouped into ", n_groups, " neighborhood groups")

  return(da.res)
}

#' Find marker genes for DA neighborhoods
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param da.fdr FDR threshold (default: 0.1)
#' @param assay Assay to use (default: "logcounts")
#' @param aggregate.samples Aggregate by sample (default: FALSE)
#' @param sample_col Sample column (required if aggregate.samples=TRUE)
#' @param overlap Minimum overlap for merging (default: 1)
#' @param gene.offset Adjust for gene detection (default: TRUE)
#' @param return.groups Return group assignments (default: FALSE)
#' @return Data frame of marker gene results or list with groups and dge
#' @export
find_milo_markers <- function(x, da.res, da.fdr = 0.1, assay = "logcounts",
                              aggregate.samples = FALSE, sample_col = NULL,
                              overlap = 1, gene.offset = TRUE,
                              return.groups = FALSE) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  message("Finding marker genes for DA neighborhoods...")
  markers <- findNhoodMarkers(x, da.res = da.res, da.fdr = da.fdr, assay = assay,
                              aggregate.samples = aggregate.samples,
                              sample_col = sample_col, overlap = overlap,
                              gene.offset = gene.offset, return.groups = return.groups)

  if (is.list(markers)) {
    message("Found markers for ", length(unique(na.omit(markers$groups$Nhood.Group))),
            " neighborhood groups")
  } else {
    message("Marker identification complete")
  }

  return(markers)
}

#' Test differential expression within neighborhoods
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param design Formula for DE testing
#' @param design.df Design data frame
#' @param nhoods Vector of neighborhood indices to test (default: all)
#' @param subset.row Subset of genes to test (default: NULL)
#' @param assay Assay to use (default: "logcounts")
#' @return Data frame of DE results
#' @export
test_milo_de <- function(x, da.res, design, design.df, nhoods = NULL,
                         subset.row = NULL, assay = "logcounts") {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  message("Testing differential expression within neighborhoods...")
  de_results <- testDiffExp(x, da.res = da.res, design = design, design.df = design.df,
                            nhoods = nhoods, subset.row = subset.row, assay = assay)

  message("DE testing complete")
  return(de_results)
}

#' Annotate neighborhoods with cell type labels
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param colData_col Column name for cell type labels
#' @param nlargest Number of top cell types to return (default: 3)
#' @return DA results with cell type annotation added
#' @export
annotate_milo_neighborhoods <- function(x, da.res, colData_col,
                                        nlargest = 3) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  if (!colData_col %in% colnames(colData(x))) {
    stop(sprintf("Column '%s' not found in colData", colData_col))
  }

  message("Annotating neighborhoods with ", colData_col, " labels...")
  da.res <- annotateNhoods(x, da.res = da.res, colData_col = colData_col,
                           nlargest = nlargest)

  return(da.res)
}
