// Subworkflow: Quality Control
// Groups FASTP trimming with QC reporting

include { FASTP } from '../modules/local/fastp'

workflow QC {
    take:
    reads  // channel: [val(meta), path(reads)]

    main:
    FASTP(reads)

    emit:
    reads   = FASTP.out.reads    // trimmed reads
    json    = FASTP.out.json     // fastp JSON reports
}
