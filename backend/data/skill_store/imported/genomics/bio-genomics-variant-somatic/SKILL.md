---
name: bio-genomics-variant-somatic
description: 体细胞变异检测，使用Mutect2或Strelka2从肿瘤-正常配对样本中检测somatic SNV和indel。Use for somatic mutation calling from tumor-normal pairs.
tool_type: cli
primary_tool: GATK Mutect2/Strelka2
prerequisites:
  - 肿瘤和正常样本的BAM文件
  - 参考基因组
---

# 体细胞变异检测

从肿瘤-正常配对样本中检测体细胞突变（somatic mutations），区分肿瘤特有的变异和生殖细胞变异。

## 与生殖细胞变异的区别

| 特征 | 生殖细胞变异 (Germline) | 体细胞变异 (Somatic) |
|------|------------------------|---------------------|
| 样本 | 单样本或家系 | 肿瘤-正常配对 |
| 变异来源 | 遗传获得 | 后天获得（肿瘤发生） |
| 等位基因频率 | ~0%, 50%, 100% | 任意（肿瘤纯度影响） |
| 主要工具 | HaplotypeCaller/DeepVariant | Mutect2/Strelka2 |
| VAF预期 | 0/1或1/1 | 通常0.05-0.5 |

## 1. GATK Mutect2（推荐）

### 安装

```bash
gatk --version  # GATK 4.5+
```

### Step 1: 创建Panel of Normals (PoN)

PoN用于过滤技术噪音和常见的生殖细胞变异。

```bash
# 为每个正常样本创建gVCF
for normal in normal1.bam normal2.bam normal3.bam; do
    sample=$(basename $normal .bam)
    gatk Mutect2 \
        -R GRCh38.fa \
        -I $normal \
        --max-mnp-distance 0 \
        -O ${sample}.vcf.gz
done

# 合并到GenomicsDB
gatk GenomicsDBImport \
    -R GRCh38.fa \
    --genomicsdb-workspace-path pon_db \
    -V normal1.vcf.gz \
    -V normal2.vcf.gz \
    -V normal3.vcf.gz \
    -L targets.interval_list  # WES需要

# 创建PoN
gatk CreateSomaticPanelOfNormals \
    -R GRCh38.fa \
    -V gendb://pon_db \
    -O pon.vcf.gz
```

### Step 2: 体细胞变异检测

```bash
gatk Mutect2 \
    -R GRCh38.fa \
    -I tumor.bam \
    -I normal.bam \
    -normal normal_sample_name \
    --germline-resource af-only-gnomad.vcf.gz \
    --panel-of-normals pon.vcf.gz \
    --f1r2-tar-gz f1r2.tar.gz \
    -O unfiltered.vcf.gz
```

### Step 3: 方向偏倚校正

```bash
gatk LearnReadOrientationModel \
    -I f1r2.tar.gz \
    -O read-orientation-model.tar.gz
```

### Step 4: 污染估计

```bash
# 计算pileup summaries
gatk GetPileupSummaries \
    -I tumor.bam \
    -V small_exac_common.vcf.gz \
    -L small_exac_common.vcf.gz \
    -O tumor_pileups.table

gatk GetPileupSummaries \
    -I normal.bam \
    -V small_exac_common.vcf.gz \
    -L small_exac_common.vcf.gz \
    -O normal_pileups.table

# 计算污染
gatk CalculateContamination \
    -I tumor_pileups.table \
    -matched normal_pileups.table \
    -O contamination.table \
    --tumor-segmentation segments.table
```

### Step 5: 过滤

```bash
gatk FilterMutectCalls \
    -R GRCh38.fa \
    -V unfiltered.vcf.gz \
    --contamination-table contamination.table \
    --tumor-segmentation segments.table \
    --ob-priors read-orientation-model.tar.gz \
    -O filtered.vcf.gz

# 提取PASS变异
bcftools view -f PASS filtered.vcf.gz -Oz -o somatic_final.vcf.gz
```

## 2. Strelka2（更快替代）

### 安装

```bash
conda install -c bioconda strelka
```

### 运行

```bash
# 配置
configureStrelkaSomaticWorkflow.py \
    --normalBam normal.bam \
    --tumorBam tumor.bam \
    --referenceFasta GRCh38.fa \
    --runDir strelka_run

# 执行
strelka_run/runWorkflow.py -m local -j 16

# 输出文件
# strelka_run/results/variants/somatic.snvs.vcf.gz
# strelka_run/results/variants/somatic.indels.vcf.gz

# 合并
bcftools concat \
    strelka_run/results/variants/somatic.snvs.vcf.gz \
    strelka_run/results/variants/somatic.indels.vcf.gz \
    -a -Oz -o strelka_somatic.vcf.gz
```

## 3. 体细胞变异质控

### 预期突变负荷

| 肿瘤类型 | 预期突变数/Mb | TMB分类 |
|----------|---------------|---------|
| 儿童肿瘤 | 0.1-1 | 低 |
| 实体瘤（常见） | 1-10 | 中 |
| 黑色素瘤/肺癌 | 10-100 | 高 |
| 超突变 | >100 | 超高 |

### 质控指标

```bash
# 1. 变异总数
bcftools stats somatic.vcf.gz | grep "number of SNPs"

# 2. 肿瘤纯度（来自CalculateContamination）
cat contamination.table

# 3. VAF分布
bcftools query -f '%AF\n' somatic.vcf.gz | \
    awk '{print int($1*100)/100}' | sort | uniq -c | sort -k2 -n

# 4. Ti/Tv比率（体细胞通常~2.0）
bcftools stats somatic.vcf.gz | grep TSTV
```

### 过滤低质量变异

```bash
# 基于VAF（去除极端值）
bcftools view -i 'FMT/AF[0]>0.05 && FMT/AF[0]<0.95' \
    somatic.vcf.gz -Oz -o filtered.vcf.gz

# 基于深度
bcftools view -i 'FMT/DP[0]>100' somatic.vcf.gz -Oz -o filtered.vcf.gz
```

## 4. 仅肿瘤模式（无配对正常）

当没有匹配的正常样本时：

```bash
gatk Mutect2 \
    -R GRCh38.fa \
    -I tumor.bam \
    --germline-resource af-only-gnomad.vcf.gz \
    --panel-of-normals pon.vcf.gz \
    -O tumor_only.vcf.gz
```

**注意**：假阳性率显著高于配对模式。

## 5. WGS vs WES体细胞检测

| 项目 | WGS | WES |
|------|-----|-----|
| 检测范围 | 全基因组 | 捕获区域 |
| 突变负荷 | 通常更高（非编码区） | 较低 |
| 临床相关性 | 需要筛选 | 更聚焦 |
| 运行时间 | 长 | 短 |
| 资源消耗 | 高 | 低 |

### WES特定考虑

```bash
# 必须使用-L限制到目标区域
gatk Mutect2 \
    -R GRCh38.fa \
    -I tumor.bam \
    -I normal.bam \
    -L targets.interval_list \  # WES必需
    ...
```

## 6. 肿瘤--only质控检查

| 检查项 | 正常范围 | 说明 |
|--------|----------|------|
| 突变负荷 | 与肿瘤类型匹配 | 过高可能为假阳性 |
| 已知驱动突变 | 应能检出 | 验证灵敏度 |
| 正常样本污染 | <5% | 来自CalculateContamination |
| VAF分布 | 主峰在0.2-0.5 | 受纯度影响 |

## 7. 完整体细胞分析脚本

```bash
#!/bin/bash
# somatic_calling.sh

TUMOR=$1
NORMAL=$2
NORMAL_NAME=$3
REF=$4
PON=$5
GNOMAD=$6
OUTPUT_PREFIX=$7
THREADS=${8:-8}

echo "=== Somatic Variant Calling ==="
echo "Tumor: ${TUMOR}"
echo "Normal: ${NORMAL}"

# Step 1: Mutect2 calling
echo "[1/4] Mutect2..."
gatk Mutect2 \
    -R ${REF} \
    -I ${TUMOR} \
    -I ${NORMAL} \
    -normal ${NORMAL_NAME} \
    --germline-resource ${GNOMAD} \
    --panel-of-normals ${PON} \
    --f1r2-tar-gz ${OUTPUT_PREFIX}_f1r2.tar.gz \
    --native-pair-hmm-threads ${THREADS} \
    -O ${OUTPUT_PREFIX}_unfiltered.vcf.gz

# Step 2: Learn orientation
echo "[2/4] LearnReadOrientationModel..."
gatk LearnReadOrientationModel \
    -I ${OUTPUT_PREFIX}_f1r2.tar.gz \
    -O ${OUTPUT_PREFIX}_orientation.tar.gz

# Step 3: Calculate contamination
echo "[3/4] CalculateContamination..."
gatk GetPileupSummaries -I ${TUMOR} -V ${GNOMAD} -L ${GNOMAD} \
    -O ${OUTPUT_PREFIX}_tumor_pileups.table
gatk GetPileupSummaries -I ${NORMAL} -V ${GNOMAD} -L ${GNOMAD} \
    -O ${OUTPUT_PREFIX}_normal_pileups.table
gatk CalculateContamination \
    -I ${OUTPUT_PREFIX}_tumor_pileups.table \
    -matched ${OUTPUT_PREFIX}_normal_pileups.table \
    -O ${OUTPUT_PREFIX}_contamination.table

# Step 4: Filter
echo "[4/4] FilterMutectCalls..."
gatk FilterMutectCalls \
    -R ${REF} \
    -V ${OUTPUT_PREFIX}_unfiltered.vcf.gz \
    --contamination-table ${OUTPUT_PREFIX}_contamination.table \
    --ob-priors ${OUTPUT_PREFIX}_orientation.tar.gz \
    -O ${OUTPUT_PREFIX}_filtered.vcf.gz

bcftools view -f PASS ${OUTPUT_PREFIX}_filtered.vcf.gz \
    -Oz -o ${OUTPUT_PREFIX}_somatic.vcf.gz
bcftools index ${OUTPUT_PREFIX}_somatic.vcf.gz

echo "Done: ${OUTPUT_PREFIX}_somatic.vcf.gz"
```

## 相关技能

- bio-genomics-variant-snp-indel - 生殖细胞变异检测（对比学习）
- bio-genomics-variant-filter-norm - 变异过滤
- bio-genomics-variant-interpretation - 变异注释（癌症数据库）
- bio-workflows-somatic-variant-pipeline - 完整体细胞分析工作流
- bio-genomics-variant-cnv - 体细胞CNV检测可结合使用
