---
name: bio-genomics-variant-germline-gpu
description: GPU加速的生殖细胞小变异(SNP/indel)检测，基于NVIDIA Parabricks。Use for germline variant calling with GPU acceleration.
tool_type: cli
primary_tool: pbrun haplotypecaller / pbrun deepvariant / pbrun germline
prerequisites:
  - NVIDIA GPU (Volta/Ampere/Hopper架构)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - Analysis-ready BAM文件 (可由fq2bam生成)
  - 参考基因组及索引
gpu_requirements:
  - 显存: 16-24GB (WGS) / 8-16GB (WES)
  - 架构: V100/A100/H100推荐
---

# GPU加速生殖细胞变异检测

基于NVIDIA Parabricks的GPU加速变异检测，支持GATK HaplotypeCaller和DeepVariant两种主流工具，结果与CPU版本数值一致。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun haplotypecaller --ref /data/ref.fa --in-bam /data/sample.bam --out-vcf /data/out.vcf.gz
```

### 方式二：独立安装

```bash
# Ubuntu/Debian
sudo dpkg -i parabricks-4.7.0-1.deb

# RHEL/CentOS
sudo rpm -i parabricks-4.7.0-1.rpm
```

安装后 `pbrun` 直接作为系统命令使用：
```bash
pbrun haplotypecaller --ref ref.fa --in-bam sample.bam --out-vcf out.vcf.gz
```

### 系统要求

| 项目 | 要求 |
|------|------|
| OS | Ubuntu 20.04/22.04, RHEL 8/9 |
| NVIDIA驱动 | ≥ 525.60 |
| GPU架构 | Volta/Ampere/Hopper (V100/A100/H100) |

### 选择建议

| 场景 | 推荐方式 |
|------|---------|
| 单机测试/开发 | Docker |
| HPC集群（Slurm/SGE） | 独立安装 |
| 云平台 | 两者皆可 |
| 与其他工具混合调用 | 独立安装 |
| 频繁升级/多版本并存 | Docker |

> **性能声明**：本技能中标注的时间与加速比为NVIDIA官方标称参考值，实际表现受GPU型号（V100/A100/H100）、存储I/O带宽、样本质量及系统负载影响。建议首次使用先以单样本实际测试为准。

## 1. 与CPU方案对比

| 工具 | CPU时间(30x WGS) | GPU时间 | 加速比 | 结果一致性 |
|------|-----------------|---------|--------|-----------|
| HaplotypeCaller | 3-4小时 | ~10分钟 | **~20x** | 100% |
| DeepVariant | 4-6小时 | ~15分钟 | **~20x** | 100% |
| 端到端germline | — | ~30分钟 | — | — |

## 2. 工具选择指南

| 工具 | 最佳场景 | 速度 | 准确性 | 队列支持 |
|------|---------|------|--------|---------|
| `haplotypecaller` | 标准GATK流程，队列联合检测 | 快 | 高 | 支持GVCF |
| `deepvariant` | 最高精度需求，验证实验 | 中等 | **最高** | 支持gVCF |
| `germline` | **端到端**：FASTQ→VCF | 最快 | 高 | 单样本 |
| `pangenome_aware_deepvariant` | 复杂区域/多样本人群 | 中等 | 最高 | 支持 |

## 3. haplotypecaller：GPU版GATK HC

### 单样本直接调用

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --out-vcf sample.vcf.gz
```

### GVCF模式（推荐用于队列）

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --gvcf \
    --out-vcf sample.g.vcf.gz
```

### WES模式（关键：--interval-file）

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --interval-file targets.interval_list \
    --gvcf \
    --out-vcf sample.g.vcf.gz
```

### 高级参数

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --gvcf \
    --interval-file targets.bed \
    --out-vcf sample.g.vcf.gz \
    --num-gpus 2 \
    --num-htads 8
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--num-gpus` | 使用GPU数量 | 1 |
| `--num-htads` | HaplotypeCaller线程数 | 自动 |
| `--gvcf` | 输出GVCF格式 | 否 |
| `--interval-file` | 限制分析区域 | 全基因组 |

## 4. deepvariant：GPU加速深度学习变异检测

### WGS

```bash
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --out-vcf sample.deepvariant.vcf.gz \
    --num-gpus 1
```

### WES

```bash
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --interval-file targets.bed \
    --out-vcf sample.deepvariant.vcf.gz
```

### 模型类型选择

| 模型 | 参数 | 适用场景 |
|------|------|---------|
| WGS | `--model-type WGS` | 全基因组短读序 |
| WES | `--model-type WES` | 全外显子组 |
| PacBio | `--model-type PACBIO` | PacBio HiFi长读序 |
| ONT | `--model-type ONT_R104` | Oxford Nanopore R10.4 |
| HYBRID | `--model-type HYBRID` | PacBio+Illumina混合 |

```bash
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.bam \
    --model-type WGS \
    --out-vcf sample.deepvariant.vcf.gz
```

### 输出gVCF（联合检测）

```bash
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --out-vcf sample.vcf.gz \
    --out-gvcf sample.g.vcf.gz
```

## 5. germline：端到端一键流程

**最简命令**：FASTQ → VCF

```bash
pbrun germline \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    --out-bam sample.bam \
    --out-vcf sample.vcf.gz \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz
```

**等效CPU流程**：bwa-mem2 → samtools sort → markdup → BQSR → HaplotypeCaller（约12-16小时）

### germline内部流程

```
FASTQ ──► fq2bam ──► haplotypecaller ──► VCF
         (GPU)         (GPU)
```

### germline完整参数

```bash
pbrun germline \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --interval-file targets.bed \
    --out-bam sample.bam \
    --out-recal-file sample.recal.txt \
    --out-vcf sample.vcf.gz \
    --gvcf \
    --num-gpus 2
```

## 6. pangenome_aware_deepvariant：泛基因组增强

```bash
pbrun pangenome_aware_deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --in-gbz pangenome.gbz \
    --out-vcf sample.pangenome.vcf.gz
```

适用场景：
- 复杂区域（如HLA、KIR）变异检测
- 多样性人群样本
- 参考基因组偏差较大区域

## 7. 联合基因分型

### 从Parabricks GVCF到队列VCF

Parabricks输出的GVCF与GATK兼容，可直接使用GATK联合基因分型：

```bash
# Step 1: 创建sample map
cat > sample_map.txt <<EOF
sample1 /path/to/sample1.g.vcf.gz
sample2 /path/to/sample2.g.vcf.gz
sample3 /path/to/sample3.g.vcf.gz
EOF

# Step 2: GenomicsDBImport (CPU)
gatk GenomicsDBImport \
    --genomicsdb-workspace-path genomicsdb \
    --sample-name-map sample_map.txt \
    -L intervals.interval_list

# Step 3: GenotypeGVCFs (CPU)
gatk GenotypeGVCFs \
    -R GRCh38.fa \
    -V gendb://genomicsdb \
    -O cohort.vcf.gz
```

### 使用GLnexus + DeepVariant gVCF

```bash
# DeepVariant生成gVCF
# ... pbrun deepvariant --out-gvcf ...

# GLnexus合并 (CPU)
docker run -v "${PWD}:/data" quay.io/mlin/glnexus:v1.4.1 \
    /usr/local/bin/glnexus_cli \
    --config DeepVariantWGS \
    /data/*.g.vcf.gz \
    | bcftools view - -Oz -o cohort.deepvariant.vcf.gz
```

## 8. 完整批量脚本

### HaplotypeCaller批量

```bash
#!/bin/bash
# gpu_haplotypecaller_batch.sh

SAMPLE=$1
REF=$2
BAM=$3
OUTDIR=$4
TYPE=${5:-wgs}
TARGETS=${6:-""}

mkdir -p ${OUTDIR}

echo "=== GPU HaplotypeCaller ==="
if [ "${TYPE}" == "wes" ] && [ -n "${TARGETS}" ]; then
    pbrun haplotypecaller \
        --ref ${REF} \
        --in-bam ${BAM} \
        --interval-file ${TARGETS} \
        --gvcf \
        --out-vcf ${OUTDIR}/${SAMPLE}.g.vcf.gz
else
    pbrun haplotypecaller \
        --ref ${REF} \
        --in-bam ${BAM} \
        --gvcf \
        --out-vcf ${OUTDIR}/${SAMPLE}.g.vcf.gz
fi

echo "Complete: ${OUTDIR}/${SAMPLE}.g.vcf.gz"
```

### DeepVariant批量

```bash
#!/bin/bash
# gpu_deepvariant_batch.sh

SAMPLE=$1
REF=$2
BAM=$3
OUTDIR=$4
MODEL=${5:-WGS}

mkdir -p ${OUTDIR}

echo "=== GPU DeepVariant (${MODEL}) ==="
pbrun deepvariant \
    --ref ${REF} \
    --in-bam ${BAM} \
    --model-type ${MODEL} \
    --out-vcf ${OUTDIR}/${SAMPLE}.deepvariant.vcf.gz \
    --out-gvcf ${OUTDIR}/${SAMPLE}.deepvariant.g.vcf.gz

echo "Complete: ${OUTDIR}/${SAMPLE}.deepvariant.vcf.gz"
```

## 9. 质控指标

| 指标 | WGS期望值 | WES期望值 | 检查命令 |
|------|----------|----------|---------|
| SNP数量 | ~400万 | ~5万 | `bcftools stats \| grep SN` |
| indel数量 | ~50万 | ~5千 | `bcftools stats \| grep SiS` |
| Ti/Tv比率 | ~2.1 | ~2.8-3.0 | `bcftools stats \| grep TSTV` |
| het/hom比率 | ~1.5-2.0 | ~1.5-2.0 | `bcftools stats \| grep HET` |

```bash
# 快速统计
bcftools stats sample.vcf.gz > sample.vcf.stats
# 查看Ti/Tv
grep TSTV sample.vcf.stats
```

## 10. 进阶：多GPU与集群运行

### 单节点多GPU加速

```bash
# HaplotypeCaller使用2个GPU
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --gvcf \
    --out-vcf sample.g.vcf.gz \
    --num-gpus 2

# DeepVariant使用2个GPU
pbrun deepvariant \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --model-type WGS \
    --out-vcf sample.deepvariant.vcf.gz \
    --num-gpus 2
```

### --num-gpus 与性能关系

| GPU数量 | 显存总量 | HaplotypeCaller | DeepVariant |
|---------|---------|----------------|-------------|
| 1 | 16-24GB | ~10min | ~15min |
| 2 | 32-48GB | ~6-8min | ~9-12min |
| 4 | 64-96GB | ~4-6min | ~6-8min |

> **注意**：多GPU的加速并非线性。受I/O带宽和模型分片开销影响，2块GPU通常比1块快1.3-1.5倍，而非2倍。DeepVariant因模型更大，多GPU收益通常比HaplotypeCaller更明显。

### Slurm集群提交示例

```bash
#!/bin/bash
#SBATCH --job-name=gpu_hc
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --time=1:00:00

pbrun haplotypecaller \
    --ref ${REF} \
    --in-bam ${BAM} \
    --gvcf \
    --out-vcf ${OUTDIR}/${SAMPLE}.g.vcf.gz
```

### 多样本并行（每样本1 GPU）

```bash
# 同时处理多个样本，每个样本分配1个GPU
for i in 0 1 2 3; do
    CUDA_VISIBLE_DEVICES=$i pbrun haplotypecaller \
        --ref GRCh38.fa \
        --in-bam sample${i}.recal.bam \
        --gvcf \
        --out-vcf sample${i}.g.vcf.gz &
done
wait
```

## 11. 资源需求

| 工具 | 显存 | WGS时间 | WES时间 |

| 工具 | 显存 | WGS时间 | WES时间 |
|------|------|---------|---------|
| haplotypecaller | 16-24GB | ~10min | ~3min |
| deepvariant | 16-24GB | ~15min | ~5min |
| germline | 16-24GB | ~30min | ~10min |
| pangenome_aware_dv | 24-32GB | ~20min | ~8min |

## 12. 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `haplotypecaller` | GATK 4.6.1.0 HaplotypeCaller | `pbrun haplotypecaller --help` |
| `deepvariant` | DeepVariant 1.6.1 | `pbrun deepvariant --help` |
| `germline` | BWA-MEM2 2.2.1 + GATK 4.6.1.0 | `pbrun germline --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 13. 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 极少数边界差异 | 与GATK在极少数边界情况可能存在舍入差异 | 查阅官方精度对比文档 |

## 14. 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| VCF为空 | BAM无Read Group | 检查BAM header中的@RG行 |
| 变异数过少 | 覆盖度不足 | 检查平均深度 `samtools depth` |
| GPU内存不足 | BAM过大/深度过高 | 添加 `--num-gpus 2` 或降低batch size |
| WES未限制区域 | 缺少--interval-file | 添加捕获区域BED/GATK interval |
| DeepVariant模型错误 | --model-type不匹配 | 根据数据类型选择正确模型 |
| GVCF无法联合分型 | 版本不兼容 | 确保GATK版本与Parabricks声明一致 |

## 相关技能

- bio-genomics-variant-snp-indel - CPU版本(GATK/DeepVariant/bcftools)
- bio-genomics-alignment-gpu - GPU加速比对(fq2bam)
- bio-genomics-workflow-wgs-germline-gpu - WGS端到端GPU流程
- bio-genomics-variant-filter-norm - 变异过滤和标准化
