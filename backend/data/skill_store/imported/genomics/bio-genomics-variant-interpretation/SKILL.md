---
name: bio-genomics-variant-interpretation
description: 变异注释、功能预测和临床解读。包括VEP、SnpEff注释和ClinVar/ACMG临床过滤。Use for annotating and interpreting variants.
tool_type: cli
primary_tool: VEP/SnpEff/ClinVar
prerequisites:
  - 已过滤的VCF文件
  - 注释数据库
---

# 变异注释与解读

对过滤后的变异进行功能注释、致病性预测和临床相关性评估。

## 工具选择

| 工具 | 最佳场景 | 速度 | 输出格式 |
|------|----------|------|----------|
| VEP | 全面注释，临床分析 | 中等 | VCF/TSV |
| SnpEff | 快速批量注释 | 快 | VCF |
| bcftools csq | 简单后果预测 | 最快 | VCF |

## 1. VEP注释（推荐）

### 基础注释

```bash
vep -i input.vcf.gz -o output.vcf \
    --vcf \
    --cache --offline \
    --assembly GRCh38 \
    --fork 4
```

### 全面注释（推荐）

```bash
vep -i input.vcf.gz -o output.vcf \
    --vcf \
    --cache --offline \
    --assembly GRCh38 \
    --everything \              # 启用所有标准注释
    --pick \                    # 每个变异选一个最相关转录本
    --fork 4
```

### --everything包含的注释

| 选项 | 说明 |
|------|------|
| --hgvs | HGVS命名 |
| --symbol | 基因符号 |
| --canonical | 典型转录本 |
| --af | 1000G频率 |
| --af_gnomad | gnomAD频率 |
| --pubmed | PubMed ID |
| --uniprot | UniProt注释 |
| --biotype | 转录本类型 |

### 过滤高影响变异

```bash
vep -i input.vcf -o output.vcf --vcf --cache --offline \
    --pick \
    --filter "IMPACT in HIGH,MODERATE"
```

## 2. SnpEff注释

### 快速注释

```bash
# 下载数据库
snpEff download GRCh38.105

# 运行注释
snpEff ann GRCh38.105 input.vcf > output.vcf

# 带统计信息
snpEff ann -v -stats stats.html GRCh38.105 input.vcf > output.vcf
```

### SnpEff影响等级

| 等级 | 描述 | 示例 |
|------|------|------|
| HIGH | 严重影响 | 无义突变，剪接位点，移码 |
| MODERATE | 中等影响 | 错义突变，inframe indel |
| LOW | 轻微影响 | 同义突变，UTR变异 |
| MODIFIER | 可能影响 | 内含子，基因间区 |

## 3. 临床解读

### ClinVar注释

```bash
# 下载ClinVar
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi

# 用bcftools注释
bcftools annotate \
    -a clinvar.vcf.gz \
    -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT \
    input.vcf.gz -Oz -o with_clinvar.vcf.gz
```

### ClinVar临床意义

| CLNSIG | 意义 | 行动 |
|--------|------|------|
| Pathogenic | 致病 | 报告 |
| Likely_pathogenic | 可能致病 | 报告，需验证 |
| Uncertain_significance | 意义不明(VUS) | 需进一步分析 |
| Likely_benign | 可能良性 | 通常排除 |
| Benign | 良性 | 排除 |

### 过滤致病性变异

```bash
# 仅致病/可能致病
bcftools view -i 'INFO/CLNSIG~"Pathogenic"' with_clinvar.vcf.gz \
    -Oz -o pathogenic.vcf.gz

# 排除良性
bcftools view -e 'INFO/CLNSIG~"Benign" || INFO/CLNSIG~"Likely_benign"' \
    with_clinvar.vcf.gz -Oz -o not_benign.vcf.gz
```

### 人群频率过滤

```bash
# 罕见变异(gnomAD AF < 1%)
bcftools view -i 'INFO/gnomAD_AF<0.01 || INFO/gnomAD_AF="."' \
    input.vcf.gz -Oz -o rare.vcf.gz

# 极罕见(适合显性遗传)
bcftools view -i 'INFO/gnomAD_AF<0.0001 || INFO/gnomAD_AF="."' \
    input.vcf.gz -Oz -o ultrarare.vcf.gz

# 过滤纯合子频率(适合隐性遗传)
bcftools view -i 'INFO/gnomAD_HOM<10' input.vcf.gz -Oz -o rare_hom.vcf.gz
```

## 4. 变异优先级过滤

### 综合过滤

```bash
# 结合临床意义和人群频率
bcftools view -i '(INFO/CLNSIG~"Pathogenic" || INFO/CLNSIG=".") && \
    (INFO/gnomAD_AF<0.01 || INFO/gnomAD_AF=".")' \
    input.vcf.gz -Oz -o prioritized.vcf.gz
```

## 5. WGS vs WES注释差异

### 注释范围

| 特征 | WGS | WES |
|------|-----|-----|
| 编码变异 | 全部注释 | 仅捕获区 |
| 剪接位点 | ±50bp分析 | 依赖捕获设计 |
| 非编码变异 | 可分析调控区 | 基本无法分析 |
| 深层内含子 | 可检测 | 无法检测 |
| 基因间区 | 可分析 | 无法分析 |

### WES特别关注

```bash
# WES: 检查剪接位点变异（即使在外显子边界外）
bcftools view -i 'INFO/CSQ~"splice"' vep_output.vcf.gz

# WES: 检查捕获效率低的基因（GC富集）
# 需结合捕获试剂特定分析
```

## 6. 生成报告

### 提取关键信息

```bash
# 基因-变异表格
bcftools query -H -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/SYMBOL\t%INFO/Consequence\t%INFO/IMPACT\t%INFO/CLNSIG\n' \
    annotated.vcf.gz > report.tsv

# 包含基因型
bcftools query -H -f '%CHROM\t%POS\t%REF\t%ALT[%\t%GT]\n' \
    annotated.vcf.gz > genotypes.tsv
```

### 按基因优先级排序

```bash
# 已知的致病基因优先
GENE_LIST="BRCA1,BRCA2,TP53,PTEN"
bcftools view -i "INFO/SYMBOL~'${GENE_LIST}'" annotated.vcf.gz \
    -Oz -o known_genes.vcf.gz
```

## 7. 完整注释流程

```bash
#!/bin/bash
# annotation_pipeline.sh

VCF=$1
VEP_CACHE=$2
OUTPUT_PREFIX=$3

echo "=== Step 1: VEP Annotation ==="
vep -i ${VCF} \
    -o ${OUTPUT_PREFIX}.vep.vcf \
    --vcf --cache --offline \
    --dir_cache ${VEP_CACHE} \
    --assembly GRCh38 \
    --everything --pick \
    --fork 4

bgzip ${OUTPUT_PREFIX}.vep.vcf
bcftools index ${OUTPUT_PREFIX}.vep.vcf.gz

echo "=== Step 2: ClinVar Annotation ==="
bcftools annotate \
    -a clinvar.vcf.gz \
    -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT \
    ${OUTPUT_PREFIX}.vep.vcf.gz \
    -Oz -o ${OUTPUT_PREFIX}.annotated.vcf.gz

echo "=== Step 3: Filter High Impact ==="
bcftools view -i 'INFO/CSQ~"HIGH" || INFO/CSQ~"MODERATE" || INFO/CLNSIG~"Pathogenic"' \
    ${OUTPUT_PREFIX}.annotated.vcf.gz \
    -Oz -o ${OUTPUT_PREFIX}.high_impact.vcf.gz

echo "=== Step 4: Generate Report ==="
bcftools query -H -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/SYMBOL\t%INFO/Consequence\t%INFO/IMPACT\t%INFO/CLNSIG\t%INFO/gnomAD_AF\n' \
    ${OUTPUT_PREFIX}.high_impact.vcf.gz > ${OUTPUT_PREFIX}.report.tsv

echo "=== Annotation Complete ==="
echo "Full VCF: ${OUTPUT_PREFIX}.annotated.vcf.gz"
echo "High Impact: ${OUTPUT_PREFIX}.high_impact.vcf.gz"
echo "Report: ${OUTPUT_PREFIX}.report.tsv"
```

## 相关技能

- bio-genomics-variant-filter-norm - 生成输入VCF
- bio-workflows-somatic-variant-pipeline - 体细胞变异解读
