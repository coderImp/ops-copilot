# Ops Copilot

> 面向 Java 微服务的排障 Agent —— 本质是一个 **Agent 运行时 + 工具协议 + 评测平台**，排障只是它的第一个落地场景。

[![CI](https://github.com/<your-name>/ops-copilot/actions/workflows/ci.yml/badge.svg)](../../actions)

## 这是什么

给定一句自然语言故障描述（"order-service 报错率飙到 30%"），Agent 自主决定：
1. 查哪个服务的**指标**（结构化通道：SQL 精确聚合）
2. 查什么**日志**、按什么签名聚合（非结构化通道：归一化 + 计数）
3. 检索哪份**runbook**（BM25）
4. 何时**停止**（三层终止）并给出根因 + 处置建议

## 核心设计

| 模块 | 设计要点 | 面试考点 |
|---|---|---|
| `agent/core/loop.py` | 手写 ReAct，三层终止（硬截断/重复检测/预算） | "怎么保证一定停" |
| `agent/core/registry.py` | ToolSpec + schema 校验 + 超时 + 幂等重试 + 只读写分级 | "100 个工具怎么路由" |
| `agent/core/context.py` | token 预算 + 滑动窗口 + 机械摘要 + 结构化记忆 | "上下文爆炸怎么办" |
| `agent/tools/logs.py` | **错误签名归一化**（3 万行日志聚成几种签名，取 top3） | "日志太多塞不下" |
| `agent/tools/metrics.py` | 基线/峰值/异常判定，基线为 0 用绝对阈值 | "怎么判断异常" |
| `eval/run_eval.py` | 24 条场景、四层指标、拒答单独统计 | "评测怎么做" |

## 快速开始

```bash
# 无需任何第三方依赖，Python 3.10+ 即可
python -m sim.inject pool_exhaust     # 注入一个故障（生成日志 + 指标）
python -m eval.run_eval               # 跑全部 24 条评测
python -m eval.run_eval --only easy   # 只跑简单场景
```

> ⚠️ `eval.run_eval` 默认用 **OraclePlanner**（启发式基线），只验证靶场与评测链路，
> **不代表模型能力**。真实指标请设置 `LLM_API_KEY` 后加 `--planner llm`。

## 目录

```
agent/          Agent 运行时（loop / registry / context / llm）
  tools/        三个只读工具 + 一个高危写工具（需人工确认）
  data/runbook/ 6 篇运维处置手册（BM25 语料）
sim/            故障模拟靶场（纯 Python，无需 Docker）
eval/           评测集与评测脚本
tests/          单元测试
docs/           开发文档 / 每日任务 / Git 规范
```

## 当前状态

**已完成**

- [x] Agent 主循环 + 三层终止
- [x] 工具注册表 + 真实 JSON Schema + 超时 + 重试 + 写操作确认令牌
- [x] 上下文预算 + 摘要 + 结构化记忆
- [x] 指标/日志/runbook 三工具（指标支持涨/跌双向异常判定）
- [x] 故障模拟靶场（6 种故障）
- [x] 24 条评测集 + 评测脚本（固定种子，可复现）
- [x] **D1 真实模型基线**：任务组 18/18、拒答组 6/6（n=3 取中位数，p95 ≈ 7–14s）
- [x] D1 失败归因 + 轨迹归档（见 `docs/FAILURE_ANALYSIS.md`）

**待办**

- [ ] D2 混合检索（中文 bigram + BM25 + RRF）+ 检索级评测
- [ ] D3 评测客观性：结构化字段比对 + LLM-as-judge
- [ ] D4 MCP Server
- [ ] D5 并行 fan-out 多 Agent
- [ ] D6 FastAPI + SSE 服务化
- [ ] D7 限流 / 会话隔离 / 审计 / 可观测
- [ ] D8 场景 B + 评测集扩到 120 条
- [ ] D9 实验 B/C + 汇总
- [ ] D10 收口 + tag v0.2.0

详见 [docs/ROADMAP_DAILY.md](docs/ROADMAP_DAILY.md)。

## 开发

本机 `python` 指向 Microsoft Store 占位符（启动会弹商店），请统一用项目内 venv：

```powershell
scripts\setup.cmd          # 一次性：uv sync --extra dev
scripts\check.cmd          # 推代码前：lint + 单测 + 冒烟评测
.venv\Scripts\python.exe -m eval.run_eval --planner llm   # 跑真实模型评测
```

贡献与分支规范见 [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)。
