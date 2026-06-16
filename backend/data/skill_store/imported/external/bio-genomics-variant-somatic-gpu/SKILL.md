---
name: bio-genomics-variant-somatic-gpu
description: GPU加速的体细胞变异检测，基于NVIDIA Parabricks。支持tumor-normal配对和tumor-only模式。Use for somatic variant calling with GPU acceleration.
tool_type: cli
primary_tool: pbrun mutectcaller / pbrun deepsomatic / pbrun somatic
prerequisites:
  - NVIDIA GPU (显存≥16GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - Tumor和Normal的analysis-ready BAM
  - 参考基因组及索引
  - (可选) Panel of Normals VCF
gpu_requirements:
  - 显存: 16-24GB
  - 架构: V100/A100/H100
  - tumor-normal配对约15-20分钟
---

# GPU加速体细胞变异检测

基于NVIDIA Parabricks的GPU加速体细胞变异检测，支持GATK Mutect2和DeepSomatic两种工具，适用于肿瘤-正常配对和纯肿瘤样本分析。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun mutectcaller --ref /data/ref.fa --in-tumor-bam /data/tumor.bam --in-normal-bam /data/normal.bam --out-vcf /data/out.vcf.gz
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
pbrun mutectcaller --ref ref.fa --in-tumor-bam tumor.bam --in-normal-bam normal.bam --out-vcf out.vcf.gz
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

| 工具 | CPU时间 | GPU时间 | 加速比 | 对应关系 |
|------|---------|---------|--------|---------|
| Mutect2 (tumor-normal) | 4-6小时 | ~15分钟 | **~20x** | GATK Mutect2 |
| DeepSomatic | 6-8小时 | ~20分钟 | **~20x** | Google DeepSomatic |
| 端到端somatic | — | ~30分钟 | — | — |

## 2. 工具选择指南

| 工具 | 最佳场景 | 速度 | 输入要求 |
|------|---------|------|---------|
| `mutectcaller` | 标准肿瘤分析，GATK兼容 | 快 | tumor BAM + normal BAM |
| `deepsomatic` | 最高精度，复杂样本 | 中等 | tumor BAM + normal BAM |
| `somatic` | **端到端**：FASTQ→VCF | 最快 | tumor FASTQ + normal FASTQ |

## 3. mutectcaller：GPU版Mutect2

### Tumor-Normal配对模式

```bash
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --out-vcf somatic.vcf.gz
```

### Tumor-Only模式

```bash
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --tumor-name TUMOR \
    --out-vcf tumor_only.vcf.gz
```

### 使用Panel of Normals (PON)

```bash
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --in-pon pon.vcf.gz \
    --out-vcf somatic_pon.vcf.gz
```

### WES模式（关键：--interval-file）

```bash
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --interval-file targets.bed \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --out-vcf somatic.wes.vcf.gz
```

### 高级参数

```bash
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --in-pon pon.vcf.gz \
    --germline-resource af-only-gnomad.hg38.vcf.gz \
    --interval-file targets.bed \
    --out-vcf somatic.vcf.gz \
    --num-gpus 2
```

| 参数 | 说明 | 推荐 |
|------|------|------|
| `--in-pon` | Panel of Normals | 使用以提高特异性 |
| `--germline-resource` | gnomAD等位基因频率 | af-only-gnomad |
| `--interval-file` | 分析区域限制 | WES必需 |
| `--num-gpus` | GPU数量 | 1-2 |
| `--tumor-name` | 肿瘤样本名 | BAM中@RG SM值 |
| `--normal-name` | 正常样本名 | BAM中@RG SM值 |

## 4. deepsomatic：GPU加速深度学习体细胞检测

### Tumor-Normal

```bash
pbrun deepsomatic \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --out-vcf somatic.deep.vcf.gz \
    --model-type WGS
```

### Tumor-Only

```bash
pbrun deepsomatic \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --out-vcf tumor_only.deep.vcf.gz \
    --model-type WGS
```

### 模型类型

| 模型 | 适用场景 |
|------|---------|
| `WGS` | 全基因组短读序 |
| `WES` | 全外显子组 |
| `PACBIO` | PacBio HiFi |
| `ONT` | Oxford Nanopore |

## 5. somatic：端到端体细胞流程

```bash
pbrun somatic \
    --ref GRCh38.fa \
    --in-tumor-fq tumor_R1.fq.gz tumor_R2.fq.gz \
    --in-normal-fq normal_R1.fq.gz normal_R2.fq.gz \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --out-tumor-bam tumor.bam \
    --out-normal-bam normal.bam \
    --out-vcf somatic.vcf.gz
```

**内部流程**：
```
Tumor FASTQ ──► fq2bam ──► mutectcaller ──► VCF
Normal FASTQ ──► fq2bam ──┘
```

### 带PON的端到端

```bash
pbrun somatic \
    --ref GRCh38.fa \
    --in-tumor-fq tumor_R1.fq.gz tumor_R2.fq.gz \
    --in-normal-fq normal_R1.fq.gz normal_R2.fq.gz \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --in-pon pon.vcf.gz \
    --germline-resource af-only-gnomad.hg38.vcf.gz \
    --interval-file targets.bed \
    --out-tumor-bam tumor.bam \
    --out-normal-bam normal.bam \
    --out-vcf somatic.vcf.gz
```

## 6. Panel of Normals (PON) 构建

### Step 1: 各normal样本变异检测

```bash
# 对每个normal样本运行mutectcaller（tumor-only模式）
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam normal1.recal.bam \
    --tumor-name NORMAL1 \
    --out-vcf normal1.mutect.vcf.gz
```

### Step 2: 合并为PON (使用GATK)

```bash
# 使用GATK CreateSomaticPanelOfNormals
gatk CreateSomaticPanelOfNormals \
    -vcfs normal1.mutect.vcf.gz \
    -vcfs normal2.mutect.vcf.gz \
    -vcfs normal3.mutect.vcf.gz \
    -O pon.vcf.gz
```

## 7. 变异过滤与注释

### FilterMutectCalls（GATK）

```bash
gatk FilterMutectCalls \
    -R GRCh38.fa \
    -V somatic.vcf.gz \
    --tumor-segmentation segments.tsv \
    --ob-priors read-orientation-model.tar.gz \
    -O somatic.filtered.vcf.gz
```

### VEP注释（肿瘤专用）

```bash
vep -i somatic.filtered.vcf.gz \
    -o somatic.vep.vcf.gz \
    --vcf --cache --offline \
    --assembly GRCh38 \
    --everything --pick \
    --fork 4 \
    --plugin Downstream \
    --plugin pLI,exac_pli_values.txt \
    --af --af_1kg --af_esp --af_gnomad \
    --filter_common
```

## 8. 完整批量脚本

### Tumor-Normal配对分析

```bash
#!/bin/bash
# gpu_somatic_pipeline.sh

TUMOR=$1
NORMAL=$2
REF=$3
TUMOR_BAM=$4
NORMAL_BAM=$5
OUTDIR=$6
PON=${7:-""}
TARGETS=${8:-""}

mkdir -p ${OUTDIR}

echo "=========================================="
echo "Somatic GPU Pipeline"
echo "Tumor: ${TUMOR}"
echo "Normal: ${NORMAL}"
echo "=========================================="

# 构建命令
CMD="pbrun mutectcaller \
    --ref ${REF} \
    --in-tumor-bam ${TUMOR_BAM} \
    --in-normal-bam ${NORMAL_BAM} \
    --tumor-name ${TUMOR} \
    --normal-name ${NORMAL} \
    --out-vcf ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz"

# 可选参数
if [ -n "${PON}" ]; then
    CMD="${CMD} --in-pon ${PON}"
fi
if [ -n "${TARGETS}" ]; then
    CMD="${CMD} --interval-file ${TARGETS}"
fi

echo "[1/2] GPU MutectCaller..."
eval ${CMD}

echo "[2/2] Statistics..."
bcftools stats ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz \
    > ${OUTDIR}/${TUMOR}_vs_${NORMAL}.stats

echo "=========================================="
echo "Complete: ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz"
echo "=========================================="
```

### 端到端Somatic（FASTQ输入）

```bash
#!/bin/bash
# gpu_somatic_end2end.sh

TUMOR=$1
NORMAL=$2
REF=$3
TUMOR_R1=$4
TUMOR_R2=$5
NORMAL_R1=$6
NORMAL_R2=$7
OUTDIR=$8

mkdir -p ${OUTDIR}

echo "=========================================="
echo "End-to-End Somatic GPU Pipeline"
echo "=========================================="

pbrun somatic \
    --ref ${REF} \
    --in-tumor-fq ${TUMOR_R1} ${TUMOR_R2} \
    --in-normal-fq ${NORMAL_R1} ${NORMAL_R2} \
    --tumor-name ${TUMOR} \
    --normal-name ${NORMAL} \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --out-tumor-bam ${OUTDIR}/${TUMOR}.bam \
    --out-normal-bam ${OUTDIR}/${NORMAL}.bam \
    --out-vcf ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz

echo "Complete!"
echo "Tumor BAM: ${OUTDIR}/${TUMOR}.bam"
echo "Normal BAM: ${OUTDIR}/${NORMAL}.bam"
echo "VCF: ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz"
```

## 9. 质控指标

### VCF统计

```bash
# 变异数量统计
bcftools stats somatic.vcf.gz > somatic.stats

# 查看各过滤状态
grep ^FT somatic.stats

# 查看PASS变异数
bcftools view -f PASS somatic.vcf.gz | grep -v "^#" | wc -l
```

### 肿瘤分析QC标准

| 指标 | 期望值 | 说明 |
|------|--------|------|
| 肿瘤覆盖度 | ≥100x (WES) / ≥30x (WGS) | 确保检测灵敏性 |
| 正常覆盖度 | ≥50x (WES) / ≥30x (WGS) | 用于去噪 |
| 肿瘤纯度 | >20% | 影响检测限 |
| SNV数量 | 数百-数千 | 因癌种而异 |
| Ti/Tv (SNV) | ~1.5-2.0 | 体细胞通常低于生殖细胞 |

## 10. 进阶：多GPU与集群运行

### 单节点多GPU加速

```bash
# Tumor-Normal使用2个GPU
pbrun mutectcaller \
    --ref GRCh38.fa \
    --in-tumor-bam tumor.recal.bam \
    --in-normal-bam normal.recal.bam \
    --tumor-name TUMOR \
    --normal-name NORMAL \
    --out-vcf somatic.vcf.gz \
    --num-gpus 2
```

### --num-gpus 与性能关系

| GPU数量 | 显存总量 | MutectCaller(T-N) | DeepSomatic(T-N) |
|---------|---------|-------------------|------------------|
| 1 | 16-24GB | ~15min | ~20min |
| 2 | 32-48GB | ~9-12min | ~13-16min |

> **注意**：体细胞分析涉及tumor和normal两个BAM文件，I/O开销较大，多GPU加速比通常低于生殖细胞分析。

### Slurm集群提交示例

```bash
#!/bin/bash
#SBATCH --job-name=gpu_mutect
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --time=1:00:00

pbrun mutectcaller \
    --ref ${REF} \
    --in-tumor-bam ${TUMOR_BAM} \
    --in-normal-bam ${NORMAL_BAM} \
    --tumor-name ${TUMOR} \
    --normal-name ${NORMAL} \
    --out-vcf ${OUTDIR}/${TUMOR}_vs_${NORMAL}.vcf.gz
```

## 11. 资源需求

| 模式 | 显存 | 时间(WGS) | 时间(WES) |
|------|------|-----------|-----------|
| Tumor-Normal | 16-24GB | ~15-20min | ~8-12min |
| Tumor-Only | 16-24GB | ~10-15min | ~5-8min |
| 端到端somatic | 16-24GB | ~30-40min | ~15-20min |
| DeepSomatic | 16-24GB | ~20-25min | ~10-15min |

## 12. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `mutectcaller` | GATK 4.6.1.0 Mutect2 | `pbrun mutectcaller --help` |
| `deepsomatic` | DeepSomatic (Google) | `pbrun deepsomatic --help` |
| `somatic` | BWA-MEM2 2.2.1 + GATK 4.6.1.0 | `pbrun somatic --help` |

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
| 假阳性过高 | 缺少PON或germline resource | 添加--in-pon和--germline-resource |
| 变异数极少 | 肿瘤纯度低 | 检查病理，使用tumor-only模式对比 |
| 正常样本污染 | 配对错误 | 核对BAM中的@RG信息 |
| WES未过滤 germline | 未限制捕获区域 | 添加--interval-file |
| FilterMutectCalls报错 | 缺少辅助文件 | 使用--tumor-segmentation等 |
| 与GATK Mutect2差异 | Parabricks版本 | 查阅官方兼容性说明 |

## 相关技能

- bio-genomics-variant-somatic - CPU版本(GATK Mutect2)
- bio-genomics-alignment-gpu - GPU加速比对
- bio-genomics-variant-germline-gpu - GPU加速生殖细胞变异检测
- bio-genomics-workflow-wgs-germline-gpu - WGS端到端GPU流程
