#' Skill Registry — Unified dependency resolution for CellClaw pipeline skills
#'
#' Resolution order (deterministic, transparent):
#'   1. Environment variable: CELLCLAW_SKILL_<SKILL_NAME>
#'   2. Registry file: ~/.cellclaw/skills.json
#'   3. Fallback relative path from this script's parent
#'
#' Usage:
#'   source("scripts/r/_skill_registry.R")
#'   data_io_dir <- resolve_skill_path("bio-single-cell-data-io", "scripts/r")
#'   source(file.path(data_io_dir, "samplesheet.R"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

.resolve_env_var_name <- function(skill_name) {
  #' Convert skill name to env var key.
  #' e.g. "bio-single-cell-data-io" -> "CELLCLAW_SKILL_BIO_SINGLE_CELL_DATA_IO"
  toupper(gsub("-", "_", skill_name))
}

.resolve_registry_file <- function() {
  #' Path to the central skills registry JSON.
  env_registry <- Sys.getenv("CELLCLAW_SKILLS_REGISTRY", unset = NA)
  if (!is.na(env_registry)) {
    return(env_registry)
  }
  file.path(path.expand("~"), ".cellclaw", "skills.json")
}

.resolve_from_registry <- function(skill_name, subpath) {
  #' Try to resolve skill path from the central registry file.
  registry_file <- .resolve_registry_file()
  if (!file.exists(registry_file)) {
    return(NULL)
  }

  registry <- tryCatch(
    jsonlite::fromJSON(registry_file),
    error = function(e) NULL
  )
  if (is.null(registry)) {
    return(NULL)
  }

  entry <- registry[[skill_name]]
  if (is.null(entry)) {
    return(NULL)
  }

  # Entry can be a string (path) or a list with 'path' key
  if (is.list(entry) && !is.null(entry$path)) {
    path_str <- entry$path
  } else {
    path_str <- as.character(entry)
  }

  resolved <- file.path(path_str, subpath)
  if (dir.exists(resolved)) {
    return(resolved)
  }
  return(NULL)
}

.resolve_fallback <- function(skill_name, subpath) {
  #' Compute fallback relative path from this script's parent.
  this_file <- sys.frame(1)$ofile
  if (is.null(this_file) || this_file == ".") {
    this_dir <- getwd()
  } else {
    this_dir <- dirname(this_file)
  }
  file.path(this_dir, "..", "..", "..", skill_name, subpath)
}


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

resolve_skill_path <- function(skill_name, subpath = "scripts/r") {
  #' Resolve skill path via env var -> registry file -> relative fallback.
  #'
  #' @param skill_name Skill name, e.g. "bio-single-cell-data-io"
  #' @param subpath Subdirectory to append, e.g. "scripts/r"
  #' @return Absolute path to the skill's scripts directory
  #' @throws Error if none of the three methods succeed

  attempted <- c()

  # 1. Environment variable
  env_key <- paste0("CELLCLAW_SKILL_", .resolve_env_var_name(skill_name))
  env_path <- Sys.getenv(env_key, unset = NA)
  if (!is.na(env_path)) {
    resolved <- file.path(env_path, subpath)
    if (dir.exists(resolved)) {
      return(normalizePath(resolved))
    }
    attempted <- c(attempted, sprintf("Env var %s=%s (directory not found)", env_key, env_path))
  } else {
    attempted <- c(attempted, sprintf("Env var %s (not set)", env_key))
  }

  # 2. Registry file
  registry_path <- .resolve_from_registry(skill_name, subpath)
  if (!is.null(registry_path)) {
    return(normalizePath(registry_path))
  }
  attempted <- c(attempted, sprintf("Registry file %s (missing or no entry)", .resolve_registry_file()))

  # 3. Fallback relative path
  fallback <- .resolve_fallback(skill_name, subpath)
  if (dir.exists(fallback)) {
    return(normalizePath(fallback))
  }
  attempted <- c(attempted, sprintf("Fallback %s (not found)", fallback))

  # None succeeded — raise informative error
  msg <- paste0(
    "Cannot resolve skill '", skill_name, "' (subpath='", subpath, "'). Tried:\n",
    paste(sprintf("  %d. %s", seq_along(attempted), attempted), collapse = "\n"),
    "\n\nFix one of:\n",
    sprintf("  • Sys.setenv(%s = \"/path/to/%s\")\n", env_key, skill_name),
    sprintf("  • Add to ~/.cellclaw/skills.json: {\"%s\": \"/path/to/%s\"}\n", skill_name, skill_name),
    sprintf("  • Ensure %s is checked out at ../../../%s/", skill_name, skill_name)
  )
  stop(msg)
}
