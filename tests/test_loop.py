"""主循环：三层终止机制。"""
from __future__ import annotations

from agent.core.llm import Decision
from agent.core.loop import run
from agent.core.registry import ToolRegistry, ToolSpec


class ScriptedPlanner:
    """按剧本吐决策，用于确定性地测试循环控制。"""

    def __init__(self, decisions):
        self._d = list(decisions)
        self._i = 0

    def decide(self, messages, tool_block, specs=None):
        d = self._d[min(self._i, len(self._d) - 1)]
        self._i += 1
        return d


def _reg() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolSpec(name="probe", description="probe",
                 params={"n": {"type": "integer", "required": True}}),
        lambda n: f"probe-{n}",
    )
    return reg


def test_final_on_first_step():
    traj = run("t", _reg(), ScriptedPlanner([Decision("final", text="done")]))
    assert traj.ok and traj.terminator == "final" and traj.steps == 1


def test_duplicate_action_terminates():
    d = Decision("tool", "probe", {"n": 1})
    traj = run("t", _reg(), ScriptedPlanner([d, d, d]), max_steps=8)
    assert traj.terminator == "duplicate"
    assert not traj.ok


def test_max_steps_terminates():
    decisions = [Decision("tool", "probe", {"n": i}) for i in range(1, 10)]
    traj = run("t", _reg(), ScriptedPlanner(decisions), max_steps=3)
    assert traj.terminator == "max_steps"
    assert traj.steps == 3


def test_tool_error_is_counted_but_loop_continues():
    bad = Decision("tool", "probe", {})           # 缺参数 → invalid_args
    good = Decision("final", text="recovered")
    traj = run("t", _reg(), ScriptedPlanner([bad, good]))
    assert traj.terminator == "final"
    assert traj.tool_errors == 1


def test_tools_used_dedup():
    d1 = Decision("tool", "probe", {"n": 1})
    d2 = Decision("tool", "probe", {"n": 2})
    traj = run("t", _reg(), ScriptedPlanner([d1, d2, Decision("final", text="ok")]))
    assert traj.tools_used == ["probe", "probe"]
    assert traj.dedup_tools == ["probe"]
