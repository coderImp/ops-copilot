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
