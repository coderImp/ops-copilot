# 连接池耗尽（HikariPool Connection is not available）

## 现象
- 日志：`HikariPool-1 - Connection is not available, request timed out after 30000ms (total=20, active=20, idle=0)`
- 指标：`pool_active` 持续贴近上限（如 20/20），`error_rate` 快速升至 20%+
- 请求表现为大面积 500，且**耗时集中在 30s 附近**（等于等待连接的超时时间）

## 判断依据
1. `pool_active` 是否等于/接近 `maximumPoolSize`
2. 是否伴随慢查询或长事务（连接被占住不还）
3. 是否只有单一服务报错，还是级联到网关

## 处置步骤
1. 先确认是不是**慢 SQL 占住连接**：查 `db_slow_query_count` 与 `p99_latency_ms`
2. 临时扩容：调大 `maximumPoolSize`（治标，注意数据库连接数上限）
3. 根因修复：找出未关闭连接 / 长事务 / N+1 查询，补 `try-with-resources` 或加索引
4. 加保护：`connectionTimeout` 不要设 30s，设 3s + 快速失败，避免线程堆积

## 验证
- `pool_active` 回落到 30% 以下
- `error_rate` 回落到基线 2% 附近
- 单请求 P99 < 500ms

## 常见误判
- 误以为是下游超时 → 看 `logger` 是否在 `com.zaxxer.hikari`，池内等待和网络超时的堆栈完全不同
