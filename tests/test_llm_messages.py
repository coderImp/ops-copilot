"""回归测试：内部上下文 → OpenAI 兼容消息格式的转换。"""
from __future__ import annotations

from agent.core.llm import OpenAICompatLLM


def test_tool_message_becomes_observation():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "tool", "name": "query_logs", "content": "{\"a\":1}"},
    ]
    out = OpenAICompatLLM.to_api_messages(msgs)
    assert [m["role"] for m in out] == ["system", "user", "user"]
    assert 'tool="query_logs"' in out[2]["content"]
    assert '{"a":1}' in out[2]["content"]


def test_mid_system_is_downgraded():
    """system 出现在中间会导致 422，必须降级为 user。"""
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "system", "content": "[记忆] x=1"},
    ]
    out = OpenAICompatLLM.to_api_messages(msgs)
    assert out[0]["role"] == "system"
    assert out[2]["role"] == "user"
    assert out[2]["content"] == "[记忆] x=1"


def test_empty_messages_fallback():
    out = OpenAICompatLLM.to_api_messages([])
    assert out == [{"role": "user", "content": ""}]
