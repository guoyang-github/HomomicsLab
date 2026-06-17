---
name: bio-genomics-longread-gpu
description: GPU加速的长读序测序分析，基于NVIDIA Parabricks。支持PacBio HiFi和Oxford Nanopore的比对和生殖细胞变异检测。Use for long-read sequencing analysis with GPU acceleration.
tool_type: cli
primary_tool: pbrun minimap2 / pbrun ont_germline / pbrun pacbio_germline
prerequisites:
  - NVIDIA GPU (显存≥16GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - PacBio HiFi或ONT reads (FASTQ/BAM)
  - 参考基因组(GRCh38)及索引
gpu_requirements:
  - 显存: 16-24GB
  - 架构: V100/A100/H100
  - 长读序比对约15-20分钟
---

# GPU加速长读序测序分析

基于NVIDIA Parabricks的GPU加速长读序分析，支持PacBio HiFi和Oxford Nanopore平台的比对和变异检测。长读序在复杂区域（如重复序列、结构变异）具有独特优势。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun minimap2 --ref /data/ref.fa --in-fq /data/reads.fq --align-type map-hifi --out-bam /data/out.bam
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
pbrun minimap2 --ref ref.fa --in-fq reads.fq --align-type map-hifi --out-bam out.bam
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

## 1. 长读序 vs 短读序

| 特性 | 短读序(Illumina) | 长读序(PacBio/ONT) |
|------|-----------------|-------------------|
| 读长 | 150-300bp | 10-50kb (HiFi) / 10kb-2Mb (ONT) |
| 准确性 | >99% (Q30) | >99.9% (HiFi) / ~92-97% (ONT) |
| 结构变异 | 难检测 | 易检测 |
| 重复区域 | 难比对 | 易跨越 |
| 相位分析 | 需统计方法 | 天然长片段相位 |
| 成本 | 低 | 高 |

## 2. minimap2：GPU加速长读序比对

### PacBio HiFi (CCS)

```bash
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq hifi_reads.fastq \
    --out-bam sample.hifi.bam \
    --align-type map-hifi
```

### Oxford Nanopore

```bash
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq ont_reads.fastq \
    --out-bam sample.ont.bam \
    --align-type map-ont
```

### 旧版PacBio (CLR)

```bash
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq clr_reads.fastq \
    --out-bam sample.clr.bam \
    --align-type map-pb
```

### align-type选项

| 类型 | 参数值 | 适用平台 |
|------|--------|---------|
| PacBio HiFi | `map-hifi` | CCS reads，准确性>99% |
| Oxford Nanopore | `map-ont` | R9/R10 化学 |
| PacBio CLR | `map-pb` | 连续长读序 |

### 高级参数

```bash
pbrun minimap2 \
    --ref GRCh38.fa \
    --in-fq reads.fastq \
    --out-bam sample.bam \
    --align-type map-hifi \
    --out-duplicate-metrics dup_metrics.txt
```

## 3. ont_germline：ONT专用端到端流程

```bash
pbrun ont_germline \
    --ref GRCh38.fa \
    --in-fq ont_reads.fastq \
    --out-bam sample.ont.bam \
    --out-vcf sample.ont.vcf.gz
```

**内部流程**：
```
ONT FASTQ ──► minimap2 (GPU) ──► DeepVariant ONT模型 (GPU) ──► VCF
```

### 带已知位点BQSR

```bash
pbrun ont_germline \
    --ref GRCh38.fa \
    --in-fq ont_reads.fastq \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --out-bam sample.ont.bam \
    --out-recal-file sample.ont.recal.txt \
    --out-vcf sample.ont.vcf.gz
```

## 4. pacbio_germline：PacBio HiFi专用端到端流程

```bash
pbrun pacbio_germline \
    --ref GRCh38.fa \
    --in-fq hifi_reads.fastq \
    --out-bam sample.hifi.bam \
    --out-vcf sample.hifi.vcf.gz
```

**内部流程**：
```
HiFi FASTQ ──► minimap2 (GPU) ──► DeepVariant PacBio模型 (GPU) ──► VCF
```

### 完整参数

```bash
pbrun pacbio_germline \
    --ref GRCh38.fa \
    --in-fq hifi_reads.fastq \
    "@RG\tID:sample\tSM:sample\tPL:PACBIO\tLB:lib1" \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --out-bam sample.hifi.bam \
    --out-recal-file sample.hifi.recal.txt \
    --out-vcf sample.hifi.vcf.gz \
    --num-gpus 2
```

## 5. 使用DeepVariant进行长读序变异检测

```bash
# PacBio HiFi
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.hifi.bam \
    --model-type PACBIO \
    --out-vcf sample.deepvariant.vcf.gz \
    --out-gvcf sample.deepvariant.g.vcf.gz

# ONT
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.ont.bam \
    --model-type ONT_R104 \
    --out-vcf sample.deepvariant.vcf.gz \
    --out-gvcf sample.deepvariant.g.vcf.gz
```

### DeepVariant长读序模型

| 模型 | 平台 | 准确性 |
|------|------|--------|
| `PACBIO` | PacBio HiFi | SNP F1 >99.9%, Indel F1 >99.5% |
| `ONT_R104` | ONT R10.4 | SNP F1 ~99%, Indel F1 ~95% |
| `HYBRID` | PacBio+Illumina | 结合优势 |

## 6. 长读序质控

### 读长统计

```bash
# NanoPlot (ONT)
NanoPlot --fastq ont_reads.fastq -o nanoplot_out

# SeqKit
seqkit stats hifi_reads.fastq

# 自定义统计
awk 'NR%4==2 {sum+=length($0); n++; if(length($0)>min) min=length($0); if(length($0)>max) max=length($0)} END {print "Mean:", sum/n, "Min:", min, "Max:", max}' reads.fastq
```

### BAM质控

```bash
# 比对统计
samtools flagstat sample.hifi.bam

# 读长分布（BAM中）
samtools view sample.hifi.bam | awk '{print length($10)}' | sort -n | uniq -c
```

### 长读序QC标准

| 指标 | PacBio HiFi | ONT R10.4 |
|------|------------|-----------|
| 平均读长 | 10-20kb | 10-50kb |
| N50读长 | 15-25kb | 20-100kb |
| 读准确性 | >99.9% | >99% |
| 比对率 | >90% | >85% |
| 覆盖度(30x) | 推荐 | 推荐 |

## 7. 完整长读序批量脚本

### PacBio HiFi

```bash
#!/bin/bash
# gpu_pacbio_pipeline.sh

SAMPLE=$1
REF=$2
FQ=$3
OUTDIR=$4

mkdir -p ${OUTDIR}

echo "=========================================="
echo "PacBio HiFi GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# 端到端流程
echo "[1/1] GPU PacBio Germline..."
pbrun pacbio_germline \
    --ref ${REF} \
    --in-fq ${FQ} \
    "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:PACBIO\tLB:lib1" \
    --out-bam ${OUTDIR}/${SAMPLE}.hifi.bam \
    --out-vcf ${OUTDIR}/${SAMPLE}.hifi.vcf.gz

# 统计
echo "[QC] Statistics..."
samtools flagstat ${OUTDIR}/${SAMPLE}.hifi.bam > ${OUTDIR}/${SAMPLE}.flagstat
bcftools stats ${OUTDIR}/${SAMPLE}.hifi.vcf.gz > ${OUTDIR}/${SAMPLE}.vcf.stats

echo "=========================================="
echo "Complete:"
echo "BAM: ${OUTDIR}/${SAMPLE}.hifi.bam"
echo "VCF: ${OUTDIR}/${SAMPLE}.hifi.vcf.gz"
echo "=========================================="
```

### ONT

```bash
#!/bin/bash
# gpu_ont_pipeline.sh

SAMPLE=$1
REF=$2
FQ=$3
OUTDIR=$4

mkdir -p ${OUTDIR}

echo "=========================================="
echo "ONT GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# 端到端流程
echo "[1/1] GPU ONT Germline..."
pbrun ont_germline \
    --ref ${REF} \
    --in-fq ${FQ} \
    "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ONT\tLB:lib1" \
    --out-bam ${OUTDIR}/${SAMPLE}.ont.bam \
    --out-vcf ${OUTDIR}/${SAMPLE}.ont.vcf.gz

# 统计
echo "[QC] Statistics..."
samtools flagstat ${OUTDIR}/${SAMPLE}.ont.bam > ${OUTDIR}/${SAMPLE}.flagstat
bcftools stats ${OUTDIR}/${SAMPLE}.ont.vcf.gz > ${OUTDIR}/${SAMPLE}.vcf.stats

echo "=========================================="
echo "Complete:"
echo "BAM: ${OUTDIR}/${SAMPLE}.ont.bam"
echo "VCF: ${OUTDIR}/${SAMPLE}.ont.vcf.gz"
echo "=========================================="
```

## 8. 资源需求

| 平台 | 显存 | 30x覆盖时间 | 输出BAM |
|------|------|------------|---------|
| PacBio HiFi | 16-24GB | ~20-30min | ~40-60GB |
| ONT | 16-24GB | ~15-25min | ~30-50GB |

## 9. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `minimap2` | minimap2 2.26 | `pbrun minimap2 --help` |
| `ont_germline` | minimap2 2.26 + DeepVariant ONT_R104 | `pbrun ont_germline --help` |
| `pacbio_germline` | minimap2 2.26 + DeepVariant PACBIO | `pbrun pacbio_germline --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 10. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| ONT模型准确性 | ONT_R104模型针对特定化学版本 | 确认basecaller版本与模型匹配 |

## 11. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 比对率低 | 参考基因组版本不匹配 | 确认参考版本与reads一致 |
| HiFi变异准确性低 | 覆盖度不足 | HiFi需≥30x，推荐≥40x |
| ONT假阳性高 | 原始准确性低 | 使用R10.4+化学，basecalling用super-accuracy |
| 结构变异未检测 | Parabricks仅检测SNV/indel | 需额外用Sniffles/SVIM等 |
| 内存不足 | reads文件过大 | 分批次处理或增加GPU显存 |

## 相关技能

- bio-genomics-alignment-gpu - 短读序GPU比对
- bio-genomics-variant-germline-gpu - 短读序GPU变异检测
- bio-genomics-pangenome-gpu - 泛基因组分析（与长读序互补）
