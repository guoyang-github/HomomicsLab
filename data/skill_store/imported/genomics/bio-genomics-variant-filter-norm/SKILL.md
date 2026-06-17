---
name: bio-genomics-variant-filter-norm
description: 变异过滤、标准化和质量控制。包括VQSR、硬过滤、bcftools过滤和VCF操作。Use for filtering and normalizing VCF files.
tool_type: cli
primary_tool: GATK/bcftools
prerequisites:
  - 原始VCF文件
  - 参考基因组
---

# 变异过滤与标准化

对变异检测结果进行标准化、过滤和质量控制，确保 downstream 分析的可靠性。

## 1. 变异标准化(bcftools norm)

标准化确保变异的一致表示，便于比较和数据库注释。

### 基础标准化

```bash
# 左对齐indels + 拆分多等位位点
bcftools norm -f GRCh38.fa -m-any input.vcf.gz -Oz -o normalized.vcf.gz
bcftools index normalized.vcf.gz
```

### 标准化选项

| 选项 | 说明 |
|------|------|
| `-f` | 参考基因组FASTA |
| `-m-any` | 拆分所有多等位位点 |
| `-m-snps` | 仅拆分多等位SNPs |
| `-m-indels` | 仅拆分多等位indels |
| `-m+any` | 合并biallelic到multiallelic |
| `-d exact` | 移除重复记录 |
| `--atomize` | 拆分MNPs为单个SNPs |

### 处理参考等位基因不匹配

```bash
# 设置正确的参考等位基因
bcftools norm -f GRCh38.fa -c s input.vcf.gz -Oz -o fixed.vcf.gz

# 或排除不匹配的位点
bcftools norm -f GRCh38.fa -c x input.vcf.gz -Oz -o clean.vcf.gz
```

## 2. VQSR(Variant Quality Score Recalibration)

机器学习方法过滤变异，需要大量变异(>30个WGS或WES样本)。

### SNP VQSR

```bash
# Step 1: 构建模型
gatk VariantRecalibrator \
    -R GRCh38.fa \
    -V input.vcf.gz \
    --resource:hapmap,known=false,training=true,truth=true,prior=15.0 hapmap.vcf.gz \
    --resource:omni,known=false,training=true,truth=false,prior=12.0 omni.vcf.gz \
    --resource:1000G,known=false,training=true,truth=false,prior=10.0 1000G_omni2.5.vcf.gz \
    --resource:dbsnp,known=true,training=false,truth=false,prior=2.0 dbsnp.vcf.gz \
    -an QD -an MQ -an MQRankSum -an ReadPosRankSum -an FS -an SOR \
    -mode SNP \
    -O snp.recal \
    --tranches-file snp.tranches

# Step 2: 应用过滤
gatk ApplyVQSR \
    -R GRCh38.fa \
    -V input.vcf.gz \
    -O snp_vqsr.vcf.gz \
    --recal-file snp.recal \
    --tranches-file snp.tranches \
    --truth-sensitivity-filter-level 99.5 \
    -mode SNP
```

### Indel VQSR

```bash
# 构建模型
gatk VariantRecalibrator \
    -R GRCh38.fa \
    -V snp_vqsr.vcf.gz \
    --resource:mills,known=false,training=true,truth=true,prior=12.0 Mills.vcf.gz \
    --resource:dbsnp,known=true,training=false,truth=false,prior=2.0 dbsnp.vcf.gz \
    -an QD -an MQRankSum -an ReadPosRankSum -an FS -an SOR \
    -mode INDEL \
    --max-gaussians 4 \
    -O indel.recal \
    --tranches-file indel.tranches

# 应用过滤
gatk ApplyVQSR \
    -R GRCh38.fa \
    -V snp_vqsr.vcf.gz \
    -O final_vqsr.vcf.gz \
    --recal-file indel.recal \
    --tranches-file indel.tranches \
    --truth-sensitivity-filter-level 99.0 \
    -mode INDEL
```

## 3. 硬过滤(Hard Filter)

当样本量不足时使用固定阈值过滤。

### GATK VariantFiltration

```bash
# 分离SNPs和Indels
gatk SelectVariants -R GRCh38.fa -V input.vcf.gz --select-type-to-include SNP -O snps.vcf.gz
gatk SelectVariants -R GRCh38.fa -V input.vcf.gz --select-type-to-include INDEL -O indels.vcf.gz

# SNP过滤
gatk VariantFiltration \
    -R GRCh38.fa \
    -V snps.vcf.gz \
    -O snps.filtered.vcf.gz \
    --filter-expression "QD < 2.0" --filter-name "QD2" \
    --filter-expression "FS > 60.0" --filter-name "FS60" \
    --filter-expression "MQ < 40.0" --filter-name "MQ40" \
    --filter-expression "MQRankSum < -12.5" --filter-name "MQRankSum-12.5" \
    --filter-expression "ReadPosRankSum < -8.0" --filter-name "ReadPosRankSum-8" \
    --filter-expression "SOR > 3.0" --filter-name "SOR3"

# Indel过滤
gatk VariantFiltration \
    -R GRCh38.fa \
    -V indels.vcf.gz \
    -O indels.filtered.vcf.gz \
    --filter-expression "QD < 2.0" --filter-name "QD2" \
    --filter-expression "FS > 200.0" --filter-name "FS200" \
    --filter-expression "ReadPosRankSum < -20.0" --filter-name "ReadPosRankSum-20" \
    --filter-expression "SOR > 10.0" --filter-name "SOR10"

# 合并
gatk MergeVcfs -I snps.filtered.vcf.gz -I indels.filtered.vcf.gz -O filtered.vcf.gz
```

## 4. bcftools过滤

### 基础过滤

```bash
# 硬过滤（移除）
bcftools filter -e 'QUAL<30' input.vcf.gz -Oz -o filtered.vcf.gz

# 软过滤（标记）
bcftools filter -s 'LowQual' -e 'QUAL<30' input.vcf.gz -Oz -o marked.vcf.gz

# 包含模式
bcftools filter -i 'QUAL>=30 && DP>=10' input.vcf.gz -Oz -o filtered.vcf.gz
```

### 常用过滤条件

```bash
# 质量和深度
bcftools filter -e 'QUAL<30 || INFO/DP<10' input.vcf.gz -Oz -o filtered.vcf.gz

# 链偏倚和映射质量
bcftools filter -e 'INFO/FS>60 || INFO/MQ<40' input.vcf.gz -Oz -o filtered.vcf.gz

# 基因型质量
bcftools filter -e 'FMT/GQ<20' input.vcf.gz -Oz -o filtered.vcf.gz

# 仅保留PASS
bcftools view -f PASS input.vcf.gz -Oz -o pass_only.vcf.gz
```

### 按变异类型筛选

```bash
# 仅SNPs
bcftools view -v snps -m2 -M2 input.vcf.gz -Oz -o snps.vcf.gz

# 仅Indels
bcftools view -v indels input.vcf.gz -Oz -o indels.vcf.gz

# 仅biallelic
bcftools view -m2 -M2 input.vcf.gz -Oz -o biallelic.vcf.gz
```

### 按区域筛选

```bash
# 特定区域
bcftools view -r chr1:1000000-2000000 input.vcf.gz -Oz -o region.vcf.gz

# BED文件
bcftools view -R targets.bed input.vcf.gz -Oz -o target.vcf.gz

# 排除区域
bcftools view -T ^blacklist.bed input.vcf.gz -Oz -o filtered.vcf.gz
```

## 5. WGS vs WES过滤策略

### 策略对比

| 策略 | WGS | WES | 说明 |
|------|-----|-----|------|
| VQSR | 推荐(>30样本) | 通常不适用 | WES变异数不足 |
| Hard Filter | 备选 | 主要方法 | WES标准方法 |
| 深度过滤 | DP 10-200 | DP 20-500 | WES覆盖更深 |
| 区域限制 | 不需要 | 必须 | WES限制到target±50bp |

### WES特定过滤

```bash
# WES: 更严格的深度过滤（覆盖更深）
bcftools filter -e 'INFO/DP<20 || INFO/DP>500' wes.vcf.gz -Oz -o wes.filtered.vcf.gz

# WES: 限制到目标区域（考虑±50bp侧翼）
bedtools slop -i targets.bed -g genome.txt -b 50 > targets_flank50.bed
bcftools view -R targets_flank50.bed wes.vcf.gz -Oz -o wes.target.vcf.gz
```

### 过滤后质控

```bash
# Ti/Tv比率
bcftools stats filtered.vcf.gz | grep TSTV
# WGS SNPs: ~2.1
# WES SNPs: ~2.8-3.0

# 变异数统计
bcftools stats filtered.vcf.gz | head -20

# 各过滤器统计
bcftools query -f '%FILTER\n' filtered.vcf.gz | sort | uniq -c
```

## 6. VCF操作

### 合并VCF文件

```bash
# 按样本合并（相同样本位置）
bcftools merge sample1.vcf.gz sample2.vcf.gz -Oz -o merged.vcf.gz

# 按区域合并（不同区域同一样本）
bcftools concat chr1.vcf.gz chr2.vcf.gz -Oz -o genome.vcf.gz
```

### 比较VCF文件

```bash
# 找交集
bcftools isec -p isec_output file1.vcf.gz file2.vcf.gz

# 找差异
bcftools isec -C file1.vcf.gz file2.vcf.gz -Oz -o unique.vcf.gz
```

### 提取信息

```bash
# 提取特定字段
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%DP\n' input.vcf.gz

# 提取基因型
bcftools query -f '%CHROM:%POS\t[%GT\t]\n' input.vcf.gz
```

## 7. 完整过滤流程

```bash
#!/bin/bash
# filter_pipeline.sh

VCF=$1
REF=$2
TYPE=${3:-wgs}  # wgs或wes
OUTPUT_PREFIX=$4

echo "=== Step 1: Normalization ==="
bcftools norm -f ${REF} -m-any ${VCF} -Oz -o ${OUTPUT_PREFIX}.norm.vcf.gz
bcftools index ${OUTPUT_PREFIX}.norm.vcf.gz

echo "=== Step 2: Hard Filtering ==="
if [ "${TYPE}" == "wes" ]; then
    # WES: 更严格的深度过滤
    bcftools filter -e 'QUAL<30 || INFO/DP<20 || INFO/DP>500 || INFO/FS>60' \
        ${OUTPUT_PREFIX}.norm.vcf.gz -Oz -o ${OUTPUT_PREFIX}.hard.vcf.gz
else
    # WGS: 标准深度过滤
    bcftools filter -e 'QUAL<30 || INFO/DP<10 || INFO/DP>200 || INFO/FS>60' \
        ${OUTPUT_PREFIX}.norm.vcf.gz -Oz -o ${OUTPUT_PREFIX}.hard.vcf.gz
fi

echo "=== Step 3: Extract PASS ==="
bcftools view -f PASS ${OUTPUT_PREFIX}.hard.vcf.gz -Oz -o ${OUTPUT_PREFIX}.filtered.vcf.gz
bcftools index ${OUTPUT_PREFIX}.filtered.vcf.gz

echo "=== Step 4: QC Stats ==="
bcftools stats ${OUTPUT_PREFIX}.filtered.vcf.gz > ${OUTPUT_PREFIX}.stats.txt

echo "=== Filtering Complete ==="
echo "Output: ${OUTPUT_PREFIX}.filtered.vcf.gz"
echo "Stats: ${OUTPUT_PREFIX}.stats.txt"
```

## 相关技能

- bio-genomics-variant-snp-indel - 生成原始VCF
- bio-genomics-variant-interpretation - 过滤后注释
