# HomomicsLab 面向个人用户的重点开发方案

> 说明：多租户隔离、企业 SSO、RBAC 等企业级功能明确不纳入当前迭代，仅作为长期方向在文末记录。
> 本文聚焦“个人用户在本地/单机上安全、稳定、可扩展地使用 HomomicsLab”所需补齐的模块。

---

## 当前最危险的gap：任意 skill 可执行任意代码

外部 skill 目前能：
1. 在 `scripts/python/*.py` 中执行任意 Python；
2. 通过 SKILL.md 的 `!`rm -rf ~`` 在激活时执行任意 shell；
3. 让 LLM 调用 `shell_exec` / `file_write` 等工具破坏用户环境。

**这是个人用户场景下也必须解决的安全问题，否则 community skill 生态无法开放。**

---

## 总体优先级

| 阶段 | 主题 | 目标 | 建议周期 |
|---|---|---|---|
| P0 | Skill 执行隔离与信任模型 | 外部 skill 不能破坏宿主机 | 2 周 |
| P1 | 长任务持久化与独立 Worker | 长流程可恢复、可取消、API 重启不丢任务 | 2 周 |
| P2 | 可观测性与调试 | 用户能看懂计划为何失败 | 1.5 周 |
| P3 | 大数据与缓存 | 能跑真实单细胞/空间组学数据 | 2 周 |
| P4 | Skill 执行正确性 | 兼容 Claude Code / OpenClaw 社区 skill | 1.5 周 |
| P5 | 个人用户 CLI/UX | `homomics run` 一键执行、查看日志 | 1 周 |

---

## P0 Skill 执行隔离与信任模型

### P0-1 统一 Sandbox 抽象

**目标**：所有脚本型 skill 必须在隔离环境中运行。

**新增文件**：
- `backend/homomics_lab/skills/sandbox_engine.py`
  - 定义 `Sandbox` 协议：`run_script(entrypoint, inputs, env, limits) -> ExecutionResult`
  - 实现 `LocalSandbox`（保留当前能力，仅用于开发模式）
  - 实现 `ContainerSandbox`（Docker/Podman，默认生产模式）
  - 实现 `FirejailSandbox`（轻量 Linux 隔离，可选 fallback）

**修改文件**：
- `backend/homomics_lab/skills/runtime.py`
  - `_execute_from_dir()` 不再直接拼接脚本，而是调用 `Sandbox.run_script()`。
- `backend/homomics_lab/skills/sandbox.py`
  - 将当前 `LocalSandbox` 改为兼容 `Sandbox` 协议的实现。

**验收标准**：
- `scripts/python/run.py` 中 `open('/etc/passwd').read()` 在容器沙箱内失败。
- 沙箱外工作目录只保留输入/输出，skill 无法访问 `$HOME` 和系统文件。

### P0-2 动态上下文注入必须走沙箱

**目标**：`!`command`` 和 ````` ```! ```` 不能成为远程代码执行后门。

**修改文件**：
- `backend/homomics_lab/skills/loader.py`
  - `_run_shell_command()` 改为调用 `Sandbox.run_shell_command()` 或新增 `Sandbox.run_command_capture()`。
  - 增加 `settings.skills_shell_execution_enabled` 开关：外部 skill 默认关闭 `!command``。

**验收标准**：
- 外部未签名 skill 中的 `!`rm -rf ~`` 被静默拒绝或需要用户显式确认。

### P0-3 Skill 信任模型

**目标**：用户能区分“内置/已信任”和“外部/未信任”skill。

**修改文件**：
- `backend/homomics_lab/skills/skill_store.py`
  - `import_skill()` 计算 skill 目录 sha256，写入 `metadata["sha256"]`。
  - 新增 `trust_skill(skill_id)` / `untrust_skill(skill_id)`。
- `backend/homomics_lab/skills/runtime.py`
  - `execute()` 对 `source == "external"` 且未标记 trusted 的 skill 抛出 `UntrustedSkillError`。
- `backend/homomics_lab/api/skills.py`
  - 增加 `POST /skills/{id}/trust` 端点。

**验收标准**：
- 自动发现的外部 skill 首次执行前必须被用户显式 trust。
- Builtin 和 legacy skill 默认 trusted。

### P0-4 危险工具二次确认

**目标**：LLM 调用 `shell_exec`、`file_write` 等高风险工具时需要用户确认。

**修改文件**：
- `backend/homomics_lab/skills/agent_executor.py`
  - 在执行高风险工具前检查 `settings.interactive_mode`；若交互式，抛出 `ToolApprovalRequired` 并返回待确认状态。
- `backend/homomics_lab/tools/registry.py` 或工具定义
  - 给工具增加 `risk_level: low | medium | high` 元数据。
- `backend/homomics_lab/api/skills.py`
  - 增加 `POST /skills/approve-tool/{call_id}` 端点。

**验收标准**：
- `shell_exec rm -rf` 类调用不会自动执行。

---

## P1 长任务持久化与独立 Worker

### P1-1 Job 持久化

**目标**：任务状态写入数据库，API 重启后可恢复。

**新增/修改文件**：
- `backend/homomics_lab/database/models.py`
  - 新增 `JobRecord` 表：`job_id`, `plan_id`, `phase_id`, `status`, `stdout`, `stderr`, `result_json`, `started_at`, `finished_at`。
- `backend/homomics_lab/jobs/manager.py`
  - 新增 `JobManager`：创建 job、更新状态、恢复未完成的 job。

**验收标准**：
- API 进程重启后，能查询到重启前提交 job 的最新状态。

### P1-2 独立 Worker 进程

**目标**：API 与执行解耦，支持多 worker。

**修改文件**：
- `backend/homomics_lab/worker.py`
  - 已存在入口 `homomics-worker`，完善其事件循环：从 Redis queue 消费，执行，更新 DB，发布 SSE。
- `backend/homomics_lab/config.py`
  - `worker_mode: bool` 默认关闭；文档推荐生产使用 `homomics-worker`。
- `backend/homomics_lab/jobs/backends/redis.py`
  - 验证 Redis backend 在 worker 独立运行时的稳定性。

**验收标准**：
- `homomics-worker` 启动后能消费 `submit_job` 事件。
- API 不阻塞在 long-running execution 上。

### P1-3 取消与超时

**目标**：用户能取消误提交的长任务。

**修改文件**：
- `backend/homomics_lab/jobs/manager.py`
  - `cancel_job(job_id)`：设置状态为 `cancelling`，worker 收到后终止进程。
- `backend/homomics_lab/hpc/scheduler.py`
  - `LocalScheduler` / `SlurmScheduler` / `NextflowRunner` 增加 `terminate(job_id)` 方法。
- `backend/homomics_lab/api/jobs.py`（若无则新建）
  - `POST /jobs/{id}/cancel`。

**验收标准**：
- 提交一个 10 分钟的 Nextflow run，调用 cancel 后 5 秒内终止。

---

## P2 可观测性与调试

### P2-1 结构化日志

**目标**：每次请求/计划/工具调用都有可追踪的日志。

**新增文件**：
- `backend/homomics_lab/logging_config.py`
  - 配置 JSON 日志格式、correlation id、按模块分级。
- 全局引入 `logging.getLogger(__name__)`，替代部分 `print()`。

**验收标准**：
- 一条执行链路中所有日志带有相同的 `correlation_id`。

### P2-2 执行 Trace Store

**目标**：保存每个 plan 的完整执行树，方便事后复盘。

**新增/修改文件**：
- `backend/homomics_lab/database/models.py`
  - 新增 `ExecutionTraceRecord`。
- `backend/homomics_lab/agent/supervisor.py` / `runtime.py`
  - 在 plan 开始、phase 开始、skill 调用、工具调用、错误处写入 trace 节点。
- `backend/homomics_lab/api/traces.py`（新建）
  - `GET /traces/{plan_id}` 返回树形 trace。

**验收标准**：
- 失败的 plan 能在 trace 中看到具体哪个 phase、哪个工具、哪个 LLM 调用出错。

### P2-3 CLI 调试命令

**目标**：不打开浏览器也能调试。

**新增文件**：
- `backend/homomics_lab/cli/commands/trace.py`
- `backend/homomics_lab/cli/commands/logs.py`

**验收标准**：
- `homomics trace <plan_id>` 在终端打印执行树。
- `homomics logs --job <job_id>` 打印 stdout/stderr。

---

## P3 大数据与缓存

### P3-1 大结果存储

**目标**：单细胞 h5ad、空间图像等大文件不走 JSON。

**新增/修改文件**：
- `backend/homomics_lab/data/data_store.py`（新建或复用 workspace）
  - `write_result(plan_id, phase_id, data, format_hint)`：自动选择 Parquet / AnnData / Zarr / JSON。
  - `read_result(uri)`。
- `backend/homomics_lab/skills/sandbox_engine.py`
  - 返回结果超过阈值时，sandbox 将结果写入文件，只把文件路径/URI 返回给 runtime。

**验收标准**：
- 1GB h5ad 经过 QC skill 后，返回结果引用文件而非 1GB JSON。

### P3-2 结果缓存 / Memoization

**目标**：相同输入不重复执行。

**新增/修改文件**：
- `backend/homomics_lab/skills/cache.py`（新建）
  - `compute_cache_key(skill_id, inputs, skill_version)`。
  - `get_or_execute(...)`。
- `backend/homomics_lab/skills/runtime.py`
  - `execute()` 在真正运行前先查缓存。

**验收标准**：
- 相同输入的 skill 第二次执行在 100ms 内返回缓存结果。

### P3-3 Dense 语义搜索（可选）

**目标**：skill 多了之后检索更准确。

**修改文件**：
- `backend/homomics_lab/skills/semantic_search.py`
  - 当 `settings.semantic_search_model` 配置时，使用 sentence-transformers 生成 embedding，否则保持 TF-IDF fallback。

**验收标准**：
- 配置 dense model 后，用自然语言“做聚类”能召回 `scanpy_leiden_clustering`。

---

## P4 Skill 执行正确性

### P4-1 Entrypoint 脚本执行

**目标**：不再按目录结构猜测脚本，而是由 skill 显式声明入口。

**修改文件**：
- `backend/homomics_lab/skills/loader.py`
  - 解析 frontmatter `entrypoint` 或 `script`。
- `backend/homomics_lab/skills/runtime.py`
  - 若 `metadata["entrypoint"]` 存在，只执行该文件；否则 fallback 到旧的 glob 拼接（保留兼容）。

**验收标准**：
- 一个 Claude Code skill 只有 `scripts/helper.py` 且 SKILL.md 写了 `entrypoint: scripts/helper.py`，能直接运行。

### P4-2 References / Assets 懒加载

**目标**：skill 可附带参考资料，执行时按需读取。

**新增/修改文件**：
- `backend/homomics_lab/skills/loader.py`
  - `load_reference(skill, ref_name) -> str`。
- `backend/homomics_lab/skills/agent_executor.py`
  - 暴露 `read_reference` 工具给 agent。

**验收标准**：
- SKILL.md 引用 `references/example_output.txt`，agent 执行时可通过工具读取。

### P4-3 Skill 测试工具

**目标**：用户安装 skill 前可快速验证。

**新增文件**：
- `backend/homomics_lab/cli/commands/skill_test.py`
  - `homomics skill test <skill-dir>` 在沙箱中用 sample input 跑一次。

**验收标准**：
- `homomics skill test ./my-skill` 输出 pass/fail 和 trace。

---

## P5 个人用户 CLI/UX

### P5-1 扩展 `homomics` CLI

**新增/修改文件**：
- `backend/homomics_lab/cli/main.py`
  - 新增子命令：
    - `homomics run <skill-id> [--args ...]`
    - `homomics plans [--status]`
    - `homomics jobs`
    - `homomics init-project`（生成项目结构）

### P5-2 项目模板

**新增文件**：
- `backend/homomics_lab/cli/templates/single-cell.yaml`
- `backend/homomics_lab/cli/templates/spatial.yaml`
- `backend/homomics_lab/cli/commands/init_project.py`

**验收标准**：
- `homomics init-project --template single-cell my-project` 生成 `homomics.yaml` + `data/` + `workspace/`。

### P5-3 环境自动安装

**修改文件**：
- `backend/homomics_lab/skills/runtime.py`
  - 执行前检测 skill `requirements.txt`，若当前环境缺少，提示用户或自动 `pip install`（需用户确认）。

**验收标准**：
- 安装一个带 `requirements.txt` 的外部 skill 后，首次执行能自动装好依赖。

---

## 长期方向（企业级，当前不做，仅记录）

- 多租户隔离（namespace / project / quota）
- 企业 SSO / OAuth2 / OIDC
- 审计日志与合规导出
- 计费与资源配额
- 高可用部署（Kubernetes Operator）
- 联邦/跨机构数据协作

---

## 建议的下一步动作

1. **立即开始 P0**：安全隔离是个人用户场景下开放的硬前提，没有它不能引入社区 skill。
2. **同步启动 P1 Worker**：把执行从 API 进程拆出来，也是 P0 沙箱化后更自然的设计。
3. **每完成一个阶段做一次全量 pytest**，保持当前 **768 passed** 的基线。
4. **先写测试再写实现**：P0 的隔离性必须有专门的渗透/安全测试覆盖。
