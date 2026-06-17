---
name: bio-genomics-variant-structural
description: 结构变异(SV)检测，包括缺失、插入、倒位、重复和易位。Use for detecting large genomic rearrangements.
tool_type: cli
primary_tool: Delly/Lumpy/SURVIVOR
prerequisites:
  - 已比对的BAM文件
  - 参考基因组
---

# 结构变异检测

检测大片段基因组重排，包括缺失(DEL)、插入(INS)、倒位(INV)、重复(DUP)和易位(BND)。

## WGS vs WES能力说明

| SV类型 | WGS检测能力 | WES检测能力 | 说明 |
|--------|-------------|-------------|------|
| 大片段缺失(>1kb) | 优秀 | 有限 | WES仅断点在捕获区内可检测 |
| 插入 | 良好 | 差 | WES难以检测插入 |
| 倒位 | 良好 | 有限 | 依赖断点位置 |
| 重复 | 良好 | 有限 | 依赖断点位置 |
| 易位 | 良好 | 差 | WES基本无法检测 |

**结论：SV检测主要推荐WGS，WES能力严重受限**

## 1. Delly

Delly适合检测所有SV类型，支持germline和somatic分析。

### 安装

```bash
conda install -c bioconda delly
```

### 检测所有SV类型

```bash
delly call \
    -g GRCh38.fa \
    -o ${SAMPLE}.sv.bcf \
    ${SAMPLE}.bam

# 转换为VCF
bcftools view ${SAMPLE}.sv.bcf > ${SAMPLE}.sv.vcf
```

### 特定类型检测

```bash
# 仅检测缺失
delly call -t DEL -g GRCh38.fa -o deletions.bcf ${SAMPLE}.bam

# 检测所有类型
delly call -t DEL,DUP,INV,INS,BND -g GRCh38.fa -o all_sv.bcf ${SAMPLE}.bam
```

### 多样本联合检测

```bash
# 1. 单样本分别检测
for bam in *.bam; do
    sample=$(basename $bam .bam)
    delly call -g GRCh38.fa -o ${sample}.bcf $bam
done

# 2. 合并BCF
ls *.bcf > bcf_list.txt
delly merge -o sites.bcf bcf_list.txt

# 3. 基因型 calling
for bam in *.bam; do
    sample=$(basename $bam .bam)
    delly call -g GRCh38.fa -v sites.bcf -o ${sample}.geno.bcf $bam
done

# 4. 合并所有样本
bcftools merge -m id -O b -o merged.bcf *.geno.bcf
```

## 2. Lumpy

Lumpy 是一款基于配对比对特征（read pair、split read、read depth）检测 SV 的工具，支持所有主要 SV 类型，常与 smoove 一起使用以简化流程。

### 安装

```bash
conda install -c bioconda lumpy-sv
# 推荐同时安装 smoove 以简化 BAM 预处理
conda install -c bioconda smoove
```

### 使用 smoove 运行 Lumpy（推荐）

```bash
# 单样本 germline
smoove call \
    --outdir ${OUTDIR}/smoove \
    --name ${SAMPLE} \
    --fasta GRCh38.fa \
    -p 4 \
    --genotype \
    ${SAMPLE}.bam

# 输出: ${OUTDIR}/smoove/${SAMPLE}-smoove.genotyped.vcf.gz
```

### 多样本联合 calling

```bash
# 1. 单样本分别 calling
for bam in *.bam; do
    sample=$(basename $bam .bam)
    smoove call --outdir ${OUTDIR}/smoove \
        --name ${sample} --fasta GRCh38.fa -p 4 --genotype $bam
done

# 2. 合并所有样本进行联合基因型判定
smoove merge --name merged --fasta GRCh38.fa --outdir ${OUTDIR}/smoove \
    ${OUTDIR}/smoove/*-smoove.genotyped.vcf.gz

# 3. 对每个样本进行基因型判定
for bam in *.bam; do
    sample=$(basename $bam .bam)
    smoove genotype --name ${sample}-joint --fasta GRCh38.fa -p 4 \
        --vcf ${OUTDIR}/smoove/merged.sites.vcf.gz --outdir ${OUTDIR}/smoove \
        $bam
done

# 4. 粘贴合并为最终 VCF
smoove paste --name cohort --outdir ${OUTDIR}/smoove \
    ${OUTDIR}/smoove/*-joint.vcf.gz
```

## 3. 多Caller结果合并（SURVIVOR）

使用多个caller提高特异性，通过SURVIVOR合并结果。

### 安装

```bash
git clone https://github.com/fritzsedlazeck/SURVIVOR.git
cd SURVIVOR/Debug
make
```

### 合并VCF文件

```bash
# 创建VCF列表
echo -e "delly.vcf.gz\nlumpy.vcf.gz" > vcf_files.txt

# 合并参数说明：
# 1000: 最大断点距离(bp)
# 2: 最少需要的caller支持数
# 1: 考虑SV类型一致
# 1: 考虑链方向一致
# 0: 不估计SV距离
# 50: 最小SV长度(bp)
SURVIVOR merge vcf_files.txt 1000 2 1 1 0 50 merged_sv.vcf
```

## 4. SV过滤和质控

### 基础过滤

```bash
# 按质量过滤
bcftools view -i 'QUAL >= 20' sv.vcf > sv.filtered.vcf

# 按大小过滤
bcftools view -i 'ABS(SVLEN) >= 50' sv.vcf > sv.min50.vcf

# 仅保留PASS
bcftools view -f PASS sv.vcf > sv.pass.vcf
```

### 按类型提取

```bash
# 提取特定类型
bcftools view -i 'SVTYPE="DEL"' sv.vcf > deletions.vcf
bcftools view -i 'SVTYPE="DUP"' sv.vcf > duplications.vcf
bcftools view -i 'SVTYPE="INV"' sv.vcf > inversions.vcf
bcftools view -i 'SVTYPE="INS"' sv.vcf > insertions.vcf
bcftools view -i 'SVTYPE="BND"' sv.vcf > translocations.vcf
```

### 使用AnnotSV注释

```bash
AnnotSV \
    -SVinputFile sv.vcf \
    -genomeBuild GRCh38 \
    -outputFile annotated_sv \
    -outputDir ./
```

## 5. SV质控指标

### 预期SV数量（WGS）

| SV类型 | 预期数量/基因组 | 大小范围 |
|--------|-----------------|----------|
| 缺失(DEL) | ~1,000-2,000 | 50bp - 数Mb |
| 插入(INS) | ~1,000-2,000 | 50bp - 数kb |
| 重复(DUP) | ~100-500 | 1kb - 数Mb |
| 倒位(INV) | ~100-500 | 1kb - 数Mb |
| 易位(BND) | ~50-200 | - |

### 质控检查

```bash
# 统计各类型SV数量
bcftools query -f '%SVTYPE\n' sv.vcf | sort | uniq -c

# 检查SV大小分布
bcftools query -f '%SVLEN\n' sv.vcf | grep -v "^\.$" | \
    awk '{print int(log($1)/log(10))}' | sort -n | uniq -c
```

## 6. 完整SV检测脚本

```bash
#!/bin/bash
# sv_calling_pipeline.sh

SAMPLE=$1
REF=$2
BAM=$3
OUTDIR=$4

mkdir -p ${OUTDIR}

echo "=== [1/3] Delly ==="
delly call -g ${REF} -o ${OUTDIR}/${SAMPLE}.delly.bcf ${BAM}
bcftools view ${OUTDIR}/${SAMPLE}.delly.bcf | \
    bgzip -c > ${OUTDIR}/${SAMPLE}.delly.vcf.gz

echo "=== [2/3] Lumpy (smoove) ==="
smoove call --outdir ${OUTDIR}/smoove --name ${SAMPLE} --fasta ${REF} -p 4 --genotype ${BAM}
cp ${OUTDIR}/smoove/${SAMPLE}-smoove.genotyped.vcf.gz \
   ${OUTDIR}/${SAMPLE}.lumpy.vcf.gz

echo "=== [3/3] Merge with SURVIVOR ==="
echo -e "${OUTDIR}/${SAMPLE}.delly.vcf.gz\n${OUTDIR}/${SAMPLE}.lumpy.vcf.gz" > \
    ${OUTDIR}/vcf_list.txt

SURVIVOR merge ${OUTDIR}/vcf_list.txt 1000 1 1 1 0 50 ${OUTDIR}/${SAMPLE}.merged.vcf

bcftools stats ${OUTDIR}/${SAMPLE}.merged.vcf > ${OUTDIR}/${SAMPLE}.stats.txt

echo "SV calling complete. Results in ${OUTDIR}/"
```

## 7. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| SV数量过少 | 覆盖度不足 | WGS需要≥30x |
| 假阳性高 | 重复区域 | 过滤segmental duplications |
| 小SV漏检 | 读长限制 | 结合长读长数据 |
| WES SV检测失败 | WES不适用于SV | 换用WGS |
| 易位检测困难 | 需要全基因组 | WGS必需 |

## 相关技能

- bio-genomics-alignment - 生成输入BAM（WES模式BAM不适用于SV）
- bio-genomics-variant-filter-norm - SV过滤
- bio-genomics-variant-interpretation - SV注释（使用AnnotSV）
