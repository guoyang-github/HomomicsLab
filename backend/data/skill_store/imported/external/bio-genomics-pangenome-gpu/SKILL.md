---
name: bio-genomics-pangenome-gpu
description: GPU加速的泛基因组分析，基于NVIDIA Parabricks giraffe和pangenome工具。Use for pangenome-aware alignment and variant calling with GPU acceleration.
tool_type: cli
primary_tool: pbrun giraffe / pbrun pangenome_germline / pbrun pangenome_aware_deepvariant
prerequisites:
  - NVIDIA GPU (显存≥24GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 泛基因组参考(GBZ格式)
  - 或线性参考基因组+Giraffe索引
  - clean FASTQ文件
gpu_requirements:
  - 显存: 24-32GB (推荐)
  - 架构: A100/H100推荐
---

# GPU加速泛基因组分析

基于NVIDIA Parabricks的GPU加速泛基因组分析，使用`giraffe`进行泛基因组比对，结合`pangenome_aware_deepvariant`提升复杂区域变异检测能力。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun giraffe --ref /data/pangenome.gbz --in-fq /data/R1.fq.gz /data/R2.fq.gz --out-bam /data/out.bam
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
pbrun giraffe --ref pangenome.gbz --in-fq R1.fq.gz R2.fq.gz --out-bam out.bam
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

## 1. 泛基因组 vs 线性参考基因组

| 特性 | 线性参考 | 泛基因组 |
|------|---------|---------|
| 参考序列 | 单倍体(如GRCh38) | 多群体单倍型图 |
| 复杂区域 | 偏差大(HLA/KIR等) | 更准确 |
| 多样本群体 | 非欧洲人群偏差 | 更公平 |
| 结构变异 | 检测困难 | 天然支持 |
| 计算需求 | 较低 | 较高 |
| 索引大小 | ~10GB | ~50-100GB |

## 2. giraffe：GPU加速泛基因组比对

### 基础用法

```bash
pbrun giraffe \
    --ref pangenome.gbz \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.pangenome.bam
```

### 带Read Group

```bash
pbrun giraffe \
    --ref pangenome.gbz \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --out-bam sample.pangenome.bam
```

### GBZ索引准备（CPU预处理，一次性）

#### 方式一：从VCF构建（推荐）

```bash
# 需要vg toolkit (https://github.com/vgteam/vg)
# Step 1: 构建泛基因组图
vg autoindex -w giraffe \
    -r GRCh38.fa \
    -v population.vcf.gz \
    -p pangenome \
    -t 16

# 输出文件:
# pangenome.gbz    - 主要索引（用于比对）
# pangenome.dist   - 距离索引
# pangenome.min    - minimizer索引
```

#### 方式二：从HPRC泛基因组下载（快速开始）

```bash
# 下载Human Pangenome Reference Consortium (HPRC)预构建索引
# 详见: https://github.com/hprc-chrom/pangenome
wget https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38.gbz
```

#### 索引文件说明

| 文件 | 大小 | 用途 | 是否必需 |
|------|------|------|---------|
| `.gbz` | ~15-30GB | 泛基因组图索引 | 是 |
| `.dist` | ~1-2GB | 距离索引（giraffe） | 是 |
| `.min` | ~2-5GB | minimizer索引 | 是 |

> **注意**：GBZ索引构建为纯CPU计算，耗时数小时至数十小时（取决于参考基因组大小和变异数量），但只需构建一次即可用于所有样本。

## 3. pangenome_germline：泛基因组端到端流程

```bash
pbrun pangenome_germline \
    --ref GRCh38.fa \
    --in-gbz pangenome.gbz \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.bam \
    --out-vcf sample.vcf.gz
```

**内部流程**：
```
FASTQ ──► giraffe (GPU) ──► pangenome_aware_deepvariant (GPU) ──► VCF
```

## 4. pangenome_aware_deepvariant：泛基因组增强变异检测

```bash
pbrun pangenome_aware_deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --in-gbz pangenome.gbz \
    --out-vcf sample.pangenome.vcf.gz
```

### 适用场景

- **复杂区域**：HLA基因座、KIR、 segmental duplications
- **多样本人群**：非洲、亚洲等非欧洲人群
- **结构变异附近**：SV断点周围的SNP/indel
- **参考基因组偏差较大区域**

## 5. 与线性参考结果对比

```bash
# 泛基因组变异检测
pbrun pangenome_aware_deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.bam \
    --in-gbz pangenome.gbz \
    --out-vcf sample.pangenome.vcf.gz

# 线性参考变异检测（对照）
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.bam \
    --model-type WGS \
    --out-vcf sample.linear.vcf.gz

# 比较
bcftools isec -p isec_out sample.pangenome.vcf.gz sample.linear.vcf.gz
```

### 预期差异

| 区域类型 | 泛基因组优势 | 预期额外检出 |
|----------|-------------|-------------|
| HLA | 大幅改善 | 数百-数千变异 |
| KIR | 大幅改善 | 数百变异 |
| 复杂重复 | 中等改善 | 数十变异 |
| 普通区域 | 相当 | 基本一致 |

## 6. 进阶：多GPU与Slurm集群运行

### 单节点多GPU

```bash
pbrun pangenome_germline \
    --ref GRCh38.fa \
    --in-gbz pangenome.gbz \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.bam \
    --out-vcf sample.vcf.gz \
    --num-gpus 2
```

### Slurm集群提交

```bash
#!/bin/bash
#SBATCH --job-name=gpu_pangenome
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --cpus-per-task=8
#SBATCH --time=2:00:00

pbrun pangenome_germline \
    --ref ${REF} \
    --in-gbz ${GBZ} \
    --in-fq ${R1} ${R2} \
    --out-bam ${OUTDIR}/${SAMPLE}.bam \
    --out-vcf ${OUTDIR}/${SAMPLE}.vcf.gz
```

## 7. 资源需求

| 步骤 | 显存 | 时间 | 说明 |
|------|------|------|------|
| giraffe比对 | 16-24GB | ~20min | GBZ索引加载占内存 |
| pangenome_germline | 24-32GB | ~40min | 端到端 |
| pangenome_aware_dv | 24-32GB | ~25min | 需加载泛基因组 |

## 8. 完整脚本

```bash
#!/bin/bash
# gpu_pangenome_pipeline.sh

SAMPLE=$1
REF=$2
GBZ=$3
R1=$4
R2=$5
OUTDIR=$6

mkdir -p ${OUTDIR}

echo "=========================================="
echo "Pangenome GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# 端到端泛基因组流程
echo "[1/1] GPU Pangenome Germline..."
pbrun pangenome_germline \
    --ref ${REF} \
    --in-gbz ${GBZ} \
    --in-fq ${R1} ${R2} \
    "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    --out-bam ${OUTDIR}/${SAMPLE}.bam \
    --out-vcf ${OUTDIR}/${SAMPLE}.vcf.gz

# 统计
echo "[QC] Statistics..."
samtools flagstat ${OUTDIR}/${SAMPLE}.bam > ${OUTDIR}/${SAMPLE}.flagstat
bcftools stats ${OUTDIR}/${SAMPLE}.vcf.gz > ${OUTDIR}/${SAMPLE}.vcf.stats

echo "=========================================="
echo "Complete:"
echo "BAM: ${OUTDIR}/${SAMPLE}.bam"
echo "VCF: ${OUTDIR}/${SAMPLE}.vcf.gz"
echo "=========================================="
```

## 9. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `giraffe` | vg giraffe (vg toolkit) | `pbrun giraffe --help` |
| `pangenome_aware_deepvariant` | DeepVariant 1.6.1 + vg giraffe | `pbrun pangenome_aware_deepvariant --help` |
| `pangenome_germline` | vg giraffe + DeepVariant | `pbrun pangenome_germline --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 10. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 泛基因组工具较新 | `pangenome_aware_deepvariant`等功能为近期新增 | 关键结果建议用CPU工具交叉验证 |
| GBZ索引构建在CPU上 | `vg autoindex`为CPU工具，非GPU加速 | 预先构建索引 |

## 11. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| GBZ索引加载慢 | 索引文件大 | 使用SSD/NVMe存储 |
| 显存不足 | 泛基因组索引占用大 | 使用A100/H100，或降低batch size |
| 与线性参考差异大 | 这是正常的 | 泛基因组在复杂区域更准确 |
| GBZ索引缺失 | 未预先构建 | 使用vg autoindex构建 |
| 速度比germline慢 | 泛基因组计算更复杂 | 正常，准确性换取时间 |

## 相关技能

- bio-genomics-alignment-gpu - 线性参考GPU比对
- bio-genomics-variant-germline-gpu - 线性参考GPU变异检测
- bio-genomics-longread-gpu - 长读序分析（与泛基因组互补）
