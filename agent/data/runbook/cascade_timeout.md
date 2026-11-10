# 下游超时级联（FeignTimeout / 504）

## 现象
- 日志：`FeignTimeout calling user-service /api/user/{id}: read timed out after 30000ms (retry 2/3)`
- 指标：**网关** `p99_latency_ms` 与 `http_5xx_rate` 同时抬升，被调服务自身指标可能正常

## 判断依据
1. 报错集中在**网关/调用方**，而被调方 `error_rate` 不高 → 说明是调用方等待超时
2. 出现 `retry` 字样 → 重试放大了下游压力（重试风暴）
3. 检查被调方 `pool_active` / `gc_pause_ms` / 线程池是否打满

## 处置步骤
1. 先止血：打开熔断（Resilience4j/Sentinel），失败快速返回，不要无限重试
2. 收敛重试：只对幂等 GET 重试，限制次数 + 指数退避 + 抖动
3. 超时分级：连接超时 1s、读超时按 P99 的 1.5 倍设置，不要统一 30s
4. 根因：定位被调方是慢查询、GC、还是线程池满
5. 加舱壁隔离：不同下游用独立线程池，避免一个慢依赖拖垮全站

## 验证
- 网关 5xx 回落
- 被调方 `pool_active` / `gc_pause_ms` 恢复
- 重试次数下降，下游 QPS 回落

## 常见误判
- 只看被调方指标正常就认为"不是它的问题" → 要看它是否**变慢但没报错**
