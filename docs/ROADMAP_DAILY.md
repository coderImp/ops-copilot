# 每日任务清单（v2 · 2026-11-10 晚 修订）

> 修订原因：11/10 一整天消耗在 CI 修复上（4 个真实缺陷），骨架已完成但"效果类工作"为 0。
> 剩余时间：11/11 – 11/15（5 天），每天 8h。

---

## 0. 当前真实基线（截至 11/10 17:45）

### 骨架：已完成 ✅

| 模块 | 文件 | 状态 |
|---|---|---|
| ReAct 主循环 + 三层终止 | `agent/core/loop.py` | ✅ 单测覆盖 |
| 工具注册表（校验/超时/重试/只读保护） | `agent/core/registry.py` | ✅ 9 个单测 |
| 上下文管理（预算/窗口/摘要/记忆） | `agent/core/context.py` | ✅ |
| 决策抽象（Oracle + OpenAI 兼容） | `agent/core/llm.py` | ✅ 真实模型已跑通 |
| 三工具 + 一高危工具 | `agent/tools/*` | ✅ |
| 故障模拟靶场（6 种故障） | `sim/target.py` + `sim/inject.py` | ✅ |
| runbook 语料 6 篇 | `agent/data/runbook/` | ✅ |
| 评测执行器（四层指标） | `eval/run_eval.py` | ✅ |
| 评测集 24 条 | `eval/scenarios.json` | ✅（目标 60，待扩） |
| 单测 16 个 | `tests/` | ✅ 全绿 |
| CI（Install→Lint→Test→Smoke） | `.github/workflows/ci.yml` | ✅ 待确认转绿 |
| 文档四件套 + PR 模板 + CONTRIBUTING | `docs/`, `.github/` | ✅ |

### 效果/扩展：未开始 ❌

| 事项 | 现状 | 阻塞点 |
|---|---|---|
| 真实模型全量基线（24 条） | 只跑了 easy(6) / hard(6)，misdirect 未跑 | 需 API key |
| `docs/BASELINE.md` | 只有 hard 子集，非全量 | 跑完覆盖 |
| 混合检索（BM25+向量+RRF） | ❌ 只有 BM25 | — |
| 评测集 60 条 | ❌ 24 条 | — |
| MCP Server | ❌ | — |
| 并行 fan-out 多 Agent | ❌ | — |
| 服务化（SSE/网关） | ❌ | **已决定砍掉**（见 §4） |

---

## Day 1 · 11/11（周三）：把"真实基线"钉死

> 今天不写新功能，只把"我现在的水平"测出来。没有基线，后面所有优化都无法证明。

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 跑全量 24 条：`python -m eval.run_eval --planner llm`；再单跑 `--only misdirect` | 两份报告，含真实数字 |
| 上午 +1h | 覆盖 `docs/BASELINE.md`，并另存 `docs/BASELINE_MISDIRECT.md` | 提交入库 |
| 下午 2h | **失败归因表**：每条失败按 5 类打标签（选错服务/参数错/日志没解析/提前收口/该拒答没拒答） | `docs/FAILURE_ANALYSIS.md` |
| 下午 1h | 挑 1 条最典型失败，把完整轨迹（每轮 tool + args + result）导出来 | 轨迹存档 |
| 晚上 1h | 八股/手撕 30min + 提交 | 3 次提交 |

**产出**：`BASELINE.md`（全量）、`BASELINE_MISDIRECT.md`、`FAILURE_ANALYSIS.md`

**如果 misdirect 全过**：说明场景太弱，立刻把 misdirect 加到 12 条（Day 3 提前做）。

---

## Day 2 · 11/12（周四）：混合检索 + 实验 A

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 给 runbook 建向量索引：优先 API embedding；无 key 则退化 TF-IDF（文档里标注"伪向量"） | 同一 query 召回 3 篇 |
| 下午 2h | 实现 RRF 融合，`search_kb(mode="bm25"|"vector"|"hybrid")` | 三模式可切换 |
| 下午 2h | **实验 A**：三模式各跑 24 条 | 对比表（Recall@3 / TaskSuccess / tokens） |
| 晚上 1h | 写 `experiments/A_retrieval.md` + 提交 | 3 次提交 |

**验收数字**：至少一组指标有变化；若无提升，**明确写出"语料太小，混合无收益"也是合格结论**。

---

## Day 3 · 11/13（周五）：评测集 24 → 60

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 扩场景：6 故障 ×3 难度 + 12 条 misdirect + 6 条多故障叠加 | 60 条 |
| 下午 2h | `sim.target.inject_multi()` 支持同时注入 2 个故障 | 单测覆盖 |
| 下午 2h | 全量 60 条跑一遍，更新基线 | 成功率与失败分类 |
| 晚上 1h | 提交 + 更新 BASELINE | 3 次提交 |

---

## Day 4 · 11/14（周六）：MCP Server + 工具路由接线

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | MCP Server（stdio）：暴露 query_metrics/query_logs/search_kb | 外部客户端能 tools/list + tools/call |
| 下午 2h | 把 `registry.route()` 接进 Agent：工具 >N 时先召回再选 | 单测 + 一条轨迹对比 |
| 下午 2h | 补 `docs/MCP.md`：一次完整交互时序 + 与 Function Calling 的边界 | 面试可直接讲 |
| 晚上 1h | 提交 | 3 次提交 |

---

## Day 5 · 11/15（周日）：fan-out + 收口

| 时段 | 任务 | 验收 |
|---|---|---|
| 上午 3h | 并行 fan-out：3 服务同时诊断（子 Agent 独立上下文）+ 冲突仲裁 | 延迟对比（串行 vs 并行） |
| 下午 2h | `demo.py`：一条命令跑完整流程并打印轨迹 | 可现场演示 |
| 下午 1h | README 补 Known Issues（没达标的如实写） | ≥2 条 |
| 下午 1h | 简历 3 条 bullet（填真实数字） | 每条"机制+两数字+对照" |
| 晚上 1h | 合并 develop→main、移动 tag、30 分钟讲法演练 | `v0.1.0` 指向绿提交 |

---

## 4. 决定砍掉的东西（以及理由）

| 砍掉 | 理由 |
|---|---|
| **Spring Boot 网关 + SSE** | 本机无 JDK/Maven；5 天内做 Java 服务化会挤掉混合检索和 60 条评测这两个"有数字"的活。**改为面试讲设计**："这套接口我设计成可被 Spring Boot 包裹，adapter 一层即可" |
| 演示视频 | 不产生面试分 |
| 4 组对照实验 | 只做 A（检索）和 D（编排）两组，B/C 留到下周 |
| 120 条评测集 | 60 条足够说明问题 |

## 5. 裁剪顺序（若某天落后）

1. 砍实验 B/C
2. 砍 MCP 的工具数：3 → 1
3. 砍多故障叠加
4. **绝不砍**：真实全量基线、失败归因、60 条评测、Git 历史

## 6. 每日固定 15 分钟

```powershell
cd D:\codeProject\ops-copilot
git checkout develop; git pull --rebase
git checkout -b feature/<当天主题>
# ... 干活，每完成一个可验证单元就 commit ...
git push -u origin feature/<当天主题>
# 去 GitHub 开 PR → CI 绿 → Squash and merge → 删分支
```
