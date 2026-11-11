# Ops Copilot 开发文档（企业规范版）

| 项 | 内容 |
|---|---|
| 文档版本 | v0.1.0 |
| 最后更新 | 2026-11-10 |
| 负责人 | Jayce |
| 状态 | 开发中（骨架已跑通，待接真实模型） |
| 适用范围 | 本项目全部源码、评测资产与文档 |

---

## 1. 项目概述

### 1.1 一句话定义

Ops Copilot 是一个**面向 Java 微服务的排障 Agent**。它的技术内核是「Agent 运行时 + 工具协议 + 评测平台」，排障只是第一个落地场景。

### 1.2 目标（Goals）

| 编号 | 目标 | 验收方式 |
|---|---|---|
| G1 | Agent 能自主完成"指标 → 日志 → runbook → 根因"的多步排查 | 24 条评测集任务成功率 ≥ 60%（真实模型） |
| G2 | 工具调用具备工程安全性 | 参数校验、超时、幂等重试、写操作人工确认均有单测 |
| G3 | 上下文成本可控 | 输出 token 基线，并通过压缩策略降低 ≥ 40% |
| G4 | 效果可量化、可复现 | `python -m eval.run_eval` 一键出报告，指标含四层 |

### 1.3 非目标（Non-Goals）——明确不做，避免范围蔓延

- ❌ 不做前端 UI（面试不产生分数，纯时间消耗）
- ❌ 不做模型微调 / 训练（应用岗 JD 中占比 1%）
- ❌ 不做多租户计费、权限体系（留到后续版本）
- ❌ 不追求"支持 100 个工具"（4 个工具做透 > 20 个玩具工具）

### 1.4 为什么这样设计（技术决策摘要）

| 决策 | 选择 | 理由 |
|---|---|---|
| Agent 循环 | **手写 ReAct**，不用 LangGraph 起步 | 能讲清每一步的取舍；后续迁移可产出对比结论 |
| 靶场 | **Python 故障模拟器**，非 Docker+Spring Boot | 零依赖可复现、评测可批量跑；日志/指标格式与真实一致 |
| 检索 | **BM25**，暂不上向量库 | 排障语料以错误类名/异常标识符为主，关键词比语义更准；文档量小 |
| 存储 | SQLite / JSONL | 单机可跑，避免引入运维复杂度 |
| 终止 | 三层机制 | 单靠 max_steps 不足以防死循环与成本失控 |

---

## 2. 架构设计

### 2.1 分层

```
┌─────────────────────────────────────────────────────┐
│  接入层（D6）FastAPI + SSE / 限流 / 会话            │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│  编排层  agent/core/loop.py                          │
│  ReAct 主循环 · 三层终止 · 轨迹记录                   │
└───────┬───────────────────────────────┬─────────────┘
        ▼                               ▼
┌──────────────────┐          ┌──────────────────────┐
│ 上下文层          │          │ 决策层                │
│ core/context.py  │          │ core/llm.py           │
│ 预算/窗口/摘要/记忆│          │ Planner 抽象          │
└──────────────────┘          │  ├ OraclePlanner(离线) │
                              │  └ OpenAICompat(真实)  │
                              └──────────┬───────────┘
                                         ▼
                              ┌──────────────────────┐
                              │ 工具层                │
                              │ core/registry.py      │
                              │ schema/超时/重试/截断  │
                              └──────────┬───────────┘
                                         ▼
                    ┌────────────┬───────────────┬─────────────┐
                    ▼            ▼               ▼             ▼
              query_metrics  query_logs    search_kb    restart_service
              (SQL 精确)     (签名聚合)     (BM25)       (高危需确认)
                    │            │               │
                    └────────────┴───────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │ 数据源（sim 靶场产生）     │
                    │ data/metrics.db          │
                    │ data/logs/*.log          │
                    │ agent/data/runbook/*.md  │
                    └──────────────────────────┘
```

### 2.2 一次排查的时序

```
User            Loop            Planner          Registry        Tools
 │  故障描述      │                │                 │              │
 ├───────────────►│               │                 │              │
 │                ├──render()─────►│                 │              │
 │                │◄──tool:metrics─┤                 │              │
 │                ├──invoke──────────────────────────►│             │
 │                │                │                 ├─query_metrics►│
 │                │◄──result──────────────────────────┤             │
 │                ├──add_tool_result│                 │              │
 │                ├──render()─────►│                 │              │
 │                │◄──tool:logs────┤                 │              │
 │                │      ...（重复 2~4 轮）...                        │
 │                │◄──final───────────────────────────┤             │
 │◄──根因+处置────┤                │                 │              │
```

### 2.3 模块职责边界

| 模块 | 负责 | **不负责**（避免职责混入） |
|---|---|---|
| `loop.py` | 循环控制、终止判定、轨迹 | 不组装 prompt、不解析工具输出 |
| `context.py` | 消息存储、预算、压缩 | 不决定"该查哪个服务" |
| `llm.py` | 决策抽象与实现 | 不执行工具 |
| `registry.py` | 工具契约、执行、错误处理 | 不做业务判断 |
| `tools/*` | 单一数据查询 | 不做多步编排 |
| `eval/*` | 注入故障、跑场景、算指标 | 不改 Agent 行为 |

---

## 3. 目录结构

```
ops-copilot/
├── agent/
│   ├── core/
│   │   ├── loop.py         ReAct 主循环 + 三层终止
│   │   ├── registry.py     工具注册表（契约/校验/执行）
│   │   ├── context.py      上下文与预算管理
│   │   └── llm.py          Planner 抽象 + Oracle + OpenAI 兼容客户端
│   ├── tools/
│   │   ├── __init__.py     build_registry() 装配
│   │   ├── metrics.py      指标查询
│   │   ├── logs.py         日志签名聚合
│   │   └── kb.py           runbook BM25 检索
│   └── data/runbook/       6 篇处置手册（语料）
├── sim/
│   ├── target.py           6 种故障注入 + 数据生成
│   └── inject.py           CLI
├── eval/
│   ├── scenarios.json      24 条评测集
│   ├── run_eval.py         评测执行器
│   └── eval_report.md      产物（不入库）
├── tests/                  单元测试
├── docs/                   开发文档 / 每日任务 / Git 规范
└── .github/                CI + PR 模板
```

---

## 4. 环境与运行

| 项 | 要求 |
|---|---|
| Python | ≥ 3.10（已用 3.12 验证） |
| 第三方依赖 | **运行时零依赖**（仅标准库）；开发需要 pytest / ruff |
| 操作系统 | Windows / macOS / Linux 均可 |
| 可选 | `LLM_API_KEY`（接真实模型时才需要） |

```bash
# 1) 开发环境
pip install -e ".[dev]"

# 2) 注入一个故障（生成 data/logs 与 data/metrics.db）
python sim/inject.py pool_exhaust

# 3) 跑评测
python -m eval.run_eval                 # Oracle 基线（验证链路）
LLM_API_KEY=xxx python -m eval.run_eval --planner llm   # 真实模型

# 4) 质量门禁
pytest -q
ruff check .
```

> 注意：`python sim/inject.py` 与 `python -m sim.inject` 等价，CI 用后者。

### 4.1 本机开发环境（2026-11-10 记录）

| 组件 | 路径 / 版本 | 备注 |
|---|---|---|
| Python | `C:\Users\Administrator\.dsh\dsh-runtimes\...\python.exe` 3.12 | 另有一个项目级 `.venv`（3.15，未装 dev 依赖） |
| JDK（**非必需，备用**） | `D:\tool\jdk18`（Amazon Corretto 18.0.2） | D6 改为 FastAPI + SSE，本项目不再依赖 Java；保留以备 2027 年投 Java 栈团队 |
| JAVA_HOME | 用户级 = `D:\tool\jdk18` | 新开终端才生效（老进程继承旧环境变量） |
| Maven | **不安装**，用项目内 `mvnw` 包装器 | 避免多版本冲突 |
| Git remote | `git@github.com:coderImp/ops-copilot.git`（SSH） | — |

**目录约定（重要）**：

```
D:\tool\              所有 SDK / 工具（jdk18、git、vscode、idea ……）
D:\codeProject\       所有代码仓库
  └─ ops-copilot\
       ├─ .venv\       项目专属虚拟环境（.gitignore 已忽略）
       └─ gateway\     D6 新建的 Java 模块（属于本项目）
```

规则：
1. **SDK 永不放进代码目录**，也不进 Git 仓库。
2. 每个项目用自己的虚拟环境（项目内 `.venv`），不装到全局 Python。
3. 依赖缓存（如 Maven `~/.m2`）保持在用户目录，不要提交。

**已知技术债**：JDK 18 非 LTS 且已 EOL（2022-07）。本项目已改为 FastAPI + SSE，**不再依赖 Java**；
JDK 仅作为 2027 年投 Java 栈团队的备用环境保留。

**IntelliJ 注意**：该 JDK 原由 IDEA 的 "Download JDK" 管理（`.jdk.intellij` 标记）。
目录迁移后需手动重新指定：`File → Project Structure → Platform Settings → SDKs → Add SDK → JDK`
→ 选 `D:\tool\jdk18`。

---

## 5. 接口契约（实现前先定契约）

### 5.1 ToolSpec（工具的声明）

```python
ToolSpec(
    name="query_metrics",              # 全局唯一，snake_case，动宾结构
    description="...",                 # 给模型看，决定路由准确率；一句话说明"做什么+返回什么"
    params={                           # 字段 → 规则
        "service": {"type": "string", "required": True, "enum": [...]},
    },
    timeout_s=10,                      # 单次执行上限
    idempotent=True,                   # 只有幂等工具允许自动重试
    read_only=True,                    # False = 写操作，必须人工确认
    risk="low",                        # low|mid|high，决定确认策略
    max_result_chars=3000,             # 结果上限，超出打截断标记
)
```

**命名规范**：`query_*`（只读查询）、`search_*`（检索）、`execute_*`（执行，必须 read_only=False）、`restart_*`/`rollback_*`（高危）。

**description 写作规范**：
- ✅ "按服务查询时序指标，返回基线、峰值与异常项。排查第一步。"
- ❌ "查询指标"（太短，模型无法判断何时用）

### 5.2 ToolResult（执行的返回）

```python
ToolResult(ok: bool, data: Any, error: str|None,
           truncated: bool, elapsed_ms: int, attempts: int)
```

**错误码约定**（模型据此决定修正策略）：

| 错误前缀 | 含义 | 模型应做什么 |
|---|---|---|
| `invalid_args:` | 参数非法（缺字段/类型错/枚举越界） | 修正参数重试 |
| `unknown tool:` | 工具不存在 | 换工具 |
| `needs_human_confirm:` | 高危操作被拦截 | 停止，请用户确认 |
| `timeout after Ns` | 超时 | 缩小查询范围或换工具 |
| `<ExcType>: <msg>` | 工具内部异常 | 不要重试同一调用 |

**约束**：错误信息**禁止**包含完整堆栈（会把上下文打爆，也会诱导模型复读）。

### 5.3 Decision（Planner 的输出）

```python
Decision(kind="tool"|"final", tool: str, args: dict, text: str)
```

约定：`kind="tool"` 时只用 `tool` + `args`；`kind="final"` 时只用 `text`。

### 5.4 上下文契约

```python
ContextManager(budget_tokens=32000, max_tool_chars=4000, keep_recent=6)
```

| 规则 | 说明 |
|---|---|
| 截断 | 工具结果超 `max_tool_chars` → 头 70% + 尾 30% + 省略计数 |
| 压缩 | 消息数超 `keep_recent + 2` → 更早的 tool 消息压成一行 `[汇总]` |
| 记忆 | 关键实体（服务名/签名）走 `remember()`，**不参与摘要** |
| 预算 | `over_budget()` 触发强制收敛（第 3 层终止） |

> ⚠️ **已知坑（务必记住）**：工具返回 JSON 被截断后，`json.loads` 会失败，导致下游
> 误判为"没有数据"。因此：① 工具输出必须紧凑（≤3 条签名、样本 ≤160 字符）；
> ② 解析方必须容忍解析失败。这条可以作为面试素材讲。

---

## 6. 数据模型

### 6.1 日志（JSONL，一行一条）

```json
{"ts":"2026-11-10T09:16:41.886","service":"gateway","level":"ERROR",
 "logger":"com.demo.gateway.ProxyFilter",
 "msg":"FeignTimeout calling user-service /api/user/339874: read timed out after 31850ms",
 "trace_id":"8a9a021ea648a7dd","thread":"http-nio-8080-exec-3"}
```

字段约束：`ts` ISO8601（毫秒）、`level ∈ {DEBUG,INFO,WARN,ERROR}`、`msg` 必填。

### 6.2 指标（SQLite）

```sql
CREATE TABLE metrics(ts TEXT, service TEXT, metric TEXT, value REAL);
CREATE INDEX idx_m ON metrics(service, metric, ts);
```

### 6.3 错误签名归一化规则

| 规则 | 示例 |
|---|---|
| UUID → `<uuid>` | `8a9a021e-...` |
| ≥8 位 hex → `<hex>` | `deadbeef12` |
| 引号内容 → `"<v>"` | `"unitPrice"` |
| **所有数字 → `<n>`（不加 `\b`）** | `31850ms` → `<n>ms` |

> 为什么数字替换不能加 `\b`：`31850ms` 中数字后紧跟字母，`\b` 不成立，会漏替换 →
> 每组日志签名都不同 → 聚合失效（本项目真实踩过的 bug）。

### 6.4 runbook 文档规范

```markdown
# <故障名称>（<关键异常类/关键字>）
## 现象        ← 日志长什么样 + 指标长什么样
## 判断依据    ← 如何与其他故障区分（最重要）
## 处置步骤    ← 先止血，再根因
## 验证        ← 指标回到什么水平算恢复
## 常见误判    ← 容易混淆的相似故障
```

### 6.5 评测场景（JSON）

```json
{"id":"S01","fault":"pool_exhaust","difficulty":"easy|medium|hard|misdirect",
 "max_steps":6,"task":"...",
 "expect":{"root_cause_any":["连接池","pool"],"tools":["query_logs"],"must_refuse":false}}
```

- `difficulty=hard`：任务不指定服务，考察"逐服务扫描"能力
- `difficulty=misdirect`：任务指定了一个**健康的**错误服务，考察"证据不足要拒答"

---

## 7. 编码规范

1. **类型标注**：所有公开函数必须有参数与返回类型；使用 `from __future__ import annotations`。
2. **文档字符串**：模块级说明"为什么这么设计"；函数级说明契约（不写废话）。
3. **异常处理**：禁止裸 `except:`；工具内部异常必须在 `registry` 层转成结构化 `ToolResult`。
4. **禁止副作用外泄**：工具函数只读数据源，不改全局状态。
5. **常量集中**：阈值（如异常判定 1.8 倍）定义为模块常量并注明依据。
6. **可观测**：每次工具调用写入 `registry.call_log`（tool/args/ok/elapsed/attempts）。
7. **命名**：文件 snake_case、类 PascalCase、常量 UPPER_SNAKE。
8. **行宽**：≤100（E501 已忽略，但不要写超长行）。

---

## 8. 测试策略

| 层级 | 覆盖什么 | 工具 | 门槛 |
|---|---|---|---|
| 单元测试 | 参数校验、只读保护、超时/重试、三层终止 | pytest | 必须 100% 通过 |
| 端到端评测 | 24 条故障场景的任务成功率 | `eval.run_eval` | 报告入库，允许失败但要有归因 |
| 静态检查 | 风格与常见缺陷 | ruff | 无新增告警 |

**单测必测清单**（已完成，见 `tests/`）：
- 缺参数 / 类型错 / 枚举越界 / 多余参数
- 写操作被拦截（`needs_human_confirm`）
- 工具异常结构化（无 Traceback 泄漏）
- 结果截断标记
- 重复动作终止 / 最大步数终止 / 工具错误计数

---

## 9. 评测规范（最重要的一节）

### 9.1 四层指标

| 层 | 指标 | 回答什么问题 |
|---|---|---|
| 工具层 | ToolSuccessRate | 工具选对了吗？参数对吗？执行成功了吗？ |
| 任务层 | TaskSuccessRate、RootCauseHitRate | 最终结论对吗？ |
| 拒答层 | RefusalAccuracy | 证据不足时是否克制？ |
| 成本层 | AvgSteps、AvgTokens、P95Latency | 代价可接受吗？ |

### 9.2 ⚠️ 反造假条款（写进规范，也写进面试话术）

1. **OraclePlanner 的结果不得作为效果指标。** 它是启发式基线，只证明"靶场+工具+评测链路正常"。
2. **所有对外引用的数字必须来自真实模型**（`--planner llm`），并保留：
   - 场景集版本（`scenarios.json` 的 commit hash）
   - 模型名与参数（temperature=0）
   - 原始报告（`eval_report.md`）
3. **禁止只报最优一次。** 至少跑 3 次取中位数，或固定 `temperature=0` 说明可复现。
4. **失败案例必须保留**，写进 `eval_report.md` 的 Failures 段。

> 面试金句：*"我的数字你能复现——场景集、模型参数、报告都在仓库里。"*

### 9.3 对照实验规范

每组实验只改**一个变量**，其余固定：

| 实验 | 变量 | 固定 |
|---|---|---|
| A 检索策略 | BM25 / 向量 / 混合+RRF | 场景集、模型、prompt |
| B 上下文管理 | 全量历史 / 窗口+摘要 | 同上 |
| C 精排 | 无 rerank / 有 rerank | 同上 |
| D 编排 | 单 Agent / 并行 fan-out | 同上 |

---

## 10. 发布与版本

- **语义化版本**：`MAJOR.MINOR.PATCH`；`0.x` 阶段允许破坏性变更，但需在 CHANGELOG 注明。
- **CHANGELOG**：每个 PR 合并到 `develop` 时追加一行（Added/Changed/Fixed）。
- **Tag**：里程碑打 tag（如 `v0.1.0-eval-ready`）。

---

## 11. 里程碑与范围（v4：全量保留，11/11 – 11/22）

> 具体排期见 [ROADMAP_DAILY.md](ROADMAP_DAILY.md)。本节只定义范围边界：**原设计不做删减**，
> 仅顺延时间（11/15 → 11/22），并按评审意见把接入层从 Spring Boot 改为 **FastAPI + SSE**。

### 必做（D1–D12）

| # | 事项 | 验收 | 日期 |
|---|---|---|---|
| 1 | 真实模型全量基线（24 条）+ 失败归因 | 报告含真实数字 + 5 类失败标签 | D1 |
| 2 | 混合检索（BM25+向量+RRF） | 实验 A 有前后对比 | D2 |
| 3 | **评测客观性**：结构化字段比对 + LLM-as-judge | 双口径成功率 + 差异解释 | D3 |
| 4 | 评测集扩到 60 条（含多故障叠加） | 覆盖 6 故障 × 3 难度 + 拒答 | D3 |
| 5 | MCP Server + 工具路由接线 | 3 工具可通过 MCP 调用 | D4 |
| 6 | 并行 fan-out 多 Agent | 实验 D 延迟对比 | D5 |
| 7 | **FastAPI + SSE 服务化** | curl 可见流式输出 | D6 |
| 8 | 限流 / 会话隔离 / 审计 / 可观测 | 50 QPS 不崩，trace 可查 | D7 |
| 9 | **场景 B**（同 runtime 换工具集） | 不改 runtime 即可跑通 | D8 |
| 10 | 评测集扩到 120 条 | 5 类题型配比完整 | D8 |
| 11 | 实验 B（上下文）+ 实验 C（rerank） | 四组实验汇总表 | D9 |
| 12 | 收口：120 条终评 + demo + 简历 + tag v0.2.0 | 可投递 | D10 |
| 13 | 追问演练（三个必答题） | 脱稿讲 40 分钟 | D11–D12 |

### 明确不做

多租户计费、权限体系、前端 UI、模型微调、演示视频。

---

## 12. 风险与已知问题

| 风险 | 影响 | 缓解 |
|---|---|---|
| Oracle 100% 成功率被误当成绩 | 面试一问就崩 | 报告首行强制标注"基线，非模型能力" |
| 靶场是模拟，非真实进程 | 被质疑"没上过生产" | 诚实表述；靶场产出的是真实格式日志/指标，接口与真服务一致，替换只改数据源 |
| 真实 LLM 成本 | 24 条 × 多轮可能烧钱 | 加 response cache；评测分"离线 mock / 在线抽样"两档 |
| 评测集偏简单 | 指标虚高 | 引入 misdirect（6 条）与 hard（不指定服务）场景 |
| 工具输出截断破坏 JSON | 下游解析失败 | 紧凑输出 + 解析容错（已修复，见 5.4） |

---

## 13. 术语表

| 术语 | 含义 |
|---|---|
| ReAct | Reasoning + Acting，模型交替"思考"与"调用工具" |
| 三层终止 | 硬截断 / 重复动作检测 / 预算控制 |
| 错误签名 | 去掉动态部分（ID/数字/时间）后可聚合的日志模板 |
| RRF | Reciprocal Rank Fusion，多路召回按排名倒数融合 |
| OraclePlanner | 离线启发式规划器，用于验证链路而非测模型 |
| misdirect | 误导型评测场景：用户指定了错误的服务 |

---

## 14. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-10 | v0.1.0 | 初版：架构、契约、数据模型、编码规范、评测规范 |
