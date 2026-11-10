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
| `agent/tools/logs.py` | **错误签名归一化**（把 3 万行聚成 5 种） | "日志太多塞不下" |
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

- [x] Agent 主循环 + 三层终止
- [x] 工具注册表 + schema 校验 + 超时 + 重试
- [x] 上下文预算 + 摘要 + 结构化记忆
- [x] 指标/日志/runbook 三工具
- [x] 故障模拟靶场（6 种故障）
- [x] 24 条评测集 + 评测脚本
- [ ] 接入真实 LLM 并产出可引用指标
- [ ] 混合检索（BM25 + 向量 + RRF）
- [ ] 并行 fan-out 多 Agent
- [ ] MCP Server
- [ ] Spring Boot 网关 + SSE

详见 [docs/ROADMAP_DAILY.md](docs/ROADMAP_DAILY.md)。

## 开发

```bash
pip install -e ".[dev]"
pytest          # 跑单测
ruff check .    # 跑 lint
```

贡献与分支规范见 [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)。

<!-- first push test -->
