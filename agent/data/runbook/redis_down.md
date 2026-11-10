# Redis 不可用（RedisConnectionFailureException）

## 现象
- 日志：`RedisConnectionFailureException: Unable to connect to Redis; Connection refused`
- 指标：`redis_hit_rate` 从 0.93 骤降到接近 0，`error_rate` 上升，`p99_latency_ms` 抬升（回源 DB）

## 判断依据
1. `redis_hit_rate` 断崖式下跌是最强信号
2. `Connection refused` → 实例挂了/网络不通/端口变更（不是超时）
3. 是否伴随 DB 压力上升（缓存击穿导致回源）

## 处置步骤
1. 确认 Redis 实例状态（进程/容器/网络 ACL）
2. 应用侧加降级：读缓存失败直接查 DB，不要抛错给用户（`@Cacheable` 配 `errorHandler`）
3. 防击穿：热点 key 加互斥锁或逻辑过期，避免同时回源
4. 恢复后：预热热点 key，逐步放开流量
5. 加监控：`redis_hit_rate` 跌落告警要早于业务报错

## 验证
- `redis_hit_rate` 回到 0.9 以上
- `error_rate` 回落，DB QPS 回落

## 常见误判
- 只看到 DB 慢就归因 DB → 实际是缓存失效后的回源风暴
