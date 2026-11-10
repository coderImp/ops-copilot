# 空指针异常（NullPointerException）

## 现象
- 日志：`NullPointerException: Cannot invoke "BigDecimal.multiply(BigDecimal)" because "unitPrice" is null at OrderService.calc(OrderService.java:88)`
- 指标：`error_rate` 与 `http_5xx_rate` 同步抬升，延迟正常

## 判断依据
1. 错误率上升但**延迟不变** → 与连接池/慢查询/GC 区分开
2. 堆栈行号固定（同一行反复报）→ 单点代码缺陷，不是环境问题
3. 是否有新版本发布/配置变更的时间相关性

## 处置步骤
1. 定位到具体字段缺失：查上游是否漏传、是否新老数据不一致
2. 短期：补空值判断 + 默认值，或对入参加 `@Valid` 校验
3. 长期：契约校验（DTO + Bean Validation）、灰度发布、加单测覆盖空值分支
4. 若为历史数据问题：写数据修复脚本，先跑影子库

## 验证
- `error_rate` 回落到基线
- 该签名在日志中不再出现

## 常见误判
- 误判为下游超时 → 超时会有 `timed out` 关键字，NPE 堆栈在业务包内
