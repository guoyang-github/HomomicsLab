rule salmon_quant:
    input:
        r1 = "trimmed/{sample}_R1.fq.gz",
        r2 = "trimmed/{sample}_R2.fq.gz",
        index = config["reference"]["salmon_index"]
    output:
        directory("salmon/{sample}")
    log:
        "logs/salmon/{sample}.log"
    benchmark:
        "benchmarks/salmon/{sample}.tsv"
    threads: 8
    resources:
        mem_mb = 32000,
        runtime = 240
    conda:
        "../envs/quantify.yaml"
    # container: "docker://quay.io/biocontainers/salmon:1.10.0--h7e5ed60_0"
    shell:
        "(salmon quant -i {input.index} -l A "
        "-1 {input.r1} -2 {input.r2} "
        "-o {output} --threads {threads} "
        "{params[\"salmon_args\"]}) "
        "2> {log}"
