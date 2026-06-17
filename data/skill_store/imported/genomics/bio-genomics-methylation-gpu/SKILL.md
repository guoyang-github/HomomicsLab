---
name: bio-genomics-methylation-gpu
description: GPU加速的DNA甲基化分析，基于NVIDIA Parabricks fq2bam_meth。Use for methylation-aware alignment with GPU acceleration.
tool_type: cli
primary_tool: pbrun fq2bam_meth
prerequisites:
  - NVIDIA GPU (显存≥8GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 亚硫酸氢盐处理后的FASTQ (RRBS/WGBS)
  - 参考基因组(GRCh38)及索引
gpu_requirements:
  - 显存: 8-16GB
  - 架构: V100/A100/H100
---

# GPU加速DNA甲基化分析

基于NVIDIA Parabricks的GPU加速甲基化感知比对，对应CPU工具BWA-METH，用于亚硫酸氢盐测序(BS-seq)数据的分析。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun fq2bam_meth --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --out-bam /data/out.bam
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
pbrun fq2bam_meth --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --out-bam out.bam
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

| 步骤 | CPU工具 | GPU工具 | 加速比 |
|------|---------|---------|--------|
| 甲基化感知比对 | BWA-METH | `fq2bam_meth` | **~15x** |

## 2. fq2bam_meth：甲基化感知比对

### 基础用法

```bash
pbrun fq2bam_meth \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.meth.bam \
    --out-recal-file sample.recal.txt
```

### 带已知位点

```bash
pbrun fq2bam_meth \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --out-bam sample.meth.bam \
    --out-recal-file sample.recal.txt
```

### WGBS vs RRBS 详细对比

| 参数 | WGBS | RRBS |
|------|------|------|
| 覆盖范围 | 全基因组 | 酶切富集区域 (MspI位点) |
| 数据量 | 大 (~100GB+ FASTQ) | 小 (~10-20GB FASTQ) |
| 推荐测序深度 | 30x | 10x |
| CpG覆盖 | ~70-80%全基因组CpG | ~90%+ CpG岛/启动子 |
| 分析重点 | 全基因组甲基化图谱 | CpG岛/启动子区差异甲基化 |
| 文库制备 | 全基因组亚硫酸氢盐处理 | MspI酶切+亚硫酸氢盐处理 |
| 应用 | 全基因组甲基化研究 | 差异甲基化区域(DMR)筛选 |

### 常见甲基化捕获方法

| 方法 | 原理 | 覆盖范围 | 适用场景 |
|------|------|---------|---------|
| WGBS | 全基因组亚硫酸氢盐转换 | ~28M CpG位点 | 全图谱研究 |
| RRBS | MspI酶切富集+转换 | ~2-4M CpG位点 | CpG岛/启动子筛选 |
| MeDIP-seq | 抗5mC抗体富集 | ~23M CpG位点 | 区域甲基化分析 |
| T-WGBS | Tn5转座酶+转换 | 可调窗口 | 低输入量样本 |

### fq2bam_meth 与标准 DNA 比对的关键差异

| 项目 | 标准DNA比对 (fq2bam) | 甲基化比对 (fq2bam_meth) |
|------|---------------------|--------------------------|
| 参考基因组处理 | 直接使用 | 需转换为三种状态 (C/T/G) |
| 比对算法 | BWA-MEM2 | BWA-METH (bwameth) |
| 输出BAM标签 | 标准 | 保留BS转换信息 |
| BQSR | 支持 | 支持 |
| 下游工具 | GATK等通用工具 | MethylDackel/Bismark等专用工具 |

## 3. 下游甲基化分析

Parabricks `fq2bam_meth` 输出BAM后，需使用CPU工具进行甲基化位点提取：

### MethylDackel

```bash
# 提取CpG甲基化水平
MethylDackel extract GRCh38.fa sample.meth.bam \
    --CHG --CHH \
    -o sample.meth

# 输出: sample.meth_CpG.bedGraph
```

### Bismark (methylation extractor)

```bash
# 如果比对由bismark完成
bismark_methylation_extractor --bedGraph sample.meth.bam
```

### 甲基化位点统计

```bash
# 计算全基因组甲基化水平
awk '{sum+=$4; n++} END {print "Mean methylation:", sum/n}' sample.meth_CpG.bedGraph

# CpG覆盖度统计
wc -l sample.meth_CpG.bedGraph

# 按染色体统计
awk '{chr[$1]++; sum[$1]+=$4} END {for(c in chr) print c, sum[c]/chr[c]}' sample.meth_CpG.bedGraph
```

### 差异甲基化区域(DMR)分析 (需多样本)

```bash
# 使用 DSS 或 methylKit (R包)
# 示例: DSS 分析流程
Rscript -e '
library(DSS)
bsdata <- read.bismark(files=c("sample1.meth_CpG.txt", "sample2.meth_CpG.txt"))
dmlTest <- DMLtest(bsdata, group1=c("sample1"), group2=c("sample2"))
dmrs <- callDMR(dmlTest, p.threshold=0.01)
'
```

## 4. 进阶：Slurm集群多节点运行

```bash
#!/bin/bash
#SBATCH --job-name=gpu_meth
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=2:00:00

pbrun fq2bam_meth \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    --out-bam ${OUTDIR}/${SAMPLE}.meth.bam \
    --out-recal-file ${OUTDIR}/${SAMPLE}.recal.txt
```

## 5. 质控指标

| 指标 | 期望值 | 说明 |
|------|--------|------|
| 比对率 | >70% | BS-seq通常低于标准DNA-seq |
| C->T转换率 | >99% | 亚硫酸氢盐处理效率 |
| CpG覆盖度 | WGBS: >70% CpGs; RRBS: >90%目标区 | |
| 平均甲基化水平 | ~70-80% | 正常组织，因组织而异 |

## 6. 完整脚本

```bash
#!/bin/bash
# gpu_methylation_pipeline.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
OUTDIR=$5

mkdir -p ${OUTDIR}

echo "=========================================="
echo "Methylation GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# Step 1: GPU甲基化感知比对
echo "[1/2] GPU Methylation Alignment..."
pbrun fq2bam_meth \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    --out-bam ${OUTDIR}/${SAMPLE}.meth.bam \
    --out-recal-file ${OUTDIR}/${SAMPLE}.recal.txt

# Step 2: 甲基化提取 (CPU)
echo "[2/2] Methylation Extraction..."
MethylDackel extract ${REF} ${OUTDIR}/${SAMPLE}.meth.bam \
    -o ${OUTDIR}/${SAMPLE}

echo "=========================================="
echo "Complete:"
echo "BAM: ${OUTDIR}/${SAMPLE}.meth.bam"
echo "Methylation: ${OUTDIR}/${SAMPLE}_CpG.bedGraph"
echo "=========================================="
```

## 7. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `fq2bam_meth` | BWA-METH (bwameth) | `pbrun fq2bam_meth --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 8. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 甲基化提取需额外工具 | Parabricks仅提供比对，提取需MethylDackel | 使用配套CPU工具 |

## 9. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 比对率低 | 亚硫酸氢盐处理过度 | 检查DNA完整性 |
| 转换率低 | 亚硫酸氢盐处理不完全 | 优化处理条件 |
| BAM不能用于标准工具 | 甲基化BAM有特定标签 | 使用甲基化专用工具 |

## 相关技能

- bio-genomics-alignment-gpu - 标准DNA比对
