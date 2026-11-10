"""Agent 主循环：手写 ReAct + 三层终止。

三层终止（面经原题"怎么保证一定停"的标准答案）：
    1. 硬截断：max_steps
    2. 重复检测：同工具同参数第二次出现就停
    3. 预算控制：token 超预算强制收敛
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from agent.core.context import ContextManager
from agent.core.llm import Planner
from agent.core.registry import ToolRegistry

SYSTEM_PROMPT = """你是一个 Java 微服务排障 Agent。
可用工具见下方清单，每次只能调用一个工具。
规则：
1. 先用 query_metrics 确认异常维度，再用 query_logs 定位错误签名。
2. 拿到错误签名后，用 search_kb 查处置手册。
3. 信息足够时直接给出根因与处置建议，不要为了调用而调用。
4. 工具报错时先修正参数，不要重复调用同一个失败工具。
"""


@dataclass
class Trajectory:
    ok: bool
    answer: str
    steps: int
    tools_used: list[str] = field(default_factory=list)
    terminator: str = "final"      # final | max_steps | duplicate | budget
    tokens: int = 0
    tool_errors: int = 0

    @property
    def dedup_tools(self) -> list[str]:
        seen, out = set(), []
        for t in self.tools_used:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out


def run(task: str, registry: ToolRegistry, planner: Planner,
        ctx: ContextManager | None = None, max_steps: int = 8,
        verbose: bool = False) -> Trajectory:
    ctx = ctx or ContextManager(system_prompt=SYSTEM_PROMPT)
    ctx.add_user(task)
    used: list[str] = []
    errors = 0
    seen: dict[tuple[str, str], int] = {}

    for step in range(1, max_steps + 1):
        # 第 3 层：预算控制
        if ctx.over_budget():
            return Trajectory(False, "上下文预算耗尽，强制收敛", step, used,
                              "budget", ctx.tokens(), errors)

        decision = planner.decide(ctx.render(), registry.prompt_block(), registry.specs())
        if verbose:
            print(f"  [step {step}] {decision.kind} {decision.tool} {decision.args}")

        if decision.kind == "final":
            return Trajectory(True, decision.text, step, used, "final",
                              ctx.tokens(), errors)

        # 第 2 层：重复动作检测（不执行重复调用；第一次重复先给模型一次改主意机会）
        key = (decision.tool, json.dumps(decision.args, sort_keys=True))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            ctx.add_user("该操作已执行过且没有新信息，请换一个工具或直接基于现有信息作答。")
            continue
        if seen[key] > 2:
            return Trajectory(False, "重复动作终止：同一工具同一参数连续被请求", step, used,
                              "duplicate", ctx.tokens(), errors)

        result = registry.invoke(decision.tool, decision.args)
        used.append(decision.tool)
        if not result.ok:
            errors += 1
        ctx.add_tool_result(decision.tool, result.render())

        # 关键实体写结构化记忆，避免被摘要吃掉
        if decision.tool == "query_logs" and result.ok:
            try:
                payload = json.loads(result.data if isinstance(result.data, str) else "{}")
                sigs = payload.get("top_signatures") or []
                if sigs:
                    ctx.remember("top_error_signature", sigs[0]["signature"])
            except Exception:
                pass

    # 第 1 层：硬截断
    return Trajectory(False, f"超过最大步数 {max_steps}", max_steps, used,
                      "max_steps", ctx.tokens(), errors)
