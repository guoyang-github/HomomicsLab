#!/bin/bash
set -euo pipefail
# Example: Generate species-specific configuration for Ribo-seq analysis
# Usage: bash generate_config.sh [SPECIES]
# Supported species: human, mouse, yeast, arabidopsis, rice

SPECIES="${1:-human}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/../scripts/generate_species_config.sh" "$SPECIES" > "${SPECIES}_config.sh"

echo "Species config saved to ${SPECIES}_config.sh"
echo "Load it with: source ${SPECIES}_config.sh"
