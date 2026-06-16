> 目标：将 HomomicsLab 连接到 SLURM 集群，使长时分析任务自动提交为 sbatch 作业。

# 教程：接入 SLURM 集群

## 前置条件

- 后端所在机器可以访问 SLURM 控制节点（`sbatch`、`squeue`、`sacct` 可用）
- 已配置共享文件系统，集群节点能访问同一工作目录

## 步骤 1：验证 SLURM 客户端

```bash
sbatch --version
squeue --version
sacct --version
```

## 步骤 2：配置 HomomicsLab

在 `.env` 或环境变量中设置：

```env
HOMOMICS_EXECUTION_BACKEND=slurm
HOMOMICS_SLURM_PARTITION=cpu
HOMOMICS_SLURM_ACCOUNT=lab
HOMOMICS_SLURM_TIME=04:00:00
HOMOMICS_SLURM_MEM=16G
HOMOMICS_SLURM_CPUS_PER_TASK=4
```

## 步骤 3：验证后端能检测到 SLURM

```bash
curl http://localhost:8080/health
```

或通过 Python：

```python
from homomics_lab.hpc.scheduler import SlurmScheduler
print(SlurmScheduler.is_available())  # True
```

## 步骤 4：发送一个分析请求

```bash
curl -X POST http://localhost:8080/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "message": "对 counts 矩阵做差异表达分析",
    "execution_backend": "slurm",
    "slurm_options": {"partition": "cpu", "time": "02:00:00"}
  }'
```

## 步骤 5：监控执行

前端 **Execution Log Panel** 会实时显示：

- `info` — 已提交 sbatch，job_id=12345
- `stdout` — 工具输出
- `stderr` — 警告/错误
- `success` / `error` — 完成状态

也可以命令行查看：

```bash
squeue -u $USER
sacct -j 12345 --format=JobID,State,Elapsed
```

## 步骤 6：按任务覆盖 SLURM 选项

在 `domain.yaml` 的 `runtime.resources` 中声明资源：

```yaml
runtime:
  type: python
  resources:
    memory: 32G
    cpu: 8
    time: 8h
```

`SlurmScheduler._build_sbatch_script` 会自动把这些转成 `#SBATCH` 指令。

## 故障排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `sbatch: command not found` | 后端机器没有 SLURM 客户端 | 在 SLURM 登录节点运行后端，或安装客户端 |
| 作业一直 PENDING | 队列繁忙或资源配置过高 | 检查 `squeue`，调整分区或时间 |
| 作业失败但前端显示成功 | `sacct` 解析失败 | 确保 sacct 输出格式与 scheduler 预期一致 |
| 输出文件找不到 | 工作目录未共享 | 使用 NFS/共享存储作为 WORKSPACE_ROOT |
