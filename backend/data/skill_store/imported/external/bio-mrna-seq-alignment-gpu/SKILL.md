---
name: bio-mrna-seq-alignment-gpu
description: GPU加速的RNA-seq比对，基于NVIDIA Parabricks rna_fq2bam。Use for RNA-seq alignment to reference genome with GPU acceleration.
tool_type: cli
primary_tool: pbrun rna_fq2bam
prerequisites:
  - NVIDIA GPU (显存≥8GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 参考基因组(GRCh38)及索引
  - GTF基因注释文件
  - clean FASTQ文件
gpu_requirements:
  - 显存: 8-16GB
  - 架构: V100/A100/H100
  - RNA-seq比对约5-10分钟
---

# GPU加速RNA-seq比对

基于NVIDIA Parabricks的GPU加速RNA-seq比对，将STAR比对从1-2小时压缩到5-10分钟。输出标准BAM文件，可直接用于表达定量、变异检测等下游分析。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun rna_fq2bam --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --gtf /data/genes.gtf --out-bam /data/out.bam
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
pbrun rna_fq2bam --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --gtf genes.gtf --out-bam out.bam
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

| 步骤 | CPU工具 | GPU工具 | 时间 | 加速比 |
|------|---------|---------|------|--------|
| RNA-seq比对 | STAR | `rna_fq2bam` | ~5-10min | **~10x** |

## 2. rna_fq2bam：GPU加速STAR比对

### 基础用法

```bash
pbrun rna_fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.rna.bam \
    --gtf Homo_sapiens.GRCh38.109.gtf \
    --out-tmp-dir /tmp/star_tmp
```

### 带Read Group

```bash
pbrun rna_fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --out-bam sample.rna.bam \
    --gtf Homo_sapiens.GRCh38.109.gtf
```

### 2-pass比对模式（推荐）

```bash
pbrun rna_fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.rna.bam \
    --gtf Homo_sapiens.GRCh38.109.gtf \
    --two-pass-mode Basic \
    --out-tmp-dir /tmp/star_tmp
```

### 关键参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--gtf` | 基因注释文件 | Ensembl/Gencode GTF |
| `--two-pass-mode` | 2-pass比对 | `Basic`（发现新剪接） |
| `--out-tmp-dir` | STAR临时目录 | SSD路径，空间≥50GB |
| `--alignIntronMax` | 最大内含子长度 | 100000（植物可增大） |
| `--alignIntronMin` | 最小内含子长度 | 21 |

## 3. RNA-seq vs DNA-seq 关键差异

| 项目 | DNA-seq (fq2bam) | RNA-seq (rna_fq2bam) |
|------|------------------|---------------------|
| 剪接处理 | 无 | 有（跨内含子比对） |
| 内含子 | 比对到基因组 | 跳过（reads跨越） |
| 链特异性 | 不分 | 可指定（dUTP方法） |
| 基因注释 | 不需要 | **必须提供GTF** |
| 2-pass | 不需要 | 推荐（发现新剪接） |

## 4. 完整RNA-seq比对流程

```bash
#!/bin/bash
# gpu_rnaseq_alignment.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
GTF=$5
OUTDIR=$6

mkdir -p ${OUTDIR}/{bam, qc}

echo "=========================================="
echo "RNA-seq GPU Alignment"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# GPU比对
echo "[1/2] GPU RNA-seq Alignment..."
pbrun rna_fq2bam \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    --out-bam ${OUTDIR}/bam/${SAMPLE}.rna.bam \
    --gtf ${GTF} \
    --two-pass-mode Basic \
    --out-tmp-dir /tmp/${SAMPLE}_star_tmp

# BAM统计
echo "[2/2] Statistics..."
samtools flagstat ${OUTDIR}/bam/${SAMPLE}.rna.bam \
    > ${OUTDIR}/qc/${SAMPLE}.flagstat

# 统计比对率
MAPPED=$(grep "primary mapped" ${OUTDIR}/qc/${SAMPLE}.flagstat | awk '{print $1}')
TOTAL=$(grep "total" ${OUTDIR}/qc/${SAMPLE}.flagstat | head -1 | awk '{print $1}')
echo "Mapping rate: $(echo "scale=2; $MAPPED / $TOTAL * 100" | bc)%"

echo "=========================================="
echo "Complete:"
echo "BAM: ${OUTDIR}/bam/${SAMPLE}.rna.bam"
echo "=========================================="
```

## 5. 下游分析建议

### 表达定量（需额外CPU工具）

Parabricks `rna_fq2bam` 输出标准BAM文件，可用以下工具进行表达定量：

```bash
# featureCounts
featureCounts -a annotation.gtf -o counts.txt sample.rna.bam

# salmon (quasi-mapping，无需BAM)
salmon quant -i index -l A -1 read1.fq.gz -2 read2.fq.gz -o salmon_out

# StringTie
cufflinks/stringtie sample.rna.bam -G annotation.gtf -o stringtie_out
```

### 变异检测

RNA-seq BAM可用于检测RNA编辑位点和转录本水平的变异，但需注意：
- RNA编辑（A-to-I）会表现为假阳性变异
- 建议与DNA-seq结果对比，或使用RNA专用变异检测工具

## 6. 质控指标

| 指标 | 期望值 | 说明 |
|------|--------|------|
| 比对率 | >70% | RNA-seq通常低于DNA |
| 唯一比对率 | >60% | 多基因区域会有多比对 |
| 剪接 reads | 可变 | 取决于样本类型 |
| rRNA残留 | <10% | 文库制备质量指标 |

```bash
# 检查rRNA比例
samtools view sample.rna.bam | grep "rRNA\|ribosomal" | wc -l

# 检查剪接junction
samtools view sample.rna.bam | grep "N" | head
```

## 7. 资源需求

| 步骤 | 显存 | 时间 | 输出大小 |
|------|------|------|---------|
| rna_fq2bam | 8-16GB | ~5-10min | ~5-10GB |
| 临时文件 | — | — | ~30-50GB |

## 8. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `rna_fq2bam` | STAR 2.7.11a | `pbrun rna_fq2bam --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 9. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |

## 10. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 比对率低(<50%) | rRNA未去除/GTF不匹配 | 检查rRNA去除，确认GTF版本 |
| 临时目录空间不足 | --out-tmp-dir路径空间不够 | 使用SSD大空间路径 |
| GTF版本不匹配 | GTF与参考基因组版本不一致 | 使用同一版本（如GRCh38=Ensembl 109） |
| 2-pass模式报错 | 临时目录残留 | 清理--out-tmp-dir后重试 |

## 相关技能

- bio-genomics-alignment-gpu - GPU加速DNA比对
- bio-mrna-seq-fusion-gpu - GPU加速RNA-seq融合基因检测
- bio-genomics-variant-germline-gpu - GPU加速变异检测
