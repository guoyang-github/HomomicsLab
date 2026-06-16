process FASTP {
    tag "${meta.id}"
    label 'process_medium'

    container 'quay.io/biocontainers/fastp:0.23.4--hadf994f_2'
    // conda 'bioconda::fastp=0.23.4'

    publishDir "${params.outdir}/fastp", mode: 'copy', pattern: '*.fq.gz'
    publishDir "${params.outdir}/qc/fastp", mode: 'copy', pattern: '*.json'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.trimmed.fq.gz'), emit: reads
    path('*.fastp.json'), emit: json

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    if (meta.single_end) {
        """
        fastp \
            -i ${reads[0]} \
            -o ${prefix}_trimmed.fq.gz \
            --json ${prefix}.fastp.json \
            --thread ${task.cpus} \
            ${args}
        """
    } else {
        """
        fastp \
            -i ${reads[0]} -I ${reads[1]} \
            -o ${prefix}_trimmed_1.fq.gz -O ${prefix}_trimmed_2.fq.gz \
            --json ${prefix}.fastp.json \
            --thread ${task.cpus} \
            ${args}
        """
    }
}
