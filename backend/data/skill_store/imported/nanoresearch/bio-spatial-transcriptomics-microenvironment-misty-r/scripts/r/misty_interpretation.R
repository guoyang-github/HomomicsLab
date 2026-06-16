#' mistyR Model Interpretation Functions
#'
#' Model interpretation, significance testing, and stability analysis for mistyR results.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.1.0

library(dplyr)
library(tidyr)

#' Calculate View Contribution Significance
#'
#' Test significance of view contributions using permutation testing.
#'
#' @param misty_results mistyR results from collect_results()
#' @param n_permutations Number of permutations (default: 100)
#' @param seed Random seed
#'
#' @return Data frame with significance results
#' @export
#'
#' @examples
#' \dontrun{
#' sig_results <- calculate_view_significance(results, n_permutations = 100)
#' }
calculate_view_significance <- function(misty_results,
                                        n_permutations = 100,
                                        seed = 42) {
  set.seed(seed)

  contributions <- misty_results$contributions.stats

  # Group by target and view
  targets <- unique(contributions$target)
  views <- unique(contributions$view)

  significance_results <- data.frame()

  for (target in targets) {
    target_data <- contributions %>% filter(target == !!target)

    for (view in views) {
      view_data <- target_data %>% filter(view == !!view)

      if (nrow(view_data) == 0) next

      observed_fraction <- view_data$fraction[1]

      # Permutation test
      permuted_fractions <- replicate(n_permutations, {
        # Shuffle fractions within this target
        shuffled <- target_data %>%
          mutate(fraction = sample(fraction)) %>%
          filter(view == !!view)

        if (nrow(shuffled) > 0) shuffled$fraction[1] else 0
      })

      # Calculate p-value
      p_value <- mean(permuted_fractions >= observed_fraction)

      significance_results <- rbind(significance_results, data.frame(
        target = target,
        view = view,
        observed_fraction = observed_fraction,
        expected_fraction = mean(permuted_fractions),
        p_value = p_value,
        significant = p_value < 0.05,
        stringsAsFactors = FALSE
      ))
    }
  }

  # Adjust p-values
  significance_results$p_adjusted <- p.adjust(significance_results$p_value,
                                              method = "BH")
  significance_results$significant_adj <- significance_results$p_adjusted < 0.05

  return(significance_results)
}


#' Analyze Marker Importance Stability
#'
#' Assess stability of marker importance across CV folds.
#'
#' @param misty_results mistyR results
#' @param importance_threshold Minimum importance for consideration
#'
#' @return Data frame with stability metrics
#' @export
#'
#' @examples
#' \dontrun{
#' stability <- analyze_importance_stability(results, importance_threshold = 0.01)
#' }
analyze_importance_stability <- function(misty_results,
                                         importance_threshold = 0.01) {
  # Check if raw importances available
  if (!"importances.raw" %in% names(misty_results)) {
    warning("Raw importances not available in results. Run mistyR with keep.raw = TRUE")
    return(NULL)
  }

  raw_importances <- misty_results$importances.raw

  # Calculate stability metrics for each predictor-target pair
  stability_metrics <- raw_importances %>%
    filter(Importance > importance_threshold) %>%
    group_by(Target, Predictor, view) %>%
    summarise(
      mean_importance = mean(Importance, na.rm = TRUE),
      sd_importance = sd(Importance, na.rm = TRUE),
      cv_importance = sd_importance / mean_importance,
      min_importance = min(Importance, na.rm = TRUE),
      max_importance = max(Importance, na.rm = TRUE),
      n_folds = n(),
      fold_consistency = sum(Importance > importance_threshold) / n(),
      .groups = "drop"
    ) %>%
    mutate(
      stability_score = 1 / (1 + cv_importance),
      reliable = fold_consistency >= 0.8 & stability_score >= 0.5
    ) %>%
    arrange(desc(stability_score))

  return(stability_metrics)
}


#' Calculate Interaction Redundancy
#'
#' Measure redundancy between different views for each target.
#'
#' @param misty_results mistyR results
#' @param method Redundancy method: "correlation", "overlap"
#'
#' @return List with redundancy matrices
#' @export
#'
#' @examples
#' \dontrun{
#' redundancy <- calculate_interaction_redundancy(results)
#' }
calculate_interaction_redundancy <- function(misty_results,
                                             method = c("correlation", "overlap")) {
  method <- match.arg(method)

  importances <- misty_results$importances.aggregated

  # Get unique targets and views
  targets <- unique(importances$Target)
  views <- unique(importances$view)

  redundancy_list <- list()

  for (target in targets) {
    target_data <- importances %>% filter(Target == !!target)

    # Create importance matrix (predictors x views)
    wide_data <- target_data %>%
      select(Predictor, view, Importance) %>%
      pivot_wider(names_from = view, values_from = Importance, values_fill = 0)

    if (ncol(wide_data) < 3) next  # Need at least 2 views + predictor column

    importance_matrix <- as.matrix(wide_data[, -1])

    if (method == "correlation") {
      # Correlation between views
      redundancy_matrix <- cor(importance_matrix, use = "pairwise.complete.obs")
    } else {
      # Overlap of top predictors
      n_top <- 10
      redundancy_matrix <- matrix(0, nrow = ncol(importance_matrix),
                                  ncol = ncol(importance_matrix))
      colnames(redundancy_matrix) <- colnames(importance_matrix)
      rownames(redundancy_matrix) <- colnames(importance_matrix)

      for (i in 1:ncol(importance_matrix)) {
        for (j in 1:ncol(importance_matrix)) {
          top_i <- order(importance_matrix[, i], decreasing = TRUE)[1:n_top]
          top_j <- order(importance_matrix[, j], decreasing = TRUE)[1:n_top]

          redundancy_matrix[i, j] <- length(intersect(top_i, top_j)) / n_top
        }
      }
    }

    redundancy_list[[target]] <- redundancy_matrix
  }

  # Calculate average redundancy across targets
  if (length(redundancy_list) > 0) {
    avg_redundancy <- Reduce(`+`, redundancy_list) / length(redundancy_list)
  } else {
    avg_redundancy <- NULL
  }

  return(list(
    per_target = redundancy_list,
    average = avg_redundancy
  ))
}


#' Identify Redundant Predictors
#'
#' Find predictors that appear in multiple views with similar importance.
#'
#' @param misty_results mistyR results
#' @param correlation_threshold Correlation threshold for redundancy
#'
#' @return Data frame with redundant predictor pairs
#' @export
#'
#' @examples
#' \dontrun{
#' redundant <- identify_redundant_predictors(results, correlation_threshold = 0.8)
#' }
identify_redundant_predictors <- function(misty_results,
                                          correlation_threshold = 0.8) {
  importances <- misty_results$importances.aggregated

  # Get predictors that appear in multiple views
  predictor_view_count <- importances %>%
    filter(Importance > 0) %>%
    group_by(Target, Predictor) %>%
    summarise(n_views = n_distinct(view), .groups = "drop") %>%
    filter(n_views > 1)

  if (nrow(predictor_view_count) == 0) {
    message("No predictors found in multiple views")
    return(data.frame())
  }

  redundant_pairs <- data.frame()

  for (i in 1:nrow(predictor_view_count)) {
    target <- predictor_view_count$Target[i]
    predictor <- predictor_view_count$Predictor[i]

    pred_data <- importances %>%
      filter(Target == !!target, Predictor == !!predictor) %>%
      select(view, Importance)

    if (nrow(pred_data) < 2) next

    # Check if importance is similar across views
    cv <- sd(pred_data$Importance) / mean(pred_data$Importance)

    if (cv < 0.3) {  # Low CV means consistent across views
      redundant_pairs <- rbind(redundant_pairs, data.frame(
        target = target,
        predictor = predictor,
        n_views = nrow(pred_data),
        mean_importance = mean(pred_data$Importance),
        cv_importance = cv,
        views = paste(pred_data$view, collapse = ", "),
        stringsAsFactors = FALSE
      ))
    }
  }

  return(redundant_pairs)
}


#' Calculate Predictive Performance by Target
#'
#' Summarize predictive performance for each target marker.
#'
#' @param misty_results mistyR results
#' @param measure Performance measure: "gain.R2", "multi.R2", "intra.R2"
#'
#' @return Data frame with performance summary
#' @export
#'
#' @examples
#' \dontrun{
#' performance <- calculate_target_performance(results)
#' }
calculate_target_performance <- function(misty_results,
                                         measure = c("gain.R2", "multi.R2", "intra.R2")) {
  measure <- match.arg(measure)

  if (!"improvements.stats" %in% names(misty_results)) {
    warning("Improvement statistics not available")
    return(NULL)
  }

  performance <- misty_results$improvements.stats %>%
    filter(measure == !!measure) %>%
    arrange(desc(mean))

  # Add performance categories
  performance$performance_category <- cut(
    performance$mean,
    breaks = c(-Inf, 0, 0.1, 0.3, 0.5, Inf),
    labels = c("Poor", "Fair", "Good", "Very Good", "Excellent")
  )

  return(performance)
}


#' Analyze View Contribution Patterns
#'
#' Identify patterns in view contributions across targets.
#'
#' @param misty_results mistyR results
#' @param method Clustering method: "hclust", "kmeans"
#' @param n_clusters Number of clusters (for kmeans)
#'
#' @return List with patterns and clusters
#' @export
#'
#' @examples
#' \dontrun{
#' patterns <- analyze_view_patterns(results, method = "kmeans", n_clusters = 4)
#' }
analyze_view_patterns <- function(misty_results,
                                  method = c("hclust", "kmeans"),
                                  n_clusters = 4) {
  method <- match.arg(method)

  contributions <- misty_results$contributions.stats

  # Create contribution matrix (targets x views)
  contrib_matrix <- contributions %>%
    select(target, view, fraction) %>%
    pivot_wider(names_from = view, values_from = fraction, values_fill = 0)

  targets <- contrib_matrix$target
  mat <- as.matrix(contrib_matrix[, -1])
  rownames(mat) <- targets

  # Cluster targets by contribution pattern
  if (method == "hclust") {
    dist_mat <- dist(mat, method = "euclidean")
    hc <- hclust(dist_mat, method = "ward.D2")
    clusters <- cutree(hc, k = n_clusters)
  } else {
    set.seed(42)
    km <- kmeans(mat, centers = n_clusters, nstart = 25)
    clusters <- km$cluster
    hc <- NULL
  }

  # Characterize each cluster
  cluster_profiles <- data.frame()
  for (i in 1:n_clusters) {
    cluster_targets <- targets[clusters == i]
    cluster_data <- contrib_matrix %>%
      filter(target %in% cluster_targets) %>%
      select(-target)

    profile <- colMeans(cluster_data, na.rm = TRUE)

    cluster_profiles <- rbind(cluster_profiles, data.frame(
      cluster = i,
      n_targets = length(cluster_targets),
      dominant_view = names(profile)[which.max(profile)],
      t(profile),
      stringsAsFactors = FALSE
    ))
  }

  return(list(
    clusters = clusters,
    cluster_profiles = cluster_profiles,
    targets = targets,
    dendrogram = hc,
    contribution_matrix = mat
  ))
}


#' Calculate Interaction Specificity
#'
#' Measure how specific interactions are to particular views.
#'
#' @param misty_results mistyR results
#' @param importance_threshold Minimum importance threshold
#'
#' @return Data frame with specificity scores
#' @export
#'
#' @examples
#' \dontrun{
#' specificity <- calculate_interaction_specificity(results)
#' }
calculate_interaction_specificity <- function(misty_results,
                                              importance_threshold = 0.01) {
  importances <- misty_results$importances.aggregated %>%
    filter(Importance > importance_threshold)

  # Calculate specificity for each predictor-target pair
  specificity <- importances %>%
    group_by(Target, Predictor) %>%
    summarise(
      n_views = n(),
      total_importance = sum(Importance),
      max_importance = max(Importance),
      primary_view = view[which.max(Importance)],
      specificity_score = max_importance / total_importance,
      .groups = "drop"
    ) %>%
    mutate(
      specific = specificity_score >= 0.8,
      view_type = case_when(
        n_views == 1 ~ "Exclusive",
        specificity_score >= 0.8 ~ "Specific",
        specificity_score >= 0.5 ~ "Moderate",
        TRUE ~ "Distributed"
      )
    ) %>%
    arrange(desc(specificity_score))

  return(specificity)
}


#' Summarize Model Interpretation
#'
#' Create a comprehensive summary of model interpretation.
#'
#' @param misty_results mistyR results
#'
#' @return List with interpretation summary
#' @export
#'
#' @examples
#' \dontrun{
#' interpretation <- summarize_model_interpretation(results)
#' print(interpretation$summary_text)
#' }
summarize_model_interpretation <- function(misty_results) {
  summary_list <- list()

  # 1. Overall performance
  if ("improvements.stats" %in% names(misty_results)) {
    perf <- misty_results$improvements.stats %>%
      filter(measure == "multi.R2")

    summary_list$performance <- list(
      n_targets = nrow(perf),
      mean_r2 = mean(perf$mean, na.rm = TRUE),
      median_r2 = median(perf$mean, na.rm = TRUE),
      targets_above_0.5 = sum(perf$mean > 0.5, na.rm = TRUE)
    )
  }

  # 2. View contributions
  if ("contributions.stats" %in% names(misty_results)) {
    contrib_summary <- misty_results$contributions.stats %>%
      group_by(view) %>%
      summarise(
        mean_fraction = mean(fraction, na.rm = TRUE),
        .groups = "drop"
      )

    summary_list$view_contributions <- contrib_summary
    summary_list$dominant_view <- contrib_summary$view[which.max(contrib_summary$mean_fraction)]
  }

  # 3. Top interactions
  if ("importances.aggregated" %in% names(misty_results)) {
    top_interactions <- misty_results$importances.aggregated %>%
      arrange(desc(Importance)) %>%
      head(10)

    summary_list$top_interactions <- top_interactions
  }

  # Create text summary
  lines <- c(
    "=== mistyR Model Interpretation Summary ===",
    "",
    sprintf("Targets analyzed: %d", summary_list$performance$n_targets),
    sprintf("Mean R²: %.3f", summary_list$performance$mean_r2),
    sprintf("Median R²: %.3f", summary_list$performance$median_r2),
    "",
    "View Contributions:",
    paste(sprintf("  %s: %.2f", summary_list$view_contributions$view,
                  summary_list$view_contributions$mean_fraction),
          collapse = "\n"),
    "",
    sprintf("Dominant view: %s", summary_list$dominant_view),
    "",
    "Top 5 Interactions:",
    paste(sprintf("  %s -> %s (%.3f) [%s]",
                  head(summary_list$top_interactions$Predictor, 5),
                  head(summary_list$top_interactions$Target, 5),
                  head(summary_list$top_interactions$Importance, 5),
                  head(summary_list$top_interactions$view, 5)),
          collapse = "\n")
  )

  summary_list$summary_text <- paste(lines, collapse = "\n")

  return(summary_list)
}
