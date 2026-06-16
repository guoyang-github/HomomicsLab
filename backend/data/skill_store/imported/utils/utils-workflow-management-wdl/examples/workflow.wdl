version 1.0

import "tasks/qc.wdl" as qc
import "tasks/quantify.wdl" as quantify

struct SampleInfo {
    String sample_id
    File fastq_1
    File? fastq_2
    String strandedness
}

workflow rnaseq_pipeline {
    input {
        Array[SampleInfo] samples
        File salmon_index
        Int threads = 8
        String fastp_args = ""
        String salmon_args = "--validateMappings"
    }

    scatter (sample in samples) {
        call qc.fastp {
            input:
                sample_id = sample.sample_id,
                reads_1 = sample.fastq_1,
                reads_2 = sample.fastq_2,
                threads = threads,
                fastp_args = fastp_args
        }

        call quantify.salmon_quant {
            input:
                sample_id = sample.sample_id,
                reads_1 = qc.fastp.trimmed_1,
                reads_2 = qc.fastp.trimmed_2,
                index = salmon_index,
                threads = threads,
                salmon_args = salmon_args
        }
    }

    call qc.multiqc {
        input:
            fastp_reports = qc.fastp.json_report,
            salmon_dirs = quantify.salmon_quant.quant_dir
    }

    output {
        Array[File] trimmed_r1 = qc.fastp.trimmed_1
        Array[File] trimmed_r2 = qc.fastp.trimmed_2
        Array[File] fastp_json = qc.fastp.json_report
        Array[File] quant_files = quantify.salmon_quant.quant_sf
        File multiqc_report = qc.multiqc.report
    }
}
