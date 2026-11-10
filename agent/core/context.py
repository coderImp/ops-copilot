"""上下文管理：token 预算 + 滑动窗口 + 机械摘要 + 结构化记忆。

关键设计（面试高频）：
- 摘要绝不动"关键实体"（traceId / 服务名 / 时间窗），它们走结构化记忆
- 工具结果先截断再进上下文，截断策略是"头 + 尾 + 计数"，不是简单砍尾巴
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


def est_tokens(text: str) -> int:
    """粗略估算：中文约 1.5 字/token，英文约 4 字符/token，取折中。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk / 1.5 + other / 4) + 1


@dataclass
class ContextManager:
    budget_tokens: int = 32000
    system_prompt: str = ""
    max_tool_chars: int = 4000
    keep_recent: int = 6          # 最近 N 条消息保留原文，更早的压缩

    messages: list[dict] = field(default_factory=list)
    memory: dict = field(default_factory=dict)
    stats: dict = field(default_factory=lambda: {
        "tool_chars_in": 0, "tool_chars_dropped": 0,
        "compressions": 0, "memory_writes": 0,
    })

    def __post_init__(self) -> None:
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})

    # ---------- 写入 ----------
    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def add_tool_result(self, tool: str, text: str) -> None:
        self.stats["tool_chars_in"] += len(text)
        if len(text) > self.max_tool_chars:
            keep_head = int(self.max_tool_chars * 0.7)
            keep_tail = self.max_tool_chars - keep_head - 40
            dropped = len(text) - keep_head - keep_tail
            text = (text[:keep_head] +
                    f"\n...[omitted {dropped} chars]...\n" +
                    text[-keep_tail:])
            self.stats["tool_chars_dropped"] += max(0, dropped)
        self.messages.append({"role": "tool", "name": tool, "content": text})

    def remember(self, key: str, value: str) -> None:
        """结构化记忆：关键实体不进摘要，随时可查。"""
        self.memory[key] = value
        self.stats["memory_writes"] += 1

    # ---------- 渲染 ----------
    def render(self) -> list[dict]:
        self._compress_if_needed()
        out = list(self.messages)
        if self.memory:
            out.append({"role": "system",
                        "content": "[已确认的实体记忆，可直接引用] " +
                                   json.dumps(self.memory, ensure_ascii=False)})
        return out

    def tokens(self) -> int:
        return sum(est_tokens(m.get("content") or "") for m in self.messages)

    def over_budget(self) -> bool:
        return self.tokens() > self.budget_tokens

    def _compress_if_needed(self) -> None:
        """滑动窗口 + 机械摘要：把超出 keep_recent 的 tool 输出压成一行结论。"""
        if len(self.messages) <= self.keep_recent + 2:
            return
        tail = self.messages[-self.keep_recent:]
        head = self.messages[: -self.keep_recent]
        compressed: list[dict] = []
        for m in head:
            if m["role"] != "tool":
                compressed.append(m)
                continue
            text = (m.get("content") or "").strip().replace("\n", " ")
            if text.startswith("[汇总]"):
                compressed.append(m)          # 已压缩过，不要再截一刀（否则摘要会漂移）
                continue
            one_line = text[:120] + ("…" if len(text) > 120 else "")
            compressed.append({"role": "tool", "name": m.get("name", "?"),
                               "content": f"[汇总] {one_line}"})
            self.stats["compressions"] += 1
        self.messages = compressed + tail
