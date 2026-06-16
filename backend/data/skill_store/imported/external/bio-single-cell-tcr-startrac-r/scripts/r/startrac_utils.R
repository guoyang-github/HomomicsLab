#' STARTRAC Utility Functions
#'
#' This file contains utility functions for STARTRAC analysis,
#' including data filtering, export, and helper functions.
#'
#' @author Based on STARTRAC package
#' @references https://github.com/Japrin/STARTRAC

#' Filter Clonotypes by Size
#'
#' Filter input data to include only clonotypes within specified size range.
#'
#' @param input_data A data.frame with STARTRAC input format
#' @param min_size Minimum number of cells per clone (default: 2)
#' @param max_size Maximum number of cells per clone (default: NULL = no limit)
#'
#' @return Filtered data.frame
#'
#' @examples
#' \dontrun{
#' filtered <- filter_clones(input_data, min_size = 3)
#' }
filter_clones <- function(input_data, min_size = 2, max_size = NULL) {
    required_cols <- c("Cell_Name", "clone.id", "patient", "majorCluster", "loc")
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        stop(sprintf("Missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    # Count cells per clone
    clone_counts <- table(input_data$clone.id)

    # Apply filters
    valid_clones <- names(clone_counts[clone_counts >= min_size])
    if (!is.null(max_size)) {
        valid_clones <- intersect(valid_clones,
                                  names(clone_counts[clone_counts <= max_size]))
    }

    filtered <- input_data[input_data$clone.id %in% valid_clones, ]

    message(sprintf("Filtered from %d to %d cells (%d clones -> %d clones)",
                    nrow(input_data), nrow(filtered),
                    length(unique(input_data$clone.id)),
                    length(valid_clones)))

    return(filtered)
}


#' Summarize Clonotypes
#'
#' Generate summary statistics of clonotype distribution.
#'
#' @param input_data A data.frame with STARTRAC input format
#' @return A list containing summary statistics
#'
#' @examples
#' \dontrun{
#' summary <- summarize_clonotypes(input_data)
#' print(summary$top_clones)
#' }
summarize_clonotypes <- function(input_data) {
    required_cols <- c("Cell_Name", "clone.id", "patient", "majorCluster", "loc")
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        stop(sprintf("Missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    # Overall clonotype statistics
    clone_counts <- table(input_data$clone.id)

    overall_stats <- list(
        total_cells = nrow(input_data),
        total_clones = length(unique(input_data$clone.id)),
        total_patients = length(unique(input_data$patient)),
        total_clusters = length(unique(input_data$majorCluster)),
        total_locations = length(unique(input_data$loc)),
        singleton_clones = sum(clone_counts == 1),
        expanded_clones = sum(clone_counts >= 10),
        max_clone_size = max(clone_counts),
        mean_clone_size = mean(clone_counts),
        median_clone_size = median(clone_counts)
    )

    # Top clones
    top_clones <- as.data.frame(clone_counts) %>%
        dplyr::arrange(desc(Freq)) %>%
        head(20)
    colnames(top_clones) <- c("clone.id", "n_cells")

    # Clonality by cluster
    clonality_by_cluster <- input_data %>%
        dplyr::group_by(majorCluster) %>%
        dplyr::summarise(
            n_cells = dplyr::n(),
            n_clones = dplyr::n_distinct(clone.id),
            singletons = sum(table(clone.id) == 1),
            clonality = 1 - sum((table(clone.id) / dplyr::n())^2),
            .groups = "drop"
        )

    # Clonality by patient
    clonality_by_patient <- input_data %>%
        dplyr::group_by(patient) %>%
        dplyr::summarise(
            n_cells = dplyr::n(),
            n_clones = dplyr::n_distinct(clone.id),
            singletons = sum(table(clone.id) == 1),
            clonality = 1 - sum((table(clone.id) / dplyr::n())^2),
            .groups = "drop"
        )

    # Clonality by location
    clonality_by_loc <- input_data %>%
        dplyr::group_by(loc) %>%
        dplyr::summarise(
            n_cells = dplyr::n(),
            n_clones = dplyr::n_distinct(clone.id),
            singletons = sum(table(clone.id) == 1),
            clonality = 1 - sum((table(clone.id) / dplyr::n())^2),
            .groups = "drop"
        )

    list(
        overall = overall_stats,
        top_clones = top_clones,
        clonality_by_cluster = clonality_by_cluster,
        clonality_by_patient = clonality_by_patient,
        clonality_by_location = clonality_by_loc
    )
}


#' Export STARTRAC Results
#'
#' Export STARTRAC results to various formats.
#'
#' @param result A StartracOut object
#' @param output_prefix Prefix for output files
#' @param formats Vector of formats: "csv", "rds", "excel" (default: c("csv", "rds"))
#' @param include_sig Logical; include significance results (default: TRUE)
#'
#' @return Invisible NULL
#'
#' @examples
#' \dontrun{
#' export_startrac_results(result, "analysis/startrac", formats = c("csv", "rds"))
#' }
export_startrac_results <- function(result,
                                    output_prefix = "startrac",
                                    formats = c("csv", "rds"),
                                    include_sig = TRUE) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    # Create output directory if needed
    out_dir <- dirname(output_prefix)
    if (out_dir != "." && !dir.exists(out_dir)) {
        dir.create(out_dir, recursive = TRUE)
    }

    # Export cluster data
    if ("csv" %in% formats) {
        write.csv(result@cluster.data,
                  paste0(output_prefix, "_cluster_data.csv"),
                  row.names = FALSE)
        write.csv(result@pIndex.migr,
                  paste0(output_prefix, "_migration_index.csv"),
                  row.names = FALSE)
        write.csv(result@pIndex.tran,
                  paste0(output_prefix, "_transition_index.csv"),
                  row.names = FALSE)

        if (include_sig && nrow(result@cluster.sig.data) > 0) {
            write.csv(result@cluster.sig.data,
                      paste0(output_prefix, "_cluster_significance.csv"),
                      row.names = FALSE)
            write.csv(result@pIndex.sig.migr,
                      paste0(output_prefix, "_migration_significance.csv"),
                      row.names = FALSE)
            write.csv(result@pIndex.sig.tran,
                      paste0(output_prefix, "_transition_significance.csv"),
                      row.names = FALSE)
        }
        message("CSV files exported")
    }

    # Export RDS
    if ("rds" %in% formats) {
        saveRDS(result, paste0(output_prefix, "_results.rds"))
        message("RDS file exported")
    }

    # Export Excel
    if ("excel" %in% formats) {
        if (!requireNamespace("openxlsx", quietly = TRUE)) {
            warning("openxlsx package not available, skipping Excel export")
        } else {
            wb <- openxlsx::createWorkbook()

            openxlsx::addWorksheet(wb, "Cluster_Data")
            openxlsx::writeData(wb, "Cluster_Data", result@cluster.data)

            openxlsx::addWorksheet(wb, "Migration_Index")
            openxlsx::writeData(wb, "Migration_Index", result@pIndex.migr)

            openxlsx::addWorksheet(wb, "Transition_Index")
            openxlsx::writeData(wb, "Transition_Index", result@pIndex.tran)

            if (include_sig && nrow(result@cluster.sig.data) > 0) {
                openxlsx::addWorksheet(wb, "Significance")
                openxlsx::writeData(wb, "Significance", result@cluster.sig.data)
            }

            openxlsx::saveWorkbook(wb,
                                   paste0(output_prefix, "_results.xlsx"),
                                   overwrite = TRUE)
            message("Excel file exported")
        }
    }

    invisible(NULL)
}


#' Find Shared Clones
#'
#' Identify clonotypes shared between tissues or patients.
#'
#' @param input_data A data.frame with STARTRAC input format
#' @param group_by Column to group by: "loc" or "patient" (default: "loc")
#' @return A list containing shared clone information
#'
#' @examples
#' \dontrun{
#' shared <- find_shared_clones(input_data, group_by = "loc")
#' print(shared$overlap_matrix)
#' }
find_shared_clones <- function(input_data, group_by = "loc") {
    required_cols <- c("clone.id", "patient", "majorCluster", "loc")
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        stop(sprintf("Missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    if (!group_by %in% c("loc", "patient")) {
        stop("group_by must be 'loc' or 'patient'")
    }

    # Get clones per group
    clones_per_group <- split(input_data$clone.id, input_data[[group_by]])
    unique_clones <- lapply(clones_per_group, unique)

    # Create overlap matrix
    groups <- names(unique_clones)
    overlap_matrix <- matrix(0, nrow = length(groups), ncol = length(groups),
                             dimnames = list(groups, groups))

    for (i in seq_along(groups)) {
        for (j in seq_along(groups)) {
            overlap_matrix[i, j] <- length(intersect(unique_clones[[i]],
                                                     unique_clones[[j]]))
        }
    }

    # Jaccard similarity
    jaccard_matrix <- matrix(0, nrow = length(groups), ncol = length(groups),
                             dimnames = list(groups, groups))

    for (i in seq_along(groups)) {
        for (j in seq_along(groups)) {
            intersection <- length(intersect(unique_clones[[i]],
                                             unique_clones[[j]]))
            union <- length(union(unique_clones[[i]], unique_clones[[j]]))
            jaccard_matrix[i, j] <- ifelse(union > 0, intersection / union, 0)
        }
    }

    # Clones shared across all groups
    shared_all <- Reduce(intersect, unique_clones)

    list(
        groups = groups,
        clones_per_group = sapply(unique_clones, length),
        overlap_matrix = overlap_matrix,
        jaccard_matrix = jaccard_matrix,
        shared_all = shared_all,
        n_shared_all = length(shared_all)
    )
}


#' Calculate Clone Sharing Statistics
#'
#' Calculate statistics for clone sharing between conditions.
#'
#' @param input_data A data.frame with STARTRAC input format
#' @param condition_col Column defining conditions (default: "loc")
#' @return A data.frame with sharing statistics
#'
#' @examples
#' \dontrun{
#' sharing <- calculate_clone_sharing(input_data, condition_col = "patient")
#' }
calculate_clone_sharing <- function(input_data, condition_col = "loc") {
    required_cols <- c("clone.id", "patient", "majorCluster", "loc")
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        stop(sprintf("Missing required columns: %s",
                     paste(missing_cols, collapse = ", ")))
    }

    # Calculate sharing by clone
    clone_sharing <- input_data %>%
        dplyr::group_by(clone.id) %>%
        dplyr::summarise(
            n_cells = dplyr::n(),
            n_conditions = dplyr::n_distinct(.data[[condition_col]]),
            conditions = paste(sort(unique(.data[[condition_col]])), collapse = ","),
            patients = paste(sort(unique(patient)), collapse = ","),
            clusters = paste(sort(unique(majorCluster)), collapse = ","),
            .groups = "drop"
        ) %>%
        dplyr::arrange(dplyr::desc(n_cells))

    # Summary statistics
    summary_stats <- clone_sharing %>%
        dplyr::group_by(n_conditions) %>%
        dplyr::summarise(
            n_clones = dplyr::n(),
            mean_cells = mean(n_cells),
            total_cells = sum(n_cells),
            .groups = "drop"
        )

    list(
        clone_details = clone_sharing,
        summary = summary_stats
    )
}


#' Validate STARTRAC Input
#'
#' Validate input data format for STARTRAC analysis.
#'
#' @param input_data A data.frame to validate
#' @param verbose Logical; print detailed validation messages (default: TRUE)
#' @return Logical; TRUE if valid, FALSE otherwise
#'
#' @examples
#' \dontrun{
#' is_valid <- validate_startrac_input(input_data)
#' }
validate_startrac_input <- function(input_data, verbose = TRUE) {
    required_cols <- c("Cell_Name", "clone.id", "patient", "majorCluster", "loc")

    # Check data frame
    if (!is.data.frame(input_data)) {
        if (verbose) message("ERROR: Input must be a data.frame")
        return(FALSE)
    }

    # Check required columns
    missing_cols <- setdiff(required_cols, colnames(input_data))
    if (length(missing_cols) > 0) {
        if (verbose) message(sprintf("ERROR: Missing columns: %s",
                                     paste(missing_cols, collapse = ", ")))
        return(FALSE)
    }

    # Check for empty data
    if (nrow(input_data) == 0) {
        if (verbose) message("ERROR: Input data is empty")
        return(FALSE)
    }

    # Check for NAs in key columns
    na_counts <- sapply(input_data[required_cols], function(x) sum(is.na(x)))
    if (any(na_counts > 0)) {
        if (verbose) {
            message("WARNING: NA values found:")
            print(na_counts[na_counts > 0])
        }
    }

    # Check unique cell names
    if (length(unique(input_data$Cell_Name)) != nrow(input_data)) {
        if (verbose) message("WARNING: Duplicate Cell_Name values found")
    }

    # Check data types
    if (!all(sapply(input_data[required_cols], is.character))) {
        if (verbose) message("WARNING: Non-character columns detected, will convert")
    }

    # Summary statistics
    if (verbose) {
        message("Validation Summary:")
        message(sprintf("  Total cells: %d", nrow(input_data)))
        message(sprintf("  Unique clones: %d", length(unique(input_data$clone.id))))
        message(sprintf("  Patients: %d", length(unique(input_data$patient))))
        message(sprintf("  Clusters: %d", length(unique(input_data$majorCluster))))
        message(sprintf("  Locations: %d (%s)",
                        length(unique(input_data$loc)),
                        paste(unique(input_data$loc), collapse = ", ")))
    }

    return(TRUE)
}


#' Merge STARTRAC Results
#'
#' Merge results from multiple STARTRAC runs.
#'
#' @param results_list A list of StartracOut objects
#' @param proj_name Name for the merged project (default: "Merged")
#' @return A StartracOut object with combined results
#'
#' @examples
#' \dontrun{
#' patient_results <- lapply(patients, function(p) {
#'     run_startrac(subset(input_data, patient == p), proj = p)
#' })
#' merged <- merge_startrac_results(patient_results, "All_Patients")
#' }
merge_startrac_results <- function(results_list, proj_name = "Merged") {
    if (!is.list(results_list) || length(results_list) == 0) {
        stop("Input must be a non-empty list")
    }

    # Validate all objects
    valid <- sapply(results_list, function(x) inherits(x, "StartracOut"))
    if (!all(valid)) {
        stop("All elements must be StartracOut objects")
    }

    # Create new object
    require(methods)
    merged <- new("StartracOut", proj = proj_name)

    # Combine data frames
    merged@cluster.data <- do.call(rbind, lapply(results_list, function(x) x@cluster.data))
    merged@cluster.sig.data <- do.call(rbind, lapply(results_list, function(x) x@cluster.sig.data))
    merged@pIndex.migr <- do.call(rbind, lapply(results_list, function(x) x@pIndex.migr))
    merged@pIndex.tran <- do.call(rbind, lapply(results_list, function(x) x@pIndex.tran))
    merged@pIndex.sig.migr <- do.call(rbind, lapply(results_list, function(x) x@pIndex.sig.migr))
    merged@pIndex.sig.tran <- do.call(rbind, lapply(results_list, function(x) x@pIndex.sig.tran))

    message(sprintf("Merged %d STARTRAC results into project '%s'",
                    length(results_list), proj_name))

    return(merged)
}
