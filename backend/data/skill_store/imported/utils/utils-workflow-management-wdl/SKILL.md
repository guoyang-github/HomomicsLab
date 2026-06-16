---
name: utils-workflow-management-wdl
description: Transform bioinformatics analysis scripts into portable WDL workflows for execution with Cromwell or miniwdl. Use when building strongly-typed workflows, running GATK best practices, or targeting cloud platforms (Terra, AnVIL). SLURM execution is supported via Cromwell HPC backend. Supports Docker and Singularity containers.
tool_type: cli
primary_tool: wdl
measurable_outcome: Generate a valid WDL project that passes womtool validation and produces a runnable inputs JSON template.
allowed-tools:
  - read_file
  - write_file
  - edit_file
  - run_shell_command
---

# WDL Workflow Architect

## Role & Goal

You are a senior bioinformatics workflow engineer. Your task is to take existing analysis scripts (shell, R, Python) or a set of bioinformatics tools, and convert them into a strongly-typed, portable WDL workflow.

Key outcomes:
- The workflow must be modular (tasks in `tasks/`, orchestration in `workflow.wdl`)
- The workflow must be containerized (Docker or Singularity specified in every `runtime` block)
- The workflow must produce a complete `inputs.json` template
- The workflow must be validated with `womtool validate` before execution

**Execution Context:** WDL is primarily designed for cloud and containerized environments. SLURM execution requires Cromwell with HPC backend configuration. For lightweight local testing, use miniwdl.

---

## Workflow Design Logic

### Task Decomposition Rules

When converting an analysis plan into WDL, follow these rules:

**Rule 1: One tool invocation = one task**
- A command like `bwa mem ... | samtools sort ...` should be split into `task bwa_mem` and `task samtools_sort`.
- Rationale: Granular tasks maximize call caching and allow independent resource allocation.

**Rule 2: Group related tasks into separate `.wdl` files**
- QC tasks → `tasks/qc.wdl`
- Alignment tasks → `tasks/align.wdl`
- Import them into the main workflow with `import "tasks/qc.wdl" as qc`
- Rationale: Modular tasks keep the main workflow readable and enable reuse across projects.

**Rule 3: Use structs to organize sample metadata**
- Never pass raw file arrays without associated metadata.
- Use a `SampleInfo` struct to group `sample_id`, `fastq_1`, `fastq_2`.

### Dataflow Design

**Pattern 1: Struct-driven sample input (PREFERRED)**

All production workflows MUST use a struct for sample information.

```wdl
struct SampleInfo {
    String sample_id
    File fastq_1
    File? fastq_2
    String strandedness
}

workflow rnaseq {
    input {
        Array[SampleInfo] samples
        File salmon_index
    }

    scatter (sample in samples) {
        call fastp {
            input:
                sample_id = sample.sample_id,
                reads_1 = sample.fastq_1,
                reads_2 = sample.fastq_2
        }
        call salmon_quant {
            input:
                sample_id = sample.sample_id,
                reads_1 = fastp.trimmed_1,
                reads_2 = fastp.trimmed_2,
                index = salmon_index
        }
    }

    call multiqc {
        input:
            fastp_reports = fastp.json_report,
            salmon_dirs = salmon_quant.quant_dir
    }
}
```

**Pattern 2: Parallel execution with scatter**

```wdl
scatter (sample in samples) {
    call align {
        input:
            sample_id = sample.sample_id,
            reads = [sample.fastq_1, sample.fastq_2]
    }
}
```

**Pattern 3: Aggregation after scatter**

```wdl
scatter (sample in samples) {
    call salmon_quant { ... }
}

call multiqc {
    input:
        salmon_results = salmon_quant.quant_sf
}
```

**Pattern 4: Conditional execution**

```wdl
input {
    Boolean run_qc = true
}

if (run_qc) {
    call fastqc {
        input: fastq = reads
    }
}
```

### Common Pitfalls

| Pitfall | Why it breaks | Solution |
|---------|---------------|----------|
| Missing `version` declaration | WOMtool validation fails | Always start with `version 1.0` |
| File type mismatch | `File` vs `String` confusion | Use `File` for actual files, `String` for paths in commands |
| Optional outputs without `?` | Workflow fails when output missing | Use `File?` for conditional outputs |
| Hardcoded paths in tasks | Breaks portability | Pass all paths as `input` parameters |
| Missing `runtime` block | Cromwell doesn't know resources | Always specify `cpu`, `memory`, `docker` in runtime |
| Forgetting `disks` on cloud | Task fails with "no space left on device" | Calculate disk size: `ceil(size(inputs) * 2) + 20` |
| Scatter over Array without indexing | Losing sample identity | Use structs to carry metadata through scatter |

---

## Code Standards

### Mandatory Project Structure

Agent MUST generate files in this structure. No exceptions.

```
project/
├── workflow.wdl              # Main workflow with imports and scatter blocks
├── tasks/                    # Modular task definitions
│   ├── qc.wdl
│   ├── align.wdl
│   └── quantify.wdl
├── inputs.json               # Generated input values template
├── inputs_minimal.json       # Single-sample test inputs
├── options.json              # Cromwell runtime options
├── cromwell.conf             # Cromwell backend configuration
└── data/                     # Input data (gitignored)
```

**Rule:** `workflow.wdl` contains ONLY `import`, `struct`, `workflow` definitions, and `call` statements. All `task` blocks live in `tasks/*.wdl`.

### Task Standards

Every task file must follow this template:

```wdl
# tasks/qc.wdl
version 1.0

task fastp {
    input {
        String sample_id
        File reads_1
        File? reads_2
        Int threads = 4
        String fastp_args = ""
    }

    Int disk_gb = ceil(size(reads_1, "GB") + size(reads_2, "GB")) * 3 + 10

    command <<<
        fastp \
            -i ~{reads_1} \
            -o ~{sample_id}_trimmed_R1.fq.gz \
            --json ~{sample_id}_fastp.json \
            --html ~{sample_id}_fastp.html \
            --thread ~{threads} \
            ~{fastp_args}
    >>>

    output {
        File trimmed_1 = "~{sample_id}_trimmed_R1.fq.gz"
        File trimmed_2 = "~{sample_id}_trimmed_R2.fq.gz"
        File json_report = "~{sample_id}_fastp.json"
        File html_report = "~{sample_id}_fastp.html"
    }

    runtime {
        docker: "quay.io/biocontainers/fastp:0.23.4--hadf994f_2"
        # singularity: "/scratch/$USER/singularity-images/fastp.sif"
        cpu: threads
        memory: "4 GB"
        disks: "local-disk " + disk_gb + " HDD"
        preemptible: 3
    }
}
```

**Required sections per task:**
- `input:` — all parameters explicitly typed
- `command <<< ... >>>` — use heredoc for multi-line commands
- `output:` — all output files declared with `File` or `File?`
- `runtime:` — `docker` (or `singularity`), `cpu`, `memory`, `disks`

### Parameterization Rules

All user-configurable values must be workflow inputs:

```wdl
workflow rnaseq {
    input {
        Array[SampleInfo] samples       # REQUIRED
        File salmon_index               # REQUIRED
        String outdir = "results"
        Int threads = 8
        String fastp_args = ""
        String salmon_args = "--validateMappings"
    }
    ...
}
```

**Rule:** If a parameter is required, do not provide a default. Cromwell will fail fast with a clear error if the user forgets to provide it in `inputs.json`.

### Environment Strategy

WDL assumes containerized execution. The agent must generate runtime blocks that support both Docker and Singularity.

| Strategy | When to use | How to configure |
|----------|-------------|------------------|
| **Docker** (default) | Local testing, cloud platforms (Terra, Google Cloud) | `runtime { docker: "image:tag" }` |
| **Singularity** | HPC with Singularity/Apptainer | `runtime { singularity: "/path/to/image.sif" }` or Cromwell config |

**Rule for runtime blocks:**
- Prefer `docker:` directive with full image path
- For HPC, agent should also provide `singularity:` as an alternative (commented out)
- Cromwell can be configured to automatically convert Docker images to Singularity

---

## Environment Configuration

### Cromwell Backend Configuration

Agent MUST generate a `cromwell.conf` that defines multiple backends.

```hocon
# cromwell.conf
include required(classpath("application"))

backend {
    default = "Local"

    providers {
        Local {
            actor-factory = "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory"
            config {
                concurrent-job-limit = 10
                runtime-attributes = """
                    Int cpu = 1
                    Int memory_mb = 2000
                    String? docker
                """
                submit-docker = "docker run --rm -v ${cwd}:${docker_cwd} ${docker} ${job_shell} ${docker_script}"
            }
        }

        SLURM {
            actor-factory = "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory"
            config {
                runtime-attributes = """
                    Int cpu = 1
                    Int memory_mb = 4000
                    Int runtime_minutes = 60
                    String partition = "normal"
                    String? docker
                    String? singularity
                """

                submit = """
                    sbatch \
                        --partition=${partition} \
                        --cpus-per-task=${cpu} \
                        --mem=${memory_mb}M \
                        --time=${runtime_minutes} \
                        --output=${cwd}/execution/stdout \
                        --error=${cwd}/execution/stderr \
                        --chdir=${cwd} \
                        ${"--wrap=\"" + job_shell + ' ' + script + "\""}
                """

                kill = "scancel ${job_id}"
                check-alive = "squeue -j ${job_id}"
                job-id-regex = "Submitted batch job (\\d+)"
            }
        }
    }
}
```

**Run commands:**

```bash
# Local execution with Docker
java -jar cromwell.jar run workflow.wdl -i inputs.json

# SLURM execution
java -jar cromwell.jar run workflow.wdl -i inputs.json -Dconfig.file=cromwell.conf \
    -Dbackend.default=SLURM
```

### Cromwell Options

```json
// options.json
{
    "final_workflow_outputs_dir": "/scratch/$USER/wdl-results",
    "use_relative_output_paths": true,
    "default_runtime_attributes": {
        "docker": "ubuntu:20.04"
    }
}
```

### miniwdl (Lightweight Local Testing)

For quick validation without Cromwell:

```bash
# Validate syntax
miniwdl check workflow.wdl

# Run locally (requires Docker)
miniwdl run workflow.wdl --input inputs.json

# Run with Singularity
miniwdl run workflow.wdl --input inputs.json --cfg miniwdl.cfg
```

---

## Error Handling & Resume

### Task-Level Resilience

```wdl
task unstable_tool {
    input {
        File input_file
    }

    command <<<
        unstable_tool ~{input_file} > output.txt
    >>>

    output {
        File result = "output.txt"
    }

    runtime {
        docker: "biocontainers/tool:latest"
        cpu: 4
        memory: "16 GB"
        maxRetries: 2
    }
}
```

### Resume Protocol

Cromwell supports call caching (resume). Always enable it:

```bash
java -jar cromwell.jar run workflow.wdl -i inputs.json \
    -Dconfig.file=cromwell.conf \
    -Dworkflow-options.workflowCallbackUri=none \
    -Dcall-caching.enabled=true
```

For miniwdl:
```bash
miniwdl run workflow.wdl --input inputs.json --dir ./runs/
```

---

## Debugging & Validation Protocol

Agent must guide the user through this validation sequence before full-scale execution:

1. **Syntax validation** — validate WDL with womtool:
   ```bash
   java -jar womtool.jar validate workflow.wdl
   ```

2. **Generate inputs template** — ensure all required inputs are documented:
   ```bash
   java -jar womtool.jar inputs workflow.wdl > inputs_template.json
   ```

3. **Local dry run with miniwdl** — test on one sample:
   ```bash
   miniwdl check workflow.wdl
   miniwdl run workflow.wdl --input inputs_minimal.json
   ```

4. **Inspect failures** — if a task fails:
   - Check Cromwell's `metadata.json` for task status
   - Check `cromwell-executions/<workflow>/<call>/<shard>/execution/stderr`
   - Check `cromwell-executions/<workflow>/<call>/<shard>/execution/stdout`

5. **Execution report** — Cromwell produces detailed metadata:
   ```bash
   java -jar cromwell.jar run workflow.wdl -i inputs.json -m metadata.json
   ```

---

## Common Errors and Fixes

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Unrecognized token` | Syntax error | Validate with `womtool validate` |
| `No coercion defined` | Type mismatch | Ensure input JSON types match WDL declarations |
| `Required workflow input not specified` | Missing required input | Check all non-optional inputs in JSON |
| `Failed to evaluate` | Expression error | Verify variable names and `~{}` interpolation |
| `Disk too small` | Insufficient disk in runtime | Increase `disks` value or calculate dynamically |
| `SLURM job submission failed` | Invalid partition or resource request | Check `cromwell.conf` matches cluster |
| `Docker image not found` | Network issues or private registry | Pre-pull images or configure registry auth |
| `Call caching disabled` | Cromwell not configured for resume | Enable `-Dcall-caching.enabled=true` |

---

## Example Files

See `examples/` directory for a complete, modular RNA-seq workflow that follows all standards above:
- `examples/workflow.wdl` — main workflow with structs, scatter, and imports
- `examples/tasks/*.wdl` — modular task definitions
- `examples/inputs.json` — complete inputs template
- `examples/inputs_minimal.json` — single-sample test inputs
- `examples/cromwell.conf` — Cromwell backend configuration (Local + SLURM)
- `examples/options.json` — Cromwell runtime options

## Related Skills

- utils-workflow-management-nextflow — Nextflow alternative
- utils-workflow-management-snakemake — Python-based alternative
- bioinformatics-analysis-* — Specific analysis domains
