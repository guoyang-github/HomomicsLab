---
name: bio-genomics-variant-snp-indel
description: 小变异(SNP/indel)检测，包括GATK HaplotypeCaller、DeepVariant和bcftools。支持单样本和队列联合检测。Use for germline SNP and indel calling.
tool_type: cli
primary_tool: GATK/DeepVariant/bcftools
prerequisites:
  - Analysis-ready BAM文件
  - 参考基因组及索引
---

# 小变异检测

从BAM文件检测生殖细胞SNP和indel变异，支持GATK HaplotypeCaller、DeepVariant和bcftools三种主流工具。

## 工具选择指南

| 工具 | 速度 | 准确性 | 最佳场景 |
|------|------|--------|----------|
| GATK HaplotypeCaller | 中等 | 高 | 标准分析，队列联合检测 |
| DeepVariant | 较慢 | 最高 | 高精度需求，小规模队列 |
| bcftools | 快 | 良好 | 快速分析，大规模队列 |

## 1. GATK HaplotypeCaller

### 单样本模式

```bash
gatk HaplotypeCaller \
    -R GRCh38.fa \
    -I ${SAMPLE}.recal.bam \
    -O ${SAMPLE}.vcf.gz \
    -native-pair-hmm-threads 4
```

### WES模式（关键差异：-L参数）

```bash
gatk HaplotypeCaller \
    -R GRCh38.fa \
    -I ${SAMPLE}.recal.bam \
    -L targets.interval_list \  # WES必须限制到目标区域
    -O ${SAMPLE}.vcf.gz
```

### GVCF模式（推荐用于队列）

GVCF(Genomic VCF)记录每个位点的基因型信息，包括非变异位点，支持后续的联合基因分型。

```bash
gatk HaplotypeCaller \
    -R GRCh38.fa \
    -I ${SAMPLE}.recal.bam \
    -O ${SAMPLE}.g.vcf.gz \
    -ERC GVCF \
    -L targets.interval_list  # WES需要
```

## 2. 联合基因分型(GenotypeGVCFs)

### 使用GenomicsDBImport（推荐）

```bash
# Step 1: 创建样本映射文件
# sample_map.txt:
# sample1 /path/to/sample1.g.vcf.gz
# sample2 /path/to/sample2.g.vcf.gz

# Step 2: 导入GenomicsDB
gatk GenomicsDBImport \
    --genomicsdb-workspace-path genomicsdb \
    --sample-name-map sample_map.txt \
    -L intervals.interval_list  # WES必须，WGS可选

# Step 3: 联合基因分型
gatk GenotypeGVCFs \
    -R GRCh38.fa \
    -V gendb://genomicsdb \
    -O cohort.vcf.gz
```

### 使用CombineGVCFs（小样队列）

```bash
# 合并GVCFs
gatk CombineGVCFs \
    -R GRCh38.fa \
    -V sample1.g.vcf.gz \
    -V sample2.g.vcf.gz \
    -V sample3.g.vcf.gz \
    -O combined.g.vcf.gz

# 联合基因分型
gatk GenotypeGVCFs \
    -R GRCh38.fa \
    -V combined.g.vcf.gz \
    -O cohort.vcf.gz
```

## 3. DeepVariant

DeepVariant使用深度学习模型，准确性最高，适合小规模高精度分析。

### Docker运行（推荐）

```bash
# WGS
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/data/GRCh38.fa \
    --reads=/data/${SAMPLE}.bam \
    --output_vcf=/data/${SAMPLE}.deepvariant.vcf.gz \
    --output_gvcf=/data/${SAMPLE}.deepvariant.g.vcf.gz \
    --num_shards=8

# WES
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WES \
    --ref=/data/GRCh38.fa \
    --reads=/data/${SAMPLE}.bam \
    --regions=/data/targets.bed \  # WES关键差异
    --output_vcf=/data/${SAMPLE}.deepvariant.vcf.gz \
    --num_shards=8
```

### 联合检测（GLnexus）

```bash
# 生成各样本gVCF
# ... DeepVariant运行 ...

# 使用GLnexus合并
docker run -v "${PWD}:/data" quay.io/mlin/glnexus:v1.4.1 \
    /usr/local/bin/glnexus_cli \
    --config DeepVariantWGS \  # 或DeepVariantWES
    /data/*.g.vcf.gz \
    | bcftools view - -Oz -o cohort.deepvariant.vcf.gz
```

## 4. bcftools（快速分析）

适合大规模队列或快速分析。

```bash
# 单样本
bcftools mpileup -Ou -f GRCh38.fa ${SAMPLE}.bam | \
    bcftools call -mv -Oz -o ${SAMPLE}.bcftools.vcf.gz

# 多样本（联合检测）
bcftools mpileup -Ou -f GRCh38.fa *.bam | \
    bcftools call -mv -Oz -o cohort.bcftools.vcf.gz

# 建立索引
bcftools index ${SAMPLE}.bcftools.vcf.gz
```

### bcftools参数优化

```bash
bcftools mpileup \
    -Ou \
    -f GRCh38.fa \
    -q 20 \              # 最小比对质量
    -Q 20 \              # 最小碱基质量
    -d 1000 \            # 最大深度（WES可适当提高）
    --annotate FORMAT/AD,FORMAT/DP \
    ${SAMPLE}.bam | \
    bcftools call \
        -mv \
        -Oz \
        -o ${SAMPLE}.vcf.gz
```

## 5. WGS vs WES差异

### 检测范围

| 项目 | WGS | WES |
|------|-----|-----|
| 检测区域 | 全基因组(~3Gb) | 外显子区(~30-60Mb) |
| 变异数量 | ~400万SNPs, ~50万indels | ~5万SNPs, ~5千indels |
| 运行时间 | 3-4小时/样本 | 30分钟/样本 |
| Ti/Tv比 | ~2.1 | ~2.8-3.0 |

### 关键参数差异

| 参数 | WGS | WES | 说明 |
|------|-----|-----|------|
| -L intervals | 可选 | 必须 | WES必须限制到捕获区 |
| 期望覆盖度 | 30x | 100x | WES更深确保灵敏性 |
| stand-call-conf | 30 | 30 | 一致 |
| 最大深度(-d) | 250 | 1000 | WES可更深 |

### 质控指标对比

```bash
# 计算Ti/Tv比率
bcftools stats ${VCF} | grep TSTV

# WGS: ~2.1 (SNPs)
# WES: ~2.8-3.0 (SNPs，外显子区富集转换)
```

## 6. 完整变异检测脚本

### GATK WGS流程

```bash
#!/bin/bash
# variant_calling_wgs.sh

SAMPLE=$1
REF=$2
BAM=$3
OUTDIR=$4

mkdir -p ${OUTDIR}

echo "=== [1/2] HaplotypeCaller ==="
gatk HaplotypeCaller \
    -R ${REF} \
    -I ${BAM} \
    -O ${OUTDIR}/${SAMPLE}.g.vcf.gz \
    -ERC GVCF \
    -native-pair-hmm-threads 8

echo "=== [2/2] Statistics ==="
bgzip -t ${OUTDIR}/${SAMPLE}.g.vcf.gz
bcftools stats ${OUTDIR}/${SAMPLE}.g.vcf.gz > ${OUTDIR}/${SAMPLE}.stats.txt

echo "Variant calling complete: ${OUTDIR}/${SAMPLE}.g.vcf.gz"
```

### GATK WES流程（关键差异）

```bash
#!/bin/bash
# variant_calling_wes.sh

SAMPLE=$1
REF=$2
BAM=$3
TARGETS=$4  # WES必须
OUTDIR=$5

echo "=== HaplotypeCaller (WES) ==="
gatk HaplotypeCaller \
    -R ${REF} \
    -I ${BAM} \
    -L ${TARGETS} \  # 关键差异：限制到目标区域
    -O ${OUTDIR}/${SAMPLE}.g.vcf.gz \
    -ERC GVCF
```

### 联合基因分型脚本

```bash
#!/bin/bash
# joint_genotyping.sh

COHORT=$1
REF=$2
GVCF_LIST=$3  # 文件，每行一个gVCF路径
OUTDIR=$4

# 创建sample map
awk '{print "sample"NR "\t" $1}' ${GVCF_LIST} > ${OUTDIR}/sample_map.txt

# GenomicsDBImport
gatk GenomicsDBImport \
    --genomicsdb-workspace-path ${OUTDIR}/genomicsdb \
    --sample-name-map ${OUTDIR}/sample_map.txt \
    -L intervals.list  # WES需要

# GenotypeGVCFs
gatk GenotypeGVCFs \
    -R ${REF} \
    -V gendb://${OUTDIR}/genomicsdb \
    -O ${OUTDIR}/${COHORT}.vcf.gz

bcftools stats ${OUTDIR}/${COHORT}.vcf.gz > ${OUTDIR}/${COHORT}.stats.txt
```

## 7. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 变异数过少 | 覆盖度不足/过滤过严 | 检查覆盖度，调整阈值 |
| Ti/Tv异常 | 污染或系统性错误 | 检查样品，重跑BQSR |
| 假阳性高 | 重复区域/比对错误 | 过滤低复杂度区域 |
| WES目标区外变异 | 未使用-L参数 | 添加interval list |
| 联合检测内存不足 | 样本太多 | 使用GenomicsDB或分染色体运行 |

## 相关技能

- bio-genomics-bam-qc-recalibration - 生成recalibrated BAM
- bio-genomics-variant-filter-norm - 变异过滤和标准化
- bio-genomics-variant-interpretation - 变异注释和解读
