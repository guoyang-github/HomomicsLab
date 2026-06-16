##' mistyR Advanced View Functions
#'
#' Advanced view creation and manipulation for mistyR.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.1.0

# Conditionally load packages
if (requireNamespace("mistyR", quietly = TRUE)) {
  library(mistyR)
}
if (requireNamespace("dplyr", quietly = TRUE)) {
  library(dplyr)
}

#' Add Custom View
#'
#' Add a custom view to an existing view composition.
#'
#' @param view_composition Existing view composition
#' @param view_data Data frame with view data (same rows as intraview)
#' @param name Name of the view
#' @param abbrev Abbreviation prefix for the view
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' custom_data <- calculate_custom_neighborhood(expr, coords, radius = 50)
#' views <- add_custom_view(views, custom_data, name = "custom", abbrev = "custom.50")
#' }
add_custom_view <- function(view_composition, view_data, name, abbrev) {
  new_view <- list(abbrev = abbrev, data = view_data)
  view_composition[[name]] <- new_view

  message(sprintf("Added view '%s' with abbreviation '%s'", name, abbrev))
  return(view_composition)
}


#' Remove Views
#'
#' Remove specific views from a view composition.
#'
#' @param view_composition View composition
#' @param view_names Vector of view names to remove
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' views <- remove_views(views, view_names = c("paraview.50", "juxtaview"))
#' }
remove_views <- function(view_composition, view_names) {
  # Don't allow removing intraview or misty.uniqueid
  protected <- c("intraview", "misty.uniqueid")

  for (name in view_names) {
    if (name %in% protected) {
      warning(sprintf("Cannot remove protected view '%s'", name))
      next
    }

    if (name %in% names(view_composition)) {
      view_composition[[name]] <- NULL
      message(sprintf("Removed view '%s'", name))
    } else {
      warning(sprintf("View '%s' not found in composition", name))
    }
  }

  return(view_composition)
}


#' Update View Data
#'
#' Update data for an existing view.
#'
#' @param view_composition View composition
#' @param view_name Name of view to update
#' @param new_data New data frame
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' views <- update_view(views, "paraview", new_para_data)
#' }
update_view <- function(view_composition, view_name, new_data) {
  if (!view_name %in% names(view_composition)) {
    stop(sprintf("View '%s' not found in composition", view_name))
  }

  if (view_name == "misty.uniqueid") {
    stop("Cannot update misty.uniqueid")
  }

  # Verify dimensions match
  n_rows_intraview <- nrow(view_composition$intraview$data)
  n_rows_new <- nrow(new_data)

  if (n_rows_intraview != n_rows_new) {
    stop(sprintf("Row count mismatch: intraview has %d rows, new data has %d",
                 n_rows_intraview, n_rows_new))
  }

  view_composition[[view_name]]$data <- new_data
  message(sprintf("Updated view '%s'", view_name))

  return(view_composition)
}


#' Filter Views by Pattern
#'
#' Keep only views matching a name pattern.
#'
#' @param view_composition View composition
#' @param pattern Regex pattern to match
#' @param invert If TRUE, keep views NOT matching pattern
#'
#' @return Filtered view composition
#' @export
#'
#' @examples
#' \dontrun{
#' # Keep only paraviews
#' views <- filter_views(views, pattern = "^para\\.")
#'
#' # Remove all juxtaviews
#' views <- filter_views(views, pattern = "^juxta\\.", invert = TRUE)
#' }
filter_views <- function(view_composition, pattern, invert = FALSE) {
  view_names <- names(view_composition)
  matches <- grepl(pattern, view_names)

  if (invert) {
    keep_names <- view_names[!matches]
  } else {
    keep_names <- view_names[matches]
  }

  # Always keep protected views
  protected <- c("intraview", "misty.uniqueid")
  keep_names <- union(keep_names, intersect(view_names, protected))

  removed <- setdiff(view_names, keep_names)
  if (length(removed) > 0) {
    message(sprintf("Removed views: %s", paste(removed, collapse = ", ")))
  }

  return(view_composition[keep_names])
}


#' List Views
#'
#' List all views in a composition with their abbreviations.
#'
#' @param view_composition View composition
#'
#' @return Data frame with view information
#' @export
#'
#' @examples
#' \dontrun{
#' list_views(views)
#' }
list_views <- function(view_composition) {
  view_info <- data.frame(
    name = names(view_composition),
    abbrev = sapply(view_composition, function(v) {
      if (is.list(v) && "abbrev" %in% names(v)) v$abbrev else NA
    }),
    n_rows = sapply(view_composition, function(v) {
      if (is.list(v) && "data" %in% names(v)) nrow(v$data) else NA
    }),
    n_cols = sapply(view_composition, function(v) {
      if (is.list(v) && "data" %in% names(v)) ncol(v$data) else NA
    }),
    stringsAsFactors = FALSE
  )

  return(view_info)
}


#' Add Family View
#'
#' Create a view aggregating markers by predefined families/groups.
#'
#' @param view_composition View composition
#' @param marker_families Named list mapping family names to marker vectors
#' @param aggregation Aggregation function: "mean", "sum", "max"
#' @param prefix Prefix for view name
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' families <- list(
#'   immune_markers = c("CD3D", "CD4", "CD8A", "CD68"),
#'   stroma_markers = c("COL1A1", "COL1A2", "ACTA2"),
#'   proliferation = c("MKI67", "PCNA", "CCND1")
#' )
#' views <- add_family_view(views, families, aggregation = "mean")
#' }
add_family_view <- function(view_composition, marker_families,
                            aggregation = c("mean", "sum", "max"),
                            prefix = "family") {
  aggregation <- match.arg(aggregation)

  intra_data <- view_composition$intraview$data
  family_data <- data.frame(row.names = rownames(intra_data))

  for (family_name in names(marker_families)) {
    markers <- marker_families[[family_name]]
    available_markers <- intersect(markers, colnames(intra_data))

    if (length(available_markers) == 0) {
      warning(sprintf("No markers from family '%s' found in data", family_name))
      next
    }

    family_matrix <- intra_data[, available_markers, drop = FALSE]

    family_values <- switch(aggregation,
      "mean" = rowMeans(family_matrix, na.rm = TRUE),
      "sum" = rowSums(family_matrix, na.rm = TRUE),
      "max" = apply(family_matrix, 1, max, na.rm = TRUE)
    )

    family_data[[family_name]] <- family_values
  }

  view_name <- paste0(prefix, "view")
  abbrev <- paste0("fam")

  return(add_custom_view(view_composition, family_data, view_name, abbrev))
}


#' Add Variable Radius Paraview
#'
#' Create paraviews with different radii for comparison.
#'
#' @param view_composition View composition
#' @param coords Spatial coordinates
#' @param radii Vector of radii to use
#' @param prefix Prefix for view name
#'
#' @return Updated view composition with multiple paraviews
#' @export
#'
#' @examples
#' \dontrun{
#' views <- add_variable_radius_paraviews(views, coords, radii = c(50, 100, 150, 200))
#' }
add_variable_radius_paraviews <- function(view_composition, coords,
                                          radii = c(50, 100, 150),
                                          prefix = "para") {
  for (radius in radii) {
    view_name <- paste0(prefix, "view.", radius)
    abbrev <- paste0("para.", radius)

    view_composition <- view_composition %>%
      add_paraview(
        positions = coords,
        radius = radius,
        prefix = abbrev
      )

    message(sprintf("Added paraview with radius %d", radius))
  }

  return(view_composition)
}


#' Add Custom Mask View
#'
#' Create a view based on a custom spatial mask.
#'
#' @param view_composition View composition
#' @param coords Spatial coordinates
#' @param mask Logical or numeric mask (1 = include, 0 = exclude)
#' @param mask_name Name for this mask view
#' @param aggregation Aggregation within mask: "mean", "sum"
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' # Create mask for tumor region
#' tumor_mask <- coords[, 1] > 500 & coords[, 1] < 1500
#' views <- add_mask_view(views, coords, tumor_mask, "tumor_region")
#' }
add_mask_view <- function(view_composition, coords, mask, mask_name,
                          aggregation = c("mean", "sum")) {
  aggregation <- match.arg(aggregation)

  if (length(mask) != nrow(coords)) {
    stop("Mask length must match number of spots")
  }

  intra_data <- view_composition$intraview$data

  # Calculate distances to find neighbors within mask
  dist_matrix <- as.matrix(dist(coords))

  mask_data <- data.frame(row.names = rownames(intra_data))

  for (marker in colnames(intra_data)) {
    masked_values <- sapply(1:nrow(coords), function(i) {
      # Find neighbors within mask
      neighbors <- which(mask & dist_matrix[i, ] > 0)

      if (length(neighbors) == 0) return(NA)

      neighbor_values <- intra_data[neighbors, marker]

      switch(aggregation,
        "mean" = mean(neighbor_values, na.rm = TRUE),
        "sum" = sum(neighbor_values, na.rm = TRUE)
      )
    })

    mask_data[[marker]] <- masked_values
  }

  view_name <- paste0("maskview.", mask_name)
  abbrev <- paste0("mask.", mask_name)

  return(add_custom_view(view_composition, mask_data, view_name, abbrev))
}


#' Add Distance-Weighted View
#'
#' Create a view with distance-weighted neighborhood aggregation.
#'
#' @param view_composition View composition
#' @param coords Spatial coordinates
#' @param radius Maximum radius
#' @param weight_function Weight function: "gaussian", "exponential", "inverse"
#' @param sigma Bandwidth parameter for weighting
#'
#' @return Updated view composition
#' @export
#'
#' @examples
#' \dontrun{
#' views <- add_distance_weighted_view(views, coords, radius = 100,
#'                                     weight_function = "gaussian", sigma = 50)
#' }
add_distance_weighted_view <- function(view_composition, coords,
                                       radius = 100,
                                       weight_function = c("gaussian", "exponential", "inverse"),
                                       sigma = 50) {
  weight_function <- match.arg(weight_function)

  intra_data <- view_composition$intraview$data
  dist_matrix <- as.matrix(dist(coords))

  # Calculate weights
  weights <- switch(weight_function,
    "gaussian" = exp(-dist_matrix^2 / (2 * sigma^2)),
    "exponential" = exp(-dist_matrix / sigma),
    "inverse" = 1 / (dist_matrix + 1)
  )

  # Zero out beyond radius
  weights[dist_matrix > radius] <- 0
  diag(weights) <- 0  # Exclude self

  # Normalize weights
  weights <- weights / rowSums(weights)

  # Calculate weighted means
  weighted_data <- as.matrix(intra_data)
  result_data <- weights %*% weighted_data

  result_df <- as.data.frame(result_data)
  colnames(result_df) <- colnames(intra_data)
  rownames(result_df) <- rownames(intra_data)

  view_name <- paste0("weightedview.", weight_function)
  abbrev <- paste0("w.", substr(weight_function, 1, 3))

  return(add_custom_view(view_composition, result_df, view_name, abbrev))
}


#' Clone View Composition
#'
#' Create a deep copy of a view composition.
#'
#' @param view_composition View composition
#'
#' @return Cloned view composition
#' @export
clone_view_composition <- function(view_composition) {
  # Deep copy
  cloned <- lapply(view_composition, function(v) {
    if (is.list(v)) {
      lapply(v, function(x) {
        if (is.data.frame(x) || is.matrix(x)) {
          x[, , drop = FALSE]
        } else {
          x
        }
      })
    } else {
      v
    }
  })

  return(cloned)
}


#' Validate View Composition
#'
#' Check that view composition is valid for running mistyR.
#'
#' @param view_composition View composition
#'
#' @return Logical indicating validity
#' @export
#'
#' @examples
#' \dontrun{
#' is_valid <- validate_view_composition(views)
#' }
validate_view_composition <- function(view_composition) {
  errors <- c()

  # Check required elements
  if (!"intraview" %in% names(view_composition)) {
    errors <- c(errors, "Missing required 'intraview'")
  }

  if (!"misty.uniqueid" %in% names(view_composition)) {
    errors <- c(errors, "Missing required 'misty.uniqueid'")
  }

  if (length(errors) > 0) {
    warning(paste(errors, collapse = "\n"))
    return(FALSE)
  }

  # Check row counts match
  n_rows <- nrow(view_composition$intraview$data)

  for (view_name in names(view_composition)) {
    if (view_name == "misty.uniqueid") next

    view_data <- view_composition[[view_name]]$data
    if (!is.null(view_data) && nrow(view_data) != n_rows) {
      errors <- c(errors,
        sprintf("View '%s' has %d rows, expected %d",
                view_name, nrow(view_data), n_rows))
    }
  }

  if (length(errors) > 0) {
    warning(paste(errors, collapse = "\n"))
    return(FALSE)
  }

  message("View composition is valid")
  return(TRUE)
}
