"""工具注册表：校验、只读保护、截断、错误结构化。"""
from __future__ import annotations

import pytest

from agent.core.registry import ToolRegistry, ToolSpec


def _reg() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolSpec(name="echo", description="echo back", params={
            "text": {"type": "string", "required": True},
        }),
        lambda text: text,
    )
    reg.register(
        ToolSpec(name="pick", description="enum", params={
            "mode": {"type": "string", "required": True, "enum": ["a", "b"]},
        }),
        lambda mode: mode,
    )
    reg.register(
        ToolSpec(name="boom", description="raises", params={}),
        lambda: (_ for _ in ()).throw(RuntimeError("kaboom")),
    )
    reg.register(
        ToolSpec(name="big", description="long output", params={}, max_result_chars=20),
        lambda: "x" * 500,
    )
    reg.register(
        ToolSpec(name="danger", description="write op",
                 params={"service": {"type": "string", "required": True}},
                 read_only=False, risk="high", idempotent=False),
        lambda service: "done",
    )
    return reg


def test_unknown_tool():
    r = _reg().invoke("nope", {})
    assert not r.ok and "unknown tool" in (r.error or "")


def test_missing_required_arg():
    r = _reg().invoke("echo", {})
    assert not r.ok and "invalid_args" in (r.error or "")


def test_wrong_type():
    r = _reg().invoke("echo", {"text": 123})
    assert not r.ok and "must be string" in (r.error or "")


def test_enum_violation():
    r = _reg().invoke("pick", {"mode": "z"})
    assert not r.ok and "one of" in (r.error or "")


def test_unknown_arg_rejected():
    r = _reg().invoke("echo", {"text": "hi", "extra": 1})
    assert not r.ok and "unknown arguments" in (r.error or "")


def test_tool_exception_is_structured():
    r = _reg().invoke("boom", {})
    assert not r.ok
    assert "RuntimeError" in (r.error or "")
    assert "Traceback" not in (r.error or "")


def test_write_tool_requires_confirm():
    r = _reg().invoke("danger", {"service": "order-service"})
    assert not r.ok
    assert "needs_human_confirm" in (r.error or "")


def test_truncation_flag():
    r = _reg().invoke("big", {})
    assert r.ok and r.truncated is True
    rendered = r.render(max_chars=20)
    assert "truncated" in rendered


def test_ok_path():
    r = _reg().invoke("echo", {"text": "hello"})
    assert r.ok and r.data == "hello" and r.attempts == 1


@pytest.mark.parametrize("name,args", [
    ("echo", {"text": "x"}),
    ("pick", {"mode": "a"}),
])
def test_call_log_records(name, args):
    reg = _reg()
    reg.invoke(name, args)
    assert reg.call_log and reg.call_log[-1]["tool"] == name
