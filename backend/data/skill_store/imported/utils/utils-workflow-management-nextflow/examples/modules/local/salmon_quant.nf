process SALMON_QUANT {
    tag "${meta.id}"
    label 'process_medium'

    container 'quay.io/biocontainers/salmon:1.10.0--h7e5ed60_0'
    // conda 'bioconda::salmon=1.10.0'

    publishDir "${params.outdir}/salmon", mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path(index)

    output:
    tuple val(meta), path("${meta.id}"), emit: quant
    path "versions.yml", emit: versions

    script:
    def args = task.ext.args ?: '--validateMappings'
    def prefix = task.ext.prefix ?: "${meta.id}"
    def input_reads = meta.single_end
        ? "-r ${reads[0]}"
        : "-1 ${reads[0]} -2 ${reads[1]}"

    """
    salmon quant \
        -i ${index} \
        -l A \
        ${input_reads} \
        -o ${prefix} \
        --threads ${task.cpus} \
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        salmon: \$(echo \$(salmon --version 2>&1) | sed 's/^salmon //')
    END_VERSIONS
    """
}
