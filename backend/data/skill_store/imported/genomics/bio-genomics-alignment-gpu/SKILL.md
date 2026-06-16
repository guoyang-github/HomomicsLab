---
name: bio-genomics-alignment-gpu
description: GPU加速的序列比对与预处理，基于NVIDIA Parabricks。Use when aligning reads to reference genome with GPU acceleration.
tool_type: cli
primary_tool: pbrun fq2bam / pbrun rna_fq2bam
prerequisites:
  - NVIDIA GPU (Volta/Ampere/Hopper架构)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 参考基因组FASTA文件
  - 已预处理的clean FASTQ文件
gpu_requirements:
  - 显存: 16-24GB (WGS) / 8-16GB (WES)
  - 架构: V100/A100/H100推荐
---

# GPU加速序列比对与预处理

基于NVIDIA Parabricks的GPU加速比对流程，将传统CPU需要数小时的比对+排序+重复标记压缩到分钟级别。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun fq2bam --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --out-bam /data/out.bam
```

### 方式二：独立安装

```bash
# Ubuntu/Debian
sudo dpkg -i parabricks-4.7.0-1.deb

# RHEL/CentOS
sudo rpm -i parabricks-4.7.0-1.rpm
```

安装后 `pbrun` 直接作为系统命令使用：
```bash
pbrun fq2bam --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --out-bam out.bam
```

### 系统要求

| 项目 | 要求 |
|------|------|
| OS | Ubuntu 20.04/22.04, RHEL 8/9 |
| NVIDIA驱动 | ≥ 525.60 |
| GPU架构 | Volta/Ampere/Hopper (V100/A100/H100) |

### 选择建议

| 场景 | 推荐方式 |
|------|---------|
| 单机测试/开发 | Docker |
| HPC集群（Slurm/SGE） | 独立安装 |
| 云平台 | 两者皆可 |
| 与其他工具混合调用 | 独立安装 |
| 频繁升级/多版本并存 | Docker |

> **性能声明**：本技能中标注的时间与加速比为NVIDIA官方标称参考值，实际表现受GPU型号（V100/A100/H100）、存储I/O带宽、样本质量及系统负载影响。建议首次使用先以单样本实际测试为准。

## 1. 与CPU方案对比

| 步骤 | CPU工具链 | GPU工具 | 时间(WGS 30x) | 加速比 |
|------|----------|---------|---------------|--------|
| 比对 | bwa-mem2 mem | `fq2bam`(内置) | — | — |
| SAM→BAM | samtools view | `fq2bam`(内置) | — | — |
| 排序 | samtools sort | `fq2bam`(内置) | — | — |
| 重复标记 | samtools markdup | `fq2bam`(内置) | — | — |
| BAM索引 | samtools index | `fq2bam`(内置) | — | — |
| **总计** | **5步流程** | **`fq2bam` 1步** | **~20min** | **~20x** |

## 2. 核心工具

| 工具 | 功能 | 对应CPU工具 |
|------|------|------------|
| `fq2bam` | FASTQ → sorted.markdup.BAM | BWA-MEM + GATK Best Practices |
| `rna_fq2bam` | RNA-seq比对 | STAR |
| `minimap2` | 长读序比对 | minimap2 |
| `giraffe` | 泛基因组比对 | vg giraffe |
| `bam2fq` | BAM转FASTQ | samtools fastq |
| `bamsort` | BAM排序 | samtools sort |
| `markdup` | 重复标记 | GATK MarkDuplicates |
| `applybqsr` | BQSR应用 | GATK ApplyBQSR |

## 3. fq2bam：一站式比对预处理

### WGS基础用法

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.markdup.bam \
    --out-recal-file sample.recal.txt
```

**等效CPU流程**：
```bash
# 需要5-6步，耗时3-4小时
bwa-mem2 mem → samtools view → samtools sort → samtools markdup → samtools index → gatk ApplyBQSR
```

### 带Read Group（GATK兼容）

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --out-bam sample.markdup.bam
```

### WES模式（关键：--interval-file）

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.markdup.bam \
    --interval-file targets.bed \
    --out-recal-file sample.recal.txt
```

### 已知位点BQSR（GATK兼容输出）

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --out-bam sample.markdup.bam \
    --out-recal-file sample.recal.txt
```

## 4. rna_fq2bam：RNA-seq比对

```bash
pbrun rna_fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.rna.bam \
    --gtf Homo_sapiens.GRCh38.109.gtf \
    --two-pass-mode Basic \
    --out-tmp-dir /tmp/star_tmp
```

**等效CPU**：STAR 2-pass alignment，耗时约1-2小时 → GPU约5-10分钟

### RNA-seq特有参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--gtf` | 基因注释GTF | Ensembl/Gencode |
| `--two-pass-mode` | 2-pass比对模式 | Basic |
| `--out-tmp-dir` | STAR临时目录 | SSD路径 |
| `--chimSegmentMin` | 融合检测最小长度 | 12 (融合分析时) |

## 5. minimap2：长读序比对

```bash
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq ont_reads.fastq \
    --out-bam sample.ont.bam \
    --align-type ont

# PacBio HiFi
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq hifi_reads.fastq \
    --out-bam sample.hifi.bam \
    --align-type hifi
```

### align-type选项

| 类型 | 说明 |
|------|------|
| `map-ont` | Oxford Nanopore |
| `map-hifi` | PacBio HiFi (CCS) |
| `map-pb` | PacBio CLR |

## 6. giraffe：泛基因组比对

```bash
pbrun giraffe \
    --ref pangenome.gbz \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.pangenome.bam
```

## 7. 独立预处理工具

### BAM排序
```bash
pbrun bamsort \
    --in-bam unsorted.bam \
    --out-bam sorted.bam
```

### 重复标记
```bash
pbrun markdup \
    --in-bam sorted.bam \
    --out-bam markdup.bam
```

### BQSR应用
```bash
pbrun applybqsr \
    --ref GRCh38.fa \
    --in-bam markdup.bam \
    --in-recal recal.txt \
    --out-bam recalibrated.bam
```

## 8. 完整WGS批量脚本

```bash
#!/bin/bash
# gpu_alignment_pipeline.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
OUTDIR=$5
TYPE=${6:-wgs}  # wgs或wes
TARGETS=${7:-""}

mkdir -p ${OUTDIR}

echo "=== GPU Accelerated Alignment ==="
if [ "${TYPE}" == "wes" ] && [ -n "${TARGETS}" ]; then
    pbrun fq2bam \
        --ref ${REF} \
        --in-fq ${R1} ${R2} \
        "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
        --interval-file ${TARGETS} \
        --knownSites dbsnp_146.hg38.vcf.gz \
        --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
        --out-bam ${OUTDIR}/${SAMPLE}.bam \
        --out-recal-file ${OUTDIR}/${SAMPLE}.recal.txt
else
    pbrun fq2bam \
        --ref ${REF} \
        --in-fq ${R1} ${R2} \
        "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
        --knownSites dbsnp_146.hg38.vcf.gz \
        --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
        --out-bam ${OUTDIR}/${SAMPLE}.bam \
        --out-recal-file ${OUTDIR}/${SAMPLE}.recal.txt
fi

echo "=== Complete ==="
echo "BAM: ${OUTDIR}/${SAMPLE}.bam"
echo "BQSR: ${OUTDIR}/${SAMPLE}.recal.txt"
```

## 9. 进阶：多GPU与集群运行

### 单节点多GPU加速

```bash
# 使用2个GPU加速fq2bam
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.markdup.bam \
    --num-gpus 2
```

### --num-gpus 与性能关系

| GPU数量 | 显存总量 | WGS 30x预估时间 | 适用场景 |
|---------|---------|----------------|---------|
| 1 | 16-24GB | ~20min | 标准单样本 |
| 2 | 32-48GB | ~12-15min | 大样本或赶时间 |
| 4 | 64-96GB | ~8-10min | 大规模队列 |

> **注意**：多GPU的加速并非线性。受I/O带宽和数据分片开销影响，2块GPU通常比1块快1.3-1.6倍，而非2倍。

### Slurm集群提交示例

```bash
#!/bin/bash
#SBATCH --job-name=gpu_fq2bam
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --time=1:00:00

pbrun fq2bam \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    --out-bam ${OUTDIR}/${SAMPLE}.bam \
    --out-recal-file ${OUTDIR}/${SAMPLE}.recal.txt
```

### 多样本并行（每样本1 GPU）

```bash
# 假设有4个GPU，同时处理4个样本
for i in 0 1 2 3; do
    CUDA_VISIBLE_DEVICES=$i pbrun fq2bam \
        --ref GRCh38.fa \
        --in-fq sample${i}_R1.fq.gz sample${i}_R2.fq.gz \
        --out-bam sample${i}.bam &
done
wait
```

## 10. 资源需求

| 数据类型 | GPU显存 | 时间(单样本) | 输出BAM大小 |
|----------|---------|-------------|-------------|
| WGS 30x | 16-24GB | ~20min | ~60-80GB |
| WES 100x | 8-16GB | ~5min | ~8-12GB |
| RNA-seq | 8-16GB | ~5min | ~5-10GB |
| ONT 30x | 16-24GB | ~15min | ~30-50GB |
| PacBio HiFi 30x | 16-24GB | ~15min | ~40-60GB |

## 11. 输出与CPU版本兼容性

Parabricks保证与对应CPU工具版本输出**数值一致**：
- `fq2bam` 输出与 BWA-MEM2 + GATK MarkDuplicates 相同
- `rna_fq2bam` 输出与 STAR 相同
- BAM文件可直接用于下游GATK/DeepVariant分析
- 官方验证：[Output Accuracy文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)

## 12. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `fq2bam` | BWA-MEM2 2.2.1, GATK MarkDuplicates | `pbrun fq2bam --help` |
| `rna_fq2bam` | STAR 2.7.11a | `pbrun rna_fq2bam --help` |
| `minimap2` | minimap2 2.26 | `pbrun minimap2 --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 13. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 极少数边界差异 | 与GATK在极少数边界情况可能存在舍入差异 | 查阅官方精度对比文档 |

## 14. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| CUDA out of memory | 显存不足 | 降低--batch-size，或换更大GPU |
| 参考基因组索引缺失 | 未建立BWA索引 | 预先运行 `bwa-mem2 index` |
| BAM与下游工具不兼容 | Read Group缺失 | 使用 `--in-fq fq1 fq2 "@RG..."` 格式 |
| 排序后BAM异常大 | 未压缩 | 添加 `--out-duplicate-metrics` 检查 |
| WES比对率异常低 | interval file格式错误 | 确保BED/GATK interval格式正确 |

## 相关技能

- bio-genomics-alignment - CPU版本(bwa-mem2/samtools)
- bio-genomics-variant-germline-gpu - GPU加速变异检测
- bio-genomics-workflow-wgs-germline-gpu - WGS端到端GPU流程
