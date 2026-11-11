"""决策层：LLM 抽象 + 离线 Oracle 规划器 + OpenAI 兼容客户端。

为什么要 OraclePlanner：
    没有 API key 也要能跑通"靶场 → 工具 → 评测"全链路，并且验证的是
    真实的工具数据（不是写死的剧本），所以成功率是有意义的。

    它是一套"合格 Agent 的启发式策略"：查指标 → 查日志 → 查 runbook → 给根因。
    用它可以测出"靶场和评测集是否合理"；换成真模型才能测出"模型能力"。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Decision:
    kind: str                       # "tool" | "final"
    tool: str = ""
    args: dict = field(default_factory=dict)
    text: str = ""                  # thought / final answer


class Planner(Protocol):
    def decide(self, messages: list[dict], tool_block: str,
               specs: list[Any] | None = None, force_text: bool = False) -> Decision: ...


# ---------------------------------------------------------------- Oracle
SERVICES = ("gateway", "order-service", "user-service")
KB_HINTS = ("pool", "timeout", "slow", "npe", "null", "gc", "redis", "connection")


class OraclePlanner:
    """启发式策略：模拟一个合格工程师的排查顺序（状态驱动，不是写死剧本）。

    流程：查指标 → 无异常就换到网关 → 查错误日志 → 查 runbook → 给根因
    证据不足时**必须拒答**（对应评测集里的 must_refuse 场景）。
    """

    REFUSAL = "未发现指标异常且无匹配错误日志，无法定位根因；建议确认服务范围、时间窗口或补充监控。"

    def __init__(self) -> None:
        self.metrics_done: set[str] = set()
        self.target: str | None = None        # 已确认异常的服务
        self.logs_error_done: set[str] = set()
        self.logs_any_done: set[str] = set()
        self.calls: list[str] = []

    @staticmethod
    def _find_service(text: str) -> str | None:
        for s in SERVICES:
            if s in text:
                return s
        return None

    @staticmethod
    def _tool_payloads(messages: list[dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for m in messages:
            if m.get("role") != "tool":
                continue
            try:
                out[m.get("name", "?")] = json.loads(m.get("content") or "{}")
            except json.JSONDecodeError:
                out[m.get("name", "?")] = {}
        return out

    def decide(self, messages: list[dict], tool_block: str,
               specs: list[Any] | None = None, force_text: bool = False) -> Decision:
        task = next((m["content"] for m in messages if m["role"] == "user"), "")
        named = self._find_service(task)
        payloads = self._tool_payloads(messages)
        last_metrics = payloads.get("query_metrics", {})
        anomalies = last_metrics.get("anomalies") or []

        # 记录"已找到异常的服务"，一旦确认就停止扫描
        if anomalies and self.target is None:
            self.target = last_metrics.get("service")

        # 1) 扫指标：指定了服务就只查它（别瞎猜）；没指定就逐个扫
        if self.target is None:
            order = [named] if named else ["gateway", "order-service", "user-service"]
            for svc in order:
                if svc and svc not in self.metrics_done:
                    self.metrics_done.add(svc)
                    return Decision("tool", "query_metrics",
                                    {"service": svc, "metric": "all", "window_minutes": 15})
            return Decision("final", text=self.REFUSAL)

        target = self.target

        # 2) 查 ERROR 日志
        if target not in self.logs_error_done:
            self.logs_error_done.add(target)
            return Decision("tool", "query_logs",
                            {"service": target, "level": "ERROR",
                             "since_minutes": 15, "limit": 50})

        sigs = (payloads.get("query_logs") or {}).get("top_signatures") or []

        # 3) ERROR 没内容 → 放宽到全等级再查一次（慢查询/GC 是 WARN 级）
        if not sigs and target not in self.logs_any_done:
            self.logs_any_done.add(target)
            return Decision("tool", "query_logs",
                            {"service": target, "since_minutes": 15, "limit": 50})

        if not sigs:
            return Decision("final", text=self.REFUSAL)

        # 4) 查 runbook
        if "search_kb" not in payloads:
            return Decision("tool", "search_kb",
                            {"query": sigs[0]["signature"], "top_k": 3})

        # 5) 作答
        kb = payloads.get("search_kb", {})
        kb_titles = [h.get("title", "") for h in (kb.get("hits") or [])]
        top = anomalies[0] if anomalies else {}
        ratio = top.get("ratio")
        if top.get("direction") == "down":
            ratio_txt = f"跌至基线的 {ratio} 倍"
        elif ratio is not None:
            ratio_txt = f"峰值为基线的 {ratio} 倍"
        else:
            ratio_txt = "基线为 0，出现非零值"
        answer = (
            f"根因判断：{target} 的 {top.get('metric', '指标')} 异常（{ratio_txt}），"
            f"关键错误签名：{sigs[0]['signature']}（出现 {sigs[0]['count']} 次）。\n"
            f"处置建议：参考《{kb_titles[0] if kb_titles else '无匹配 runbook'}》，"
            f"先止血再定位根因，观察指标是否回落。"
        )
        return Decision("final", text=answer)


# ---------------------------------------------------------------- 真 LLM
class OpenAICompatLLM:
    """任何 OpenAI 兼容端点（DeepSeek / 通义 / vLLM / Ollama）。

    注意：本机无 API key，未做端到端验证；W3 接入时请先跑一句 hello 验证连通性。
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str = "deepseek-chat") -> None:
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model
        if not self.api_key:
            raise RuntimeError("缺少 LLM_API_KEY（或改用 OraclePlanner 离线跑）")
        self.last_usage: dict | None = None
        self.dropped_parallel_calls = 0

    @staticmethod
    def _json_schema(spec: Any) -> dict:
        """把 ToolSpec.params 转成标准 JSON Schema —— 这是模型能正确调工具的前提。"""
        props: dict[str, dict] = {}
        required: list[str] = []
        for name, rule in spec.params.items():
            prop: dict[str, Any] = {"type": rule.get("type", "string")}
            if rule.get("enum"):
                prop["enum"] = list(rule["enum"])
            if rule.get("description"):
                prop["description"] = rule["description"]
            props[name] = prop
            if rule.get("required"):
                required.append(name)
        schema: dict[str, Any] = {"type": "object", "properties": props,
                                  "additionalProperties": False}
        if required:
            schema["required"] = required
        return schema

    @staticmethod
    def to_api_messages(messages: list[dict]) -> list[dict]:
        """把内部上下文转成 OpenAI 兼容格式。

        两个必踩的坑：
        1) 内部用 {"role":"tool","name":..,"content":..} 存工具结果，但 OpenAI 的
           tool 消息必须紧跟 assistant 的 tool_calls 并带 tool_call_id。我们不走
           原生 tool 通道，改成「观测」user 消息，任何兼容接口都能吃。
        2) system 只能出现在首条，出现在中间会被 422 拒绝 —— 非首位的 system 降级为 user。
        """
        out: list[dict] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content") or ""
            if role == "tool":
                name = m.get("name", "tool")
                out.append({"role": "user",
                            "content": f'<observation tool="{name}">\n{content}\n</observation>'})
            elif role == "system" and out:
                out.append({"role": "user", "content": content})
            else:
                out.append({"role": role, "content": content})
        if not out:
            out = [{"role": "user", "content": ""}]
        return out

    def decide(self, messages: list[dict], tool_block: str,
               specs: list[Any] | None = None, force_text: bool = False) -> Decision:
        if not specs:
            raise ValueError(
                "OpenAICompatLLM 需要 registry.specs()："
                "缺了它模型拿不到参数名/类型/enum，只会瞎猜参数"
            )
        tools = [{
            "type": "function",
            "function": {"name": s.name,
                         "description": s.description,
                         "parameters": self._json_schema(s)},
        } for s in specs]

        api_messages = self.to_api_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "temperature": 0,
        }
        if force_text:
            # 强制收敛：不给工具，逼模型基于现有信息直接给结论
            payload["tool_choice"] = "none"
        else:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode()
        if os.getenv("OPS_DEBUG_LLM"):
            print(f"[debug] POST {self.base_url}/chat/completions "
                  f"msgs={len(api_messages)} bytes={len(body)}")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        last_err: Exception | None = None
        for attempt in range(2):                       # 简单重试：仅对网络/5xx
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:         # 4xx/5xx：把响应体贴出来，否则没法排查
                body_txt = ""
                try:
                    body_txt = e.read().decode("utf-8", "replace")[:600]
                except Exception:                      # noqa: BLE001 - 读不到就算了
                    pass
                msg = f"LLM API {e.code} {e.reason}: {body_txt}"
                if e.code < 500:
                    raise RuntimeError(msg) from e      # 4xx 重试没用，直接抛
                last_err = RuntimeError(msg)
            except Exception as e:                     # noqa: BLE001 - 需要区分后决定是否重试
                last_err = e
                if attempt == 0:
                    time.sleep(1.5)
                    continue
                raise
        else:
            raise last_err  # pragma: no cover

        self.last_usage = data.get("usage")
        msg = data["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if len(calls) > 1:
            # 已知限制：当前只执行第一个并行调用，其余计数丢弃（TODO: D5 支持多调用合并）
            self.dropped_parallel_calls += len(calls) - 1
        if calls:
            fn = calls[0]["function"]
            try:
                args: Any = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            return Decision("tool", fn.get("name", ""), args, msg.get("content") or "")
        return Decision("final", text=msg.get("content") or "")
