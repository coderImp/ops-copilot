# 慢查询（SlowQuery / 全表扫描）

## 现象
- 日志：`SlowQuery elapsed=4821ms sql=SELECT * FROM t_order WHERE user_id = ? rows=23000`
- 指标：`db_slow_query_count` 从 0 抬升，`p99_latency_ms` 涨至秒级，`error_rate` 轻微上升（未超时）

## 判断依据
1. `elapsed` 稳定在数百毫秒到数秒
2. `rows` 扫描行数远大于返回行数 → 典型全表扫描
3. 错误率不高但延迟高 → 说明还没超时，只是慢

## 处置步骤
1. `EXPLAIN` 看是否走索引；`WHERE user_id` 无索引 → 建索引 `idx_user_id`
2. 避免 `SELECT *`，只取必要字段
3. 大结果集改分页（深分页用游标/延迟关联）
4. 热点查询加缓存（Redis），注意缓存与 DB 一致性

## 验证
- `db_slow_query_count` 归零
- `p99_latency_ms` 回落到基线 130ms 量级
- 扫描行数 ≈ 返回行数

## 常见误判
- 只看 `p99` 上升就怀疑 GC → 有 `SlowQuery` 日志时优先归因 SQL
