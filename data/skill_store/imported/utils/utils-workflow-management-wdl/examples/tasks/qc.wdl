version 1.0

task fastp {
    input {
        String sample_id
        File reads_1
        File? reads_2
        Int threads = 4
        String fastp_args = ""
    }

    Int disk_gb = ceil(size(reads_1, "GB") + size(reads_2, "GB")) * 3 + 10

    command <<<
        fastp \
            -i ~{reads_1} \
            -o ~{sample_id}_trimmed_R1.fq.gz \
            --json ~{sample_id}_fastp.json \
            --html ~{sample_id}_fastp.html \
            --thread ~{threads} \
            ~{fastp_args}
    >>>

    output {
        File trimmed_1 = "~{sample_id}_trimmed_R1.fq.gz"
        File trimmed_2 = "~{sample_id}_trimmed_R2.fq.gz"
        File json_report = "~{sample_id}_fastp.json"
        File html_report = "~{sample_id}_fastp.html"
    }

    runtime {
        docker: "quay.io/biocontainers/fastp:0.23.4--hadf994f_2"
        # singularity: "/scratch/$USER/singularity-images/fastp.sif"
        cpu: threads
        memory: "4 GB"
        disks: "local-disk " + disk_gb + " HDD"
        preemptible: 3
    }
}

task multiqc {
    input {
        Array[File] fastp_reports
        Array[File] salmon_dirs
    }

    command <<<
        mkdir -p qc_input salmon_input
        cp -L ~{sep=' ' fastp_reports} qc_input/
        for f in ~{sep=' ' salmon_dirs}; do
            cp -rL "$f" salmon_input/$(basename "$f")
        done
        multiqc qc_input salmon_input -n multiqc_report
    >>>

    output {
        File report = "multiqc_report.html"
    }

    runtime {
        docker: "quay.io/biocontainers/multiqc:1.14--pyhdfd78af_0"
        # singularity: "/scratch/$USER/singularity-images/multiqc.sif"
        cpu: 2
        memory: "4 GB"
        disks: "local-disk 50 HDD"
        preemptible: 3
    }
}
