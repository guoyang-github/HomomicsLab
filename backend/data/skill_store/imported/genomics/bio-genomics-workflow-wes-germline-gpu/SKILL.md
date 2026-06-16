---
name: bio-genomics-workflow-wes-germline-gpu
description: GPU加速的WES生殖细胞变异检测端到端工作流，基于NVIDIA Parabricks。Use for end-to-end WES germline variant calling with GPU acceleration.
tool_type: workflow
primary_tool: pbrun germline / pbrun fq2bam + pbrun haplotypecaller
depends_on:
  - bio-genomics-alignment-gpu
  - bio-genomics-variant-germline-gpu
workflow: true
prerequisites:
  - NVIDIA GPU (显存≥8GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 参考基因组(GRCh38)及索引
  - 捕获区域BED或Interval List
  - dbSNP和已知Indels VCF
  - clean FASTQ文件
gpu_requirements:
  - 显存: 8-16GB
  - 架构: V100/A100/H100
  - 单样本WES 100x约10-15分钟
---

# GPU加速WES生殖细胞变异检测端到端工作流

完整的全外显子组测序(WES)GPU加速分析流程。WES数据量约为WGS的1-2%，GPU加速后单样本100x WES仅需10-15分钟（CPU版本约4-6小时）。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun germline --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --interval-file /data/targets.bed --out-bam /data/out.bam --out-vcf /data/out.vcf.gz
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
pbrun germline --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --interval-file targets.bed --out-bam out.bam --out-vcf out.vcf.gz
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

## 流程概览

```
FASTQ输入
    │
    ├── [1] GPU比对+预处理 ──► pbrun fq2bam --interval-file
    │                           ├─ 比对 + 排序 + 重复标记 + BQSR (GPU)
    │                           ├─ 自动限制到捕获区域
    │                           └─ 输出: recalibrated BAM (~8-12GB)
    │                              时间: ~5min
    │
    ├── [2] GPU变异检测 ───────► pbrun haplotypecaller --interval-file
    │                           ├─ 仅分析捕获区域 (GPU)
    │                           ├─ 输出: gVCF
    │                           └─ 时间: ~3min
    │
    ├── [3] [CPU] 队列联合基因分型 ──► GATK GenomicsDBImport
    │                                   ├─ 按捕获区域分片
    │                                   └─ 输出: 队列VCF
    │
    ├── [4] [CPU] 过滤与标准化 ────────► bcftools norm/filter
    │                                   └─ 输出: filtered VCF
    │
    └── [5] [CPU] 注释 ────────────────► VEP注释
                                        └─ 输出: 注释VCF
```

### 时间对比

| 阶段 | 执行方式 | CPU流程 | GPU流程 | 加速比 |
|------|---------|---------|---------|--------|
| 比对+预处理 | **GPU** | 2-3小时 | ~5分钟 | ~25x |
| 变异检测 | **GPU** | 30-60分钟 | ~3分钟 | ~15x |
| 联合基因分型 | CPU | 30-60分钟 | 30-60分钟 | 1x |
| 过滤与标准化 | CPU | 1-2小时 | 1-2小时 | 1x |
| 注释 | CPU | 1-2小时 | 1-2小时 | 1x |
| **总计/样本** | — | **4-6小时** | **~10-15分钟** | **~20-30x** |

## WES vs WGS 关键差异

| 项目 | WGS | WES |
|------|-----|-----|
| 数据量 | ~90GB FASTQ (30x) | ~10GB FASTQ (100x) |
| 分析区域 | 全基因组 (~3Gb) | 捕获区域 (~30-60Mb) |
| GPU显存 | 16-24GB | 8-16GB |
| 单样本时间 | ~30-45min | ~10-15min |
| BAM大小 | ~60-80GB | ~8-12GB |
| 期望SNP数 | ~400万 | ~5万 |
| Ti/Tv比率 | ~2.1 | ~2.8-3.0 |
| 关键参数 | 无 | **--interval-file** |

## 方案一：端到端germline（最简单）

```bash
pbrun germline \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --interval-file targets.bed \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --out-bam sample.bam \
    --out-recal-file sample.recal.txt \
    --out-vcf sample.vcf.gz \
    --gvcf
```

**关键差异**：必须添加 `--interval-file targets.bed`

### interval-file格式支持

| 格式 | 扩展名 | 示例 |
|------|--------|------|
| BED | `.bed` | `chr1 10000 20000` |
| GATK Interval List | `.interval_list` | `@HD` header + `chr1:10001-20000` |
| Picard Interval List | `.interval_list` | 同上 |

### 捕获试剂盒常见BED来源

```bash
# Agilent SureSelect Human All Exon V6
# Twist Human Core Exome
# IDT xGen Exome Research Panel

# 从供应商获取BED后，建议排序合并
bedtools sort -i targets.bed | bedtools merge -i - > targets.merged.bed
```

## 方案二：分步流程

### Step 1: GPU比对+预处理（带捕获区域）

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --interval-file targets.bed \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --out-bam sample.recal.bam \
    --out-recal-file sample.recal.txt
```

### Step 2: GPU变异检测（限制捕获区）

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --interval-file targets.bed \
    --gvcf \
    --out-vcf sample.g.vcf.gz
```

### Step 3-5: 联合基因分型、过滤、注释（同WGS）

与WGS流程相同，但限制在捕获区域：

```bash
# 联合基因分型
gatk GenomicsDBImport \
    --genomicsdb-workspace-path genomicsdb \
    --sample-name-map sample_map.txt \
    -L targets.interval_list  # WES必须使用

gatk GenotypeGVCFs \
    -R GRCh38.fa \
    -V gendb://genomicsdb \
    -L targets.interval_list \
    -O cohort.vcf.gz

# 过滤（WES阈值可适当放宽）
bcftools filter \
    -e 'QUAL<30 || INFO/DP<10 || INFO/FS>60.0' \
    cohort.vcf.gz -Oz -o cohort.filtered.vcf.gz

# 注释
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf --cache --offline \
    --assembly GRCh38 \
    --everything --pick \
    --fork 4
```

## 方案三：使用DeepVariant（WES模式）

```bash
# 方式1: 分步
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --interval-file targets.bed \
    --out-bam sample.bam

pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.bam \
    --model-type WES \
    --interval-file targets.bed \
    --out-vcf sample.deepvariant.vcf.gz \
    --out-gvcf sample.deepvariant.g.vcf.gz

# 方式2: 端到端（germline + deepvariant不支持直接混合，需分步）
```

## WES覆盖度质控

```bash
# 使用mosdepth计算捕获区域覆盖度
mosdepth -t 4 --by targets.bed sample sample.recal.bam

# 检查关键指标
cat sample.regions.bed.gz | zcat | awk '
{
    sum+=$4; n++;
    if($4>=10) ge10++;
    if($4>=20) ge20++;
    if($4>=100) ge100++;
}
END {
    print "Mean coverage:", sum/n;
    print "% >=10x:", ge10/n*100;
    print "% >=20x:", ge20/n*100;
    print "% >=100x:", ge100/n*100;
}'
```

### WES QC标准

| 指标 | 期望值 | 说明 |
|------|--------|------|
| 平均覆盖度 | ≥100x | WES通常更深 |
| ≥10x覆盖率 | ≥95% | 目标区域 |
| ≥20x覆盖率 | ≥90% | 目标区域 |
| 比对率 | >95% | 与WGS相同 |
| 重复率 | <50% | WES容忍更高 |
| 捕获效率 | >70% | 目标区reads占比 |
| 均一性 | >80% | 覆盖度>0.2x mean |

## 完整WES批量脚本

```bash
#!/bin/bash
# gpu_wes_pipeline.sh

SAMPLE=$1
REF=$2
R1=$3
R2=$4
TARGETS=$5
OUTDIR=$6
DBSNP=${7:-"dbsnp_146.hg38.vcf.gz"}
KNOWN_INDELS=${8:-"Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"}

mkdir -p ${OUTDIR}/{bam,vcf,qc}

echo "=========================================="
echo "WES GPU Pipeline"
echo "Sample: ${SAMPLE}"
echo "Targets: ${TARGETS}"
echo "=========================================="

# Step 1: GPU比对+预处理
echo "[1/3] GPU Alignment + Preprocessing..."
pbrun fq2bam \
    --ref ${REF} \
    --in-fq ${R1} ${R2} \
    "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
    --interval-file ${TARGETS} \
    --knownSites ${DBSNP} \
    --knownSites ${KNOWN_INDELS} \
    --out-bam ${OUTDIR}/bam/${SAMPLE}.bam \
    --out-recal-file ${OUTDIR}/bam/${SAMPLE}.recal.txt

# WES覆盖度QC
echo "[QC] Coverage metrics..."
mosdepth -t 4 --by ${TARGETS} ${OUTDIR}/qc/${SAMPLE} ${OUTDIR}/bam/${SAMPLE}.bam

# Step 2: GPU变异检测
echo "[2/3] GPU Variant Calling..."
pbrun haplotypecaller \
    --ref ${REF} \
    --in-bam ${OUTDIR}/bam/${SAMPLE}.bam \
    --interval-file ${TARGETS} \
    --gvcf \
    --out-vcf ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz

# Step 3: 统计
echo "[3/3] Statistics..."
bcftools stats ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz > ${OUTDIR}/qc/${SAMPLE}.vcf.stats

echo "=========================================="
echo "Sample Complete: ${SAMPLE}"
echo "BAM: ${OUTDIR}/bam/${SAMPLE}.bam"
echo "GVCF: ${OUTDIR}/vcf/${SAMPLE}.g.vcf.gz"
echo "=========================================="
```

## 输出文件结构

```
results/
├── bam/
│   ├── sample.bam              # WES BAM (8-12GB)
│   ├── sample.bam.bai
│   └── sample.recal.txt        # BQSR表
├── vcf/
│   ├── sample.vcf.gz           # 原始VCF
│   └── sample.g.vcf.gz         # GVCF
├── qc/
│   ├── sample.regions.bed.gz   # 覆盖度 (mosdepth)
│   ├── sample.regions.bed.gz.csi
│   └── sample.vcf.stats        # VCF统计
└── cohort.vep.vcf.gz           # 最终注释结果
```

## 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `fq2bam` | BWA-MEM2 2.2.1, GATK MarkDuplicates | `pbrun fq2bam --help` |
| `haplotypecaller` | GATK 4.6.1.0 HaplotypeCaller | `pbrun haplotypecaller --help` |
| `germline` | BWA-MEM2 2.2.1 + GATK 4.6.1.0 | `pbrun germline --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 极少数边界差异 | 与GATK在极少数边界情况可能存在舍入差异 | 查阅官方精度对比文档 |
| 全流程并非全部GPU | 联合基因分型和注释仍为CPU步骤 | 见流程概览中的步骤标注 |

## 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 比对BAM过大 | 未使用--interval-file | 添加捕获区域BED |
| 捕获区外变异 | interval file未生效 | 检查BED格式和染色体命名 |
| 覆盖度不均一 | 捕获试剂盒问题 | 检查捕获效率，考虑rebalance |
| 目标区覆盖不足 | 测序深度不够 | 增加测序量或降低质控阈值 |
| 与WGS结果不一致 | WES只检测外显子 | 这是正常的，WES不检测内含子/调控区 |
| DeepVariant WES报错 | --model-type错误 | 使用`--model-type WES` |

## 相关技能

- bio-genomics-workflow-wgs-germline-gpu - WGS版本GPU流程
- bio-genomics-alignment-gpu - GPU加速比对
- bio-genomics-variant-germline-gpu - GPU加速变异检测
- bio-genomics-variant-filter-norm - 变异过滤标准化
