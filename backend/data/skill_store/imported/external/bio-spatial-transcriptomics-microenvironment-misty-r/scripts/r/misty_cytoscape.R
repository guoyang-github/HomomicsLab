#' mistyR Cytoscape Export Functions
#'
#' Export mistyR networks to Cytoscape-compatible formats.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

library(igraph)
library(dplyr)

#' Export Network to GraphML Format
#'
#' Export network to GraphML format for Cytoscape.
#'
#' @param g igraph object
#' @param output_file Output file path (.graphml)
#' @param node_attrs Data frame with node attributes
#' @param edge_attrs Data frame with edge attributes
#' @param layout Layout matrix for node positions
#' @param communities Community object for visual grouping
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' export_cytoscape_graphml(network, "misty_network.graphml", layout = coords)
#' }
export_cytoscape_graphml <- function(g,
                                     output_file = "misty_network.graphml",
                                     node_attrs = NULL,
                                     edge_attrs = NULL,
                                     layout = NULL,
                                     communities = NULL) {
  # Add node attributes
  if (!is.null(node_attrs)) {
    for (col in colnames(node_attrs)) {
      if (col != "node" && col != "name") {
        values <- node_attrs[[col]][match(V(g)$name, node_attrs$node)]
        g <- set_vertex_attr(g, name = col, value = values)
      }
    }
  }

  # Add layout positions
  if (!is.null(layout)) {
    g <- set_vertex_attr(g, name = "x", value = layout[, 1])
    g <- set_vertex_attr(g, name = "y", value = layout[, 2])
  }

  # Add community information
  if (!is.null(communities)) {
    comm_membership <- communities$membership$community[
      match(V(g)$name, communities$membership$node)
    ]
    g <- set_vertex_attr(g, name = "community", value = comm_membership)
  }

  # Add edge attributes
  if (!is.null(edge_attrs)) {
    for (col in colnames(edge_attrs)) {
      if (!col %in% c("from", "to", "source", "target")) {
        g <- set_edge_attr(g, name = col, value = edge_attrs[[col]])
      }
    }
  }

  # Write GraphML
  write_graph(g, file = output_file, format = "graphml")

  message(sprintf("GraphML exported to: %s", output_file))
  message(sprintf("Nodes: %d, Edges: %d", vcount(g), ecount(g)))

  invisible(NULL)
}

#' Export Cytoscape Tables
#'
#' Export nodes and edges as separate CSV tables for Cytoscape import.
#'
#' @param g igraph object
#' @param output_prefix Output file prefix
#' @param node_attrs Additional node attributes
#' @param layout Layout matrix
#' @param communities Community object
#'
#' @return List with file paths
#' @export
#'
#' @examples
#' \dontrun{
#' files <- export_cytoscape_tables(network, "misty_network")
#' # Creates: misty_network_nodes.csv, misty_network_edges.csv
#' }
export_cytoscape_tables <- function(g,
                                    output_prefix = "misty_network",
                                    node_attrs = NULL,
                                    layout = NULL,
                                    communities = NULL) {

  # Prepare node table
  nodes_df <- data.frame(
    id = V(g)$name,
    name = V(g)$name,
    stringsAsFactors = FALSE
  )

  # Add layout coordinates
  if (!is.null(layout)) {
    nodes_df$x <- layout[, 1]
    nodes_df$y <- layout[, 2]
  }

  # Add igraph attributes
  for (attr_name in vertex_attr_names(g)) {
    if (!attr_name %in% colnames(nodes_df)) {
      nodes_df[[attr_name]] <- vertex_attr(g, attr_name)
    }
  }

  # Add community
  if (!is.null(communities)) {
    nodes_df$community <- communities$membership$community[
      match(nodes_df$id, communities$membership$node)
    ]
  }

  # Add additional node attributes
  if (!is.null(node_attrs)) {
    for (col in colnames(node_attrs)) {
      if (col != "node" && col != "name" && col != "id") {
        nodes_df[[col]] <- node_attrs[[col]][match(nodes_df$id, node_attrs$node)]
      }
    }
  }

  # Prepare edge table
  edge_list <- as_edgelist(g, names = TRUE)
  edges_df <- data.frame(
    source = edge_list[, 1],
    target = edge_list[, 2],
    interaction = "regulates",
    stringsAsFactors = FALSE
  )

  # Add edge attributes
  for (attr_name in edge_attr_names(g)) {
    edges_df[[attr_name]] <- edge_attr(g, attr_name)
  }

  # Rename weight to importance if present
  if ("weight" %in% colnames(edges_df)) {
    colnames(edges_df)[colnames(edges_df) == "weight"] <- "importance"
  }

  # Write files
  node_file <- paste0(output_prefix, "_nodes.csv")
  edge_file <- paste0(output_prefix, "_edges.csv")

  write.csv(nodes_df, node_file, row.names = FALSE)
  write.csv(edges_df, edge_file, row.names = FALSE)

  message(sprintf("Node table: %s (%d nodes)", node_file, nrow(nodes_df)))
  message(sprintf("Edge table: %s (%d edges)", edge_file, nrow(edges_df)))

  return(list(nodes = node_file, edges = edge_file))
}


#' Export to Cytoscape JSON
#'
#' Export network to Cytoscape.js JSON format.
#'
#' @param g igraph object
#' @param output_file Output file path (.json)
#' @param node_attrs Node attributes
#' @param layout Layout matrix
#' @param communities Community object
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' export_cytoscape_json(network, "misty_network.json")
#' }
export_cytoscape_json <- function(g,
                                  output_file = "misty_network.json",
                                  node_attrs = NULL,
                                  layout = NULL,
                                  communities = NULL) {

  # Build nodes
  nodes <- lapply(seq_len(vcount(g)), function(i) {
    node_data <- list(id = V(g)$name[i], name = V(g)$name[i])

    # Add position
    if (!is.null(layout)) {
      node_data$x <- layout[i, 1]
      node_data$y <- layout[i, 2]
    }

    # Add attributes
    for (attr_name in vertex_attr_names(g)) {
      node_data[[attr_name]] <- vertex_attr(g, attr_name, i)
    }

    # Add community
    if (!is.null(communities)) {
      node_data$community <- communities$membership$community[
        match(V(g)$name[i], communities$membership$node)
      ]
    }

    list(data = node_data)
  })

  # Build edges
  edge_list <- as_edgelist(g, names = TRUE)
  edges <- lapply(seq_len(nrow(edge_list)), function(i) {
    edge_data <- list(
      source = edge_list[i, 1],
      target = edge_list[i, 2],
      interaction = "regulates"
    )

    # Add attributes
    for (attr_name in edge_attr_names(g)) {
      edge_data[[attr_name]] <- edge_attr(g, attr_name, i)
    }

    list(data = edge_data)
  })

  # Build complete structure
  cyjs <- list(
    elements = list(
      nodes = nodes,
      edges = edges
    )
  )

  # Write JSON
  jsonlite::write_json(cyjs, output_file, auto_unbox = TRUE, pretty = TRUE)

  message(sprintf("Cytoscape.js JSON exported to: %s", output_file))

  invisible(NULL)
}


#' Create Cytoscape Style XML
#'
#' Generate a Cytoscape style XML file for consistent visualization.
#'
#' @param style_name Name of the style
#' @param output_file Output file path
#' @param node_color_by Attribute to color nodes by (e.g., "community")
#' @param node_size_by Attribute to size nodes by (e.g., "degree")
#' @param edge_width_by Attribute to width edges by (e.g., "importance")
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' create_cytoscape_style("misty_style", "misty_style.xml",
#'                        node_color_by = "community",
#'                        node_size_by = "degree")
#' }
create_cytoscape_style <- function(style_name = "misty_style",
                                   output_file = "misty_style.xml",
                                   node_color_by = NULL,
                                   node_size_by = NULL,
                                   edge_width_by = "importance") {

  # Build style XML
  style_xml <- paste0(
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
    '<vizmap documentVersion="3.0" id="root">\n',
    '  <visualStyle name="', style_name, '">\n'
  )

  # Node defaults
  style_xml <- paste0(
    style_xml,
    '    <node>\n',
    '      <dependency name="nodeCustomGraphicsSizeSync" value="true"/>\n',
    '      <dependency name="nodeSizeLocked" value="true"/>\n',
    '      <visualProperty name="NODE_FILL_COLOR" value="#CCCCCC"/>\n',
    '      <visualProperty name="NODE_SHAPE" value="ellipse"/>\n',
    '      <visualProperty name="NODE_SIZE" value="30"/>\n',
    '      <visualProperty name="NODE_LABEL" value="name"/>\n',
    '      <visualProperty name="NODE_LABEL_FONT_SIZE" value="12"/>\n',
    '      <visualProperty name="NODE_BORDER_WIDTH" value="1"/>\n',
    '      <visualProperty name="NODE_BORDER_COLOR" value="#666666"/>\n'
  )

  # Node coloring
  if (!is.null(node_color_by)) {
    style_xml <- paste0(
      style_xml,
      '      <visualProperty name="NODE_FILL_COLOR" type="DISCRETE">\n',
      '        <mapping attribute="', node_color_by, '" type="discrete">\n',
      '          <!-- Cytoscape will auto-assign colors -->\n',
      '        </mapping>\n',
      '      </visualProperty>\n'
    )
  }

  # Node sizing
  if (!is.null(node_size_by)) {
    style_xml <- paste0(
      style_xml,
      '      <visualProperty name="NODE_SIZE" type="CONTINUOUS">\n',
      '        <mapping attribute="', node_size_by, '" type="continuous">\n',
      '          <continuousMappingPoint lesserValue="10" greaterValue="10" attrValue="0"/>\n',
      '          <continuousMappingPoint lesserValue="50" greaterValue="50" attrValue="100"/>\n',
      '        </mapping>\n',
      '      </visualProperty>\n'
    )
  }

  style_xml <- paste0(style_xml, '    </node>\n')

  # Edge defaults
  style_xml <- paste0(
    style_xml,
    '    <edge>\n',
    '      <visualProperty name="EDGE_LINE_TYPE" value="SOLID"/>\n',
    '      <visualProperty name="EDGE_COLOR" value="#999999"/>\n',
    '      <visualProperty name="EDGE_WIDTH" value="1"/>\n',
    '      <visualProperty name="EDGE_TARGET_ARROW_SHAPE" value="ARROW"/>\n',
    '      <visualProperty name="EDGE_TARGET_ARROW_COLOR" value="#999999"/>\n',
    '      <visualProperty name="EDGE_TRANSPARENCY" value="150"/>\n'
  )

  # Edge width mapping
  if (!is.null(edge_width_by)) {
    style_xml <- paste0(
      style_xml,
      '      <visualProperty name="EDGE_WIDTH" type="CONTINUOUS">\n',
      '        <mapping attribute="', edge_width_by, '" type="continuous">\n',
      '          <continuousMappingPoint lesserValue="0.5" greaterValue="0.5" attrValue="0"/>\n',
      '          <continuousMappingPoint lesserValue="5" greaterValue="5" attrValue="1"/>\n',
      '        </mapping>\n',
      '      </visualProperty>\n'
    )
  }

  style_xml <- paste0(
    style_xml,
    '    </edge>\n',
    '  </visualStyle>\n',
    '</vizmap>\n'
  )

  # Write file
  writeLines(style_xml, output_file)

  message(sprintf("Cytoscape style exported to: %s", output_file))

  invisible(NULL)
}


#' Generate Cytoscape Import Script
#'
#' Generate an R script for importing data into Cytoscape using RCy3.
#'
#' @param network_files List of network files
#' @param style_file Style file path
#' @param output_file Output script file
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' generate_cytoscape_script(list(nodes="nodes.csv", edges="edges.csv"),
#'                          "style.xml", "import_to_cytoscape.R")
#' }
generate_cytoscape_script <- function(network_files,
                                      style_file = NULL,
                                      output_file = "import_to_cytoscape.R") {

  script <- c(
    "# Cytoscape Import Script",
    "# Generated by mistyR",
    "",
    "library(RCy3)",
    "",
    "# Check Cytoscape connection",
    "cytoscapePing()",
    "",
    "# Import network",
    sprintf("nodes_file <- '%s'", network_files$nodes),
    sprintf("edges_file <- '%s'", network_files$edges),
    "",
    "# Create network",
    "network <- importNetworkFromFile(",
    "  nodesFile = nodes_file,",
    "  edgesFile = edges_file,",
    "  sourceIdList = c('source'),",
    "  targetIdList = c('target'),",
    "  interactionTypeList = c('interaction')",
    ")",
    "",
    "# Apply layout",
    "layoutNetwork('force-directed')",
    ""
  )

  if (!is.null(style_file)) {
    script <- c(
      script,
      sprintf("# Import and apply style"),
      sprintf("importVisualStyles(filename = '%s')", style_file),
      sprintf("setVisualStyle('%s')", "misty_style"),
      ""
    )
  }

  script <- c(
    script,
    "# Fit network to window",
    "fitContent()",
    "",
    "message('Network imported successfully!')",
    ""
  )

  writeLines(script, output_file)

  message(sprintf("Cytoscape import script: %s", output_file))

  invisible(NULL)
}


#' Complete Cytoscape Export
#'
#' Export network and create all necessary files for Cytoscape.
#'
#' @param g igraph object
#' @param output_prefix Output file prefix
#' @param node_attrs Node attributes
#' @param layout Layout matrix
#' @param communities Community object
#' @param create_style Whether to create style file
#' @param create_script Whether to create import script
#'
#' @return List with all output files
#' @export
#'
#' @examples
#' \dontrun{
#' export_complete_cytoscape(network, "misty_results",
#'                          layout = coords, communities = comm)
#' }
export_complete_cytoscape <- function(g,
                                      output_prefix = "misty_network",
                                      node_attrs = NULL,
                                      layout = NULL,
                                      communities = NULL,
                                      create_style = TRUE,
                                      create_script = TRUE) {

  output_files <- list()

  # Export GraphML
  graphml_file <- paste0(output_prefix, ".graphml")
  export_cytoscape_graphml(g, graphml_file, node_attrs, NULL, layout, communities)
  output_files$graphml <- graphml_file

  # Export tables
  tables <- export_cytoscape_tables(g, output_prefix, node_attrs, layout, communities)
  output_files$nodes <- tables$nodes
  output_files$edges <- tables$edges

  # Export JSON
  json_file <- paste0(output_prefix, ".json")
  export_cytoscape_json(g, json_file, node_attrs, layout, communities)
  output_files$json <- json_file

  # Create style
  if (create_style) {
    style_file <- paste0(output_prefix, "_style.xml")
    create_cytoscape_style(
      style_name = "misty_style",
      output_file = style_file,
      node_color_by = if (!is.null(communities)) "community" else NULL,
      node_size_by = "degree",
      edge_width_by = "importance"
    )
    output_files$style <- style_file
  }

  # Create import script
  if (create_script) {
    script_file <- paste0(output_prefix, "_import.R")
    generate_cytoscape_script(tables, output_files$style, script_file)
    output_files$script <- script_file
  }

  message("\n=== Cytoscape Export Complete ===")
  message("Files created:")
  for (name in names(output_files)) {
    message(sprintf("  [%s] %s", name, output_files[[name]]))
  }

  return(output_files)
}
