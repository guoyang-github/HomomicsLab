#' mistyR Result Contrast and Comparison Functions
#'
#' Compare mistyR results between conditions or samples.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.1.0

library(dplyr)
library(ggplot2)
library(tidyr)

#' Compare View Contributions Between Conditions
#'
#' Compare view contributions across multiple conditions or samples.
#'
#' @param results_list Named list of mistyR results
#' @param plot Create comparison plot (default: TRUE)
#'
#' @return List with comparison data and plot
#' @export
#'
#' @examples
#' \dontrun{
#' results_list <- list(control = control_results, treated = treated_results)
#' comparison <- compare_view_contributions(results_list)
#' print(comparison$plot)
#' }
compare_view_contributions <- function(results_list, plot = TRUE) {
  # Extract contributions from each result
  comparison_data <- lapply(names(results_list), function(name) {
    results_list[[name]]$contributions.stats %>%
      mutate(condition = name)
  }) %>% bind_rows()

  # Summarize by condition and view
  summary <- comparison_data %>%
    group_by(condition, view) %>%
    summarise(
      mean_fraction = mean(fraction, na.rm = TRUE),
      sd_fraction = sd(fraction, na.rm = TRUE),
      .groups = "drop"
    )

  # Create plot
  p <- NULL
  if (plot && nrow(summary) > 0) {
    p <- ggplot(summary, aes(x = view, y = mean_fraction, fill = condition)) +
      geom_bar(stat = "identity", position = "dodge") +
      geom_errorbar(aes(ymin = mean_fraction - sd_fraction,
                       ymax = mean_fraction + sd_fraction),
                   position = position_dodge(width = 0.9),
                   width = 0.25) +
      scale_fill_brewer(palette = "Set2") +
      labs(x = "View", y = "Mean Contribution Fraction",
           fill = "Condition",
           title = "View Contribution Comparison") +
      theme_minimal() +
      theme(axis.text.x = element_text(angle = 45, hjust = 1))

    print(p)
  }

  return(list(summary = summary, plot = p, raw_data = comparison_data))
}


#' Plot Contrast Results Between Conditions
#'
#' Visualize differences in interactions between two conditions.
#'
#' @param misty_results_base mistyR results for base condition
#' @param misty_results_contrast mistyR results for contrast condition
#' @param view View name to contrast
#' @param cutoff Threshold for importance
#' @param plot_type "heatmap" or "network"
#'
#' @return ggplot object or list
#' @export
#'
#' @examples
#' \dontrun{
#' plot_contrast_results(control_results, treated_results,
#'                       view = "para.100", cutoff = 0.5)
#' }
plot_contrast_results <- function(misty_results_base,
                                  misty_results_contrast,
                                  view = "intra",
                                  cutoff = 0.5,
                                  plot_type = c("heatmap", "network")) {
  plot_type <- match.arg(plot_type)

  # Check if view exists in both results
  views_base <- unique(misty_results_base$importances.aggregated$view)
  views_contrast <- unique(misty_results_contrast$importances.aggregated$view)

  if (!(view %in% views_base) || !(view %in% views_contrast)) {
    stop(sprintf("View '%s' not found in one or both results", view))
  }

  # Extract data for the view
  base_data <- misty_results_base$importances.aggregated %>%
    filter(view == !!view) %>%
    select(Predictor, Target, Importance)

  contrast_data <- misty_results_contrast$importances.aggregated %>%
    filter(view == !!view) %>%
    select(Predictor, Target, Importance)

  # Find differences
  all_pairs <- unique(rbind(
    base_data %>% select(Predictor, Target),
    contrast_data %>% select(Predictor, Target)
  ))

  comparison <- all_pairs %>%
    left_join(base_data %>% rename(base_importance = Importance),
             by = c("Predictor", "Target")) %>%
    left_join(contrast_data %>% rename(contrast_importance = Importance),
             by = c("Predictor", "Target")) %>%
    mutate(
      base_importance = replace_na(base_importance, 0),
      contrast_importance = replace_na(contrast_importance, 0),
      difference = contrast_importance - base_importance,
      gained = base_importance < cutoff & contrast_importance >= cutoff,
      lost = base_importance >= cutoff & contrast_importance < cutoff,
      changed = gained | lost
    )

  if (plot_type == "heatmap") {
    # Create heatmap of differences
    plot_data <- comparison %>%
      filter(changed) %>%
      arrange(desc(abs(difference)))

    if (nrow(plot_data) > 50) {
      plot_data <- head(plot_data, 50)
    }

    p <- ggplot(plot_data, aes(x = Predictor, y = Target, fill = difference)) +
      geom_tile() +
      scale_fill_gradient2(low = "blue", mid = "white", high = "red",
                          midpoint = 0, name = "Importance\nDifference") +
      labs(title = sprintf("Interaction Changes: %s", view),
           subtitle = sprintf("Base vs Contrast (cutoff = %.2f)", cutoff)) +
      theme_minimal() +
      theme(axis.text.x = element_text(angle = 90, hjust = 1))

    print(p)
    return(list(plot = p, comparison = comparison))

  } else {
    # Network plot showing gained and lost edges
    gained_edges <- comparison %>% filter(gained)
    lost_edges <- comparison %>% filter(lost)

    message(sprintf("Gained interactions: %d", nrow(gained_edges)))
    message(sprintf("Lost interactions: %d", nrow(lost_edges)))

    return(list(
      gained = gained_edges,
      lost = lost_edges,
      comparison = comparison
    ))
  }
}


#' Compare Target Performance Across Conditions
#'
#' Compare predictive performance for each target across conditions.
#'
#' @param results_list Named list of mistyR results
#' @param measure Performance measure
#'
#' @return Data frame with performance comparison
#' @export
#'
#' @examples
#' \dontrun{
#' perf_comparison <- compare_target_performance(
#'   list(control = ctrl_res, treated = trt_res),
#'   measure = "multi.R2"
#' )
#' }
compare_target_performance <- function(results_list,
                                       measure = c("multi.R2", "gain.R2", "intra.R2")) {
  measure <- match.arg(measure)

  comparison <- lapply(names(results_list), function(name) {
    results_list[[name]]$improvements.stats %>%
      filter(measure == !!measure) %>%
      select(target, mean, sd) %>%
      mutate(condition = name)
  }) %>% bind_rows()

  # Reshape for comparison
  wide_comparison <- comparison %>%
    pivot_wider(
      names_from = condition,
      values_from = c(mean, sd),
      names_sep = "."
    )

  # Calculate differences if exactly 2 conditions
  conditions <- unique(comparison$condition)
  if (length(conditions) == 2) {
    wide_comparison <- wide_comparison %>%
      mutate(
        performance_diff = .data[[paste0("mean.", conditions[2])]] -
                          .data[[paste0("mean.", conditions[1])]]
      ) %>%
      arrange(desc(abs(performance_diff)))
  }

  return(list(
    long_format = comparison,
    wide_format = wide_comparison
  ))
}


#' Identify Differential Interactions
#'
#' Find interactions that significantly differ between conditions.
#'
#' @param misty_results_list Named list of mistyR results (2 conditions)
#' @param view View to analyze
#' @param importance_threshold Minimum importance
#' @param fold_change_threshold Minimum fold change
#'
#' @return Data frame with differential interactions
#' @export
#'
#' @examples
#' \dontrun{
#' diff_int <- identify_differential_interactions(
#'   list(control = ctrl, treated = trt),
#'   view = "para.100"
#' )
#' }
identify_differential_interactions <- function(misty_results_list,
                                               view = "intra",
                                               importance_threshold = 0.01,
                                               fold_change_threshold = 2) {
  if (length(misty_results_list) != 2) {
    stop("Exactly 2 conditions required")
  }

  condition_names <- names(misty_results_list)

  # Extract importances
  imp1 <- misty_results_list[[1]]$importances.aggregated %>%
    filter(view == !!view, Importance > importance_threshold) %>%
    select(Predictor, Target, Importance) %>%
    rename(imp1 = Importance)

  imp2 <- misty_results_list[[2]]$importances.aggregated %>%
    filter(view == !!view, Importance > importance_threshold) %>%
    select(Predictor, Target, Importance) %>%
    rename(imp2 = Importance)

  # Merge and calculate differences
  comparison <- full_join(imp1, imp2, by = c("Predictor", "Target")) %>%
    mutate(
      imp1 = replace_na(imp1, 0),
      imp2 = replace_na(imp2, 0),
      fold_change = ifelse(imp1 > 0, imp2 / imp1, Inf),
      log2_fc = log2(fold_change + 0.001),
      unique_to_1 = imp1 > importance_threshold & imp2 <= importance_threshold,
      unique_to_2 = imp2 > importance_threshold & imp1 <= importance_threshold,
      changed = abs(log2_fc) > log2(fold_change_threshold),
      direction = case_when(
        unique_to_1 ~ "unique_to_1",
        unique_to_2 ~ "unique_to_2",
        log2_fc > 0 ~ "increased",
        log2_fc < 0 ~ "decreased",
        TRUE ~ "unchanged"
      )
    )

  return(comparison %>%
    filter(direction != "unchanged") %>%
    arrange(desc(abs(log2_fc))))
}


#' Plot Differential Network
#'
#' Visualize network differences between conditions.
#'
#' @param comparison_result Output from identify_differential_interactions
#' @param layout_matrix Layout matrix for nodes
#' @param top_n Number of top differential edges to show
#'
#' @return Plot object
#' @export
#'
#' @examples
#' \dontrun{
#' diff_net <- identify_differential_interactions(list(ctrl, trt))
#' plot_differential_network(diff_net, layout)
#' }
plot_differential_network <- function(comparison_result,
                                     layout_matrix = NULL,
                                     top_n = 50) {
  if (nrow(comparison_result) == 0) {
    message("No differential interactions found")
    return(NULL)
  }

  # Select top differential edges
  plot_data <- head(comparison_result, top_n)

  # Create igraph
  edges <- data.frame(
    from = plot_data$Predictor,
    to = plot_data$Target,
    weight = abs(plot_data$log2_fc),
    direction = plot_data$direction,
    stringsAsFactors = FALSE
  )

  g <- graph_from_data_frame(edges, directed = TRUE)

  # Create layout if not provided
  if (is.null(layout_matrix)) {
    layout_matrix <- layout_with_fr(g, weights = E(g)$weight)
  }

  # Color edges by direction
  edge_colors <- case_when(
    edges$direction == "unique_to_1" ~ "blue",
    edges$direction == "unique_to_2" ~ "red",
    edges$direction == "increased" ~ "darkred",
    edges$direction == "decreased" ~ "darkblue",
    TRUE ~ "gray"
  )

  # Plot
  plot(g, layout = layout_matrix,
       vertex.size = 5,
       vertex.label.cex = 0.6,
       vertex.color = "lightgray",
       edge.width = edges$weight * 2,
       edge.color = edge_colors,
       edge.arrow.size = 0.3,
       main = sprintf("Differential Network (top %d)", top_n))

  legend("topright",
         legend = c("Unique to 1", "Unique to 2", "Increased", "Decreased"),
         col = c("blue", "red", "darkred", "darkblue"),
         lty = 1, cex = 0.7)

  invisible(g)
}


#' Create Contrast Summary Report
#'
#' Generate a comprehensive summary comparing two conditions.
#'
#' @param misty_results_1 mistyR results for condition 1
#' @param misty_results_2 mistyR results for condition 2
#' @param condition_1_name Name for condition 1
#' @param condition_2_name Name for condition 2
#'
#' @return List with summary statistics and text
#' @export
#'
#' @examples
#' \dontrun{
#' report <- create_contrast_summary(control, treated, "Control", "Treated")
#' cat(report$summary_text)
#' }
create_contrast_summary <- function(misty_results_1,
                                   misty_results_2,
                                   condition_1_name = "Condition1",
                                   condition_2_name = "Condition2") {
  summary <- list(
    condition_1 = condition_1_name,
    condition_2 = condition_2_name
  )

  # Compare view contributions
  contrib_comparison <- compare_view_contributions(
    list(setNames(list(misty_results_1), condition_1_name),
         setNames(list(misty_results_2), condition_2_name)),
    plot = FALSE
  )
  summary$view_contributions <- contrib_comparison$summary

  # Compare performance
  perf_comparison <- compare_target_performance(
    list(setNames(list(misty_results_1), condition_1_name),
         setNames(list(misty_results_2), condition_2_name))
  )
  summary$performance <- perf_comparison$wide_format

  # Find differential interactions for each view
  views <- intersect(
    unique(misty_results_1$importances.aggregated$view),
    unique(misty_results_2$importances.aggregated$view)
  )

  summary$differential_interactions <- list()
  for (view in views) {
    diff <- identify_differential_interactions(
      list(misty_results_1, misty_results_2),
      view = view,
      importance_threshold = 0.05
    )
    summary$differential_interactions[[view]] <- diff
  }

  # Create text summary
  lines <- c(
    sprintf("=== Contrast Summary: %s vs %s ===", condition_2_name, condition_1_name),
    "",
    "View Contribution Differences:",
    paste(sprintf("  %s: %.3f vs %.3f",
                  contrib_comparison$summary$view,
                  contrib_comparison$summary$mean_fraction[seq(1, nrow(contrib_comparison$summary), 2)],
                  contrib_comparison$summary$mean_fraction[seq(2, nrow(contrib_comparison$summary), 2)]),
          collapse = "\n"),
    "",
    "Differential Interactions:",
    paste(sprintf("  %s: %d changed",
                  names(summary$differential_interactions),
                  sapply(summary$differential_interactions, nrow)),
          collapse = "\n")
  )

  summary$summary_text <- paste(lines, collapse = "\n")

  return(summary)
}
