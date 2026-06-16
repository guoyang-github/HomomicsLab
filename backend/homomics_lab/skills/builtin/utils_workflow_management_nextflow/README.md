# utils-workflow-management-nextflow 使用说明

## 概述

`utils-workflow-management-nextflow` 是一个面向 LLM Agent 的 Nextflow 工作流构建技能。它使 Agent 能够将生物信息学分析脚本（Shell、R、Python）自动转化为生产级的 Nextflow DSL2 流程，并直接在 SLURM HPC 集群上投递执行。

该技能的核心设计理念：
- **模块化**：每个工具封装为独立 process，相关 process 组合为 subworkflow
- **环境无关**：支持 Singularity、Conda 和本地软件三种执行模式
- **资源感知**：通过标签系统自动分配 CPU/内存/队列/GPU 资源
- **可恢复**：基于 Nextflow 的缓存机制，支持断点续跑

---

## 前置条件

### 用户侧准备

在使用该技能前，请确保你的运行环境满足以下条件：

| 组件 | 要求 | 验证命令 |
|------|------|----------|
| Nextflow | >= 23.04.0 | `nextflow -version` |
| Java | >= 17 | `java -version` |
| SLURM | 集群已部署 | `sinfo` |

### 三选一：执行环境

你的 HPC 环境必须至少支持以下三种模式之一：

| 模式 | 适用场景 | 验证命令 |
|------|----------|----------|
| **Singularity/Apptainer** | HPC 已安装容器运行时（推荐） | `singularity --version` |
| **Conda/Mamba** | 无容器权限，但有 conda | `conda --version` |
| **本地/Module** | 软件由管理员预装，通过 `module load` 加载 | `module avail` |

### 存储空间

- **工作目录（workDir）**：Nextflow 在运行期间会产生大量中间文件，**必须**配置到 `/scratch` 或类似的高速临时存储，不可使用 `$HOME`
- **镜像缓存（singularity_cachedir）**：如使用 Singularity，镜像文件通常每个 500MB-2GB，需预留足够空间

---

## 快速开始

### 1. 告诉 Agent 你的需求

向 Agent 描述你的分析流程，Agent 会自动生成完整的 Nextflow 项目。

**示例 Prompt：**

> "我有一个 RNA-seq 分析流程：先用 fastp 做质控和接头去除，然后用 HISAT2 比对到参考基因组，最后用 featureCounts 做定量。请帮我转化为 Nextflow 流程，目标是在我们的 SLURM 集群上运行。集群队列是 normal，账户是 bioinfo，有 Singularity 环境。"

**Agent 将输出：**
- `main.nf` — 工作流编排文件
- `nextflow.config` — 配置文件（含 SLURM、Singularity、资源标签）
- `modules/local/*.nf` — 每个工具的独立模块
- `subworkflows/*.nf` — 逻辑分组（如 QC、Alignment、Quantification）
- `samplesheet.csv` — 输入样本表示例

### 2. 准备输入数据

Agent 会生成一个 `samplesheet.csv` 模板。你需要根据实际数据路径填写：

```csv
sample,fastq_1,fastq_2,strandedness
SAMPLE1,/data/S1_R1.fq.gz,/data/S1_R2.fq.gz,auto
SAMPLE2,/data/S2_R1.fq.gz,/data/S2_R2.fq.gz,auto
SAMPLE3,/data/S3_R1.fq.gz,,reverse
```

**字段说明：**
- `sample`：样本唯一标识符
- `fastq_1`：R1 文件绝对路径
- `fastq_2`：R2 文件绝对路径（单端测序留空）
- `strandedness`：建库链特异性（auto / forward / reverse / unstranded）

### 3. 验证配置

在正式投递前，先检查生成的配置是否符合你的集群环境：

```groovy
// nextflow.config 中需要确认的关键参数
params {
    input = "samplesheet.csv"           // 你的样本表路径
    outdir = "results"                  // 结果输出目录
    salmon_index = "/ref/salmon_index"  // 参考数据路径（根据分析类型不同）
}

profiles {
    slurm {
        process.queue = 'normal'        // 改为你的默认队列
        process.clusterOptions = '--account=bioinfo'  // 改为你的账户
        workDir = "/scratch/$USER/nextflow-work"      // 改为你的 scratch 路径
        singularity.cacheDir = "/scratch/$USER/singularity-cache"
    }
}
```

### 4. 三阶段验证执行

**阶段一：语法验证（stub run）**

不执行任何真实计算，仅验证流程结构和通道连接是否正确：

```bash
nextflow run main.nf -stub-run -profile slurm --input samplesheet.csv
```

**阶段二：单样本试运行**

选取一个样本验证工具参数和环境配置：

```bash
# 只保留 samplesheet 的第一行数据（含表头共两行）
head -n 2 samplesheet.csv > samplesheet_test.csv

nextflow run main.nf -profile slurm --input samplesheet_test.csv -with-report report.html
```

**阶段三：全量生产执行**

确认单样本通过后，提交全部样本：

```bash
nextflow run main.nf -profile slurm --input samplesheet.csv -resume
```

> **关键：** 始终携带 `-resume` 参数。如果任务失败或需要修改参数后重跑，Nextflow 会自动跳过已完成的步骤。

---

## 项目结构说明

Agent 生成的项目遵循严格的目录规范：

```
pipeline/
├── main.nf                 # 工作流编排层：只包含 include 和 workflow 定义
├── nextflow.config         # 全局参数和 profile 配置
├── conf/
│   └── slurm.config        # SLURM 专用配置（可选）
├── modules/
│   ├── local/              # 自定义 process 模块
│   │   ├── fastp.nf
│   │   ├── hisat2_align.nf
│   │   └── featurecounts.nf
│   └── nf-core/            # 从 nf-core 安装的现成模块（如使用）
│       └── fastp/
│           └── main.nf
├── subworkflows/           # 逻辑分组
│   ├── qc.nf               # 质控子流程
│   ├── align.nf            # 比对子流程
│   └── quantify.nf         # 定量子流程
├── bin/                    # 自定义辅助脚本（自动加入 PATH）
│   └── parse_counts.py
├── assets/                 # 随流程绑定的参考文件
│   └── adapters.fa
└── samplesheet.csv         # 输入样本表
```

**设计原则：**
- `main.nf` 中**禁止**出现 `process` 定义，所有 process 必须在 `modules/` 中
- `subworkflows/` 将相关 process 组合为可复用的逻辑单元
- `bin/` 中的脚本可在 process 的 `script:` 块中直接调用

**`bin/` 目录的 R/Python 脚本规范：**

```r
# bin/run_deseq2.R
# 1. 通过命令行参数接收输入输出路径，禁止硬编码
# 2. 处理单样本/单任务，不遍历目录
# 3. 使用 --outprefix 确保输出文件名唯一
# 4. 异常时退出码非零

args <- commandArgs(trailingOnly = TRUE)
input_file  <- args[args == "--input"]      %>% { .[which.max(. == "--input") + 1] }
outprefix   <- args[args == "--outprefix"]  %>% { .[which.max(. == "--outprefix") + 1] }

# ... DESeq2 analysis ...

write.csv(results, file = paste0(outprefix, ".results.csv"))
pdf(paste0(outprefix, ".plots.pdf"))
# ... plots ...
dev.off()
```

```groovy
// modules/local/deseq2.nf 中调用方式
script:
"""
run_deseq2.R \\
    --input ${counts_matrix} \\
    --outprefix ${meta.id}
"""
```

---

## 环境配置详解

根据你的 HPC 环境，选择对应的 profile：

### Profile 1：SLURM + Singularity（推荐）

适用于绝大多数现代 HPC 集群。Singularity 镜像从 Biocontainers 自动拉取，环境完全隔离且可复现。

```bash
nextflow run main.nf -profile slurm --input samplesheet.csv -resume
```

**配置要点：**
- `singularity.enabled = true`
- `singularity.cacheDir` 指向 scratch 目录
- `singularity.autoMounts = true` 自动挂载宿主目录

**预拉取镜像（计算节点无网络时必需）：**

```bash
# 在登录节点执行，提前下载镜像到缓存目录
singularity pull /scratch/$USER/singularity-cache/fastp.sif \
    docker://quay.io/biocontainers/fastp:0.23.4--hadf994f_2
```

### Profile 2：SLURM + Conda

适用于无容器权限但已安装 conda/mamba 的集群。

```bash
nextflow run main.nf -profile slurm_conda --input samplesheet.csv -resume
```

**配置要点：**
- `conda.enabled = true`
- `singularity.enabled = false`
- `conda.cacheDir` 指向 scratch 目录（避免在 $HOME 中创建大量环境）
- 每个 process 的 `conda` 指令指定精确的软件版本

### Profile 3：SLURM + 本地软件

适用于软件由管理员统一安装、通过 `module load` 加载的环境。

```bash
nextflow run main.nf -profile slurm_local --input samplesheet.csv -resume
```

**配置要点：**
- `singularity.enabled = false`
- `conda.enabled = false`
- 在 process 中使用 `beforeScript` 加载模块：
  ```groovy
  process HISAT2_ALIGN {
      beforeScript 'module load HISAT2/2.2.1 SAMtools/1.17'
      // 无 container / conda 指令
      ...
  }
  ```

### Profile 4：本地调试（login node）

仅用于小规模测试，**不要在 login node 上运行大规模计算**：

```bash
nextflow run main.nf -profile standard --input samplesheet.csv
```

---

## 资源标签系统

Agent 会根据工具特性自动分配资源标签。你也可在生成后手动调整：

| 标签 | CPU | 内存 | 时间 | 队列 | 适用工具 |
|------|-----|------|------|------|----------|
| `process_single` | 1 | 4 GB | 2h | normal | FastQC、单线程工具 |
| `process_low` | 2 | 8 GB | 4h | normal | MultiQC、samtools index |
| `process_medium` | 8 | 32 GB | 8h | normal | STAR、BWA-MEM、fastp、salmon |
| `process_high` | 16 | 64 GB | 24h | long | GATK HaplotypeCaller (WGS)、SPAdes |
| `process_high_memory` | 8 | 128 GB | 24h | highmem | Cell Ranger、大型组装 |
| `process_gpu` | 4 | 32 GB | 12h | gpu | GPU 加速的深度学习工具 |

**自定义资源：**

如需为特定 process 调整资源，在 `nextflow.config` 中覆盖：

```groovy
process {
    withName: 'STAR_ALIGN' {
        cpus = 24
        memory = '128 GB'
        time = '48h'
    }
}
```

---

## 常用执行命令速查

```bash
# 语法验证（无实际执行）
nextflow run main.nf -stub-run -profile slurm --input samplesheet.csv

# 单样本测试
nextflow run main.nf -profile slurm,debug --input samplesheet_test.csv

# 生产执行（Singularity）
nextflow run main.nf -profile slurm --input samplesheet.csv -resume

# 生产执行（Conda）
nextflow run main.nf -profile slurm_conda --input samplesheet.csv -resume

# 生产执行（本地软件）
nextflow run main.nf -profile slurm_local --input samplesheet.csv -resume

# 带执行报告（推荐用于性能分析）
nextflow run main.nf -profile slurm --input samplesheet.csv -resume \
    -with-report report.html \
    -with-timeline timeline.html \
    -with-trace trace.txt

# 查看执行历史
nextflow log

# 清理旧的工作目录（释放空间）
nextflow clean -f -before $(date -I)

# 强制重新运行（不使用缓存）
nextflow run main.nf -profile slurm --input samplesheet.csv  # 不带 -resume
```

---

## 调试指南

### 流程失败的排查步骤

1. **查看 Nextflow 级别错误**
   ```bash
   tail -n 50 .nextflow.log
   ```

2. **查看具体任务的工具错误**
   ```bash
   # 从 .nextflow.log 中找到失败任务的 work 目录哈希
   # 例如：work/3f/2a1b4c...
   cat work/3f/2a1b4c.../.command.log    # 工具的 stderr/stdout
   cat work/3f/2a1b4c.../.command.sh     # 实际执行的脚本
   cat work/3f/2a1b4c.../.exitcode       # 退出码
   ```

3. **常见退出码含义**

   | 退出码 | 含义 | 解决方向 |
   |--------|------|----------|
   | 1 | 通用错误 | 检查 `.command.log` 中的工具报错 |
   | 137 | OOM Killed (SIGKILL) | 增加 `memory` 标签或申请更大内存队列 |
   | 143 | 超时或手动取消 | 增加 `time` 标签或检查队列限制 |
   | 127 | 命令未找到 | 检查容器/conda/环境变量配置 |

4. **修复后恢复执行**
   ```bash
   nextflow run main.nf -profile slurm --input samplesheet.csv -resume
   ```

### 常见问题

**Q：任务提交失败，报错 "sbatch: error"**
- 检查 `nextflow.config` 中的 `queue` 和 `clusterOptions` 是否匹配你的集群
- 检查账户名是否正确：`--account=your_account`

**Q：磁盘配额超限**
- 确认 `workDir` 配置到了 `/scratch`，而不是 `$HOME`
- 运行 `nextflow clean -f` 清理旧的工作目录

**Q：Singularity 镜像拉取失败**
- 计算节点通常无外网，需要在 login node 预拉取：`singularity pull ...`
- 或设置镜像缓存目录为共享路径，让已下载的镜像复用

**Q：如何只运行流程的一部分？**
- 使用 `-stub-run` 验证结构
- 或使用 `params.max_samples = N` 限制样本数（debug profile 已内置）

**Q：如何修改某个工具的参数？**
- 编辑 `nextflow.config` 中的 `params.<tool>_args`，无需修改模块文件
- 例如：`params.salmon_args = '--validateMappings --gcBias'`

---

## 高级用法

### 复用 nf-core 模块

nf-core 社区维护了大量高质量的现成模块。Agent 可以在生成流程时优先使用这些模块，而非手写：

```bash
# 安装 nf-core 工具
pip install nf-core

# 列出可用模块
nf-core modules list remote

# 安装模块到当前项目
nf-core modules install fastp
nf-core modules install star/align
```

安装后，Agent 会在 `main.nf` 中自动引用：

```groovy
include { FASTP } from './modules/nf-core/fastp/main'
include { STAR_ALIGN } from './modules/nf-core/star/align/main'
```

### 自定义子工作流

如果你有多个分析流程共享相同的 QC 或比对步骤，可以将它们提取为 subworkflow：

```groovy
// subworkflows/qc.nf
include { FASTP } from '../modules/local/fastp'
include { MULTIQC } from '../modules/local/multiqc'

workflow QC {
    take:
    reads

    main:
    FASTP(reads)
    MULTIQC(FASTP.out.json.collect())

    emit:
    reads = FASTP.out.reads
    report = MULTIQC.out.report
}
```

然后在 `main.nf` 中调用：

```groovy
include { QC } from './subworkflows/qc'
include { ALIGN } from './subworkflows/align'

workflow {
    QC(reads_ch)
    ALIGN(QC.out.reads)
}
```

### 动态资源分配

对于内存需求随输入大小变化的工具，可使用动态表达式：

```groovy
process ASSEMBLY {
    label 'process_high_memory'
    memory { 64.GB * Math.pow(2, task.attempt - 1) }  // 64GB -> 128GB -> 256GB
    errorStrategy { task.exitStatus == 137 ? 'retry' : 'finish' }
    maxRetries 2
    ...
}
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `SKILL.md` | Agent 的核心行动指南（面向 LLM） |
| `usage-guide.md` | Agent 的辅助参考（prompt 示例和概念速查） |
| `README.md` | 本文件：面向最终用户的完整使用说明 |
| `examples/main.nf` | 模块化 RNA-seq 流程示例（编排层） |
| `examples/nextflow.config` | 含 SLURM/Singularity/Conda/Local 四 profile 的完整配置 |
| `examples/modules/local/*.nf` | fastp、salmon_quant、multiqc 模块示例 |
| `examples/subworkflows/qc.nf` | 子工作流示例 |
| `examples/bin/run_deseq2.R` | R 脚本示例：参数化输入输出、单任务执行 |
| `examples/bin/parse_counts.py` | Python 脚本示例：参数化输入输出、异常退出码 |
| `examples/samplesheet.csv` | 标准输入样本表示例 |
