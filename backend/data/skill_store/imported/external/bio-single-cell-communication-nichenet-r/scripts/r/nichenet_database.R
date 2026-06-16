#' NicheNet Database Management
#'
#' Auto-download and cache NicheNet databases from Zenodo.
#' Supports human and mouse databases with version management.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

#' Get NicheNet Database Directory
#'
#' Get the directory path for cached NicheNet databases.
#'
#' @return Path to cache directory
#' @keywords internal
.get_nichenet_dir <- function() {
  cache_dir <- file.path(Sys.getenv("HOME"), ".nichenetr")
  if (!dir.exists(cache_dir)) {
    dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  }
  return(cache_dir)
}

#' List Available Databases
#'
#' List all cached NicheNet databases and their status.
#'
#' @return Data frame with database information
#' @export
#'
#' @examples
#' \dontrun{
#' list_nichenet_databases()
#' }
list_nichenet_databases <- function() {
  cache_dir <- .get_nichenet_dir()

  # Define expected databases
  organisms <- c("human", "mouse")
  files <- c("ligand_target_matrix.rds", "lr_network.rds",
             "weighted_networks.rds", "sig_network.rds", "gr_network.rds")

  results <- data.frame(
    organism = character(),
    file = character(),
    cached = logical(),
    size_mb = numeric(),
    modified = character(),
    stringsAsFactors = FALSE
  )

  for (org in organisms) {
    org_dir <- file.path(cache_dir, org)
    for (f in files) {
      file_path <- file.path(org_dir, f)
      if (file.exists(file_path)) {
        info <- file.info(file_path)
        results <- rbind(results, data.frame(
          organism = org,
          file = f,
          cached = TRUE,
          size_mb = round(info$size / 1024 / 1024, 2),
          modified = as.character(info$mtime),
          stringsAsFactors = FALSE
        ))
      } else {
        results <- rbind(results, data.frame(
          organism = org,
          file = f,
          cached = FALSE,
          size_mb = NA,
          modified = NA,
          stringsAsFactors = FALSE
        ))
      }
    }
  }

  return(results)
}

#' Download NicheNet Database
#'
#' Download NicheNet databases from Zenodo and cache locally.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#' @param force Force re-download even if cached (default: FALSE)
#' @param quiet Suppress messages (default: FALSE)
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' download_nichenet_database("human")
#' download_nichenet_database("mouse", force = TRUE)
#' }
download_nichenet_database <- function(organism = c("human", "mouse"),
                                        force = FALSE,
                                        quiet = FALSE) {
  organism <- match.arg(organism)

  # Zenodo URLs (NicheNet v2)
  urls <- list(
    human = list(
      ligand_target_matrix = "https://zenodo.org/record/7074291/files/ligand_target_matrix_nsga2r_final.rds",
      lr_network = "https://zenodo.org/record/7074291/files/lr_network_human_21122021.rds",
      weighted_networks = "https://zenodo.org/record/7074291/files/weighted_networks_nsga2r_final.rds",
      sig_network = "https://zenodo.org/record/7074291/files/signaling_network_human_21122021.rds",
      gr_network = "https://zenodo.org/record/7074291/files/gr_network_human_21122021.rds"
    ),
    mouse = list(
      ligand_target_matrix = "https://zenodo.org/record/7074291/files/ligand_target_matrix_nsga2r_final_mouse.rds",
      lr_network = "https://zenodo.org/record/7074291/files/lr_network_mouse_21122021.rds",
      weighted_networks = "https://zenodo.org/record/7074291/files/weighted_networks_nsga2r_final_mouse.rds",
      sig_network = "https://zenodo.org/record/7074291/files/signaling_network_mouse_21122021.rds",
      gr_network = "https://zenodo.org/record/7074291/files/gr_network_mouse_21122021.rds"
    )
  )

  cache_dir <- .get_nichenet_dir()
  org_dir <- file.path(cache_dir, organism)

  if (!dir.exists(org_dir)) {
    dir.create(org_dir, recursive = TRUE, showWarnings = FALSE)
  }

  if (!quiet) {
    message(sprintf("Downloading NicheNet database for %s...", organism))
  }

  # Download each file
  for (name in names(urls[[organism]])) {
    url <- urls[[organism]][[name]]
    dest_file <- file.path(org_dir, paste0(name, ".rds"))

    if (file.exists(dest_file) && !force) {
      if (!quiet) message(sprintf("  %s: already cached", name))
      next
    }

    if (!quiet) message(sprintf("  Downloading %s...", name))

    tryCatch({
      download.file(url, dest_file, mode = "wb", quiet = quiet)
      if (!quiet) message(sprintf("  %s: downloaded successfully", name))
    }, error = function(e) {
      warning(sprintf("Failed to download %s: %s", name, e$message))
      if (file.exists(dest_file)) file.remove(dest_file)
    })
  }

  if (!quiet) {
    message("Download complete. Use get_ligand_target_matrix() to load.")
  }

  invisible(NULL)
}

#' Get Ligand-Target Matrix
#'
#' Load the ligand-target probability matrix.
#' Auto-downloads if not cached.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#' @param cached Use cached version if available (default: TRUE)
#'
#' @return Ligand-target matrix
#' @export
#'
#' @examples
#' \dontrun{
#' ligand_target_matrix <- get_ligand_target_matrix("human")
#' }
get_ligand_target_matrix <- function(organism = c("human", "mouse"),
                                      cached = TRUE) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  matrix_file <- file.path(cache_dir, organism, "ligand_target_matrix.rds")

  if (!file.exists(matrix_file) || !cached) {
    download_nichenet_database(organism)
  }

  if (!file.exists(matrix_file)) {
    stop(sprintf("Failed to load ligand-target matrix for %s", organism))
  }

  message(sprintf("Loading ligand-target matrix for %s...", organism))
  readRDS(matrix_file)
}

#' Get Ligand-Receptor Network
#'
#' Load the ligand-receptor interaction network.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#'
#' @return Data frame with ligand-receptor pairs
#' @export
#'
#' @examples
#' \dontrun{
#' lr_network <- get_lr_network("human")
#' }
get_lr_network <- function(organism = c("human", "mouse")) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  network_file <- file.path(cache_dir, organism, "lr_network.rds")

  if (!file.exists(network_file)) {
    download_nichenet_database(organism)
  }

  readRDS(network_file)
}

#' Get Weighted Networks
#'
#' Load the weighted signaling and gene regulatory networks.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#'
#' @return List containing weighted networks
#' @export
#'
#' @examples
#' \dontrun{
#' weighted_networks <- get_weighted_networks("human")
#' }
get_weighted_networks <- function(organism = c("human", "mouse")) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  network_file <- file.path(cache_dir, organism, "weighted_networks.rds")

  if (!file.exists(network_file)) {
    download_nichenet_database(organism)
  }

  readRDS(network_file)
}

#' Get Signaling Network
#'
#' Load the signaling network.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#'
#' @return Data frame with signaling interactions
#' @export
get_sig_network <- function(organism = c("human", "mouse")) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  network_file <- file.path(cache_dir, organism, "sig_network.rds")

  if (!file.exists(network_file)) {
    download_nichenet_database(organism)
  }

  readRDS(network_file)
}

#' Get Gene Regulatory Network
#'
#' Load the gene regulatory network.
#'
#' @param organism Organism: "human" or "mouse" (default: "human")
#'
#' @return Data frame with gene regulatory interactions
#' @export
get_gr_network <- function(organism = c("human", "mouse")) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  network_file <- file.path(cache_dir, organism, "gr_network.rds")

  if (!file.exists(network_file)) {
    download_nichenet_database(organism)
  }

  readRDS(network_file)
}

#' Clear Database Cache
#'
#' Remove all cached NicheNet databases.
#'
#' @param confirm Ask for confirmation (default: TRUE)
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' clear_database_cache(confirm = FALSE)
#' }
clear_database_cache <- function(confirm = TRUE) {
  cache_dir <- .get_nichenet_dir()

  if (!dir.exists(cache_dir)) {
    message("No cache directory found.")
    return(invisible(NULL))
  }

  if (confirm) {
    response <- readline("Are you sure you want to clear the NicheNet cache? (yes/no): ")
    if (tolower(response) != "yes") {
      message("Cache clearing cancelled.")
      return(invisible(NULL))
    }
  }

  unlink(cache_dir, recursive = TRUE)
  message("NicheNet cache cleared.")
  invisible(NULL)
}

#' Check Database Status
#'
#' Check if required databases are available.
#'
#' @param organism Organism to check
#' @param verbose Print status messages
#'
#' @return Logical indicating if all databases are available
#' @export
check_nichenet_database <- function(organism = c("human", "mouse"),
                                     verbose = TRUE) {
  organism <- match.arg(organism)

  cache_dir <- .get_nichenet_dir()
  org_dir <- file.path(cache_dir, organism)

  required_files <- c("ligand_target_matrix.rds", "lr_network.rds",
                      "weighted_networks.rds")

  all_present <- TRUE

  for (f in required_files) {
    file_path <- file.path(org_dir, f)
    present <- file.exists(file_path)

    if (verbose) {
      status <- if (present) "✓" else "✗"
      message(sprintf("  %s %s", status, f))
    }

    if (!present) all_present <- FALSE
  }

  if (verbose) {
    if (all_present) {
      message(sprintf("\nAll databases for %s are available.", organism))
    } else {
      message(sprintf("\nSome databases for %s are missing. Run download_nichenet_database().", organism))
    }
  }

  return(all_present)
}
