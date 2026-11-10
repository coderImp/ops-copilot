"""工具注册表：schema 校验 + 超时 + 幂等重试 + 结果截断。

设计要点（面试要讲的三件事）：
1. 工具分 read_only / write，write 必须人工确认（防 AI 自己执行 rollback）
2. 只有幂等工具才允许自动重试
3. 结果必须截断，否则 3 万行日志会撑爆上下文
"""
from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: dict            # {field: {"type": str, "required": bool, "enum": list|None}}
    timeout_s: float = 10.0
    idempotent: bool = True
    read_only: bool = True
    risk: str = "low"       # low | mid | high
    max_result_chars: int = 3000

    def to_prompt(self) -> str:
        fields = ", ".join(
            f"{k}:{v.get('type','string')}{'*' if v.get('required') else ''}"
            for k, v in self.params.items()
        )
        return f"- {self.name}({fields}) — {self.description}"


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None
    truncated: bool = False
    elapsed_ms: int = 0
    attempts: int = 1

    def render(self, max_chars: int = 3000) -> str:
        if not self.ok:
            return f"[tool_error] {self.error}"
        text = self.data if isinstance(self.data, str) else str(self.data)
        if len(text) > max_chars:
            return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"
        return text


class SchemaError(ValueError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._fns: dict[str, Callable[..., Any]] = {}
        self._specs: dict[str, ToolSpec] = {}
        self.call_log: list[dict] = []
        # 高危写操作的待确认队列：token -> (name, args)
        self._pending: dict[str, tuple[str, dict]] = {}
        self._confirm_seq = 0

    # ---------- 注册 ----------
    def register(self, spec: ToolSpec, fn: Callable[..., Any]) -> None:
        if spec.name in self._specs:
            raise ValueError(f"duplicate tool: {spec.name}")
        self._specs[spec.name] = spec
        self._fns[spec.name] = fn

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def prompt_block(self) -> str:
        return "\n".join(s.to_prompt() for s in self.specs())

    # ---------- 路由（工具 >20 个时用，避免全塞 prompt）----------
    def route(self, intent: str, top_k: int = 3) -> list[str]:
        tokens = set(intent.lower().replace("，", " ").replace(",", " ").split())

        def score(spec: ToolSpec) -> float:
            hay = (spec.name + " " + spec.description).lower()
            hit = sum(1 for t in tokens if t and t in hay)
            return hit + 0.1

        ranked = sorted(self._specs.values(), key=score, reverse=True)
        return [s.name for s in ranked[:top_k]]

    # ---------- 校验 ----------
    @staticmethod
    def _validate(spec: ToolSpec, args: dict) -> None:
        if not isinstance(args, dict):
            raise SchemaError("arguments must be a JSON object")
        unknown = set(args) - set(spec.params)
        if unknown:
            raise SchemaError(f"unknown arguments: {sorted(unknown)}")
        for name, rule in spec.params.items():
            required = rule.get("required", False)
            if name not in args:
                if required:
                    raise SchemaError(f"missing required argument: {name}")
                continue
            val = args[name]
            typ = rule.get("type", "string")
            ok = {
                "string": isinstance(val, str),
                "integer": isinstance(val, int) and not isinstance(val, bool),
                "number": isinstance(val, (int, float)) and not isinstance(val, bool),
                "boolean": isinstance(val, bool),
                "array": isinstance(val, list),
                "object": isinstance(val, dict),
            }.get(typ, True)
            if not ok:
                raise SchemaError(f"argument {name} must be {typ}, got {type(val).__name__}")
            enum = rule.get("enum")
            if enum is not None and val not in enum:
                raise SchemaError(f"argument {name} must be one of {enum}, got {val!r}")

    # ---------- 执行 ----------
    def invoke(self, name: str, args: dict, max_attempts: int = 2) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult(ok=False, error=f"unknown tool: {name}")

        try:
            self._validate(spec, args)
        except SchemaError as e:
            # 关键：参数错误回给模型让它自我修正，而不是抛异常崩掉
            return ToolResult(ok=False, error=f"invalid_args: {e}")

        if not spec.read_only:
            # 高危写操作：不直接执行，登记待确认，由人工调用 confirm() 放行
            self._confirm_seq += 1
            token = f"cfm-{self._confirm_seq:04d}"
            self._pending[token] = (name, args)
            self.call_log.append({"tool": name, "args": args, "ok": False,
                                  "error": "needs_human_confirm", "token": token})
            return ToolResult(
                ok=False,
                error=f"needs_human_confirm: {name} 是 risk={spec.risk} 的写操作，"
                      f"已登记确认令牌 {token}；请人工调用 registry.confirm('{token}') 后才会执行",
            )

        attempts = max_attempts if spec.idempotent else 1
        last: ToolResult | None = None
        for i in range(1, attempts + 1):
            started = time.time()
            try:
                # 注意：共享线程池 (见模块底部)。超时只会放弃等待，
                # 不会杀死工作线程 —— 工具实现必须自己可中断（如给底层 IO 设超时）。
                fut = _EXECUTOR.submit(self._fns[name], **args)
                data = fut.result(timeout=spec.timeout_s)
                elapsed = int((time.time() - started) * 1000)
                truncated = isinstance(data, str) and len(data) > spec.max_result_chars
                res = ToolResult(ok=True, data=data, truncated=truncated,
                                 elapsed_ms=elapsed, attempts=i)
                self.call_log.append({"tool": name, "args": args, "ok": True,
                                      "elapsed_ms": elapsed, "attempts": i})
                return res
            except concurrent.futures.TimeoutError:
                last = ToolResult(ok=False, error=f"timeout after {spec.timeout_s}s",
                                  elapsed_ms=int((time.time() - started) * 1000), attempts=i)
            except TypeError as e:
                last = ToolResult(ok=False, error=f"bad_signature: {e}", attempts=i)
                break
            except Exception as e:  # 工具内部异常要结构化，不能把堆栈丢给模型
                last = ToolResult(ok=False, error=f"{type(e).__name__}: {e}", attempts=i)
                break

        assert last is not None
        self.call_log.append({"tool": name, "args": args, "ok": False,
                              "error": last.error, "attempts": last.attempts})
        return last

    # ---------- 高危操作的二次确认 ----------
    def pending_confirms(self) -> list[str]:
        return list(self._pending)

    def confirm(self, token: str) -> ToolResult:
        """人工放行一个待确认的写操作。这是"AI 不能自己动生产"的落地开关。"""
        item = self._pending.pop(token, None)
        if item is None:
            return ToolResult(ok=False, error=f"unknown_confirm_token: {token}")
        name, args = item
        spec = self._specs[name]
        started = time.time()
        try:
            fut = _EXECUTOR.submit(self._fns[name], **args)
            data = fut.result(timeout=spec.timeout_s)
        except Exception as e:  # noqa: BLE001 - 对外统一成结构化错误
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        elapsed = int((time.time() - started) * 1000)
        self.call_log.append({"tool": name, "args": args, "ok": True,
                              "elapsed_ms": elapsed, "confirmed": token})
        return ToolResult(ok=True, data=data, elapsed_ms=elapsed)


# 全局共享线程池：避免每次调用新建池导致线程泄漏（超时时工作线程无法被杀死）
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=8, thread_name_prefix="tool")
