---
name: bio-mrna-seq-fusion-gpu
description: GPU加速的RNA-seq融合基因检测，基于NVIDIA Parabricks starfusion。Use for gene fusion detection from RNA-seq with GPU acceleration.
tool_type: cli
primary_tool: pbrun starfusion
prerequisites:
  - NVIDIA GPU (显存≥8GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 参考基因组(GRCh38)及索引
  - GTF基因注释文件
  - clean FASTQ文件
gpu_requirements:
  - 显存: 8-16GB
  - 架构: V100/A100/H100
  - 融合检测约10-15分钟
---

# GPU加速RNA-seq融合基因检测

基于NVIDIA Parabricks的GPU加速融合基因检测，对应CPU工具STAR-Fusion。直接从FASTQ输入检测基因融合事件，无需上游比对步骤。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun starfusion --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --gtf /data/genes.gtf --fusion-output-dir /data/fusion_out
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
pbrun starfusion --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --gtf genes.gtf --fusion-output-dir fusion_out
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
| 融合检测 | STAR-Fusion | `starfusion` | ~10-15min | **~10x** |

## 2. 与RNA-seq比对的关系

> **重要说明**：`starfusion` 是**独立工具**，不依赖上游 `rna_fq2bam` 的BAM输出。它直接从FASTQ输入完成融合检测的全部计算步骤。

| 需求场景 | 需要运行的工具 |
|---------|-------------|
| 仅需融合检测 | 只需 `starfusion` |
| 仅需RNA-seq比对BAM | 只需 `rna_fq2bam` |
| 同时需要比对BAM + 融合检测 | `rna_fq2bam` + `starfusion`（独立运行） |

## 3. starfusion：GPU加速融合基因检测

### 基础用法

```bash
pbrun starfusion \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.fusion.bam \
    --fusion-output-dir fusion_out \
    --gtf Homo_sapiens.GRCh38.109.gtf
```

### 关键参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--gtf` | 基因注释文件 | Ensembl/Gencode GTF |
| `--fusion-output-dir` | 融合检测结果输出目录 | 必需 |
| `--out-bam` | 输出BAM（可选） | 包含chimeric reads |

### 融合检测结果

```
fusion_out/
├── star-fusion.fusion_predictions.tsv          # 主要预测结果
├── star-fusion.fusion_predictions.abridged.tsv  # 简化版
└── star-fusion.fusion_predictions.json          # JSON格式
```

### 结果解读

| 列名 | 说明 |
|------|------|
| `#FusionName` | 融合基因名称（如BCR--ABL1） |
| `LeftGene` | 5'端基因 |
| `RightGene` | 3'端基因 |
| `LeftBreakpoint` | 5'端断点位置 |
| `RightBreakpoint` | 3'端断点位置 |
| `JunctionReadCount` | 跨越断点的reads数 |
| `SpanningFragCount` | 支持融合的spanning reads |
| `FFPM` | 每百万片段数 |

## 4. 完整融合检测流程

```bash
#!/bin/bash
# gpu_fusion_detection.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
GTF=$5
OUTDIR=$6

mkdir -p ${OUTDIR}/{fusion, qc}

echo "=========================================="
echo "Fusion Detection GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "=========================================="

# GPU融合检测
echo "[1/2] GPU Fusion Detection..."
pbrun starfusion \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    --out-bam ${OUTDIR}/fusion/${SAMPLE}.fusion.bam \
    --fusion-output-dir ${OUTDIR}/fusion/${SAMPLE}_fusion \
    --gtf ${GTF}

# 统计
echo "[2/2] Statistics..."
FUSION_FILE="${OUTDIR}/fusion/${SAMPLE}_fusion/star-fusion.fusion_predictions.tsv"
if [ -f "${FUSION_FILE}" ]; then
    NUM_FUSIONS=$(tail -n +2 "${FUSION_FILE}" | wc -l)
    echo "Detected fusions: ${NUM_FUSIONS}"
else
    echo "Fusion output not found"
fi

echo "=========================================="
echo "Complete:"
echo "Fusion: ${FUSION_FILE}"
echo "=========================================="
```

## 5. 质控指标

| 指标 | 期望值 | 说明 |
|------|--------|------|
| 融合基因数 | 0-数十 | 肿瘤样本可能较多，正常样本应极少 |
| 已知致癌融合 | 视癌种而定 | 如BCR-ABL1（CML）、EML4-ALK（NSCLC） |
| FFPM阈值 | >0.1 | 可信融合通常FFPM > 0.1 |
| JunctionReadCount | >3 | 至少3条reads支持 |

### 常见致癌融合参考

| 癌种 | 常见融合 | 临床意义 |
|------|---------|---------|
| 慢性髓性白血病(CML) | BCR--ABL1 | 伊马替尼靶点 |
| 非小细胞肺癌(NSCLC) | EML4--ALK | 克唑替尼靶点 |
| 前列腺癌 | TMPRSS2--ERG | 预后标志物 |
| 软组织肉瘤 | FUS--CHOP | 诊断标志物 |

## 6. 资源需求

| 步骤 | 显存 | 时间 | 输出大小 |
|------|------|------|---------|
| starfusion | 8-16GB | ~10-15min | ~2-5GB |

## 7. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `starfusion` | STAR-Fusion 1.12.0 | `pbrun starfusion --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 8. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 融合检测版本差异 | `starfusion`与独立STAR-Fusion版本可能不同 | 关键结果用独立工具验证 |

## 9. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 融合检测结果为空 | 无融合/参数过严 | 检查样本类型，肿瘤样本应更可能有结果 |
| GTF版本不匹配 | GTF与参考基因组版本不一致 | 使用同一版本（如GRCh38=Ensembl 109） |
| 输出目录不可写 | 权限不足 | 检查--fusion-output-dir路径权限 |
| 与独立STAR-Fusion结果不一致 | 版本差异 | 使用相同版本的参考数据和注释 |

## 相关技能

- bio-mrna-seq-alignment-gpu - GPU加速RNA-seq比对
- bio-genomics-variant-germline-gpu - GPU加速变异检测
