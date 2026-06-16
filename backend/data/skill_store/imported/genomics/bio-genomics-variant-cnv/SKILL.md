---
name: bio-genomics-variant-cnv
description: 拷贝数变异(CNV)检测，包括CNVkit和GATK CNV。检测基因水平的拷贝数增加和缺失。Use for detecting copy number variations from sequencing data.
tool_type: cli
primary_tool: CNVkit/GATK CNV
prerequisites:
  - 已比对的BAM文件
  - 参考基因组
  - 捕获芯片BED文件(WES必需)
---

# 拷贝数变异检测

检测基因水平和大片段的拷贝数增加（扩增）和拷贝数缺失，包括生殖细胞和体细胞CNV分析。

## 工具选择

| 工具 | 最佳场景 | 特点 |
|------|----------|------|
| CNVkit | WES/WGS | 推荐，支持tumor-normal和germline |
| GATK CNV | WES/WGS | GATK生态，需PoN |

## 1. CNVkit（推荐）

### 安装

```bash
conda install -c bioconda cnvkit
```

### Germline CNV分析（WES）

#### Step 1: 准备目标区域

```bash
# 从捕获芯片BED创建目标区域
cnvkit.py target capture_targets.bed \
    --annotate refFlat.txt \
    --split \
    -o targets.bed

# 创建access区域（可访问区域）
cnvkit.py access GRCh38.fa -o access.bed

# 创建off-target区域（antitargets）
cnvkit.py antitarget targets.bed \
    --access access.bed \
    -o antitargets.bed
```

#### Step 2: 计算覆盖度

```bash
# 对每个样本计算目标区和off-target区覆盖度
for bam in *.bam; do
    sample=$(basename $bam .bam)

    # Target coverage
    cnvkit.py coverage $bam targets.bed \
        -o ${sample}.targetcoverage.cnn

    # Antitarget coverage
    cnvkit.py coverage $bam antitargets.bed \
        -o ${sample}.antitargetcoverage.cnn
done
```

#### Step 3: 创建参考（Pool of Normals）

```bash
# 使用正常样本创建参考
cnvkit.py reference \
    normal*.targetcoverage.cnn \
    normal*.antitargetcoverage.cnn \
    --fasta GRCh38.fa \
    -o reference.cnn

# 或使用flat参考（无正常样本时）
cnvkit.py reference \
    --fasta GRCh38.fa \
    --targets targets.bed \
    --antitargets antitargets.bed \
    -o flat_reference.cnn
```

#### Step 4: CNV Calling

```bash
for bam in sample*.bam; do
    sample=$(basename $bam .bam)

    # Fix（计算log2 ratio）
    cnvkit.py fix \
        ${sample}.targetcoverage.cnn \
        ${sample}.antitargetcoverage.cnn \
        reference.cnn \
        -o ${sample}.cnr

    # Segment（ segmentation ）
    cnvkit.py segment ${sample}.cnr \
        -o ${sample}.cns

    # Call（确定拷贝数）
    cnvkit.py call ${sample}.cns \
        --ploidy 2 \
        -o ${sample}.call.cns
done
```

### 批量处理（Batch模式）

```bash
# 一次性处理所有样本
cnvkit.py batch sample*.bam \
    --normal normal*.bam \
    --targets targets.bed \
    --fasta GRCh38.fa \
    --output-reference reference.cnn \
    --output-dir cnv_output \
    --scatter --diagram
```

### 可视化

```bash
# 散点图
sample="patient_001"
cnvkit.py scatter ${sample}.cnr \
    -s ${sample}.cns \
    -o ${sample}_scatter.pdf

# 染色体特定区域
cnvkit.py scatter ${sample}.cnr \
    -s ${sample}.cns \
    -c chr17 \
    -g TP53 \
    -o ${sample}_chr17.pdf

# 热图（多个样本）
cnvkit.py heatmap *.cns -o cohort_heatmap.pdf

# 染色体图（ideogram）
cnvkit.py diagram ${sample}.cnr \
    -s ${sample}.cns \
    -o ${sample}_diagram.pdf
```

### 基因水平CNV分析

```bash
# 计算基因水平的CNV
cnvkit.py genemetrics ${sample}.cnr \
    -s ${sample}.cns \
    --threshold 0.2 \
    -o ${sample}_genes.tsv

# 过滤显著的CNV
awk '$6 < -0.4 || $6 > 0.3' ${sample}_genes.tsv > ${sample}_significant_cnvs.tsv
```

## 2. GATK CNV

### 创建Panel of Normals (PoN)

```bash
# 预处理正常样本
for normal in normal*.bam; do
    sample=$(basename $normal .bam)

    gatk CollectReadCounts \
        -I $normal \
        -L targets.interval_list \
        --interval-merging-rule OVERLAPPING_ONLY \
        -O ${sample}.counts.hdf5
done

# 创建PoN
gatk CreateReadCountPanelOfNormals \
    -I normal1.counts.hdf5 \
    -I normal2.counts.hdf5 \
    -I normal3.counts.hdf5 \
    -O pon.hdf5
```

### Denoise和Segment

```bash
# 收集read counts
gatk CollectReadCounts \
    -I sample.bam \
    -L targets.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -O sample.counts.hdf5

# Denoise（标准化）
gatk DenoiseReadCounts \
    -I sample.counts.hdf5 \
    --count-panel-of-normals pon.hdf5 \
    --standardized-copy-ratios sample.standardizedCR.tsv \
    --denoised-copy-ratios sample.denoisedCR.tsv

# Segmentation
gatk ModelSegments \
    --denoised-copy-ratios sample.denoisedCR.tsv \
    --output-prefix sample \
    -O output_dir
```

## 3. WGS vs WES CNV检测

### 检测能力对比

| 特征 | WGS | WES |
|------|-----|-----|
| 检测分辨率 | ~1kb（高覆盖） | ~1个外显子 |
| 大片段CNV | 优秀 | 良好（跨多个外显子） |
| 单外显子CNV | 良好 | 优秀 |
| 断点精度 | 高 | 受限于捕获边界 |
| 参考创建 | 需要更多样本 | 可用标准PoN |

### WGS特定参数

```bash
# WGS: 使用binned方法
cnvkit.py batch sample.bam \
    --method wgs \
    --fasta GRCh38.fa \
    --output-dir cnv_wgs \
    --scatter

# 或使用seq（自动分bin）
cnvkit.py batch sample.bam \
    --method amplicon \
    --fasta GRCh38.fa \
    --output-dir cnv_wgs
```

### WES特定考虑

```bash
# WES: 标准hybrid方法
cnvkit.py batch sample.bam \
    --method hybrid \
    --targets targets.bed \
    --fasta GRCh38.fa \
    --output-dir cnv_wes

# 注意：第一和最后一个外显子可能不可靠（捕获边缘效应）
```

## 4. CNV过滤和解读

### 基于质量的过滤

```bash
# 从CNVkit .cns文件过滤
# 1. 移除小片段（<3个probe）
awk 'NR==1 || ($3-$2) >= 10000' sample.call.cns > filtered.cns

# 2. 移除低置信度
awk 'NR==1 || ($5 >= 0.3 || $5 <= -0.3)' sample.call.cns > significant.cns
```

### 基于基因注释

```bash
# 导出为VCF格式
cnvkit.py export vcf sample.call.cns \
    -o sample.cnv.vcf \
    --cn-sample ${SAMPLE}

# 使用VEP注释
cnvkit.py export seg *.cns -o cohort.seg
```

### 临床相关CNV数据库

| 数据库 | 用途 | 网址 |
|--------|------|------|
| ClinGen | 基因剂量敏感性 | clinGen.org |
| DECIPHER | 发育障碍CNV | decipher.sanger.ac.uk |
| DGV | 正常人群CNV | dgv.tcag.ca |
| OMIM | 基因-疾病关联 | omim.org |

## 5. 体细胞CNV（肿瘤-正常配对）

```bash
# CNVkit tumor-normal模式
cnvkit.py batch \
    tumor.bam \
    --normal normal.bam \
    --targets targets.bed \
    --fasta GRCh38.fa \
    --output-dir cnv_tumor \
    --scatter --diagram

# 或使用已有参考
cnvkit.py fix \
    tumor.targetcoverage.cnn \
    tumor.antitargetcoverage.cnn \
    reference.cnn \
    -o tumor.cnr

cnvkit.py segment tumor.cnr -o tumor.cns
cnvkit.py call tumor.cns --method threshold -o tumor.call.cns
```

## 6. 完整CNV分析脚本

```bash
#!/bin/bash
# cnv_pipeline.sh

SAMPLE=$1
REF=$2
TARGETS=$3  # WES需要，WGS可省略
TYPE=${4:-wes}  # wgs或wes
OUTDIR=$5

mkdir -p ${OUTDIR}

echo "=== CNV Analysis: ${SAMPLE} (${TYPE}) ==="

if [ "${TYPE}" == "wes" ]; then
    # WES模式
    echo "[1/3] Target preparation..."
    cnvkit.py target ${TARGETS} --split -o ${OUTDIR}/targets.bed
    cnvkit.py access ${REF} -o ${OUTDIR}/access.bed
    cnvkit.py antitarget ${OUTDIR}/targets.bed \
        --access ${OUTDIR}/access.bed -o ${OUTDIR}/antitargets.bed

    echo "[2/3] Coverage and calling..."
    cnvkit.py batch ${SAMPLE}.bam \
        --method hybrid \
        --targets ${OUTDIR}/targets.bed \
        --fasta ${REF} \
        --output-dir ${OUTDIR} \
        --scatter --diagram
else
    # WGS模式
    echo "[1/2] WGS CNV calling..."
    cnvkit.py batch ${SAMPLE}.bam \
        --method wgs \
        --fasta ${REF} \
        --output-dir ${OUTDIR} \
        --scatter
fi

echo "[3/3] Gene-level analysis..."
cnvkit.py genemetrics ${OUTDIR}/${SAMPLE}.cnr \
    -s ${OUTDIR}/${SAMPLE}.cns \
    -o ${OUTDIR}/${SAMPLE}_genes.tsv

echo "CNV analysis complete: ${OUTDIR}/"
echo "  Main result: ${OUTDIR}/${SAMPLE}.call.cns"
echo "  Gene-level: ${OUTDIR}/${SAMPLE}_genes.tsv"
echo "  Plot: ${OUTDIR}/${SAMPLE}-scatter.pdf"
```

## 7. WGS vs WES CNV质控

| 指标 | WGS | WES | 说明 |
|------|-----|-----|------|
| 平均bin大小 | 100bp-1kb | 外显子大小 | WGS分辨率更高 |
| 期望CNV数 | ~100-200 | ~50-100 | WGS检测更多 |
| 单外显子CNV | 较难 | 较好 | WES优势 |
| 大片段CNV | 优秀 | 良好 | WGS优势 |
| 参考样本数 | >10 | >3 | WGS需要更多 |

## 相关技能

- bio-genomics-alignment - 生成输入BAM
- bio-genomics-variant-structural - SV检测（可互补）
- bio-workflows-somatic-variant-pipeline - 体细胞分析
- bio-workflows-cnv-pipeline - 完整CNV工作流（保留）
