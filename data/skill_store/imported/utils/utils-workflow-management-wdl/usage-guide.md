# WDL Workflow Architect — Usage Guide

## Overview

This skill enables an LLM agent to convert bioinformatics analysis requirements into strongly-typed, portable WDL workflows. WDL is the language of choice for GATK best practices, Terra/AnVIL cloud platforms, and containerized execution via Cromwell. SLURM execution is supported through Cromwell's HPC backend.

## Prerequisites

```bash
# Install womtool (syntax validation)
wget https://github.com/broadinstitute/cromwell/releases/download/91/womtool-91.jar

# Install Cromwell (full-featured execution engine)
wget https://github.com/broadinstitute/cromwell/releases/download/91/cromwell-91.jar

# Or install miniwdl (lightweight local runner)
pip install miniwdl

# Docker or Singularity for containerized execution
docker --version
singularity --version
```

## How to Prompt the Agent

### Converting Analysis Scripts to WDL

> "I have a variant calling pipeline: BWA-MEM alignment, GATK MarkDuplicates, GATK BaseRecalibrator, GATK HaplotypeCaller. Convert it into a modular WDL workflow with proper structs and scatter blocks."

> "Build an RNA-seq quantification workflow with fastp and Salmon. Use a SampleInfo struct for inputs and generate the inputs.json template."

### Cloud Execution

> "Configure my WDL workflow for execution on Terra with preemptible instances."

> "Set up my WDL workflow to run on Google Cloud through Cromwell."

### SLURM Execution

> "Configure Cromwell to submit WDL tasks to our SLURM cluster with partition 'normal' and account 'bioinfo'."

### Modular Design

> "Refactor this monolithic workflow.wdl into tasks/ directory. Each tool should be its own .wdl file."

> "Add a struct to organize my sample inputs (sample_id, fastq_1, fastq_2, condition)."

### Debugging

> "My WDL workflow failed validation. Help me fix the syntax errors."

> "Generate a minimal inputs.json with only one sample for testing."

## What the Agent Will Do

1. **Decompose** the analysis into granular tasks (one tool = one task)
2. **Design** strongly-typed dataflows using structs and scatter blocks
3. **Generate** a modular project structure with `tasks/`, `workflow.wdl`, and `inputs.json`
4. **Configure** Cromwell backend for Local or SLURM execution
5. **Assign** runtime resources (`cpu`, `memory`, `disks`) based on tool requirements
6. **Validate** via `womtool validate` and provide miniwdl test instructions

## Project Structure (Agent Output)

```
pipeline/
├── workflow.wdl              # Main workflow with imports and scatter
├── tasks/                    # Modular task definitions
│   ├── qc.wdl
│   ├── align.wdl
│   └── quantify.wdl
├── inputs.json               # Input values template
├── inputs_minimal.json       # Single-sample test inputs
├── options.json              # Cromwell runtime options
├── cromwell.conf             # Cromwell backend configuration
└── data/                     # Input data
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Task** | Single command/tool definition with input, output, command, runtime |
| **Workflow** | Orchestration of tasks with data flow |
| **Scatter** | Parallel execution over an array |
| **Struct** | Custom data type for grouping related inputs |
| **Runtime** | Resource and container specification per task |
| **Inputs JSON** | External parameter file providing values for workflow inputs |

## Run Commands

```bash
# --- Validation (ALWAYS run first) ---

# Validate WDL syntax
java -jar womtool.jar validate workflow.wdl

# Generate inputs template
java -jar womtool.jar inputs workflow.wdl > inputs_template.json

# Check with miniwdl
miniwdl check workflow.wdl


# --- Local Execution ---

# Run with Cromwell (Docker required)
java -jar cromwell.jar run workflow.wdl -i inputs.json

# Run with miniwdl (simpler, faster)
miniwdl run workflow.wdl --input inputs.json


# --- SLURM Execution ---

# Run with Cromwell using SLURM backend
java -jar cromwell.jar run workflow.wdl -i inputs.json \
    -Dconfig.file=cromwell.conf \
    -Dbackend.default=SLURM

# With options
java -jar cromwell.jar run workflow.wdl \
    -i inputs.json \
    -o options.json \
    -Dconfig.file=cromwell.conf \
    -Dbackend.default=SLURM \
    -m metadata.json


# --- Cloud Execution (Terra) ---

# Upload workflow.wdl and inputs.json to Terra workspace
# Terra uses Cromwell backend automatically
```

## Execution Engine Selection Guide

| Engine | Best For | SLURM Support | Container |
|--------|----------|---------------|-----------|
| **Cromwell** | Production, cloud, HPC | Yes (via config) | Docker / Singularity |
| **miniwdl** | Local testing, debugging | No | Docker / Singularity |
| **Terra** | Cloud analysis, sharing | N/A (cloud backend) | Docker |

## Tips

- **Always validate first** with `womtool validate` before running. Syntax errors are much easier to fix before execution.
- **Use structs** to organize sample metadata. They make workflows more readable and less error-prone than raw arrays.
- **Calculate disk dynamically** using `ceil(size(inputs)) * factor + buffer`. This prevents "disk full" errors on cloud.
- **Start with miniwdl** for local testing on one sample, then scale to Cromwell + SLURM.
- **Use preemptible instances** (`preemptible: 3` in runtime) for cost savings on Google Cloud / Terra.
- **Enable call caching** in Cromwell for resume capability: `-Dcall-caching.enabled=true`
- **Keep `workflow.wdl` clean**: only imports, structs, workflow inputs, and call statements. All task definitions go in `tasks/*.wdl`.

## Related Skills

- utils-workflow-management-nextflow — Nextflow alternative with native DSL2
- utils-workflow-management-snakemake — Python-based alternative with make-like syntax
- bioinformatics-analysis-* — Domain-specific analysis skills
