version 1.0

task salmon_quant {
    input {
        String sample_id
        File reads_1
        File? reads_2
        File index
        Int threads = 8
        String salmon_args = "--validateMappings"
    }

    Int disk_gb = ceil(size(index, "GB") + size(reads_1, "GB") * 2) + 20

    command <<<
        salmon quant \
            -i ~{index} \
            -l A \
            -1 ~{reads_1} \
            -2 ~{reads_2} \
            -o ~{sample_id}_salmon \
            --threads ~{threads} \
            ~{salmon_args}
    >>>

    output {
        File quant_sf = "~{sample_id}_salmon/quant.sf"
        File quant_genes = "~{sample_id}_salmon/quant.genes.sf"
        File cmd_info = "~{sample_id}_salmon/cmd_info.json"
        File quant_dir = "~{sample_id}_salmon"
    }

    runtime {
        docker: "quay.io/biocontainers/salmon:1.10.0--h7e5ed60_0"
        # singularity: "/scratch/$USER/singularity-images/salmon.sif"
        cpu: threads
        memory: "16 GB"
        disks: "local-disk " + disk_gb + " SSD"
        preemptible: 3
    }
}
