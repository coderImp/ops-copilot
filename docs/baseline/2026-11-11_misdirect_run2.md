# Agent 离线评测报告

> 生成时间：2026-11-11 11:17:08｜场景数：6｜子集：**all**｜实际规划器：**recomputed-from-trace(traces_misdirect_run2.jsonl)**（model: n/a）｜场景集指纹：`ec31736d`

## 汇总指标

| 指标 | 值 |
|---|---|
| n | 6 |
| n_task | 0 |
| n_refuse | 6 |
| task_success_rate | N/A |
| root_cause_hit_rate | N/A |
| refusal_accuracy | 100.0 |
| no_fabrication_rate | 100.0 |
| tool_success_rate | 100.0 |
| avg_steps | 2.5 |
| avg_tokens | 186 |
| p95_latency_ms | 13858 |
| abnormal_termination | 0 |

## 逐条结果

```
ID    难度        终止         步数   根因   拒答   成功  
----------------------------------------------
S19   misdirect final      2    -    Y    PASS
S20   misdirect final      3    -    Y    PASS
S21   misdirect final      2    -    Y    PASS
S22   misdirect final      2    -    Y    PASS
S23   misdirect final      3    -    Y    PASS
S24   misdirect final      3    -    Y    PASS
```

## 失败案例

无
