#' NicheNet Utility Functions
#'
#' Helper functions for data preparation and conversion.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

# Conditionally load dplyr
if (requireNamespace("dplyr", quietly = TRUE)) {
  library(dplyr)
}

#' Convert Mouse to Human Gene Symbols
#'
#' Convert mouse gene symbols to human orthologs.
#'
#' @param genes Vector of mouse gene symbols
#' @param lr_network Optional: ligand-receptor network to map against
#'
#' @return Vector of human gene symbols
#' @export
#'
#' @examples
#' \dontrun{
#' human_genes <- convert_mouse_to_human(c("Il2", "Ifng", "Tnf"))
#' }
convert_mouse_to_human <- function(genes, lr_network = NULL) {
  if (!requireNamespace("nichenetr", quietly = TRUE)) {
    stop("nichenetr package required")
  }

  # Load gene info from nichenetr
  gene_info <- nichenetr::geneinfo_human

  # Map mouse to human
  mapped <- gene_info$symbol[match(genes, gene_info$symbol_mouse)]
  names(mapped) <- genes

  # Remove NA
  mapped <- mapped[!is.na(mapped)]

  if (!is.null(lr_network)) {
    # Filter to genes in network
    network_genes <- unique(c(lr_network$from, lr_network$to))
    mapped <- mapped[mapped %in% network_genes]
  }

  return(mapped)
}


#' Convert Human to Mouse Gene Symbols
#'
#' Convert human gene symbols to mouse orthologs.
#'
#' @param genes Vector of human gene symbols
#' @param lr_network Optional: ligand-receptor network to map against
#'
#' @return Vector of mouse gene symbols
#' @export
#'
#' @examples
#' \dontrun{
#' mouse_genes <- convert_human_to_mouse(c("IL2", "IFNG", "TNF"))
#' }
convert_human_to_mouse <- function(genes, lr_network = NULL) {
  if (!requireNamespace("nichenetr", quietly = TRUE)) {
    stop("nichenetr package required")
  }

  # Load gene info
  gene_info <- nichenetr::geneinfo_human

  # Map human to mouse
  mapped <- gene_info$symbol_mouse[match(genes, gene_info$symbol)]
  names(mapped) <- genes

  # Remove NA
  mapped <- mapped[!is.na(mapped)]

  if (!is.null(lr_network)) {
    network_genes <- unique(c(lr_network$from, lr_network$to))
    mapped <- mapped[mapped %in% network_genes]
  }

  return(mapped)
}


#' Get All Ligands
#'
#' Get all ligands from the ligand-receptor network.
#'
#' @param lr_network Ligand-receptor network
#'
#' @return Vector of ligand names
#' @export
#'
#' @examples
#' \dontrun{
#' all_ligands <- get_all_ligands(lr_network)
#' }
get_all_ligands <- function(lr_network) {
  unique(lr_network$from)
}


#' Get All Receptors
#'
#' Get all receptors from the ligand-receptor network.
#'
#' @param lr_network Ligand-receptor network
#'
#' @return Vector of receptor names
#' @export
#'
#' @examples
#' \dontrun{
#' all_receptors <- get_all_receptors(lr_network)
#' }
get_all_receptors <- function(lr_network) {
  unique(lr_network$to)
}


#' Filter LR Network
#'
#' Filter ligand-receptor network by expression.
#'
#' @param lr_network Ligand-receptor network
#' @param expressed_ligands Vector of expressed ligands
#' @param expressed_receptors Vector of expressed receptors
#'
#' @return Filtered LR network
#' @export
#'
#' @examples
#' \dontrun{
#' lr_filtered <- filter_lr_network(lr_network, sender_genes, receiver_genes)
#' }
filter_lr_network <- function(lr_network, expressed_ligands, expressed_receptors) {
  lr_network %>%
    dplyr::filter(from %in% expressed_ligands, to %in% expressed_receptors)
}


#' Summarize NicheNet Results
#'
#' Create a summary of NicheNet analysis results.
#'
#' @param results NicheNet results list
#'
#' @return Summary string
#' @export
#'
#' @examples
#' \dontrun{
#' cat(summarize_nichenet_results(results))
#' }
summarize_nichenet_results <- function(results) {
  lines <- c(
    "=== NicheNet Analysis Summary ===",
    "",
    sprintf("Sender: %s", paste(results$sender, collapse = ", ")),
    sprintf("Receiver: %s", results$receiver),
    "",
    sprintf("Top 5 Ligands:"),
    paste("  -", head(results$top_ligands, 5), collapse = "\n"),
    "",
    sprintf("Ligand Activities:"),
    sprintf("  - Total ligands tested: %d", nrow(results$ligand_activities)),
    sprintf("  - Top pearson correlation: %.3f", max(results$ligand_activities$pearson)),
    "",
    sprintf("Parameters:"),
    sprintf("  - Organism: %s", results$parameters$organism),
    sprintf("  - Sender genes: %d", results$parameters$n_sender_genes),
    sprintf("  - Receiver genes: %d", results$parameters$n_receiver_genes),
    sprintf("  - Genes of interest: %d", results$parameters$n_geneset)
  )

  if (!is.null(results$condition_oi)) {
    lines <- c(lines, "",
               sprintf("Condition: %s vs %s",
                      results$condition_oi, results$condition_reference))
  }

  return(paste(lines, collapse = "\n"))
}


#' Create Ligand-Target Data Frame
#'
#' Convert ligand_targets list to a data frame.
#'
#' @param ligand_targets List of target genes per ligand
#' @param ligand_activities Optional: activities data frame to merge
#'
#' @return Data frame with ligand-target pairs
#' @export
#'
#' @examples
#' \dontrun{
#' lt_df <- ligand_targets_to_df(results$ligand_targets)
#' }
ligand_targets_to_df <- function(ligand_targets, ligand_activities = NULL) {
  df <- data.frame(
    ligand = rep(names(ligand_targets), sapply(ligand_targets, length)),
    target = unlist(ligand_targets, use.names = FALSE),
    stringsAsFactors = FALSE
  )

  if (!is.null(ligand_activities)) {
    df <- df %>%
      left_join(
        ligand_activities %>% select(test_ligand, pearson),
        by = c("ligand" = "test_ligand")
      )
  }

  return(df)
}


#' Batch NicheNet Analysis
#'
#' Run NicheNet on multiple sender-receiver pairs.
#'
#' @param seurat_obj Seurat object
#' @param cell_type_pairs Data frame with sender and receiver columns
#' @param condition_col Optional: condition column
#' @param condition_oi Optional: condition of interest
#' @param condition_ref Optional: reference condition
#' @param organism "human" or "mouse"
#'
#' @return Named list of results
#' @export
#'
#' @examples
#' \dontrun{
#' pairs <- data.frame(
#'   sender = c("Macrophage", "Macrophage", "DC"),
#'   receiver = c("T_cell", "B_cell", "T_cell")
#' )
#' results <- run_nichenet_batch(seurat_obj, pairs)
#' }
run_nichenet_batch <- function(seurat_obj,
                                cell_type_pairs,
                                condition_col = NULL,
                                condition_oi = NULL,
                                condition_ref = NULL,
                                organism = "human") {

  results <- list()

  for (i in seq_len(nrow(cell_type_pairs))) {
    sender <- cell_type_pairs$sender[i]
    receiver <- cell_type_pairs$receiver[i]

    pair_name <- sprintf("%s_to_%s", sender, receiver)
    message(sprintf("\n[%d/%d] Analyzing: %s", i, nrow(cell_type_pairs), pair_name))

    tryCatch({
      if (!is.null(condition_col)) {
        result <- run_nichenet_aggregate(
          seurat_obj,
          sender = sender,
          receiver = receiver,
          condition_colname = condition_col,
          condition_oi = condition_oi,
          condition_reference = condition_ref,
          organism = organism
        )
      } else {
        # Need genes_of_interest for basic mode
        message("  Note: Skipping basic mode (requires genes_of_interest)")
        next
      }

      results[[pair_name]] <- result

    }, error = function(e) {
      warning(sprintf("Failed for %s: %s", pair_name, e$message))
    })
  }

  message(sprintf("\nCompleted: %d/%d analyses successful", length(results), nrow(cell_type_pairs)))

  return(results)
}


#' Check Gene Symbol Format
#'
#' Check if gene symbols match expected organism format.
#'
#' @param genes Vector of gene symbols
#' @param expected_organism Expected organism: "human" or "mouse"
#'
#' @return List with check results
#' @export
#'
#' @examples
#' \dontrun{
#' check <- check_gene_format(c("IL2", "IFNG"), "human")
#' check <- check_gene_format(c("Il2", "Ifng"), "mouse")
#' }
check_gene_format <- function(genes, expected_organism = c("human", "mouse")) {
  expected_organism <- match.arg(expected_organism)

  # Check capitalization
  all_upper <- sum(genes == toupper(genes))
  all_lower <- sum(genes == tolower(genes))
  mixed_case <- length(genes) - all_upper - all_lower

  # First letter capitalized (typical mouse format)
  first_cap <- sum(substr(genes, 1, 1) == toupper(substr(genes, 1, 1)) &
                    genes != toupper(genes))

  result <- list(
    all_uppercase = all_upper,
    all_lowercase = all_lower,
    mixed_case = mixed_case,
    first_capitalized = first_cap,
    suggestion = NULL
  )

  if (expected_organism == "human" && all_upper < length(genes) * 0.5) {
    result$suggestion <- "Genes appear to be mouse format. Use organism='mouse' or convert to human."
  } else if (expected_organism == "mouse" && first_cap < length(genes) * 0.5) {
    result$suggestion <- "Genes appear to be human format. Use organism='human' or convert to mouse."
  }

  return(result)
}
