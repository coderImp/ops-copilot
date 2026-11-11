"""回归测试：--planner llm 必须真的切到真实模型（曾经的 bug：硬编码 Oracle）。"""
from __future__ import annotations

import sys

import pytest

from eval import run_eval


def test_planner_oracle_is_default(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["run_eval", "--only", "easy", "--out", str(tmp_path / "r.md")])
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    # Oracle 不需要 API key，应能正常跑完
    run_eval.main()
    report = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "实际规划器：**OraclePlanner**" in report


def test_planner_llm_requires_api_key(monkeypatch, tmp_path):
    """没有 key 时必须直接报错，而不是悄悄退回 Oracle。"""
    monkeypatch.setattr(sys, "argv", ["run_eval", "--only", "easy",
                                      "--planner", "llm", "--out", str(tmp_path / "r.md")])
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        run_eval.main()
