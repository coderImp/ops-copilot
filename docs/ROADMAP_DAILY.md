# 每日任务清单（v3 · 全量保留版 · 2026-11-10 晚）

> **变更说明**：v2 曾砍掉 Spring Boot 网关与部分实验。现按"不砍任何原设计"重排，
> 截止日期从 11/15 顺延到 **11/20（周五）**，共 10 个工作日。
> 每天 8 小时（上午 3h / 下午 3h / 晚上 2h），另留 30 分钟八股手撕（不可压缩）。

---

## 0. 当前基线（截至 11/10 晚）

### 已完成 ✅

| 项 | 证据 |
|---|---|
| Agent 主循环 + 三层终止 | `agent/core/loop.py` + 单测 |
| 工具注册表（校验/超时/重试/只读保护） | `agent/core/registry.py` + 9 单测 |
| 上下文管理 | `agent/core/context.py` |
| 决策抽象（Oracle / 真实 LLM） | `agent/core/llm.py` |
| 3 工具 + 1 高危工具 | `agent/tools/` |
| 故障靶场 6 种 | `sim/target.py`、`sim/inject.py` |
| runbook 6 篇 | `agent/data/runbook/` |
| 评测执行器（四层指标） | `eval/run_eval.py` |
| 评测集 24 条 | `eval/scenarios.json` |
| 单测 16 个 | `tests/` 全绿 |
| CI（Install→Lint→Test→Smoke） | **已绿** |
| 文档四件套 + PR 模板 | `docs/`、`.github/` |
| Git：14+ 提交、main/develop、tag v0.1.0（指向绿提交） | ✅ |

### 未完成（全部保留，按下表排期）

真实全量基线、混合检索、评测集 60→120、MCP、fan-out、Spring Boot 网关 + SSE、
4 组对照实验、可观测。

---

## 1. 范围对照表（原设计 → 落地日期）

| 原设计项 | 落在哪天 | 备注 |
|---|---|---|
| 真实模型全量基线 + 失败归因 | D1 11/11 | 一切优化的参照系 |
| 混合检索（BM25 + 向量 + RRF） | D2 11/12 | 实验 A |
| 评测集 24 → 60 | D3 11/13 | 含多故障叠加 |
| MCP Server + 工具路由接线 | D4 11/14 | 字节 JD 点名 |
| 并行 fan-out 多 Agent | D5 11/15 | 实验 D |
| Spring Boot 网关 + SSE 流式 | D6 11/16 | **需先装 JDK17** |
| 限流 / 会话隔离 / 审计 | D7 11/17 | 企业级后端要素 |
| 评测集 60 → 120 | D8 11/18 | 含实验 B（上下文） |
| 实验 C（rerank）+ 可观测 | D9 11/19 | trace 落库 + 成本看板 |
| 收口（demo/简历/讲法/tag v0.2.0） | D10 11/20 | 可投递 |

---

## D1 · 11/11（周三）：把真实基线钉死

> 今天不写新功能，只测"我现在什么水平"。

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | `python -m eval.run_eval --planner llm` 全量 24 条；再单跑 `--only misdirect` | 两份报告 |
| 上午 +1h | 覆盖 `docs/BASELINE.md`；另存 `docs/BASELINE_MISDIRECT.md` | 入库 |
| 下午 3h | **失败归因表**：5 类标签（选错服务/参数错/日志没解析/提前收口/该拒答没拒答）；挑 1 条最典型失败导出完整轨迹 | `docs/FAILURE_ANALYSIS.md` |
| 晚上 1h | 八股 30min + 3 次提交 | — |

**若 misdirect 全过** → 场景太弱，把 misdirect 加到 12 条（D3 提前）。

---

## D2 · 11/12（周四）：混合检索 + 实验 A

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | runbook 向量索引（API embedding；无 key 退化 TF-IDF 并标注"伪向量"） | 同 query 召回 3 篇 |
| 下午 2h | RRF 融合；`search_kb(mode=bm25|vector|hybrid)` | 三模式可切 |
| 下午 2h | 实验 A：三模式各跑 24 条 | Recall@3 / TaskSuccess / tokens 对比表 |
| 晚上 1h | `experiments/A_retrieval.md` + 提交 | 3 次提交 |

---

## D3 · 11/13（周五）：评测集 24 → 60

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 扩场景：6 故障 ×3 难度 + 12 misdirect + 6 多故障叠加 | 60 条 |
| 下午 2h | `sim.target.inject_multi()` 支持双故障 + 单测 | 覆盖 |
| 下午 2h | 全量 60 条跑真实模型，更新基线 | 新成功率 |
| 晚上 1h | 提交 + 更新 BASELINE | 3 次提交 |

---

## D4 · 11/14（周六）：MCP + 工具路由

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | MCP Server（stdio）暴露 3 工具 | 客户端可 tools/list + tools/call |
| 下午 2h | `registry.route()` 接进 Agent（工具 >N 先召回） | 单测 + 轨迹对比 |
| 下午 2h | `docs/MCP.md`：交互时序 + 与 Function Calling 边界 | 可讲 10 分钟 |
| 晚上 1h | 提交 | 3 次提交 |

---

## D5 · 11/15（周日）：并行 fan-out + 实验 D

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | fan-out：3 服务并行诊断（子 Agent 独立上下文）+ 冲突仲裁 | 可跑 |
| 下午 2h | 实验 D：单 Agent vs fan-out 延迟/成功率 | 对比表 |
| 下午 2h | `experiments/D_orchestration.md` + 提交 | 3 次提交 |
| 晚上 1h | 八股 30min | — |

---

## D6 · 11/16（周一）：Java 环境 + Spring Boot 骨架 + SSE

> ⚠️ 前置：本机无 JDK/Maven。先装 JDK17（推荐 Microsoft OpenJDK 或 Temurin），
> **Maven 用 wrapper（mvnw）避免单独安装**。

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 2h | 装 JDK17，`java -version` 通过；用 Spring Initializr 生成 `gateway/`（Web + WebFlux，含 mvnw） | `./mvnw -v` 可用 |
| 上午 2h | 网关基础：`/api/agent/chat` 转发到 Python `http://localhost:8000/chat` | curl 打通 |
| 下午 3h | **SSE 流式**：Python 侧流式产出，Java 侧透传（Flux<ServerSentEvent>） | curl 能看到逐段输出 |
| 晚上 1h | 提交 | 3 次提交 |

**降级方案**：若 JDK 安装受阻超过 2 小时，改用 Python `http.server` 实现 SSE（保持接口一致），
Java 层留到 D10 之后补——**不阻塞其他日**。

---

## D7 · 11/17（周二）：网关企业能力

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 限流（令牌桶/Redis 或内存）、会话隔离（sessionId → 上下文） | 压测 50 QPS 不崩 |
| 下午 2h | 审计日志（请求/工具调用/耗时落库）+ 错误码统一 | 有记录可查 |
| 下午 2h | 网关与 Agent 的接口契约文档 `docs/API.md` | 可交付 |
| 晚上 1h | 提交 | 3 次提交 |

---

## D8 · 11/18（周三）：评测集 60 → 120 + 实验 B

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 扩到 120 条（按 DESIGN 的 5 类题型配比：知识/参数/跨章节/计算校验/无答案） | 120 条 |
| 下午 2h | 实验 B：全量历史 vs 窗口+摘要 | token 降幅 + 成功率 |
| 下午 2h | `experiments/B_context.md` + 全量重跑 | 新基线 |
| 晚上 1h | 提交 | 3 次提交 |

---

## D9 · 11/19（周四）：实验 C + 可观测

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 2h | 实验 C：rerank（规则或 LLM 精排 top-5） | 前后对比 |
| 下午 3h | 可观测：trace 表（每轮 tool/args/耗时/tokens 落 SQLite）+ 一条命令出统计 | 报表可用 |
| 下午 2h | 成本看板：每场景 token/费用汇总 | 报告附成本 |
| 晚上 1h | 提交 | 3 次提交 |

---

## D10 · 11/20（周五）：收口

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 2h | 最终评测：120 条 × 3 次取中位数 | 终版报告 |
| 上午 2h | `demo.py` 一条命令跑完整链路 + 轨迹打印 | 可现场演示 |
| 下午 2h | README 补 Known Issues、架构图、指标表 | 对外可读 |
| 下午 2h | 简历 3 条 bullet（填真实数字）+ 30 分钟讲法演练 | 录音回放 |
| 晚上 1h | 合并 main、tag `v0.2.0`、清理分支 | 可投递 |

---

## 2. 裁剪顺序（仅在真的超期时启用，且必须记录原因）

1. 实验 C（rerank）
2. 可观测的成本看板（保留 trace 落库）
3. 评测集 120 → 80
4. MCP 工具数 3 → 1

**绝不砍**：真实全量基线、失败归因、混合检索、60+ 评测、Spring Boot + SSE、Git 历史。

## 3. 每日固定 15 分钟

```powershell
cd D:\codeProject\ops-copilot
git checkout develop; git pull --rebase
git checkout -b feature/<当天主题>
# 干活，每完成一个可验证单元就 commit
git push -u origin feature/<当天主题>
# GitHub 开 PR → CI 绿 → Squash merge → 删分支
```
