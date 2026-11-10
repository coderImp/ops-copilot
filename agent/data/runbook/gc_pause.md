# GC 停顿（Full GC Allocation Failure）

## 现象
- 日志：`Full GC (Allocation Failure) 2100ms, heap 3.8G->3.7G (4G)`
- 指标：`gc_pause_ms` 从 30ms 飙到 2000ms+，`p99_latency_ms` 同步出现毛刺

## 判断依据
1. `gc_pause_ms` 是最直接信号；表现为**周期性**毛刺，不是持续高
2. GC 后老年代没降多少（3.8G->3.7G）→ 说明对象**活着**，不是回收不掉而是内存不足
3. 是否伴随 `OutOfMemoryError`（那就更严重）

## 处置步骤
1. 先看是谁在占内存：`jmap -histo` / heap dump 分析大对象
2. 常见原因：大结果集一次性加载、缓存无上限、连接/流未关闭、日志字符串拼接
3. 参数层面：调大堆或换 G1/ZGC（治标）；ZGC 停顿可降到 10ms 级
4. 根因修复：分页查询、限制缓存容量（Caffeine maximumSize）、及时关闭资源

## 验证
- `gc_pause_ms` P99 < 200ms
- 老年代占用在多次 GC 后回落

## 常见误判
- 看到延迟高就查 DB → 先看 `gc_pause_ms` 是否有周期性尖峰
