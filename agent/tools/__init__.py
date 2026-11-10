"""工具装配：把 3 个只读工具 + 1 个高危写工具注册进来。

高危工具（restart_service）故意做成"必须人工确认才能执行"，
用于演示"AI 不能自己动生产环境"这条设计红线，也是面试常问的点。
"""
from __future__ import annotations

from agent.core.registry import ToolRegistry, ToolSpec
from agent.tools import kb, logs, metrics


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(
        ToolSpec(
            name="query_metrics",
            description="按服务查询时序指标(错误率/延迟/连接池等)，返回基线、峰值与异常项。排查第一步。",
            params={
                "service": {"type": "string", "required": True,
                            "enum": ["gateway", "order-service", "user-service"]},
                "metric": {"type": "string", "required": False},
                "window_minutes": {"type": "integer", "required": False},
            },
            timeout_s=10,
        ),
        metrics.query_metrics,
    )

    reg.register(
        ToolSpec(
            name="query_logs",
            description="按服务查询日志，自动归一化为错误签名并计数，返回 top5 签名与样本。",
            params={
                "service": {"type": "string", "required": True,
                            "enum": ["gateway", "order-service", "user-service"]},
                "level": {"type": "string", "required": False,
                          "enum": ["ERROR", "WARN", "INFO", "DEBUG"]},
                "since_minutes": {"type": "integer", "required": False},
                "keyword": {"type": "string", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            timeout_s=10,
        ),
        logs.query_logs,
    )

    reg.register(
        ToolSpec(
            name="search_kb",
            description="检索运维 runbook（处置手册），输入错误签名或现象描述。",
            params={
                "query": {"type": "string", "required": True},
                "top_k": {"type": "integer", "required": False},
            },
            timeout_s=10,
            max_result_chars=2500,
        ),
        kb.search_kb,
    )

    # 高危写操作：默认被 registry 拦下，需要走人工确认流程
    reg.register(
        ToolSpec(
            name="restart_service",
            description="重启指定服务（高危写操作，必须人工确认）",
            params={"service": {"type": "string", "required": True}},
            timeout_s=30,
            idempotent=False,
            read_only=False,
            risk="high",
        ),
        lambda service: f"restarted {service}",
    )

    return reg
