#!/bin/bash
# 变异过滤示例

VCF="input.vcf.gz"
REF="GRCh38.fa"
PREFIX="filtered"

# Step 1: 标准化
bcftools norm -f ${REF} -m-any ${VCF} -Oz -o ${PREFIX}.norm.vcf.gz

# Step 2: Hard filter (SNP标准)
bcftools filter \
    -e 'QUAL<30 || INFO/DP<10 || INFO/FS>60 || INFO/MQ<40' \
    ${PREFIX}.norm.vcf.gz -Oz -o ${PREFIX}.hard.vcf.gz

# Step 3: 仅保留PASS
bcftools view -f PASS ${PREFIX}.hard.vcf.gz -Oz -o ${PREFIX}.pass.vcf.gz

# Step 4: 分离SNPs和Indels
bcftools view -v snps ${PREFIX}.pass.vcf.gz -Oz -o ${PREFIX}.snps.vcf.gz
bcftools view -v indels ${PREFIX}.pass.vcf.gz -Oz -o ${PREFIX}.indels.vcf.gz

# 统计
bcftools stats ${PREFIX}.pass.vcf.gz > ${PREFIX}.stats.txt

echo "Filtering complete:"
echo "  All: ${PREFIX}.pass.vcf.gz"
echo "  SNPs: ${PREFIX}.snps.vcf.gz"
echo "  Indels: ${PREFIX}.indels.vcf.gz"
