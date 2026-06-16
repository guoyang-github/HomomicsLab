> 目标：通过 HomomicsLab 调用 nf-core 流程，无需手写 Nextflow DSL。

# 教程：运行 nf-core 流程

## 前置条件

- 已安装 Nextflow：`nextflow -version`
- 已安装 Docker 或 Singularity（取决于要使用的 profile）
- 后端可以访问 nf-core 仓库或已缓存流程

## 步骤 1：配置 nf-core

```env
HOMOMICS_NFCORE_PROFILES=docker,slurm
HOMOMICS_NFCORE_WORKDIR=./work/nfcore
```

## 步骤 2：列出可用流程

```bash
curl http://localhost:8080/api/nfcore/pipelines?refresh=false
```

首次调用会缓存流程列表到本地，避免重复联网。

## 步骤 3：查看流程参数模式

```bash
curl http://localhost:8080/api/nfcore/schema/rnaseq
```

返回 JSON Schema，说明必填参数和默认值。

## 步骤 4：准备样本表

创建 `samplesheet.csv`：

```csv
sample,fastq_1,fastq_2,strandedness
sample1,/data/reads/sample1_R1.fastq.gz,/data/reads/sample1_R2.fastq.gz,auto
sample2,/data/reads/sample2_R1.fastq.gz,,auto
```

## 步骤 5：运行流程

```bash
curl -X POST http://localhost:8080/api/nfcore/run \
  -H "Content-Type: application/json" \
  -d '{
    "name": "nf-core/rnaseq",
    "version": "3.14.0",
    "params": {
      "input": "samplesheet.csv",
      "outdir": "./results/rnaseq",
      "genome": "GRCh38",
      "aligner": "star_salmon"
    },
    "profiles": ["docker"]
  }'
```

## 步骤 6：从 Agent 自然语言触发

```bash
curl -X POST http://localhost:8080/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "message": "用 nf-core/rnaseq 分析我的 FASTQ 数据，参考基因组 GRCh38",
    "execution_backend": "nextflow"
  }'
```

Agent 会：

1. 识别 `rnaseq_analysis` 意图
2. 从 `NextflowTemplateRegistry` 选择 nf-core/rnaseq 模板
3. 加载 schema 并验证参数
4. 生成 `nextflow run` 命令并提交
5. 监控执行并 ingest 结果报告

## 步骤 7：查看结果

流程完成后，HomomicsLab 会自动将以下产物注册到 Workspace：

- `multiqc_report.html` → report 类型
- `star_salmon/` 下的 count 矩阵 → counts 类型
- 流程运行日志 → logs/

前端 Report 面板和 Workspace 画布可直接查看。

## 故障排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `nextflow not found` | PATH 中无 nextflow | 安装或设置 `NEXTFLOW_HOME` |
| `ProfileNotDetected` | 未安装 Docker/Singularity | 安装对应容器引擎，或改用 `conda` profile |
| `NFCoreSchemaValidationError` | 参数类型/必填项错误 | 对照 `/api/nfcore/schema/{pipeline}` 修正 |
| 下载流程超时 | 网络问题 | 手动 `nf-core download` 后放到缓存目录 |
