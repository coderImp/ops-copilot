# Agent 离线评测报告

> 生成时间：2026-11-11 10:49:21｜场景数：6｜子集：**all**｜实际规划器：**recomputed-from-trace(traces_misdirect.jsonl)**（model: n/a）｜场景集指纹：`496b809b`

## 汇总指标

| 指标 | 值 |
|---|---|
| n | 6 |
| n_task | 0 |
| n_refuse | 6 |
| task_success_rate | N/A |
| root_cause_hit_rate | N/A |
| refusal_accuracy | 66.7 |
| no_fabrication_rate | 100.0 |
| tool_success_rate | 100.0 |
| avg_steps | 5 |
| avg_tokens | 423 |
| p95_latency_ms | 12272 |
| abnormal_termination | 2 |

## 逐条结果

```
ID    难度        终止         步数   根因   拒答   成功  
----------------------------------------------
S19   misdirect final      5    -    Y    PASS
S20   misdirect duplicate  4    -    Y    FAIL
S21   misdirect max_steps  6    -    Y    FAIL
S22   misdirect final      6    -    Y    PASS
S23   misdirect final      3    -    Y    PASS
S24   misdirect final      6    -    Y    PASS
```

## 失败案例

- **S20** (misdirect, slow_sql) terminator=duplicate root_hit=False refused=True
  - answer: `重复动作终止：同一工具同一参数连续被请求`
- **S21** (misdirect, npe) terminator=max_steps root_hit=False refused=True
  - answer: `超过最大步数 6`

# 拒答组基线（misdirect，6 条）

修复 duplicate 终止策略后的 3 次运行：

| 运行 | refusal_accuracy | no_fabrication | avg_steps | avg_tokens | abnormal |
|---|---|---|---|---|---|
| run1 | 83.3% | 83.3% | 2.67 | 193 | 0 |
| run2 | 66.7% | 83.3% | 3.17 | 369 | 1 |
| run3 | 83.3% | 83.3% | 2.50 | 186 | 0 |
| **中位数** | **83.3%** | **83.3%** | **2.67** | **193** | — |

结论：6 条中稳定通过 5 条（S23 因判分禁区词与任务文本重叠被误判，已修）。
方差说明：单次运行的 refusal 在 66.7%~83.3% 之间波动，**对外引用必须注明 n=3 取中位数**。

# 拒答组基线（misdirect，n=3 取中位数）

> 真实模型 DeepSeek ｜ 场景集指纹 `e994aa26` ｜ 判分规则以当前 `eval/scenarios.json` 为准
> 原始轨迹：`eval/traces_misdirect_run{1,2,3}.jsonl` ｜ 单次报告：`docs/baseline/`

| 运行 | refusal_accuracy | no_fabrication | avg_steps | avg_tokens | abnormal |
|---|---|---|---|---|---|
| run1 | 100% | 100% | 2.50 | 186 | 0 |
| run2 | 100% | 100% | 2.50 | 186 | 0 |
| run3 | 100% | 100% | 2.67 | 193 | 0 |
| **中位数** | **100%** | **100%** | **2.50** | **186** | 0 |

6 条 misdirect 全部通过：用户指错服务时，模型能明确指出"该服务自身无异常证据"，
并主动把排查方向转向上游，而不是编造根因。

## 判分口径的三次修正（本次最有价值的部分）

1. `refused` 曾是子串命中 → 正确答案含"无法确定"被判成拒答（S16/S17 被冤枉）
2. misdirect 从"必须说无法定位"改为"**不得点名真实根因**"（`forbidden_root_cause`）
3. 禁区词曾与任务文本、工具 enum 重叠（"缓存"、"redis_hit_rate"）→
   模型复述用户的话、或正常调用工具都被判泄露

## 已知局限

子串判分本质脆弱，已经修了 3 轮。D3 改为「结构化字段比对 + LLM-as-judge」，双口径并报。
