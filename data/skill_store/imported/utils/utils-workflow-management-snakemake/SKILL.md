---
name: utils-workflow-management-snakemake
description: Transform bioinformatics analysis scripts into reproducible Snakemake workflows for SLURM HPC execution. Use when wrapping existing tools/pipelines into rule-based workflows, designing wildcard-driven dataflows, or configuring resource-aware cluster submission. Supports Conda, Singularity, and locally installed software. Compatible with Snakemake 7.x and 8.x.
tool_type: python
primary_tool: Snakemake
measurable_outcome: Generate a valid Snakemake project that passes dry-run validation and is ready for SLURM submission.
allowed-tools:
  - read_file
  - write_file
  - edit_file
  - run_shell_command
---

# Snakemake Workflow Architect

## Role & Goal

You are a senior bioinformatics workflow engineer. Your task is to take existing analysis scripts (shell, R, Python) or a set of bioinformatics tools, and convert them into a maintainable, modular Snakemake workflow that can execute on a SLURM HPC cluster.

Key outcomes:
- The workflow must be modular (rules in `rules/`, orchestration in `Snakefile`)
- The workflow must be environment-agnostic (support Conda, Singularity, or local software via profiles)
- The workflow must be resource-aware (use standardized resource tiers in `resources:`)
- The workflow must be resumable and debuggable (`--rerun-incomplete`, proper logging)

**Version Compatibility:** Snakemake 7.x uses `--cluster` / `--cluster-config`. Snakemake 8.x+ uses `--executor slurm` / `--workflow-profile`. The agent MUST generate configuration appropriate for the target version and clearly distinguish between them.

---

## Workflow Design Logic

### Task Decomposition Rules

When converting an analysis plan into Snakemake, follow these rules:

**Rule 1: One tool invocation = one rule**
- A command like `bwa mem ... | samtools sort ...` should be split into `rule bwa_mem` and `rule samtools_sort`.
- Rationale: Granular rules maximize cache reuse (Snakemake reruns only changed outputs) and allow independent resource allocation.

**Rule 2: Group related rules into separate `.smk` files**
- QC rules → `rules/qc.smk`
- Alignment rules → `rules/align.smk`
- Rationale: Modular rules keep `Snakefile` readable and enable reuse across projects.

**Rule 3: Use wildcards for sample-driven execution**
- Input/output file paths MUST use `{sample}` wildcards, not hardcoded lists.
- The sample list is defined centrally in `config.yaml` and referenced via `config["samples"]`.

### Dataflow Design

**Pattern 1: Centralized sample list (PREFERRED)**

All production workflows MUST define samples in `config.yaml`. Never rely solely on filesystem globbing.

```yaml
# config.yaml
samples:
  SAMPLE1: data/SAMPLE1_R1.fq.gz
  SAMPLE2: data/SAMPLE2_R1.fq.gz
```

```python
# Snakefile
configfile: "config.yaml"
SAMPLES = list(config["samples"].keys())

rule all:
    input:
        expand("results/{sample}.txt", sample=SAMPLES)
```

**Pattern 2: Wildcard chaining across rules**

```python
rule fastp:
    input:
        r1 = "data/{sample}_R1.fq.gz",
        r2 = "data/{sample}_R2.fq.gz"
    output:
        r1 = "trimmed/{sample}_R1.fq.gz",
        r2 = "trimmed/{sample}_R2.fq.gz"
    shell:
        "fastp -i {input.r1} -I {input.r2} -o {output.r1} -O {output.r2}"

rule salmon:
    input:
        r1 = "trimmed/{sample}_R1.fq.gz",
        r2 = "trimmed/{sample}_R2.fq.gz"
    output:
        "salmon/{sample}/quant.sf"
    shell:
        "salmon quant -1 {input.r1} -2 {input.r2} -o salmon/{wildcards.sample}"
```

**Pattern 3: Aggregation with expand()**

```python
rule multiqc:
    input:
        expand("salmon/{sample}/quant.sf", sample=SAMPLES)
    output:
        "results/multiqc_report.html"
    shell:
        "multiqc salmon/ -o results/"
```

### Common Pitfalls

| Pitfall | Why it breaks | Solution |
|---------|---------------|----------|
| Missing `rule all` | Snakemake doesn't know what to build | Always define `rule all` with final targets |
| Wildcard ambiguity | Multiple rules can produce the same wildcard pattern | Ensure output paths are unique across rules |
| Hardcoded sample lists in rules | Breaks portability | Use `config["samples"]` or `SAMPLES` variable |
| Forgetting `expand()` in `rule all` | Only processes the first sample | Wrap aggregation targets in `expand(..., sample=SAMPLES)` |
| `temp()` on files needed for `-rerun-incomplete` | Intermediate files deleted, causing unnecessary reruns | Use `temp()` only for true scratch files; keep meaningful intermediates |
| Output directories without `directory()` | Snakemake treats dirs as files and fails | Wrap directory outputs in `directory("path/")` |

---

## Code Standards

### Mandatory Project Structure

Agent MUST generate files in this structure. No exceptions.

```
project/
├── Snakefile                 # Workflow orchestration ONLY. No rule definitions.
├── config.yaml               # Parameters, sample lists, reference paths
├── envs/                     # Conda environment definitions
│   ├── qc.yaml
│   └── align.yaml
├── rules/                    # Modular rule definitions
│   ├── qc.smk
│   ├── align.smk
│   └── quantify.smk
├── profiles/                 # Execution profiles (Snakemake 8.x)
│   └── slurm/
│       └── config.v8+.yaml
├── cluster.yaml              # Resource config (Snakemake 7.x)
├── scripts/                  # Custom helper scripts
│   └── deseq2.R
├── benchmarks/               # Auto-populated by benchmark directive
├── logs/                     # Auto-populated by log directive
└── data/                     # Input data (gitignored)
```

**Rule:** `Snakefile` contains ONLY `configfile`, `include`, `SAMPLES` definitions, and `rule all`. All rule blocks live in `rules/*.smk`.

### Rule Standards

Every rule file must follow this template:

```python
# rules/qc.smk
rule fastp:
    input:
        r1 = "data/{sample}_R1.fq.gz",
        r2 = "data/{sample}_R2.fq.gz"
    output:
        r1 = "trimmed/{sample}_R1.fq.gz",
        r2 = "trimmed/{sample}_R2.fq.gz",
        json = "qc/{sample}_fastp.json"
    log:
        "logs/fastp/{sample}.log"
    benchmark:
        "benchmarks/fastp/{sample}.tsv"
    threads: 4
    resources:
        mem_mb = 8000,
        runtime = 60
    conda:
        "envs/qc.yaml"
    # container: "docker://quay.io/biocontainers/fastp:0.23.4"
    shell:
        "(fastp -i {input.r1} -I {input.r2} "
        "-o {output.r1} -O {output.r2} "
        "--json {output.json} --thread {threads}) "
        "2> {log}"
```

**Required directives per rule:**
- `input:` and `output:` with wildcard patterns
- `log:` — for debugging failed rules
- `benchmark:` — for performance tracking
- `threads:` — for parallel tool invocation
- `resources:` — `mem_mb`, `runtime` (minutes) for cluster scheduling
- `conda:` or `container:` — environment specification

### Parameterization Rules

All user-configurable values must be in `config.yaml`:

```yaml
# config.yaml
samples:
  SAMPLE1: data/SAMPLE1
  SAMPLE2: data/SAMPLE2

reference:
  genome: "ref/hg38.fa"
  index: "ref/hg38_bwa"

params:
  fastp_args: ""
  salmon_args: "--validateMappings"

resources:
  default_threads: 4
  default_mem_mb: 4000
```

**Rule:** Access config values in rules via `config["key"]` or `configfile:` directive.

### Environment Strategy

The workflow MUST support three execution modes. The agent must generate config that enables all three.

| Strategy | When to use | Snakemake flag |
|----------|-------------|----------------|
| **Conda** (default for HPC without root) | Conda/mamba available | `--use-conda` |
| **Singularity** | HPC has Singularity/Apptainer | `--use-singularity --singularity-prefix /scratch/...` |
| **Local/Module** | Software pre-installed via `module load` | No flag; use `envmodules:` or prepend `module load` to shell |

**Rule for rule definitions:**
- Prefer `conda:` directive with pinned versions
- Provide `container:` as an alternative (commented out)
- If using local installation, omit both and ensure tools are in PATH or loaded via module

```python
rule fastp:
    conda: "envs/qc.yaml"
    # container: "docker://quay.io/biocontainers/fastp:0.23.4"
    # If using local installation, omit both above
    ...
```

---

## Environment Configuration

### Snakemake 8.x+ SLURM Profile (Modern / Recommended)

Agent MUST generate a `profiles/slurm/config.v8+.yaml` for Snakemake 8.x+ users.

```yaml
# profiles/slurm/config.v8+.yaml
executor: slurm
jobs: 100

# Default resources
resources:
  mem_mb: 4000
  runtime: 60

default-resources:
  mem_mb: 4000
  runtime: 60
  slurm_partition: normal

# Rule-specific resources
set-resources:
  fastp:
    mem_mb: 8000
    runtime: 60
    slurm_partition: normal
    cpus_per_task: 4
  salmon_quant:
    mem_mb: 32000
    runtime: 240
    slurm_partition: normal
    cpus_per_task: 8
  star_align:
    mem_mb: 64000
    runtime: 480
    slurm_partition: long
    cpus_per_task: 16

# Command modifiers
set-threads:
  fastp: 4
  salmon_quant: 8
  star_align: 16

# Restart behavior
restart-times: 1
rerun-incomplete: true
keep-going: true
latency-wait: 60

# Conda / Singularity
use-conda: true
conda-prefix: /scratch/$USER/conda-envs
# use-singularity: true
# singularity-prefix: /scratch/$USER/singularity-images
```

**Run command (v8):**
```bash
snakemake --workflow-profile profiles/slurm --use-conda
```

### Snakemake 7.x SLURM Configuration (Legacy)

For environments still on Snakemake 7.x, generate `cluster.yaml`:

```yaml
# cluster.yaml
__default__:
    partition: normal
    time: "1:00:00"
    mem: 4G
    cpus-per-task: 2

fastp:
    partition: normal
    time: "1:00:00"
    mem: 8G
    cpus-per-task: 4

salmon_quant:
    partition: normal
    time: "4:00:00"
    mem: 32G
    cpus-per-task: 8

star_align:
    partition: long
    time: "8:00:00"
    mem: 64G
    cpus-per-task: 16
```

**Run command (v7):**
```bash
snakemake --cluster "sbatch --partition={cluster.partition} \
    --time={cluster.time} --mem={cluster.mem} \
    --cpus-per-task={cluster.cpus-per-task}" \
    --cluster-config cluster.yaml \
    --jobs 100 --use-conda
```

### Resource Tier Assignment Guide

Agent must assign `resources:` based on the tool's known requirements:

| mem_mb | runtime | cpus | Typical tools | Label equivalent |
|--------|---------|------|---------------|------------------|
| 4000 | 60 min | 1-2 | FastQC, samtools index, MultiQC | process_low |
| 8000 | 120 min | 4 | fastp, picard MarkDuplicates | process_medium |
| 32000 | 240 min | 8 | BWA-MEM, salmon quant, HISAT2 | process_medium |
| 64000 | 480 min | 16 | STAR align, GATK HaplotypeCaller (WGS) | process_high |
| 128000 | 480 min | 8 | Cell Ranger, large assembly | process_high_memory |

---

## Error Handling & Resume

### Rule-Level Resilience

```python
rule unstable_tool:
    output:
        "results/{sample}.txt"
    resources:
        mem_mb = lambda wildcards, attempt: 16000 * attempt
    retries: 2
    shell:
        "unstable_tool {wildcards.sample} > {output}"
```

### Resume Protocol

Snakemake has built-in resume via file timestamps. Always use these flags:

```bash
# Resume incomplete jobs after failure
snakemake --rerun-incomplete ...

# Keep going on independent jobs if one fails
snakemake --keep-going ...

# Force rerun of a specific rule
snakemake --forcerun salmon_quant ...

# Touch outputs to mark as complete (manual override)
snakemake --touch ...
```

---

## Debugging & Validation Protocol

Agent must guide the user through this validation sequence before full-scale execution:

1. **Dry run** — verify DAG and rule dependencies without executing:
   ```bash
   snakemake -n --dry-run
   # or with profile
   snakemake -n --workflow-profile profiles/slurm
   ```

2. **DAG visualization** — inspect the workflow graph:
   ```bash
   snakemake --dag | dot -Tpdf > dag.pdf
   ```

3. **Single-sample test** — run on one sample to catch tool-specific errors:
   ```bash
   # Edit config.yaml to contain only 1 sample, then:
   snakemake --workflow-profile profiles/slurm --use-conda --jobs 1
   ```

4. **Inspect failures** — if a rule fails:
   - Read `logs/{rule}/{sample}.log` for tool stderr
   - Check `benchmarks/{rule}/{sample}.tsv` for resource usage
   - Run with `--printshellcmds` to see exact commands

5. **Detailed execution report**:
   ```bash
   snakemake --report report.html
   ```

---

## Common Errors and Fixes

| Error | Root Cause | Fix |
|-------|------------|-----|
| `MissingRuleException` | Target file not matched by any rule | Check wildcard patterns and file names |
| `CyclicGraphException` | Circular dependency | Review rule input/output relationships |
| `ProtectedOutputException` | Trying to overwrite protected file | Remove `protected()` wrapper or delete manually |
| `Job failed with exit code` | Tool error in rule | Check `logs/{rule}/{sample}.log` |
| `DAG has no jobs` | All outputs already exist | Use `--forcerun` or delete outputs |
| `SLURM job submission failed` | Invalid partition or resource request | Check `cluster.yaml` / profile config matches cluster |
| `Disk quota exceeded` | Work directory or conda env on `$HOME` | Move `--conda-prefix` and output dirs to `/scratch` |

---

## Example Files

See `examples/` directory for a complete, modular RNA-seq workflow that follows all standards above:
- `examples/Snakefile` — workflow orchestration
- `examples/rules/*.smk` — rule modules
- `examples/config.yaml` — parameterized configuration
- `examples/envs/*.yaml` — conda environment definitions
- `examples/profiles/slurm/` — SLURM execution profile (v8)
- `examples/cluster.yaml` — SLURM resource config (v7)

## Related Skills

- utils-workflow-management-nextflow — Nextflow alternative
- utils-workflow-management-wdl — WDL alternative
- bioinformatics-analysis-* — Specific analysis domains
