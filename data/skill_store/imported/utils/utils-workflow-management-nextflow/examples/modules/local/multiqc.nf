process MULTIQC {
    label 'process_low'

    container 'quay.io/biocontainers/multiqc:1.14--pyhdfd78af_0'
    // conda 'bioconda::multiqc=1.14'

    publishDir "${params.outdir}/multiqc", mode: 'copy'

    input:
    path('*')

    output:
    path("multiqc_report.html"), emit: report
    path("multiqc_data"), emit: data

    script:
    def args = task.ext.args ?: ''

    """
    multiqc . \
        -n multiqc_report \
        --interactive \
        ${args}
    """
}
