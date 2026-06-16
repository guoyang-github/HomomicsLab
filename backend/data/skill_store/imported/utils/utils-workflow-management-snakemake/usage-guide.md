# Snakemake Workflow Architect — Usage Guide

## Overview

This skill enables an LLM agent to convert bioinformatics analysis requirements into reproducible Snakemake workflows optimized for SLURM HPC clusters. It supports Conda, Singularity, and locally installed software environments. Compatible with both Snakemake 7.x and 8.x.

## Prerequisites

```bash
# Install Snakemake (v8.x recommended)
pip install snakemake

# For Snakemake 8.x SLURM execution
pip install snakemake-executor-plugin-slurm

# For Snakemake 7.x (legacy cluster mode)
pip install snakemake

# Verify version
snakemake --version
```

## How to Prompt the Agent

### Converting Analysis Scripts to Snakemake

> "I have a shell script that runs fastp for trimming, then salmon for quantification, then multiqc for reporting. Convert it into a modular Snakemake workflow with SLURM support. We use Snakemake 8.x."

> "Wrap this variant calling pipeline (BWA-MEM → GATK MarkDuplicates → GATK HaplotypeCaller) into a Snakemake workflow. Use Conda environments and assign appropriate resources for our SLURM cluster."

### SLURM Configuration

> "Configure my Snakemake workflow to run on our SLURM cluster with partition 'normal', account 'bioinfo', using Conda. We are on Snakemake 8.x."

> "My HPC doesn't have Conda. Set up the workflow to use Singularity containers instead, with images cached in /scratch/$USER/singularity-images."

> "Our software is pre-installed via module load. Configure the workflow for local execution on SLURM without containers or Conda."

### Modular Design

> "Refactor this monolithic Snakefile into rules/ directory. Each tool should be its own .smk file."

> "Add benchmark and logging directives to every rule in my workflow."

### Debugging

> "My workflow failed on sample 5. How do I find the error log and resume from where it left off?"

> "Run a dry-run on my workflow to verify the DAG before submitting to the cluster."

## What the Agent Will Do

1. **Decompose** the analysis into granular rules (one tool = one rule)
2. **Design** wildcard-driven dataflows using centralized `config.yaml`
3. **Generate** a modular project structure with `rules/`, `envs/`, and `Snakefile`
4. **Configure** SLURM execution for Snakemake 7.x (`cluster.yaml`) or 8.x (`profiles/slurm/`)
5. **Assign** resource tiers (`mem_mb`, `runtime`, `threads`) based on tool requirements
6. **Validate** via dry-run and provide single-sample test instructions

## Project Structure (Agent Output)

```
pipeline/
├── Snakefile                 # Workflow orchestration only
├── config.yaml               # Parameters, samples, references
├── envs/                     # Conda environment files
│   ├── qc.yaml
│   └── align.yaml
├── rules/                    # Modular rule definitions
│   ├── qc.smk
│   ├── align.smk
│   └── quantify.smk
├── profiles/                 # Snakemake 8.x execution profiles
│   └── slurm/
│       └── config.v8+.yaml
├── cluster.yaml              # Snakemake 7.x resource config
├── scripts/                  # Custom helper scripts
├── benchmarks/               # Auto-populated performance data
├── logs/                     # Auto-populated execution logs
└── data/                     # Input data
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Rule** | Single processing step with input/output wildcards |
| **Wildcard** | Variable in file paths (e.g., `{sample}`) |
| **Expand** | Generate file lists for all samples |
| **DAG** | Directed acyclic graph of rule dependencies |
| **Profile** | Execution configuration (local, slurm, etc.) |
| **Benchmark** | Performance tracking directive per rule |

## Run Commands

```bash
# --- Validation (ALWAYS run first) ---

# Dry run: verify DAG without executing
snakemake -n
snakemake -n --workflow-profile profiles/slurm

# DAG visualization
snakemake --dag | dot -Tpdf > dag.pdf


# --- Local Execution ---

# Run with 8 cores locally
snakemake --cores 8 --use-conda

# Run with Singularity locally
snakemake --cores 8 --use-singularity --use-conda


# --- SLURM Execution (Snakemake 8.x) ---

# Submit to SLURM with profile
snakemake --workflow-profile profiles/slurm --use-conda

# Limit concurrent jobs
snakemake --workflow-profile profiles/slurm --use-conda --jobs 50


# --- SLURM Execution (Snakemake 7.x) ---

# Submit to SLURM with cluster config
snakemake --cluster "sbatch --partition={cluster.partition} \
    --time={cluster.time} --mem={cluster.mem} \
    --cpus-per-task={cluster.cpus-per-task}" \
    --cluster-config cluster.yaml \
    --jobs 100 --use-conda


# --- Resume and Debugging ---

# Resume incomplete jobs after failure
snakemake --rerun-incomplete ...

# Keep going on independent jobs if one fails
snakemake --keep-going ...

# Force rerun of specific rule
snakemake --forcerun salmon_quant ...

# Generate execution report
snakemake --report report.html

# Print all shell commands (verbose)
snakemake --printshellcmds ...
```

## Environment Selection Guide

| Your HPC Setup | Flags to Use | Prerequisites |
|----------------|--------------|---------------|
| Conda available | `--use-conda` | `conda --version` works |
| Singularity/Apptainer | `--use-singularity --use-conda` | `singularity --version` works |
| Software via `module load` | No env flags; add `module load` to shell blocks | All tools in PATH |

## Version-Specific Notes

| Feature | Snakemake 7.x | Snakemake 8.x+ |
|---------|---------------|----------------|
| SLURM execution | `--cluster "sbatch ..." --cluster-config` | `--executor slurm` or `--workflow-profile` |
| Profile location | `~/.config/snakemake/` | `profiles/` directory |
| Resource config | `cluster.yaml` | `profiles/slurm/config.v8+.yaml` |
| Plugin required | No | `snakemake-executor-plugin-slurm` |

## Tips

- **Always run `-n` first** before submitting to the cluster. It catches DAG errors in seconds.
- **Use `--rerun-incomplete`** for production runs. It resumes failed jobs without redoing completed ones.
- **Set `--conda-prefix`** to scratch: `--conda-prefix /scratch/$USER/conda-envs`
- **Start with 1 sample** in `config.yaml` to validate tool behavior before scaling.
- **Add `benchmark:` to every rule** to collect performance data for future resource optimization.
- **Use `directory()`** for outputs that are directories (e.g., salmon index, cell ranger output).
- **Keep `Snakefile` clean**: only `configfile`, `include`, `SAMPLES`, and `rule all`.

## Related Skills

- utils-workflow-management-nextflow — Nextflow alternative
- utils-workflow-management-wdl — WDL alternative
- bioinformatics-analysis-* — Domain-specific analysis skills
