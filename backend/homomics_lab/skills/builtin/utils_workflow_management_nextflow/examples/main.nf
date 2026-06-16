#!/usr/bin/env nextflow
nextflow.enable.dsl=2

/*
 * RNA-seq Quantification Pipeline
 * Follows the project structure and coding standards defined in SKILL.md
 */

include { FASTP } from './modules/local/fastp'
include { SALMON_QUANT } from './modules/local/salmon_quant'
include { MULTIQC } from './modules/local/multiqc'

workflow {

    log.info """
    =========================================
    R N A - S E Q   P I P E L I N E
    =========================================
    input        : ${params.input}
    salmon_index : ${params.salmon_index}
    outdir       : ${params.outdir}
    profile      : ${workflow.profile}
    """.stripIndent()

    // Channel 1: Samplesheet-driven input (PREFERRED)
    reads_ch = Channel.fromPath(params.input, checkIfExists: true)
        .splitCsv(header: true, sep: ',')
        .map { row ->
            def meta = [id: row.sample, single_end: row.fastq_2 ? false : true]
            def reads = row.fastq_2
                ? [file(row.fastq_1, checkIfExists: true), file(row.fastq_2, checkIfExists: true)]
                : [file(row.fastq_1, checkIfExists: true)]
            [meta, reads]
        }

    // Channel 2: Reference index (broadcast with .first())
    index_ch = Channel.fromPath(params.salmon_index, checkIfExists: true)
        .first()

    // Pipeline wiring
    FASTP(reads_ch)
    SALMON_QUANT(FASTP.out.reads, index_ch)

    // Aggregate QC outputs for MultiQC
    qc_ch = FASTP.out.json
        .mix(SALMON_QUANT.out.quant.map { it[1] })
        .collect()

    MULTIQC(qc_ch)
}

workflow.onComplete {
    log.info "========================================="
    log.info "Pipeline completed at: ${workflow.complete}"
    log.info "Duration: ${workflow.duration}"
    log.info "Success: ${workflow.success}"
    log.info "Output directory: ${params.outdir}"
    log.info "========================================="
}
