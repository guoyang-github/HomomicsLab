#' STARTRAC Analysis Wrapper Functions
#'
#' This file contains wrapper functions for the STARTRAC (Single T-cell Analysis
#' by Rna-seq and Tcr TRACking) pipeline. These functions simplify the process
#' of preparing data and running STARTRAC analysis.
#'
#' @author Based on STARTRAC package by Xianwen Ren and Liangtao Zheng
#' @references https://github.com/Japrin/STARTRAC

#' Prepare STARTRAC Input from Seurat Object
#'
#' Converts a Seurat object to the input format required by STARTRAC.
#'
#' @param seurat_obj A Seurat object with metadata containing clone, patient,
#'   cluster, and location information
#' @param clone_col Name of the column containing clonotype IDs (default: "clone_id")
#' @param patient_col Name of the column containing patient IDs (default: "patient")
#' @param cluster_col Name of the column containing cell cluster annotations
#'   (default: "cell_type")
#' @param loc_col Name of the column containing tissue location information
#'   (default: "tissue")
#' @param filter_single Logical; whether to remove cells with singleton clones
#'   (default: TRUE)
#' @param min_cells_per_patient Minimum number of cells required per patient
#'   (default: 30)
#'
#' @return A data.frame with columns: Cell_Name, clone.id, patient, majorCluster, loc
#'
#' @examples
#' \dontrun{
#' input_data <- prepare_startrac_input(
#'     seurat_obj,
#'     clone_col = "tcr_clone_id",
#'     patient_col = "patient_id",
#'     cluster_col = "cell_type",
#'     loc_col = "tissue"
#' )
#' }
prepare_startrac_input <- function(seurat_obj,
                                    clone_col = "clone_id",
                                    patient_col = "patient",
                                    cluster_col = "cell_type",
                                    loc_col = "tissue",
                                    filter_single = TRUE,
                                    min_cells_per_patient = 30) {
    # Check if Seurat object
    if (!inherits(seurat_obj, "Seurat")) {
        stop("Input must be a Seurat object")
    }

    # Get metadata
    meta <- seurat_obj@meta.data

    # Check required columns exist
    required_cols <- c(clone_col, patient_col, cluster_col, loc_col)
    missing_cols <- setdiff(required_cols, colnames(meta))
    if (length(missing_cols) > 0) {
        stop(sprintf("Missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    # Create input data frame
    input_data <- data.frame(
        Cell_Name = rownames(meta),
        clone.id = as.character(meta[[clone_col]]),
        patient = as.character(meta[[patient_col]]),
        majorCluster = as.character(meta[[cluster_col]]),
        loc = as.character(meta[[loc_col]]),
        stringsAsFactors = FALSE
    )

    # Remove cells without TCR information
    na_count <- sum(is.na(input_data$clone.id) | input_data$clone.id == "")
    if (na_count > 0) {
        message(sprintf("Removing %d cells without TCR information", na_count))
        input_data <- input_data[!is.na(input_data$clone.id) &
                                   input_data$clone.id != "", ]
    }

    # Filter singleton clones if requested
    if (filter_single) {
        clone_counts <- table(input_data$clone.id)
        recurrent_clones <- names(clone_counts[clone_counts > 1])
        removed <- nrow(input_data) - sum(input_data$clone.id %in% recurrent_clones)
        if (removed > 0) {
            message(sprintf("Removing %d cells with singleton clones", removed))
            input_data <- input_data[input_data$clone.id %in% recurrent_clones, ]
        }
    }

    # Filter patients with too few cells
    patient_counts <- table(input_data$patient)
    valid_patients <- names(patient_counts[patient_counts >= min_cells_per_patient])
    removed_patients <- setdiff(unique(input_data$patient), valid_patients)
    if (length(removed_patients) > 0) {
        message(sprintf("Removing patients with < %d cells: %s",
                        min_cells_per_patient,
                        paste(removed_patients, collapse = ", ")))
        input_data <- input_data[input_data$patient %in% valid_patients, ]
    }

    # Check we still have data
    if (nrow(input_data) == 0) {
        stop("No valid cells remaining after filtering")
    }

    message(sprintf("Prepared %d cells from %d patients with %d unique clonotypes",
                    nrow(input_data),
                    length(unique(input_data$patient)),
                    length(unique(input_data$clone.id))))

    return(input_data)
}


#' Run STARTRAC Analysis
#'
#' Wrapper function to run the complete STARTRAC pipeline including cluster-level
#' index calculation, pairwise index calculation, and significance testing.
#'
#' @param input_data A data.frame with columns: Cell_Name, clone.id, patient,
#'   majorCluster, loc
#' @param proj Project identifier (default: "STARTRAC")
#' @param cores Number of cores for parallel processing (default: NULL = auto)
#' @param n.perm Number of permutations for significance testing (default: NULL)
#' @param verbose Verbosity level: 0 (minimal), 1 (include main object), 2 (include all)
#'   (default: 0)
#'
#' @return A StartracOut object containing all results
#'
#' @examples
#' \dontrun{
#' # Basic analysis
#' result <- run_startrac(input_data, proj = "MyProject")
#'
#' # With significance testing
#' result <- run_startrac(input_data, proj = "MyProject", n.perm = 100, cores = 4)
#' }
run_startrac <- function(input_data,
                          proj = "STARTRAC",
                          cores = NULL,
                          n.perm = NULL,
                          verbose = 0) {
    # Check required columns
    required_cols <- c("Cell_Name", "clone.id", "patient", "majorCluster", "loc")
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        stop(sprintf("Input data missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    # Ensure data types are correct
    input_data$clone.id <- as.character(input_data$clone.id)
    input_data$patient <- as.character(input_data$patient)
    input_data$majorCluster <- as.character(input_data$majorCluster)
    input_data$loc <- as.character(input_data$loc)

    # Load Startrac package
    if (!requireNamespace("Startrac", quietly = TRUE)) {
        stop("Startrac package not installed. Please install with:\n",
             "devtools::install_github('Japrin/STARTRAC')")
    }

    message(sprintf("Running STARTRAC analysis: %s", proj))
    message(sprintf("Input: %d cells, %d clonotypes, %d patients, %d clusters, %d locations",
                    nrow(input_data),
                    length(unique(input_data$clone.id)),
                    length(unique(input_data$patient)),
                    length(unique(input_data$majorCluster)),
                    length(unique(input_data$loc))))

    # Run the analysis
    result <- Startrac::Startrac.run(
        cell.data = input_data,
        proj = proj,
        cores = cores,
        n.perm = n.perm,
        verbose = verbose
    )

    message("STARTRAC analysis complete")
    return(result)
}


#' Run STARTRAC by Patient
#'
#' Run STARTRAC analysis separately for each patient and combine results.
#'
#' @param input_data A data.frame with STARTRAC input format
#' @param proj Project identifier prefix
#' @param cores Number of cores per patient analysis
#' @param n.perm Number of permutations for significance testing
#' @param min_cells Minimum cells required per patient (default: 30)
#'
#' @return A list of StartracOut objects, one per patient
#'
#' @examples
#' \dontrun{
#' patient_results <- run_startrac_by_patient(input_data, proj = "CRC")
#' }
run_startrac_by_patient <- function(input_data,
                                     proj = "STARTRAC",
                                     cores = NULL,
                                     n.perm = NULL,
                                     min_cells = 30) {
    patients <- unique(input_data$patient)
    message(sprintf("Running STARTRAC for %d patients", length(patients)))

    results <- list()

    for (pid in patients) {
        patient_data <- subset(input_data, patient == pid)

        if (nrow(patient_data) < min_cells) {
            message(sprintf("Skipping patient %s: only %d cells", pid, nrow(patient_data)))
            next
        }

        message(sprintf("Processing patient %s: %d cells", pid, nrow(patient_data)))

        tryCatch({
            result <- run_startrac(
                patient_data,
                proj = pid,
                cores = cores,
                n.perm = n.perm,
                verbose = 0
            )
            results[[pid]] <- result
        }, error = function(e) {
            message(sprintf("Error processing patient %s: %s", pid, e$message))
        })
    }

    message(sprintf("Successfully processed %d/%d patients", length(results), length(patients)))
    return(results)
}


#' Extract STARTRAC Results as Data Frames
#'
#' Extract all results from a StartracOut object as a list of data frames.
#'
#' @param result A StartracOut object
#' @param include_sig Logical; include significance results (default: TRUE)
#'
#' @return A list containing data frames of results
#'
#' @examples
#' \dontrun{
#' dfs <- extract_startrac_results(result)
#' head(dfs$cluster_data)
#' }
extract_startrac_results <- function(result, include_sig = TRUE) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    results_list <- list(
        cluster_data = result@cluster.data,
        migration_index = result@pIndex.migr,
        transition_index = result@pIndex.tran
    )

    if (include_sig && nrow(result@cluster.sig.data) > 0) {
        results_list$cluster_significance <- result@cluster.sig.data
        results_list$migration_significance <- result@pIndex.sig.migr
        results_list$transition_significance <- result@pIndex.sig.tran
    }

    return(results_list)
}


#' Summarize STARTRAC Results
#'
#' Create a summary of STARTRAC analysis results.
#'
#' @param result A StartracOut object
#' @return A list containing summary statistics
#'
#' @examples
#' \dontrun{
#' summary <- summarize_startrac_results(result)
#' print(summary)
#' }
summarize_startrac_results <- function(result) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    if (!requireNamespace("dplyr", quietly = TRUE)) {
        stop("dplyr is required for summarize_startrac_results(). Install with: install.packages('dplyr')")
    }

    # Cluster-level summary
    cluster_summary <- result@cluster.data %>%
        dplyr::group_by(aid) %>%
        dplyr::summarise(
            n_clusters = dplyr::n(),
            total_cells = sum(NCells),
            mean_expa = mean(expa, na.rm = TRUE),
            mean_migr = mean(migr, na.rm = TRUE),
            mean_tran = mean(tran, na.rm = TRUE),
            .groups = "drop"
        )

    # Top expanded clusters
    top_expanded <- result@cluster.data %>%
        dplyr::arrange(dplyr::desc(expa)) %>%
        head(5)

    # Migration summary
    if (nrow(result@pIndex.migr) > 0) {
        migr_summary <- result@pIndex.migr %>%
            dplyr::select(-aid, -NCells, -majorCluster) %>%
            colMeans(na.rm = TRUE)
    } else {
        migr_summary <- NULL
    }

    list(
        project = result@proj,
        cluster_summary = cluster_summary,
        top_expanded = top_expanded,
        migration_summary = migr_summary,
        n_clusters = nrow(result@cluster.data),
        has_significance = nrow(result@cluster.sig.data) > 0 &&
            any(!is.na(result@cluster.sig.data$p.value))
    )
}


#' Compare STARTRAC Results Across Patients
#'
#' Compare cluster-level indices across multiple patients.
#'
#' @param results_list A list of StartracOut objects
#' @return A data.frame with combined cluster data
#'
#' @examples
#' \dontrun{
#' patient_results <- run_startrac_by_patient(input_data)
#' comparison <- compare_startrac_patients(patient_results)
#' }
compare_startrac_patients <- function(results_list) {
    if (!is.list(results_list) || length(results_list) == 0) {
        stop("Input must be a non-empty list of StartracOut objects")
    }

    combined_data <- do.call(rbind, lapply(names(results_list), function(name) {
        result <- results_list[[name]]
        if (!inherits(result, "StartracOut")) {
            warning(sprintf("Skipping %s: not a StartracOut object", name))
            return(NULL)
        }
        result@cluster.data
    }))

    return(combined_data)
}
