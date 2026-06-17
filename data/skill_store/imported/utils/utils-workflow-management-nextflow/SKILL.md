---
name: utils-workflow-management-nextflow
description: Transform bioinformatics analysis scripts into production-grade Nextflow DSL2 workflows for SLURM HPC execution. Use when wrapping existing tools/pipelines into portable workflows, designing channel dataflows, or configuring resource-aware cluster submission. Supports Singularity, Conda, and locally installed software.
tool_type: cli
primary_tool: Nextflow
measurable_outcome: Generate a valid Nextflow project that passes -stub-run validation and is ready for SLURM submission.
allowed-tools:
  - read_file
  - write_file
  - edit_file
  - run_shell_command
---

# Nextflow Workflow Architect

## Role & Goal

You are a senior bioinformatics workflow engineer. Your task is to take existing analysis scripts (shell, R, Python) or a set of bioinformatics tools, and convert them into a maintainable, modular Nextflow DSL2 pipeline that can execute on a SLURM HPC cluster.

Key outcomes:
- The pipeline must be modular (processes in `modules/`, orchestration in `main.nf`)
- The pipeline must be environment-agnostic (support Singularity, Conda, or local software via profiles)
- The pipeline must be resource-aware (use label-based resource tiers)
- The pipeline must be resumable and debuggable

---

## Workflow Design Logic

### Task Decomposition Rules

When converting an analysis plan into Nextflow, follow these rules:

**Rule 1: One tool invocation = one process**
- A command like `bwa mem ... | samtools sort ...` should be split into `BWA_MEM` and `SAMTOOLS_SORT`.
- Rationale: Granular processes maximize cache reuse and allow independent resource allocation.

**Rule 1a: One cacheable computation = one process (for scripts)**
- When the input is an R or Python script (not a command-line tool), apply the same
  granularity principle by looking at *cacheable file outputs*:
  - If a script produces intermediate files that downstream steps consume → split
    into multiple processes at file boundaries.
  - If a script is a pure in-memory pipeline (read → analyze → plot) with no
    reusable intermediates → keep as a single process.
  - If a script mixes command-line tool calls with custom code → extract tool calls
    into their own processes; wrap the remaining script code as one or more processes
    using the same file-output rule.
- Rationale: Nextflow caches at the process level. Splitting at file boundaries
  maximizes `-resume` efficiency.

**Rule 2: Group related processes into subworkflows**
- QC steps (FastQC + MultiQC) → `subworkflows/qc.nf`
- Alignment steps (BWA + sorting + marking duplicates) → `subworkflows/align.nf`
- Rationale: Subworkflows make `main.nf` readable and enable reuse across projects.

**Rule 3: Inputs and outputs must be strictly typed**
- Always use `tuple val(meta), path(files)` where `meta` is a map containing at least `id`.
- Example: `tuple val(meta), path(reads)` where `meta = [id: 'sample1', single_end: false]`
- Rationale: The `meta` map carries sample metadata through the pipeline without losing context.

### Channel Dataflow Design

**Pattern 1: Samplesheet-driven input (PREFERRED)**

All production pipelines MUST accept a CSV samplesheet. Never rely solely on file globbing.

```groovy
// main.nf
Channel.fromPath(params.input)
    .splitCsv(header: true, sep: ',')
    .map { row ->
        def meta = [id: row.sample, single_end: row.fastq_2 ? false : true]
        def reads = row.fastq_2 ? [file(row.fastq_1), file(row.fastq_2)] : [file(row.fastq_1)]
        [meta, reads]
    }
    .set { reads_ch }
```

```csv
// samplesheet.csv
sample,fastq_1,fastq_2,strandedness
SAMPLE1,/data/S1_R1.fq.gz,/data/S1_R2.fq.gz,auto
SAMPLE2,/data/S2_R1.fq.gz,,reverse
```

**Pattern 2: Process output chaining**

```groovy
workflow {
    FASTP(reads_ch)                    // emits: reads, json
    SALMON(FASTP.out.reads, index_ch)  // emits: quant
    MULTIQC(FASTP.out.json.mix(SALMON.out.quant).collect())
}
```

**Pattern 3: Reference/index broadcasting**

```groovy
// Reference files should be broadcast with .first() or .collect()
index_ch = Channel.fromPath(params.salmon_index, checkIfExists: true).first()
SALMON(FASTP.out.reads, index_ch)
```

### Common Pitfalls

| Pitfall | Why it breaks | Solution |
|---------|---------------|----------|
| `collect()` on large channels | Pulls all items into one list, causing memory blow-up or blocking | Only use for aggregation steps (e.g., MultiQC). For pairing, use `join()` or `combine()` |
| `Channel.fromFilePairs` without `checkIfExists` | Silent empty channels if path is wrong | Always add `checkIfExists: true` |
| Missing `meta` in output tuple | Downstream processes lose sample ID | Always propagate `tuple val(meta), path(...)` |
| `publishDir` with `mode: 'move'` | Breaks `-resume` because work dir files disappear | Always use `mode: 'copy'` or `mode: 'symlink'` |
| Hardcoded paths in scripts | Breaks portability | Use `params.` for all paths; use `projectDir` for bundled assets |

---

## Code Standards

### Mandatory Project Structure

Agent MUST generate files in this structure. No exceptions.

```
project/
├── main.nf                 # Workflow orchestration ONLY. No process definitions.
├── nextflow.config         # Global params + profile definitions
├── conf/
│   └── slurm.config        # SLURM-specific settings (optional but recommended)
├── modules/
│   ├── local/              # Custom process modules written by agent
│   │   ├── fastp.nf
│   │   └── salmon.nf
│   └── nf-core/            # Installed nf-core modules (if used)
│       └── fastp/
│           └── main.nf
├── subworkflows/
│   ├── qc.nf
│   └── quantification.nf
├── bin/                    # Custom helper scripts (auto-added to PATH)
│   └── custom_parser.py
├── assets/                 # Reference files, adapters bundled with pipeline
│   └── adapters.fa
└── samplesheet.csv         # Input manifest
```

**Rule:** `main.nf` contains ONLY `include`, `workflow`, and `workflow.onComplete`. All `process` blocks live in `modules/local/*.nf` or `modules/nf-core/*`.

### Module Standards

Every module file must follow this template:

```groovy
// modules/local/fastp.nf
process FASTP {
    tag "${meta.id}"
    label 'process_medium'

    // Environment: ONE of container, conda, or neither (local)
    container 'quay.io/biocontainers/fastp:0.23.4--hadf994f_2'
    // conda 'bioconda::fastp=0.23.4'

    publishDir "${params.outdir}/fastp", mode: 'copy', pattern: '*.fq.gz'
    publishDir "${params.outdir}/fastp", mode: 'copy', pattern: '*.json'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.trimmed.fq.gz'), emit: reads
    path('*.fastp.json'), emit: json

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    if (meta.single_end) {
        """
        fastp \
            -i ${reads[0]} \
            -o ${prefix}_trimmed.fq.gz \
            --json ${prefix}.fastp.json \
            --thread ${task.cpus} \
            ${args}
        """
    } else {
        """
        fastp \
            -i ${reads[0]} -I ${reads[1]} \
            -o ${prefix}_trimmed_1.fq.gz -O ${prefix}_trimmed_2.fq.gz \
            --json ${prefix}.fastp.json \
            --thread ${task.cpus} \
            ${args}
        """
    }
}
```

**Required directives per process:**
- `tag` — for readable log output
- `label` — for resource allocation (see Resource Label Strategy below)
- `publishDir` — with `mode: 'copy'`
- `input:` and `output:` with named `emit:` channels
- `script:` with `task.ext.args` and `task.ext.prefix` for extensibility

### nf-core Module Strategy

When the analysis requires a standard bioinformatics tool (e.g., fastp, STAR, samtools),
Agent MUST check nf-core availability before writing a local module:

1. **Search nf-core remote modules** for the tool: `nf-core modules list remote | grep <tool>`.
2. **If the tool exists in nf-core AND its inputs/outputs match the pipeline's channel
   contract** (`tuple val(meta), path(...)`):
   - Install it: `nf-core modules install <tool>`.
   - Reference it in `main.nf`:
     ```groovy
     include { FASTP } from './modules/nf-core/fastp/main'
     ```
3. **If the tool is not in nf-core OR its channel contract is incompatible** (e.g.,
   lacks `meta` map, uses different output names):
   - Write a local module in `modules/local/<tool>.nf` following the template above.

**Rationale:** nf-core modules are community-tested, version-pinned, and follow
consistent conventions. Reusing them reduces maintenance burden. Only fall back to
local modules when nf-core cannot satisfy the pipeline's channel contract.

### Script-based Processes (R / Python)

When wrapping R or Python scripts:

1. **Place the script in `bin/`** — it is automatically added to `PATH`.
2. **Parameterize all I/O paths** via `argparse` or `commandArgs()`; never hardcode.
3. **Design for single-sample execution** — Nextflow handles parallelization via
   channels. The script should process one sample/task per invocation.
4. **Use `meta.id` to prefix outputs** — prevents filename collisions when multiple
   tasks run in parallel.
5. **Exit with non-zero status on failure** — enables Nextflow's error handling and
   retry logic.

```groovy
// modules/local/deseq2.nf
process DESEQ2 {
    tag "${meta.id}"
    label 'process_medium'

    container 'bioconductor/deseq2:1.40.0'
    // conda 'bioconda::bioconductor-deseq2=1.40.0'

    publishDir "${params.outdir}/deseq2", mode: 'copy'

    input:
    tuple val(meta), path(counts_matrix)

    output:
    path('*.results.csv'), emit: results
    path('*.plots.pdf'), emit: plots

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    run_deseq2.R \\
        --input ${counts_matrix} \\
        --sample ${meta.id} \\
        --outprefix ${prefix}
    """
}
```

### Parameterization Rules

All user-configurable values must be params:

```groovy
// nextflow.config
params {
    input = null                    // REQUIRED: samplesheet path
    outdir = 'results'
    
    // Reference data
    genome = null
    index = null
    
    // Tool-specific options
    fastp_args = ''
    salmon_args = '--validateMappings'
    
    // Environment overrides
    workdir = "/scratch/$USER/nextflow-work"
    singularity_cachedir = "/scratch/$USER/singularity-cache"
    conda_cachedir = "/scratch/$USER/conda-cache"
}
```

**Rule:** If a parameter is required, set it to `null`. Nextflow will fail fast with a clear error if the user forgets to provide it.

### Environment Strategy

The pipeline MUST support three execution modes via profiles. The agent must generate config that enables all three.

| Strategy | When to use | How to configure |
|----------|-------------|------------------|
| **Singularity** (default for HPC) | HPC has Singularity/Apptainer | `singularity.enabled = true; singularity.autoMounts = true` |
| **Conda** | No container runtime, but conda/mamba available | `conda.enabled = true` |
| **Local/Module** | Software pre-installed via `module load` or system-wide | Neither enabled; use `process.beforeScript = 'module load ...'` |

**Rule for process definitions:**
- Prefer providing a `container` directive on each process (Docker/Singularity image path)
- Comment out `conda` as a fallback alternative
- If the target environment requires local software, remove both and document requirements

```groovy
process FASTP {
    container 'quay.io/biocontainers/fastp:0.23.4--hadf994f_2'
    // conda 'bioconda::fastp=0.23.4'
    // If using local installation, omit both and ensure fastp is in PATH
    ...
}
```

---

## Environment Configuration

### SLURM Profile (Production Template)

Agent MUST generate a `nextflow.config` that includes this SLURM profile. Adapt queue names and paths to the target cluster.

```groovy
// nextflow.config
manifest {
    name = 'pipeline-name'
    author = 'Generated by Agent'
    description = 'Bioinformatics workflow'
    version = '1.0.0'
    nextflowVersion = '>=23.04.0'
}

params {
    input = null
    outdir = 'results'
    workdir = "/scratch/$USER/nextflow-work"
    singularity_cachedir = "/scratch/$USER/singularity-cache"
    conda_cachedir = "/scratch/$USER/conda-cache"
}

profiles {
    standard {
        process.executor = 'local'
    }
    
    slurm {
        process.executor = 'slurm'
        process.clusterOptions = '--export=ALL'
        
        // CRITICAL: workDir must be on scratch, never $HOME
        workDir = params.workdir
        
        // Default Singularity setup
        singularity.enabled = true
        singularity.cacheDir = params.singularity_cachedir
        singularity.autoMounts = true
        
        // Conda cache (used if conda profile is mixed in)
        conda.cacheDir = params.conda_cachedir
        
        // Resource tiers — agent MUST assign appropriate labels
        process {
            withLabel: 'process_single' {
                cpus = 1
                memory = '4 GB'
                time = '2h'
            }
            withLabel: 'process_low' {
                cpus = 2
                memory = '8 GB'
                time = '4h'
            }
            withLabel: 'process_medium' {
                cpus = 8
                memory = '32 GB'
                time = '8h'
            }
            withLabel: 'process_high' {
                cpus = 16
                memory = '64 GB'
                time = '24h'
                queue = 'long'
            }
            withLabel: 'process_high_memory' {
                cpus = 8
                memory = '128 GB'
                time = '24h'
                queue = 'highmem'
            }
            withLabel: 'process_gpu' {
                cpus = 4
                memory = '32 GB'
                time = '12h'
                clusterOptions = '--gres=gpu:1'
            }
        }
        
        executor {
            queueSize = 200
            submitRateLimit = '10/1min'
            pollInterval = '30 sec'
            jobName = { "nf-${task.process}-${task.index}" }
        }
    }
    
    slurm_conda {
        process.executor = 'slurm'
        process.clusterOptions = '--export=ALL'
        workDir = params.workdir
        
        singularity.enabled = false
        conda.enabled = true
        conda.cacheDir = params.conda_cachedir
        
        includeConfig 'conf/slurm.config'
    }
    
    slurm_local {
        process.executor = 'slurm'
        process.clusterOptions = '--export=ALL'
        workDir = params.workdir
        
        singularity.enabled = false
        conda.enabled = false
        
        includeConfig 'conf/slurm.config'
    }
    
    debug {
        // For quick testing: limit to first 2 samples
        params.max_samples = 2
        executor.queueSize = 2
    }
}
```

### Resource Label Assignment Guide

Agent must assign labels based on the tool's known resource requirements:

| Label | Typical tools | Rationale |
|-------|---------------|-----------|
| `process_single` | FastQC, featureCounts (single-threaded) | Low CPU, short runtime |
| `process_low` | MultiQC, samtools index, picard MarkDuplicates | Moderate CPU, I/O bound |
| `process_medium` | STAR align, BWA-MEM, fastp, salmon | Multi-threaded, moderate memory |
| `process_high` | DeepVariant, GATK HaplotypeCaller (WGS), SPAdes | High CPU + memory, long runtime |
| `process_high_memory` | Cell Ranger, megahit, large assembly | Memory-bound, may need special queue |
| `process_gpu` | Deep learning models, GPU-accelerated tools | Requires GPU scheduler flag |

---

## Error Handling & Resume

### Process-Level Resilience

```groovy
process UNSTABLE_TOOL {
    errorStrategy { task.exitStatus in [137, 143] ? 'retry' : 'finish' }
    maxRetries 2
    memory { 16.GB * task.attempt }
    time { 4.h * task.attempt }
    ...
}
```

### Resume Protocol

Every execution command MUST include `-resume`:

```bash
nextflow run main.nf -profile slurm --input samplesheet.csv -resume
```

To force a full restart, the user explicitly removes `-resume`.

---

## Debugging & Validation Protocol

Agent must guide the user through this validation sequence before full-scale execution:

1. **Stub run** — validate syntax and channel wiring without executing tools:
   ```bash
   nextflow run main.nf -stub-run -profile slurm --input samplesheet_minimal.csv
   ```

2. **Single-sample dry run** — test on one sample to catch tool-specific errors:
   ```bash
   nextflow run main.nf -profile slurm --input samplesheet_1sample.csv -with-report report.html
   ```

3. **Inspect failures** — if a task fails:
   - Read `.nextflow.log` for Nextflow-level errors
   - Read `work/<hash>/.command.log` for tool stderr
   - Read `work/<hash>/.command.sh` for the rendered script
   - Read `work/<hash>/.exitcode` for the exit code

4. **Resume after fix**:
   ```bash
   nextflow run main.nf -profile slurm --input samplesheet.csv -resume
   ```

5. **Clean old work directories**:
   ```bash
   nextflow clean -f -before $(date -I)
   ```

---

## Common Errors and Fixes

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Unknown variable` | Missing `params.` prefix | Use `params.outdir` not `outdir` |
| `Process terminated with an error exit status` | Tool failure inside process | Check `.command.log` in work dir |
| `Channel not connected` | Missing input channel in workflow | Verify all process inputs are wired |
| `Cannot find file` | Relative path or missing `checkIfExists` | Use `file(path, checkIfExists: true)` or `projectDir` |
| `SLURM job submission failed` | Invalid queue/account or rate limit | Verify `queue`, `clusterOptions`, and `submitRateLimit` |
| `Disk quota exceeded` | `workDir` on `$HOME` | Move `workDir` to `/scratch` or `/tmp` |
| `Singularity image pull failed` | Network issues or missing cache dir | Set `singularity.cacheDir` and pre-pull images |

---

## Example Files

See `examples/` directory for a complete, modular RNA-seq pipeline that follows all standards above:
- `examples/main.nf` — workflow orchestration
- `examples/modules/local/*.nf` — process modules
- `examples/nextflow.config` — full configuration with SLURM profiles

## Related Skills

- utils-workflow-management-snakemake — Python-based alternative
- utils-workflow-management-wdl — WDL alternative
- bioinformatics-analysis-* — Specific analysis domains (alignment, variant calling, etc.)
