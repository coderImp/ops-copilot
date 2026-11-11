# Agent 离线评测报告

> 生成时间：2026-11-11 10:49:20｜场景数：24｜子集：**all**｜实际规划器：**recomputed-from-trace(traces.jsonl)**（model: n/a）｜场景集指纹：`496b809b`

## 汇总指标

| 指标 | 值 |
|---|---|
| n | 24 |
| n_task | 18 |
| n_refuse | 6 |
| task_success_rate | 100.0 |
| root_cause_hit_rate | 100.0 |
| refusal_accuracy | 66.7 |
| no_fabrication_rate | 100.0 |
| tool_success_rate | 100.0 |
| avg_steps | 5.17 |
| avg_tokens | 944 |
| p95_latency_ms | 13356 |
| abnormal_termination | 2 |

## 逐条结果

```
ID    难度        终止         步数   根因   拒答   成功  
----------------------------------------------
S01   easy      final      4    Y    -    PASS
S02   medium    final      4    Y    -    PASS
S03   hard      final      5    Y    -    PASS
S04   easy      final      6    Y    -    PASS
S05   medium    final      5    Y    -    PASS
S06   hard      final      6    Y    -    PASS
S07   easy      final      4    Y    -    PASS
S08   medium    final      4    Y    -    PASS
S09   hard      final      5    Y    -    PASS
S10   easy      final      6    Y    -    PASS
S11   medium    final      6    Y    -    PASS
S12   hard      final      6    Y    -    PASS
S13   easy      final      5    Y    -    PASS
S14   medium    final      4    Y    -    PASS
S15   hard      final      5    Y    -    PASS
S16   easy      final      5    Y    -    PASS
S17   medium    final      5    Y    -    PASS
S18   hard      final      6    Y    -    PASS
S19   misdirect final      6    -    Y    PASS
S20   misdirect max_steps  6    -    Y    FAIL
S21   misdirect final      3    -    Y    PASS
S22   misdirect final      6    -    Y    PASS
S23   misdirect max_steps  6    -    Y    FAIL
S24   misdirect final      6    -    Y    PASS
```

## 失败案例

- **S20** (misdirect, slow_sql) terminator=max_steps root_hit=False refused=True
  - answer: `超过最大步数 6`
- **S23** (misdirect, redis_down) terminator=max_steps root_hit=False refused=True
  - answer: `超过最大步数 6`
