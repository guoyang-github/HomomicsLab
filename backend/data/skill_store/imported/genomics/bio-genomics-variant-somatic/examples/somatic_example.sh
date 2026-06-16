#!/bin/bash
# 体细胞变异检测示例 (Mutect2)

TUMOR="tumor.bam"
NORMAL="normal.bam"
NORMAL_NAME="patient_normal"
REF="GRCh38.fa"
PON="pon.vcf.gz"
GNOMAD="af-only-gnomad.vcf.gz"
PREFIX="patient_tumor"

echo "=== Somatic Variant Calling ==="

# Mutect2 calling
gatk Mutect2 \
    -R ${REF} \
    -I ${TUMOR} \
    -I ${NORMAL} \
    -normal ${NORMAL_NAME} \
    --germline-resource ${GNOMAD} \
    --panel-of-normals ${PON} \
    --f1r2-tar-gz ${PREFIX}_f1r2.tar.gz \
    -O ${PREFIX}_unfiltered.vcf.gz

# Orientation bias
gatk LearnReadOrientationModel \
    -I ${PREFIX}_f1r2.tar.gz \
    -O ${PREFIX}_orientation.tar.gz

# Contamination
gatk GetPileupSummaries -I ${TUMOR} -V ${GNOMAD} -L ${GNOMAD} \
    -O ${PREFIX}_tumor_pileups.table
gatk GetPileupSummaries -I ${NORMAL} -V ${GNOMAD} -L ${GNOMAD} \
    -O ${PREFIX}_normal_pileups.table
gatk CalculateContamination \
    -I ${PREFIX}_tumor_pileups.table \
    -matched ${PREFIX}_normal_pileups.table \
    -O ${PREFIX}_contamination.table

# Filter
gatk FilterMutectCalls \
    -R ${REF} \
    -V ${PREFIX}_unfiltered.vcf.gz \
    --contamination-table ${PREFIX}_contamination.table \
    --ob-priors ${PREFIX}_orientation.tar.gz \
    -O ${PREFIX}_filtered.vcf.gz

bcftools view -f PASS ${PREFIX}_filtered.vcf.gz \
    -Oz -o ${PREFIX}_somatic.vcf.gz

echo "Done: ${PREFIX}_somatic.vcf.gz"
