#' STARTRAC Example Analysis
#'
#' This script demonstrates a complete STARTRAC analysis workflow
#' using example data or your own data.
#'
#' @author STARTRAC Skills Example

# Load required libraries
library(Seurat)
library(Startrac)
library(ggplot2)
library(dplyr)

# Source wrapper functions
source("../scripts/r/startrac_analysis.R")
source("../scripts/r/startrac_visualization.R")
source("../scripts/r/startrac_utils.R")

# ============================================================================
# Example 1: Basic Analysis
# ============================================================================

#' Run a basic STARTRAC analysis on prepared input data
run_basic_analysis <- function() {
    # Example: Load your prepared input data
    # input_data <- read.csv("your_input_data.csv")

    # For demonstration, we'll create mock data
    set.seed(42)
    n_cells <- 1000
    patients <- c("P01", "P02", "P03")
    clusters <- c("CD4_Treg", "CD4_Th17", "CD8_Tex", "CD8_Tem")
    locations <- c("T", "N", "PB")

    input_data <- data.frame(
        Cell_Name = paste0("Cell_", 1:n_cells),
        clone.id = sample(paste0("Clone_", 1:200), n_cells, replace = TRUE),
        patient = sample(patients, n_cells, replace = TRUE),
        majorCluster = sample(clusters, n_cells, replace = TRUE),
        loc = sample(locations, n_cells, replace = TRUE),
        stringsAsFactors = FALSE
    )

    # Remove singleton clones for better analysis
    input_data <- filter_clones(input_data, min_size = 2)

    # Run STARTRAC
    message("Running basic STARTRAC analysis...")
    result <- run_startrac(
        input_data,
        proj = "Example",
        cores = 2,
        n.perm = NULL  # No permutation for speed
    )

    # Print results summary
    message("\nCluster-level indices:")
    print(result@cluster.data)

    # Visualize
    p1 <- plot(result, index.type = "cluster.all", byPatient = FALSE)
    print(p1)

    # Export results
    export_startrac_results(result, "output/basic_analysis", formats = "csv")

    return(result)
}

# ============================================================================
# Example 2: Analysis from Seurat Object
# ============================================================================

#' Convert Seurat object to STARTRAC input and run analysis
run_seurat_analysis <- function(seurat_obj) {
    # If you don't have a Seurat object, create mock data
    if (missing(seurat_obj)) {
        message("Creating mock Seurat object for demonstration...")
        seurat_obj <- create_mock_seurat()
    }

    # Prepare input data from Seurat
    message("Preparing STARTRAC input from Seurat object...")
    input_data <- prepare_startrac_input(
        seurat_obj,
        clone_col = "tcr_clone_id",
        patient_col = "patient",
        cluster_col = "cell_type",
        loc_col = "tissue",
        filter_single = TRUE
    )

    # Run analysis with significance testing
    message("Running STARTRAC with permutation test...")
    result <- run_startrac(
        input_data,
        proj = "SeuratAnalysis",
        cores = 4,
        n.perm = 100  # Enable significance testing
    )

    # Comprehensive visualization
    message("Generating visualizations...")
    plot_startrac_results(
        result,
        output_prefix = "output/seurat_analysis",
        plot_types = "all"
    )

    # Export all results
    export_startrac_results(
        result,
        output_prefix = "output/seurat_analysis",
        formats = c("csv", "rds", "excel")
    )

    return(result)
}

# ============================================================================
# Example 3: Per-Patient Analysis
# ============================================================================

#' Run STARTRAC separately for each patient
run_per_patient_analysis <- function(input_data) {
    # Create mock data if not provided
    if (missing(input_data)) {
        input_data <- create_mock_input_data()
    }

    # Run analysis by patient
    message("Running per-patient analysis...")
    patient_results <- run_startrac_by_patient(
        input_data,
        proj = "PerPatient",
        cores = 2,
        n.perm = 50,
        min_cells = 50
    )

    # Compare across patients
    message("Comparing results across patients...")
    comparison <- compare_startrac_patients(patient_results)
    print(comparison)

    # Plot comparison
    p <- ggplot(comparison, aes(x = majorCluster, y = expa, fill = aid)) +
        geom_bar(stat = "identity", position = "dodge") +
        theme_bw() +
        theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
        labs(title = "Expansion Index by Patient",
             x = "Cell Cluster", y = "Expansion Index")
    print(p)

    # Save comparison
    write.csv(comparison, "output/patient_comparison.csv", row.names = FALSE)

    return(patient_results)
}

# ============================================================================
# Example 4: Clone Sharing Analysis
# ============================================================================

#' Analyze clone sharing between tissues
run_clone_sharing_analysis <- function(input_data) {
    # Create mock data if not provided
    if (missing(input_data)) {
        input_data <- create_mock_input_data()
    }

    # Find shared clones
    message("Analyzing clone sharing between tissues...")
    shared <- find_shared_clones(input_data, group_by = "loc")

    message(sprintf("Total clones: %d", sum(shared$clones_per_group)))
    message(sprintf("Clones shared across all locations: %d", shared$n_shared_all))
    message("\nClones per location:")
    print(shared$clones_per_group)

    message("\nOverlap matrix:")
    print(shared$overlap_matrix)

    message("\nJaccard similarity:")
    print(round(shared$jaccard_matrix, 3))

    # Calculate sharing statistics
    sharing_stats <- calculate_clone_sharing(input_data, condition_col = "loc")
    message("\nClone sharing summary:")
    print(sharing_stats$summary)

    # Plot sharing matrix
    sharing_df <- as.data.frame(shared$overlap_matrix)
    sharing_df$from <- rownames(sharing_df)
    sharing_long <- tidyr::pivot_longer(sharing_df, cols = -from,
                                         names_to = "to", values_to = "n_shared")

    p <- ggplot(sharing_long, aes(x = from, y = to, fill = n_shared)) +
        geom_tile() +
        geom_text(aes(label = n_shared), color = "white") +
        scale_fill_gradient(low = "lightblue", high = "darkblue") +
        labs(title = "Clone Sharing Between Tissues",
             x = "From", y = "To") +
        theme_bw()
    print(p)

    return(shared)
}

# ============================================================================
# Helper Functions
# ============================================================================

#' Create mock Seurat object for demonstration
create_mock_seurat <- function() {
    set.seed(42)

    # Create mock count matrix
    n_cells <- 500
    n_genes <- 100
    counts <- matrix(rpois(n_cells * n_genes, lambda = 5),
                     nrow = n_genes, ncol = n_cells)
    rownames(counts) <- paste0("Gene", 1:n_genes)
    colnames(counts) <- paste0("Cell", 1:n_cells)

    # Create Seurat object
    seurat_obj <- CreateSeuratObject(counts = counts)

    # Add metadata
    seurat_obj$tcr_clone_id <- sample(paste0("Clone_", 1:100), n_cells, replace = TRUE)
    seurat_obj$patient <- sample(c("P01", "P02", "P03"), n_cells, replace = TRUE)
    seurat_obj$cell_type <- sample(c("CD4_Treg", "CD4_Th17", "CD8_Tex", "CD8_Tem"),
                                    n_cells, replace = TRUE)
    seurat_obj$tissue <- sample(c("T", "N", "PB"), n_cells, replace = TRUE)

    return(seurat_obj)
}

#' Create mock input data for demonstration
create_mock_input_data <- function() {
    set.seed(42)
    n_cells <- 1000

    input_data <- data.frame(
        Cell_Name = paste0("Cell_", 1:n_cells),
        clone.id = sample(paste0("Clone_", 1:200), n_cells, replace = TRUE),
        patient = sample(c("P01", "P02", "P03"), n_cells, replace = TRUE),
        majorCluster = sample(c("CD4_Treg", "CD4_Th17", "CD8_Tex", "CD8_Tem"),
                               n_cells, replace = TRUE),
        loc = sample(c("T", "N", "PB"), n_cells, replace = TRUE),
        stringsAsFactors = FALSE
    )

    return(input_data)
}

# ============================================================================
# Main execution
# ============================================================================

if (interactive()) {
    message("STARTRAC Example Analysis")
    message("=========================")
    message("Available functions:")
    message("  - run_basic_analysis()")
    message("  - run_seurat_analysis(seurat_obj)")
    message("  - run_per_patient_analysis(input_data)")
    message("  - run_clone_sharing_analysis(input_data)")
    message("")
    message("Run an example with: result <- run_basic_analysis()")
}
