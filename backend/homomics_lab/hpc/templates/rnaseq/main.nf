#!/usr/bin/env nextflow

nextflow.enable.dsl = 2

params {
    samplesheet = "samplesheet.csv"
    outdir = "results"
    salmon_index = ""
    fasta = ""
    gtf = ""
    skip_qc = false
    skip_quant = false
    threads = 4
}

process FASTP {
    tag "$sample"
    container 'quay.io/biocontainers/fastp:0.23.4--h5f740d0_0'

    input:
        tuple val(sample), path(reads)
    output:
        tuple val(sample), path("*.trimmed.fastq.gz"), emit: reads
        path "*.json", emit: json
        path "*.html", emit: html

    script:
    def single = reads instanceof List ? "" : "-i ${reads}"
    def paired = reads instanceof List ? "-i ${reads[0]} -I ${reads[1]}" : ""
    def out_single = reads instanceof List ? "" : "-o ${sample}.trimmed.fastq.gz"
    def out_paired = reads instanceof List ? "-o ${sample}_1.trimmed.fastq.gz -O ${sample}_2.trimmed.fastq.gz" : ""
    """
    fastp ${single} ${paired} ${out_single} ${out_paired} \
        -j ${sample}.fastp.json -h ${sample}.fastp.html \
        -q 20 -u 40 --detect_adapter_for_pe -w ${params.threads}
    """
}

process SALMON_QUANT {
    tag "$sample"
    container 'quay.io/biocontainers/salmon:1.10.3--h7d5fdc7_0'

    input:
        tuple val(sample), path(reads)
        path salmon_index
    output:
        path "${sample}_quant", emit: quant

    script:
    def lib_type = reads instanceof List ? "A" : "U"
    def read_args = reads instanceof List ? "-1 ${reads[0]} -2 ${reads[1]}" : "-r ${reads}"
    """
    salmon quant -i ${salmon_index} -l ${lib_type} ${read_args} \
        -p ${params.threads} -o ${sample}_quant --validateMappings
    """
}

process MULTIQC {
    publishDir "${params.outdir}/multiqc", mode: 'copy'
    container 'quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0'

    input:
        path '*' 
    output:
        path "multiqc_report.html"
        path "multiqc_data"

    """
    multiqc .
    """
}

workflow {
    Channel.fromPath(params.samplesheet)
        .splitCsv(header: true)
        .map { row ->
            def reads = row.fastq_2 ? [file(row.fastq_1), file(row.fastq_2)] : file(row.fastq_1)
            tuple(row.sample, reads)
        }
        .set { reads_ch }

    index_ch = Channel.fromPath(params.salmon_index).first()

    if (!params.skip_qc) {
        FASTP(reads_ch)
        qc_ch = FASTP.out.json.collect()
        reads_ch = FASTP.out.reads
    } else {
        qc_ch = Channel.empty()
    }

    if (!params.skip_quant) {
        SALMON_QUANT(reads_ch, index_ch)
        quant_ch = SALMON_QUANT.out.quant.collect()
    } else {
        quant_ch = Channel.empty()
    }

    MULTIQC(qc_ch.mix(quant_ch).collect())
}
