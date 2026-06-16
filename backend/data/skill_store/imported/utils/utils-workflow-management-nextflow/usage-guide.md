# Nextflow Workflow Architect — Usage Guide

## Overview

This skill enables an LLM agent to convert bioinformatics analysis requirements into production-grade Nextflow DSL2 workflows optimized for SLURM HPC clusters. It supports Singularity, Conda, and locally installed software environments.

## Prerequisites

```bash
# Install Nextflow
curl -s https://get.nextflow.io | bash
chmod +x nextflow
mv nextflow ~/.local/bin/   # or any directory in $PATH

# Verify
nextflow -version

# For Singularity/Apptainer (default HPC mode)
# Usually pre-installed on HPC; verify with:
singularity --version

# For Conda fallback
conda --version

# For nf-core modules (optional but recommended)
pip install nf-core
```

## How to Prompt the Agent

### Converting Analysis Scripts to Nextflow

> "I have a shell script that runs fastp for trimming, then salmon for quantification, then multiqc for reporting. Convert it into a modular Nextflow pipeline with SLURM support."

> "Wrap this variant calling pipeline (BWA-MEM → GATK MarkDuplicates → GATK HaplotypeCaller) into a Nextflow workflow. Use Singularity containers and assign appropriate resource labels."

### SLURM Configuration

> "Configure my pipeline to run on our SLURM cluster with queue 'normal', account 'bioinfo', and use Singularity from /scratch/shared/singularity-cache."

> "My HPC doesn't have Singularity. Set up the pipeline to use Conda environments instead, with environments stored in /scratch/$USER/conda-envs."

> "Our software is pre-installed via module load. Configure the pipeline for local execution on SLURM without containers or Conda."

### Modular Design

> "Refactor this monolithic main.nf into modules/ and subworkflows/. Each tool should be its own module file."

> "Install the nf-core fastp and star_align modules into my pipeline instead of writing custom processes."

### Debugging

> "My pipeline failed on sample 5. How do I find the error log and resume from where it left off?"

> "Run a stub test on my pipeline to verify the channel wiring before submitting to the cluster."

## What the Agent Will Do

1. **Decompose** the analysis into granular processes (one tool = one process)
2. **Design** channel dataflows using samplesheet-driven input and `meta` map propagation
3. **Generate** a modular project structure with `modules/local/`, `subworkflows/`, and `main.nf`
4. **Configure** `nextflow.config` with SLURM profiles supporting Singularity, Conda, and local software
5. **Assign** resource labels (`process_low`, `process_medium`, `process_high`, etc.) based on tool requirements
6. **Validate** via `-stub-run` and provide single-sample dry-run instructions

## Project Structure (Agent Output)

```
pipeline/
├── main.nf                 # Workflow orchestration only
├── nextflow.config         # Global config with SLURM profiles
├── conf/
│   └── slurm.config        # SLURM-specific overrides (optional)
├── modules/
│   ├── local/              # Custom process modules
│   └── nf-core/            # Installed nf-core modules (if used)
├── subworkflows/           # Logical groupings of processes
├── bin/                    # Custom helper scripts
├── assets/                 # Bundled reference files
└── samplesheet.csv         # Input manifest
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Process** | Single execution unit (one bioinformatics tool) |
| **Channel** | Data flow carrying files/metadata between processes |
| **Module** | Reusable process definition in a separate `.nf` file |
| **Subworkflow** | Logical grouping of modules (e.g., QC, Alignment) |
| **Profile** | Execution environment configuration (slurm, slurm_conda, slurm_local, debug) |
| **Label** | Resource tier assigned to a process for scheduler allocation |
| **Meta map** | `[id: sample, single_end: bool]` carrying sample metadata through channels |

## Run Commands

```bash
# --- Validation (ALWAYS run first) ---

# Syntax and channel wiring check (no real execution)
nextflow run main.nf -stub-run -profile slurm --input samplesheet.csv

# Dry run on 1 sample
nextflow run main.nf -profile slurm,debug --input samplesheet_1sample.csv


# --- Production Execution ---

# SLURM with Singularity (default HPC)
nextflow run main.nf -profile slurm --input samplesheet.csv -resume

# SLURM with Conda (no Singularity available)
nextflow run main.nf -profile slurm_conda --input samplesheet.csv -resume

# SLURM with locally installed software (module load)
nextflow run main.nf -profile slurm_local --input samplesheet.csv -resume

# Local execution (testing on login node — avoid for real jobs)
nextflow run main.nf -profile standard --input samplesheet.csv


# --- Monitoring and Debugging ---

# Generate execution report
nextflow run main.nf -profile slurm --input samplesheet.csv -with-report report.html -with-timeline timeline.html -with-trace trace.txt

# Resume after failure
nextflow run main.nf -profile slurm --input samplesheet.csv -resume

# Clean work directories older than today
nextflow clean -f -before $(date -I)

# View execution history
nextflow log
```

## Environment Selection Guide

| Your HPC Setup | Profile to Use | Prerequisites |
|----------------|----------------|---------------|
| Singularity/Apptainer available | `slurm` | `singularity --version` works |
| No containers, but conda/mamba | `slurm_conda` | `conda --version` works |
| Software via `module load` or system | `slurm_local` | All tools in PATH or loaded via `process.beforeScript` |

## Tips

- **Always run `-stub-run` first** before submitting to the cluster. It catches syntax and wiring errors in seconds.
- **Always use `-resume`** for production runs. Nextflow's caching saves hours of compute on re-runs.
- **Set `workDir` to scratch** in `nextflow.config`. Never use `$HOME` — work directories can grow to hundreds of GB.
- **Pre-pull Singularity images** if your cluster has no internet on compute nodes:
  ```bash
  singularity pull /scratch/$USER/singularity-cache/fastp.sif docker://quay.io/biocontainers/fastp:0.23.4--hadf994f_2
  ```
- **Start with 1 sample** (`debug` profile) to validate tool behavior before scaling to hundreds.
- **Use `task.ext.args`** in process scripts to make tools configurable via `nextflow.config` without editing the module.

## Related Skills

- utils-workflow-management-snakemake — Python-based workflow alternative
- utils-workflow-management-wdl — WDL alternative
- bioinformatics-analysis-* — Domain-specific analysis skills (alignment, variant calling, RNA-seq, etc.)
