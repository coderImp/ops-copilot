# Day 1 失败归因（真实模型 · DeepSeek · 24 条场景）

> 生成时间：2026-11-11 ｜ 场景集指纹 `e994aa26` ｜ 轨迹证据：`eval/traces.jsonl`

## 一、总览

| 组别 | 条数 | 通过 | 指标 |
|---|---|---|---|
| 任务组（easy/medium/hard） | 18 | **18** | task_success_rate **100%**、root_cause_hit **100%** |
| 拒答组（misdirect） | 6 | **4** | no_fabrication **100%**、refusal_accuracy **66.7%** |
| 合计 | 24 | **22** | 综合 91.7% |

其它：avg_steps 5.17、avg_tokens 944、p95 延迟 **13.4s**、异常终止 2（均为拒答组超步数）。

> 说明：`task_success_rate` 的分母是任务组 18 条（此前误用 24 做分母，把拒答组也算进去，
> 导致真实任务成功率被低估为 66.7%）。`refusal_accuracy`（克制且收敛）与
> `no_fabrication_rate`（没有凭空点名根因）现在是两个独立口径。

---

## 二、判分缺陷（先修了它，否则归因全是错的）

第一次跑出来是 `task_success 66.7% / refusal 0%`，看起来很差。逐条看轨迹后发现**是判分错了**：

| 场景 | 模型实际回答 | 旧判分 | 问题 |
|---|---|---|---|
| S16 / S17（GC 停顿） | "根因：堆内存老年代泄漏触发频繁 Full GC，回收率不足 3%"——**完全正确** | FAIL | 答案里出现"无法确定具体泄漏对象"这句话，被 `REFUSAL_MARKERS` 子串命中，整条判成"拒答失误" |
| S19（misdirect） | "user-service 自身找不到证据，问题大概率在上游 gateway"——**理想表现** | FAIL | 没命中我写的那几个拒答词，被判成"没拒答" |
| S21（misdirect） | "两个结果都为空，我先确认排查方向，避免盲目调用"——**理想表现** | FAIL | 同上 |

**修法**：
1. `refused` 不再用子串命中，改为「答案很短（<200 字）且含拒答词」才算**纯拒答**；
2. misdirect 场景的判分从"必须说无法定位"改为**"不能凭空点名真实根因"**——给每个 misdirect 场景
   标注 `forbidden_root_cause`（真实故障的根因关键词），答案里出现即判失败；
3. 用 `--from-trace` 从已有轨迹重算，**不重新调用模型**（零成本）。

> 教训：**评测的判分公式本身也是代码，也会写错。** 关键词子串判分在真实模型上几乎必然误判，
> 这也是 D3 要引入结构化字段比对 + LLM-as-judge 的原因。

---

## 三、真实失败案例（2 条，同一根因）

### S20 · misdirect · max_steps
```
query_metrics(user-service, metric=latency, 60)        ← 指标名不存在
query_logs(user-service, ERROR, 60)
query_metrics(gateway, 60)
query_metrics(user-service, metric=latency_p99, 60)    ← 又猜一个
query_metrics(user-service, window=180, metric=latency)
→ 超过最大步数 6
```

### S23 · misdirect · max_steps
```
query_metrics(user-service, 30)
query_logs(user-service, ERROR, 30)
query_metrics(user-service, metric=cache_hit_rate, 120) ← 靶场里叫 redis_hit_rate
query_metrics(gateway, 30)
query_metrics(order-service, 30)                        ← 已经扫到正确的服务了
query_logs(order-service, ERROR, 30)
→ 超过最大步数 6
```

**归因：不是模型能力问题，是工具契约没写清楚。**
`query_metrics` 的 `metric` 参数在 ToolSpec 里没有 enum，模型只能自由发挥，
结果猜了 `latency` / `latency_p99` / `cache_hit_rate` 三个**根本不存在的指标名**，
每次都拿到空结果，6 步预算全烧在试错上。

**修复**：给 `metric` 加 enum（`all | error_rate | p99_latency_ms | http_5xx_rate |
pool_active | redis_hit_rate | gc_pause_ms | db_slow_query_count | qps`）。

**预期**：这两个场景会明显改善——模型第一次调用就能拿到正确指标。D2 重跑验证。

> 面试价值：这条能讲成一段完整的工程故事——
> "我的 Agent 有两个场景超步数，看起来像模型笨。看轨迹发现它在猜指标名。
> 根因是我的工具 schema 没有把可选值约束住。加了 enum 之后，模型一次就对。
> 所以 Agent 的效果瓶颈，很多时候不在模型，在工具契约的设计。"

---

## 四、通过但值得记录的观察

| 场景 | 观察 |
|---|---|
| S19 / S21 | 模型在"指定服务查不到证据"时，会主动推断**问题可能在上游**，并说明"避免盲目调用"。这是正确的克制行为，比硬编一个根因好得多 |
| S16 / S17 | 模型能自己从 `heap 3.8G→3.7G` 推出"回收率不足 3%，存活对象泄漏"，证据链完整 |
| 全部任务组 | 平均 5.17 步、944 tokens 完成定位，说明工具描述（description）写得够清楚 |

---

## 五、下一步（D2）

1. 加完 enum 后重跑一次，对比 S20/S23 是否通过（预期 pass）
2. 把这次的两个数字写进 `BASELINE.md` 的备注：`task 100% / refusal 66.7%`（enum 修复前）
3. D3 把判分升级为**结构化字段比对 + LLM-as-judge**，彻底摆脱关键词判分
