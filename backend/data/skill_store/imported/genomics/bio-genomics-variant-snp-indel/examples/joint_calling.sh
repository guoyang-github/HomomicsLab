#!/bin/bash
# 队列联合基因分型示例

COHORT="my_cohort"
REF="GRCh38.fa"
GVCF_DIR="gvcfs"

# Step 1: 创建sample map
echo "Creating sample map..."
ls ${GVCF_DIR}/*.g.vcf.gz | \
    awk -F'/' '{sample=$NF; gsub(/\.g\.vcf\.gz$/, "", sample); print sample "\t" $0}' \
    > sample_map.txt

# Step 2: GenomicsDBImport
echo "Importing to GenomicsDB..."
gatk GenomicsDBImport \
    --genomicsdb-workspace-path genomicsdb \
    --sample-name-map sample_map.txt

# Step 3: Joint Genotyping
echo "Joint genotyping..."
gatk GenotypeGVCFs \
    -R ${REF} \
    -V gendb://genomicsdb \
    -O ${COHORT}.vcf.gz

# Step 4: Filter
echo "Filtering..."
bcftools norm -f ${REF} -m-any ${COHORT}.vcf.gz | \
    bcftools filter -e 'QUAL<30 || DP<10' -Oz -o ${COHORT}.filtered.vcf.gz

bcftools stats ${COHORT}.filtered.vcf.gz > ${COHORT}.stats.txt

echo "Cohort calling complete: ${COHORT}.filtered.vcf.gz"
