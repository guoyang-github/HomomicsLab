# Unit tests for mistyR microenvironment analysis
# Test suite for bio-spatial-transcriptomics-microenvironment-misty-r skill

library(testthat)
library(igraph)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "misty_analysis.R"))
source(file.path(script_dir, "misty_network.R"))
source(file.path(script_dir, "misty_views.R"))

context("mistyR Analysis Functions")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_interactions <- function() {
  data.frame(
    Target = c("A", "B", "C", "A", "B", "D"),
    Predictor = c("B", "C", "A", "C", "D", "A"),
    Importance = c(0.15, 0.25, 0.1, 0.2, 0.3, 0.05),
    view = c("intra", "intra", "intra", "para.100", "para.100", "juxta.4"),
    stringsAsFactors = FALSE
  )
}

create_test_network <- function() {
  # Create a simple directed weighted graph
  edges <- data.frame(
    from = c("A", "B", "C", "D"),
    to = c("B", "C", "D", "A"),
    weight = c(0.5, 0.3, 0.7, 0.4),
    stringsAsFactors = FALSE
  )
  graph_from_data_frame(edges, directed = TRUE)
}

create_mock_view_composition <- function() {
  # Create a minimal mock view composition
  intra_data <- data.frame(
    marker1 = c(1, 2, 3),
    marker2 = c(4, 5, 6),
    row.names = c("spot1", "spot2", "spot3"),
    stringsAsFactors = FALSE
  )

  list(
    intraview = list(
      abbrev = "intra",
      data = intra_data
    ),
    `misty.uniqueid` = list(
      data = data.frame(id = 1:3)
    ),
    paraview.100 = list(
      abbrev = "para.100",
      data = data.frame(
        marker1 = c(1.1, 2.1, 3.1),
        marker2 = c(4.1, 5.1, 6.1),
        row.names = c("spot1", "spot2", "spot3")
      )
    )
  )
}

# ============================================================================
# Tests for extract_interaction_communities
# ============================================================================

test_that("extract_interaction_communities works with valid input", {
  interactions <- create_test_interactions()

  communities <- extract_interaction_communities(interactions)

  expect_type(communities, "list")
  expect_true("marker" %in% colnames(communities))
  expect_true("community" %in% colnames(communities))
  expect_gt(nrow(communities), 0)
})

test_that("extract_interaction_communities handles empty edges", {
  interactions <- data.frame(
    Target = character(),
    Predictor = character(),
    Importance = numeric(),
    stringsAsFactors = FALSE
  )

  communities <- extract_interaction_communities(interactions)

  expect_equal(nrow(communities), 0)
})

test_that("extract_interaction_communities respects threshold", {
  interactions <- data.frame(
    Target = c("A", "B"),
    Predictor = c("B", "C"),
    Importance = c(0.5, 0.001),
    stringsAsFactors = FALSE
  )

  communities <- extract_interaction_communities(interactions, importance_threshold = 0.01)

  # Only A-B edge passes threshold
  expect_lte(nrow(communities), 2)
})

# ============================================================================
# Tests for identify_hub_markers
# ============================================================================

test_that("identify_hub_markers returns correct structure", {
  interactions <- create_test_interactions()

  hubs <- identify_hub_markers(interactions)

  expect_type(hubs, "list")
  expect_true("marker" %in% colnames(hubs))
  expect_true("page_rank" %in% colnames(hubs))
})

test_that("identify_hub_markers respects top_n parameter", {
  interactions <- create_test_interactions()

  hubs <- identify_hub_markers(interactions, top_n = 2)

  expect_lte(nrow(hubs), 2)
})

test_that("identify_hub_markers handles empty interactions", {
  interactions <- data.frame(
    Target = character(),
    Predictor = character(),
    Importance = numeric(),
    stringsAsFactors = FALSE
  )

  hubs <- identify_hub_markers(interactions)

  expect_equal(nrow(hubs), 0)
})

# ============================================================================
# Tests for Network Functions
# ============================================================================

test_that("create_interaction_network creates valid graph", {
  interactions <- create_test_interactions()

  g <- create_interaction_network(interactions, view_name = "intra")

  expect_true(is_igraph(g))
  expect_gt(vcount(g), 0)
  expect_gt(ecount(g), 0)
})

test_that("create_interaction_network handles empty data", {
  interactions <- data.frame(
    Target = character(),
    Predictor = character(),
    Importance = numeric(),
    stringsAsFactors = FALSE
  )

  g <- create_interaction_network(interactions)

  expect_true(is_igraph(g))
  expect_equal(vcount(g), 0)
})

test_that("create_multi_view_network combines views", {
  interactions <- create_test_interactions()

  g <- create_multi_view_network(
    interactions,
    views = c("intra", "para.100"),
    importance_threshold = 0.01
  )

  expect_true(is_igraph(g))
  expect_gt(vcount(g), 0)
})

test_that("calculate_network_stats returns correct structure", {
  g <- create_test_network()

  stats <- calculate_network_stats(g)

  expect_type(stats, "list")
  expect_true("basic" %in% names(stats))
  expect_true("degree" %in% names(stats))
  expect_true("weights" %in% names(stats))

  expect_equal(stats$basic$n_nodes, 4)
  expect_equal(stats$basic$n_edges, 4)
})

test_that("calculate_centrality returns correct metrics", {
  g <- create_test_network()

  centrality <- calculate_centrality(g)

  expect_type(centrality, "list")
  expect_true("node" %in% colnames(centrality))
  expect_true("degree" %in% colnames(centrality))
  expect_true("betweenness" %in% colnames(centrality))
  expect_equal(nrow(centrality), 4)
})

test_that("identify_network_hubs returns top hubs", {
  g <- create_test_network()

  hubs <- identify_network_hubs(g, method = "degree", top_n = 2)

  expect_lte(nrow(hubs), 2)
  expect_true("is_hub" %in% colnames(hubs))
  expect_true(all(hubs$is_hub))
})

test_that("extract_network_communities detects communities", {
  g <- create_test_network()

  comm <- extract_network_communities(g, algorithm = "walktrap")

  expect_type(comm, "list")
  expect_true("membership" %in% names(comm))
  expect_true("summary" %in% names(comm))
  expect_gt(comm$summary$n_communities, 0)
})

test_that("compare_networks identifies differences", {
  g1 <- create_test_network()
  g2 <- create_test_network()
  g2 <- add_vertices(g2, 1, name = "E")

  comparison <- compare_networks(g1, g2)

  expect_type(comparison, "list")
  expect_true("node_overlap" %in% names(comparison))
  expect_equal(length(comparison$node_overlap$only_in_2), 1)
})

test_that("summarize_network returns string", {
  g <- create_test_network()

  summary_text <- summarize_network(g)

  expect_type(summary_text, "character")
  expect_true(grepl("Network Summary", summary_text))
})

# ============================================================================
# Tests for misty_views.R Functions
# ============================================================================

test_that("add_custom_view adds view correctly", {
  views <- create_mock_view_composition()
  new_data <- data.frame(
    new_marker = c(7, 8, 9),
    row.names = c("spot1", "spot2", "spot3")
  )

  updated <- add_custom_view(views, new_data, "custom", "custom.")

  expect_true("custom" %in% names(updated))
  expect_equal(updated$custom$abbrev, "custom.")
})

test_that("remove_views removes non-protected views", {
  views <- create_mock_view_composition()

  updated <- remove_views(views, "paraview.100")

  expect_false("paraview.100" %in% names(updated))
  expect_true("intraview" %in% names(updated))  # Protected
})

test_that("remove_views protects intraview and misty.uniqueid", {
  views <- create_mock_view_composition()

  expect_warning(
    updated <- remove_views(views, c("intraview", "misty.uniqueid")),
    "Cannot remove protected view"
  )

  expect_true("intraview" %in% names(updated))
  expect_true("misty.uniqueid" %in% names(updated))
})

test_that("update_view updates data correctly", {
  views <- create_mock_view_composition()
  new_data <- data.frame(
    marker1 = c(10, 20, 30),
    marker2 = c(40, 50, 60),
    row.names = c("spot1", "spot2", "spot3")
  )

  updated <- update_view(views, "paraview.100", new_data)

  expect_equal(updated$paraview.100$data$marker1[1], 10)
})

test_that("update_view validates row count", {
  views <- create_mock_view_composition()
  bad_data <- data.frame(marker1 = c(1, 2))  # Wrong number of rows

  expect_error(
    update_view(views, "paraview.100", bad_data),
    "Row count mismatch"
  )
})

test_that("update_view prevents updating misty.uniqueid", {
  views <- create_mock_view_composition()

  expect_error(
    update_view(views, "misty.uniqueid", data.frame()),
    "Cannot update misty.uniqueid"
  )
})

test_that("filter_views keeps matching views", {
  views <- create_mock_view_composition()

  filtered <- filter_views(views, pattern = "^paraview")

  expect_true("paraview.100" %in% names(filtered))
  # Protected views are always kept
  expect_true("intraview" %in% names(filtered))
})

test_that("filter_views with invert removes matching views", {
  views <- create_mock_view_composition()

  filtered <- filter_views(views, pattern = "^paraview", invert = TRUE)

  # With invert=TRUE, we keep non-matching views + protected views
  expect_false("paraview.100" %in% names(filtered))  # Matching removed
  expect_true("intraview" %in% names(filtered))  # Protected always kept
})

test_that("list_views returns correct structure", {
  views <- create_mock_view_composition()

  info <- list_views(views)

  expect_type(info, "list")
  expect_true("name" %in% colnames(info))
  expect_true("abbrev" %in% colnames(info))
  expect_equal(nrow(info), length(views))
})

test_that("validate_view_composition checks required elements", {
  valid_views <- create_mock_view_composition()
  expect_true(validate_view_composition(valid_views))

  invalid_views <- list(
    paraview.100 = list(data = data.frame())
  )
  expect_warning(
    result <- validate_view_composition(invalid_views),
    "Missing required"
  )
  expect_false(result)
})

test_that("clone_view_composition creates independent copy", {
  views <- create_mock_view_composition()
  cloned <- clone_view_composition(views)

  expect_equal(names(cloned), names(views))

  # Modify clone - should not affect original
  cloned$intraview$data$marker1[1] <- 999
  expect_false(identical(cloned$intraview$data, views$intraview$data))
})

# ============================================================================
# Tests for add_family_view
# ============================================================================

test_that("add_family_view aggregates markers correctly", {
  views <- create_mock_view_composition()

  families <- list(
    group1 = c("marker1"),
    group2 = c("marker2")
  )

  updated <- add_family_view(views, families, aggregation = "mean")

  expect_true("familyview" %in% names(updated))
})

test_that("add_family_view warns about missing markers", {
  views <- create_mock_view_composition()

  families <- list(
    group1 = c("nonexistent_marker")
  )

  expect_warning(
    add_family_view(views, families),
    "No markers from family"
  )
})

# ============================================================================
# Tests for add_variable_radius_paraviews (mock)
# ============================================================================

test_that("add_variable_radius_paraviews validates parameters", {
  skip("Requires mistyR package")
})

# ============================================================================
# Integration Tests
# ============================================================================

test_that("Network workflow works end-to-end", {
  interactions <- create_test_interactions()

  # Create network
  g <- create_interaction_network(interactions)

  # Calculate stats
  stats <- calculate_network_stats(g)

  # Get centrality
  centrality <- calculate_centrality(g)

  # Identify hubs
  hubs <- identify_network_hubs(g)

  # Extract communities
  comm <- extract_network_communities(g)

  expect_true(is_igraph(g))
  expect_gt(nrow(centrality), 0)
  expect_gt(comm$summary$n_communities, 0)
})

test_that("View manipulation workflow works", {
  views <- create_mock_view_composition()

  # Add custom view
  new_data <- data.frame(new = c(1, 2, 3), row.names = c("spot1", "spot2", "spot3"))
  views <- add_custom_view(views, new_data, "custom", "cust.")

  # List views
  info <- list_views(views)
  expect_equal(nrow(info), 4)

  # Validate
  expect_true(validate_view_composition(views))

  # Remove custom view
  views <- remove_views(views, "custom")
  expect_false("custom" %in% names(views))
})

# ============================================================================
# Edge Cases
# ============================================================================

test_that("Network functions handle single-node graphs", {
  g <- graph_from_data_frame(
    data.frame(from = character(), to = character(), stringsAsFactors = FALSE),
    directed = TRUE
  )
  g <- add_vertices(g, 1, name = "A")

  stats <- calculate_network_stats(g)
  expect_equal(stats$basic$n_nodes, 1)
  expect_equal(stats$basic$n_edges, 0)
})

test_that("Network functions handle disconnected graphs", {
  edges <- data.frame(
    from = c("A", "C"),
    to = c("B", "D"),
    weight = c(0.5, 0.3),
    stringsAsFactors = FALSE
  )
  g <- graph_from_data_frame(edges, directed = TRUE)

  stats <- calculate_network_stats(g)
  expect_false(stats$basic$is_connected)
  expect_equal(stats$basic$n_components, 2)
})

test_that("extract_interaction_communities handles warning", {
  interactions <- data.frame(
    Target = "A",
    Predictor = "B",
    Importance = 0.0001,  # Below default threshold
    stringsAsFactors = FALSE
  )

  expect_warning(
    communities <- extract_interaction_communities(interactions),
    "No edges passed threshold"
  )
})

# Note: Tests requiring mistyR package are skipped when not installed
# Run with: test_file("tests/test_misty_analysis.R")
