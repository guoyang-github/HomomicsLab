rule fastp:
    input:
        r1 = "data/{sample}_R1.fq.gz",
        r2 = "data/{sample}_R2.fq.gz"
    output:
        r1 = "trimmed/{sample}_R1.fq.gz",
        r2 = "trimmed/{sample}_R2.fq.gz",
        json = "qc/{sample}_fastp.json",
        html = "qc/{sample}_fastp.html"
    log:
        "logs/fastp/{sample}.log"
    benchmark:
        "benchmarks/fastp/{sample}.tsv"
    threads: 4
    resources:
        mem_mb = 8000,
        runtime = 60
    conda:
        "../envs/qc.yaml"
    # container: "docker://quay.io/biocontainers/fastp:0.23.4--hadf994f_2"
    shell:
        "(fastp -i {input.r1} -I {input.r2} "
        "-o {output.r1} -O {output.r2} "
        "--json {output.json} --html {output.html} "
        "--thread {threads} "
        "{params[\"fastp_args\"]}) "
        "2> {log}"

rule multiqc:
    input:
        fastp_json = expand("qc/{sample}_fastp.json", sample=SAMPLES),
        salmon_dirs = expand("salmon/{sample}", sample=SAMPLES)
    output:
        "results/multiqc_report.html"
    log:
        "logs/multiqc.log"
    benchmark:
        "benchmarks/multiqc.tsv"
    threads: 2
    resources:
        mem_mb = 4000,
        runtime = 30
    conda:
        "../envs/qc.yaml"
    # container: "docker://quay.io/biocontainers/multiqc:1.14--pyhdfd78af_0"
    shell:
        "(multiqc qc/ salmon/ -o results/ -n multiqc_report) 2> {log}"
