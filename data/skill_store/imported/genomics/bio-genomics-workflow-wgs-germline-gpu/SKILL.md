---
name: bio-genomics-workflow-wgs-germline-gpu
description: GPU加速的WGS生殖细胞变异检测端到端工作流，基于NVIDIA Parabricks。Use for end-to-end WGS germline variant calling with GPU acceleration.
tool_type: workflow
primary_tool: pbrun germline / pbrun fq2bam + pbrun haplotypecaller
depends_on:
  - bio-genomics-alignment-gpu
  - bio-genomics-variant-germline-gpu
workflow: true
prerequisites:
  - NVIDIA GPU (V100/A100/H100，显存≥16GB)
  - Parabricks v4.7.0+（Docker容器或独立安装，见下方安装方式）
  - 参考基因组(GRCh38)及索引
  - dbSNP和已知Indels VCF
  - clean FASTQ文件
gpu_requirements:
  - 显存: 16-24GB
  - 架构: V100/A100/H100
  - 单样本WGS 30x约30-45分钟
---

# GPU加速WGS生殖细胞变异检测端到端工作流

完整的全基因组测序(WGS)GPU加速分析流程，从原始FASTQ到过滤后VCF，单样本30x WGS仅需30-45分钟（CPU版本需12-24小时）。

## 安装方式

Parabricks支持Docker容器和独立安装两种方式。

### 方式一：Docker容器（推荐）

```bash
# 拉取镜像
docker pull nvcr.io/nvidia/clara/parabricks:4.7.0-1

# 运行（将本地/data挂载到容器内）
docker run --gpus all --rm -v /data:/data nvcr.io/nvidia/clara/parabricks:4.7.0-1 \
    pbrun germline --ref /data/ref.fa --in-fq /data/R1.fq.gz /data/R2.fq.gz --out-bam /data/out.bam --out-vcf /data/out.vcf.gz
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
pbrun germline --ref ref.fa --in-fq R1.fq.gz R2.fq.gz --out-bam out.bam --out-vcf out.vcf.gz
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

## 流程概览

```
FASTQ输入
    │
    ├── [1] GPU比对+预处理 ──► pbrun fq2bam
    │                           ├─ BWA-MEM2比对 (GPU)
    │                           ├─ 排序 (GPU)
    │                           ├─ 重复标记 (GPU)
    │                           ├─ BQSR (GPU)
    │                           └─ 输出: recalibrated BAM
    │                              时间: ~20min
    │
    ├── [2] GPU变异检测 ───────► pbrun haplotypecaller
    │                           ├─ 单样本变异 calling (GPU)
    │                           ├─ 输出: gVCF
    │                           └─ 时间: ~10min
    │
    ├── [3] [CPU] 队列联合基因分型 ──► GATK GenomicsDBImport
    │                                   ├─ GenotypeGVCFs
    │                                   └─ 输出: 队列VCF
    │
    ├── [4] [CPU] 过滤与标准化 ────────► bcftools norm/filter
    │                                   └─ 输出: filtered VCF
    │
    └── [5] [CPU] 注释 ────────────────► VEP注释
                                        └─ 输出: 注释VCF
```

### 时间对比

| 阶段 | 执行方式 | CPU流程 | GPU流程 | 加速比 |
|------|---------|---------|---------|--------|
| 比对+预处理 | **GPU** | 4-5小时 | ~20分钟 | ~15x |
| 变异检测 | **GPU** | 3-4小时 | ~10分钟 | ~20x |
| 联合基因分型 | CPU | 1-2小时 | 1-2小时 | 1x |
| 过滤与标准化 | CPU | 2-3小时 | 2-3小时 | 1x |
| 注释 | CPU | 2-3小时 | 2-3小时 | 1x |
| **总计/样本** | — | **12-24小时** | **~30-45分钟** | **~20-40x** |

## 方案一：端到端germline（最简单）

### 单命令完成全部

```bash
pbrun germline \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --out-bam sample.bam \
    --out-recal-file sample.recal.txt \
    --out-vcf sample.vcf.gz
```

**输出文件**：
| 文件 | 说明 |
|------|------|
| `sample.bam` | 比对+排序+重复标记+BQSR后的BAM |
| `sample.bam.bai` | BAM索引 |
| `sample.recal.txt` | BQSR校正表 |
| `sample.vcf.gz` | 变异检测结果 |

## 方案二：分步流程（更灵活）

### Step 1: GPU比对+预处理

```bash
pbrun fq2bam \
    --ref GRCh38.fa \
    --in-fq sample_R1.fq.gz sample_R2.fq.gz \
    "@RG\tID:sample\tSM:sample\tPL:ILLUMINA\tLB:lib1" \
    --knownSites dbsnp_146.hg38.vcf.gz \
    --knownSites Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    --out-bam sample.recal.bam \
    --out-recal-file sample.recal.txt
```

### Step 2: GPU变异检测(GVCF)

```bash
pbrun haplotypecaller \
    --ref GRCh38.fa \
    --in-bam sample.recal.bam \
    --gvcf \
    --out-vcf sample.g.vcf.gz
```

### Step 3: 队列联合基因分型（CPU）

```bash
# 创建样本映射（多样本时）
cat > sample_map.txt <<EOF
sample1 /path/to/sample1.g.vcf.gz
sample2 /path/to/sample2.g.vcf.gz
EOF

# GenomicsDBImport
gatk GenomicsDBImport \
    --genomicsdb-workspace-path genomicsdb \
    --sample-name-map sample_map.txt \
    --reader-threads 8

# 联合基因分型
gatk GenotypeGVCFs \
    -R GRCh38.fa \
    -V gendb://genomicsdb \
    -O cohort.vcf.gz
```

### Step 4: 过滤与标准化

```bash
# 标准化（多等位拆分，左对齐）
bcftools norm -f GRCh38.fa -m-any cohort.vcf.gz -Oz -o cohort.norm.vcf.gz

# 硬过滤
bcftools filter \
    -e 'QUAL<30 || INFO/DP<10 || INFO/FS>60.0 || INFO/SOR>3.0 || INFO/MQ<40.0' \
    cohort.norm.vcf.gz -Oz -o cohort.hard.vcf.gz

# 保留PASS变异
bcftools view -f PASS cohort.hard.vcf.gz -Oz -o cohort.filtered.vcf.gz
bcftools index cohort.filtered.vcf.gz
```

### Step 5: 注释（CPU）

```bash
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf --cache --offline \
    --assembly GRCh38 \
    --everything --pick \
    --fork 4 \
    --plugin CADD,whole_genome_SNVs.tsv.gz \
    --plugin SpliceAI,snv.hg38.vcf.gz
```

## 方案三：多GPU并行（大规模样本）

```bash
#!/bin/bash
# gpu_wgs_batch.sh
# 批量处理多个样本，每个样本分配1-2个GPU

REF="GRCh38.fa"
DBSNP="dbsnp_146.hg38.vcf.gz"
KNOWN_INDELS="Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"
OUTDIR="results"
mkdir -p ${OUTDIR}

# 样本列表
SAMPLES=("NA12878" "NA12891" "NA12892")
R1_FILES=("NA12878_R1.fq.gz" "NA12891_R1.fq.gz" "NA12892_R1.fq.gz")
R2_FILES=("NA12878_R2.fq.gz" "NA12891_R2.fq.gz" "NA12892_R2.fq.gz")

# 并行处理（每样本1个GPU，假设有N个GPU）
for i in "${!SAMPLES[@]}"; do
    SAMPLE="${SAMPLES[$i]}"
    R1="${R1_FILES[$i]}"
    R2="${R2_FILES[$i]}"
    
    # 后台运行，每个样本用不同GPU（通过CUDA_VISIBLE_DEVICES）
    (
        export CUDA_VISIBLE_DEVICES=$i
        echo "[$(date)] Starting ${SAMPLE} on GPU ${i}..."
        
        pbrun germline \
            --ref ${REF} \
            --in-fq ${R1} ${R2} \
            "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:lib1" \
            --knownSites ${DBSNP} \
            --knownSites ${KNOWN_INDELS} \
            --out-bam ${OUTDIR}/${SAMPLE}.bam \
            --out-vcf ${OUTDIR}/${SAMPLE}.vcf.gz \
            --gvcf \
            --num-gpus 1
        
        echo "[$(date)] Completed ${SAMPLE}"
    ) &
    
    # 每N个样本等待一次（N=GPU数量）
    if [ $(( (i+1) % 4 )) -eq 0 ]; then
        wait
    fi
done
wait

echo "All samples completed. Start joint genotyping..."

# 联合基因分型（所有gVCF）
ls ${OUTDIR}/*.g.vcf.gz | \
    awk -F'/' '{s=$NF; gsub(/\.g\.vcf\.gz$/, "", s); print s "\t" $0}' \
    > ${OUTDIR}/sample_map.txt

gatk GenomicsDBImport \
    --genomicsdb-workspace-path ${OUTDIR}/genomicsdb \
    --sample-name-map ${OUTDIR}/sample_map.txt \
    --reader-threads 8

gatk GenotypeGVCFs \
    -R ${REF} \
    -V gendb://${OUTDIR}/genomicsdb \
    -O ${OUTDIR}/cohort.vcf.gz

echo "Pipeline complete: ${OUTDIR}/cohort.vcf.gz"
```

## 资源需求

| 配置 | GPU显存 | GPU数量 | 单样本时间(30x) |
|------|---------|---------|----------------|
| 最小配置 | 16GB | 1 | ~45分钟 |
| 推荐配置 | 24GB | 1 | ~30分钟 |
| 高端配置 | 40-80GB | 2 | ~20分钟 |

## 输出文件结构

```
results/
├── sample.bam              # 比对后BAM
├── sample.bam.bai          # BAM索引
├── sample.recal.txt        # BQSR校正表
├── sample.vcf.gz           # 单样本原始VCF
├── sample.vcf.gz.tbi       # VCF索引
├── sample.g.vcf.gz         # 单样本GVCF（如启用--gvcf）
├── cohort.vcf.gz           # 队列联合VCF
├── cohort.filtered.vcf.gz  # 过滤后VCF
└── cohort.vep.vcf.gz       # 注释后VCF
```

## WGS特定QC指标

| 指标 | CPU流程期望值 | GPU流程期望值 | 检查点 |
|------|-------------|-------------|--------|
| 比对率 | >95% | >95% | BAM输出后 |
| 重复率 | <30% | <30% | BAM输出后 |
| 平均覆盖度 | 30x | 30x | BAM输出后 |
| SNP数量 | ~400万 | ~400万 | VCF输出后 |
| Ti/Tv比率 | ~2.1 | ~2.1 | VCF输出后 |
| het/hom比率 | ~1.5-2.0 | ~1.5-2.0 | VCF输出后 |

```bash
# 快速验证变异数量
bcftools stats sample.vcf.gz | grep -E "^SN|TSTV"
```

## 与CPU工作流的关键差异

| 项目 | CPU工作流 | GPU工作流 |
|------|----------|----------|
| 比对工具 | bwa-mem2 | `fq2bam`(内置) |
| 变异检测 | GATK HaplotypeCaller | `haplotypecaller`(GPU) |
| 单样本时间 | 12-24小时 | 30-45分钟 |
| 结果一致性 | 基准 | 与CPU 100%一致 |
| 中间文件 | 多(SAM,sorted BAM等) | 少(直接输出最终BAM) |
| 磁盘IO | 高 | 低 |

## 版本兼容性

Parabricks保证其输出与对应版本的CPU工具**数值一致**。以下为Parabricks v4.7.0对应的基准工具版本：

| Parabricks组件 | 对应CPU工具版本 | 验证命令 |
|----------------|----------------|---------|
| `fq2bam` | BWA-MEM2 2.2.1, GATK MarkDuplicates | `pbrun fq2bam --help` |
| `haplotypecaller` | GATK 4.6.1.0 HaplotypeCaller | `pbrun haplotypecaller --help` |
| `germline` | BWA-MEM2 2.2.1 + GATK 4.6.1.0 | `pbrun germline --help` |

> **注意**：上述版本可能随Parabricks更新而变化。生产环境中请以 `pbrun <tool> --help` 底部显示的版本信息为准，并参考[NVIDIA官方兼容性文档](https://docs.nvidia.com/clara/parabricks/latest/comparisons.html)。

## 已知问题与版本限制

| 限制项 | 说明 | 解决方案 |
|--------|------|---------|
| 参数可能随版本变化 | Parabricks CLI参数在不同版本间可能有调整 | 升级后务必核对 `--help` |
| GPU驱动要求 | 需NVIDIA驱动 ≥ 525.60 | 使用 `nvidia-smi` 检查 |
| CUDA版本绑定 | Parabricks内置CUDA，与系统CUDA可能冲突 | 使用Docker隔离 |
| 极少数边界差异 | 与GATK在极少数边界情况可能存在舍入差异 | 查阅官方精度对比文档 |
| 全流程并非全部GPU | 联合基因分型和注释仍为CPU步骤 | 见流程概览中的步骤标注 |

## 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 总时间仍很长 | 联合基因分型/注释用CPU | 这是正常的，GPU只加速比对和变异检测 |
| germline命令失败 | 参考基因组索引不全 | 确保bwa-mem2 index已运行 |
| VCF与CPU版差异 | Parabricks版本更新 | 查阅官方兼容性文档 |
| 多GPU报错 | CUDA_VISIBLE_DEVICES冲突 | 确保每个进程独立GPU |
| BAM无法用于GATK | 缺少@RG | 使用带RG的--in-fq格式 |

## 相关技能

- bio-genomics-alignment-gpu - GPU加速比对
- bio-genomics-variant-germline-gpu - GPU加速变异检测
- bio-genomics-workflow-wes-germline-gpu - WES版本GPU流程
- bio-genomics-variant-filter-norm - 变异过滤标准化
- bio-genomics-variant-interpretation - 变异注释解读
