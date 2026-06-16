# Species Templates - Usage Guide

## Overview

Select standardized Ribo-seq parameters for your organism to ensure consistent preprocessing, alignment, and P-site calibration.

## Prerequisites

None - this skill provides configuration templates only.

## Quick Start

Tell your AI agent:
- "Set up Ribo-seq parameters for human samples"
- "What are the correct settings for yeast Ribo-seq?"
- "Generate a species config for Arabidopsis"

## Example Prompts

### Parameter Selection

> "Get the Ribo-seq parameter template for yeast"

> "What adapter sequence and footprint size should I use for rice?"

> "Generate a JSON config for mouse Ribo-seq analysis"

## What the Agent Will Do

1. Select the appropriate species template
2. Generate Bash or JSON configuration files
3. Set adapter sequence, read length filters, P-site offsets, and alignment parameters
4. Flag organism-specific requirements (e.g., yeast readthrough, plant organelle filtering)

## Tips

- **Human/mouse** are the defaults for mammalian Ribo-seq
- **Yeast** requires special handling for short 5' UTRs and stop codon readthrough
- **Plants** need aggressive chloroplast rRNA filtering for cytoplasmic Ribo-seq
- Always verify adapter sequence against your actual library prep kit
