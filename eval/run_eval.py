"""离线评测：注入故障 → 跑 Agent → 算指标 → 出报告。

用法:
    python -m eval.run_eval                 # 跑全部场景
    python -m eval.run_eval --only easy     # 只跑某个难度
    python -m eval.run_eval --planner oracle # 默认；填 llm 走真实模型

设计说明（面试要能讲）：
    1. 每个场景独立注入故障到临时目录，互不污染 → 可复现
    2. 指标分三层：工具层(ToolSuccess) / 任务层(TaskSuccess) / 成本层(tokens, latency)
    3. 拒答场景单独统计（RefusalAccuracy），因为"答错"和"该拒答却乱答"是两类错误
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.core.llm import OraclePlanner  # noqa: E402
from agent.core.loop import run  # noqa: E402
from agent.tools import build_registry  # noqa: E402
from sim.target import inject  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(HERE, "scenarios.json")
REFUSAL_MARKERS = ("无法定位", "未发现", "无法确定", "无法判断")


def load_scenarios(only: str | None = None) -> list[dict]:
    with open(SCENARIOS, encoding="utf-8") as f:
        data = json.load(f)
    if only:
        data = [s for s in data if s["difficulty"] == only]
    return data


def evaluate_one(sc: dict) -> dict:
    """每个场景用独立临时目录注入故障，跑完立即清理，避免在仓库留下残留目录。"""
    tmp = tempfile.mkdtemp(prefix="opscop-")
    try:
        return _evaluate(sc, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _evaluate(sc: dict, tmp: str) -> dict:
    inject(sc["fault"], out_dir=tmp, minutes=15, seed=hash(sc["id"]) % 1000, clean=True)
    os.environ["OPS_DATA_DIR"] = tmp

    registry = build_registry()
    planner = OraclePlanner()

    started = time.time()
    traj = run(sc["task"], registry, planner, max_steps=sc.get("max_steps", 6))
    latency_ms = (time.time() - started) * 1000

    exp = sc["expect"]
    answer = traj.answer or ""
    refused = any(m in answer for m in REFUSAL_MARKERS)
    root_hit = any(k.lower() in answer.lower() for k in exp.get("root_cause_any", [])) \
        if exp.get("root_cause_any") else False
    tools_ok = all(t in traj.tools_used for t in exp.get("tools", []))

    if exp.get("must_refuse"):
        success = refused and traj.terminator == "final"
    else:
        success = (root_hit and tools_ok and traj.terminator == "final" and not refused)

    tool_calls = len(registry.call_log)
    tool_ok = sum(1 for c in registry.call_log if c.get("ok"))

    return {
        "id": sc["id"], "difficulty": sc["difficulty"], "fault": sc["fault"],
        "terminator": traj.terminator, "steps": traj.steps,
        "tokens": traj.tokens, "latency_ms": round(latency_ms),
        "root_hit": root_hit, "tools_ok": tools_ok,
        "refused": refused, "must_refuse": bool(exp.get("must_refuse")),
        "success": success,
        "tool_calls": tool_calls, "tool_ok_calls": tool_ok,
        "answer": answer[:160].replace("\n", " "),
    }


def summarize(results: list[dict]) -> dict:
    n = len(results)
    lat = sorted(r["latency_ms"] for r in results)
    live = [r for r in results if not r["must_refuse"]]
    refu = [r for r in results if r["must_refuse"]]
    calls = sum(r["tool_calls"] for r in results)
    ok_calls = sum(r["tool_ok_calls"] for r in results)

    def rate(sub, key):
        return round(100 * sum(1 for r in sub if r[key]) / len(sub), 1) if sub else 0.0

    return {
        "n": n,
        "n_task": len(live),
        "n_refuse": len(refu),
        "task_success_rate": rate(results, "success"),
        "root_cause_hit_rate": rate(live, "root_hit"),
        # 没有拒答场景时不能报 0.0 —— 那会被误读成"拒答全错"
        "refusal_accuracy": rate(refu, "refused") if refu else None,
        "tool_success_rate": round(100 * ok_calls / calls, 1) if calls else 0.0,
        "avg_steps": round(statistics.mean(r["steps"] for r in results), 2),
        "avg_tokens": round(statistics.mean(r["tokens"] for r in results)),
        "p95_latency_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
        "abnormal_termination": sum(1 for r in results if r["terminator"] != "final"),
    }


def render_table(results: list[dict]) -> str:
    head = f"{'ID':5s} {'难度':9s} {'终止':10s} {'步数':4s} {'根因':4s} {'拒答':4s} {'成功':4s}"
    lines = [head, "-" * len(head)]
    for r in results:
        lines.append(
            f"{r['id']:5s} {r['difficulty']:9s} {r['terminator']:10s} {r['steps']:<4d} "
            f"{'Y' if r['root_hit'] else '-':4s} {'Y' if r['refused'] else '-':4s} "
            f"{'PASS' if r['success'] else 'FAIL':4s}"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="easy|medium|hard|misdirect")
    ap.add_argument("--planner", default="oracle", choices=["oracle", "llm"])
    ap.add_argument("--out", default=os.path.join(HERE, "eval_report.md"))
    args = ap.parse_args()

    if args.planner == "oracle":
        print("=" * 72)
        print("[重要] 当前使用 OraclePlanner —— 启发式基线，只用于验证")
        print("       靶场 / 工具 / 评测链路是否正常，**不代表模型能力**。")
        print("       简历里的数字必须来自真实模型：设置 LLM_API_KEY 后加 --planner llm。")
        print("=" * 72 + "\n")

    scenarios = load_scenarios(args.only)
    print(f"running {len(scenarios)} scenarios ...\n")
    results = [evaluate_one(sc) for sc in scenarios]
    summary = summarize(results)

    print(render_table(results))
    print("\n=== 汇总 ===")
    for k, v in summary.items():
        print(f"  {k:24s} {'N/A' if v is None else v}")

    with open(args.out, "w", encoding="utf-8") as f:
        model = os.getenv("LLM_MODEL", "deepseek-chat") if args.planner == "llm" else "n/a"
        subset = args.only or "all"
        fp = hashlib.sha1(open(SCENARIOS, "rb").read()).hexdigest()[:8]
        f.write("# Agent 离线评测报告\n\n")
        f.write(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}｜场景数：{summary['n']}"
                f"｜子集：**{subset}**｜规划器：**{args.planner}**（model: {model}）"
                f"｜场景集指纹：`{fp}`\n\n")
        if args.planner == "oracle":
            f.write("> ⚠️ **本报告由 OraclePlanner（启发式基线）生成**，用于验证靶场与评测链路，"
                    "不代表模型能力。对外引用/写简历前必须用真实模型重跑"
                    "（`python -m eval.run_eval --planner llm`）。\n\n")
        f.write("## 汇总指标\n\n| 指标 | 值 |\n|---|---|\n")
        for k, v in summary.items():
            f.write(f"| {k} | {'N/A' if v is None else v} |\n")
        f.write("\n## 逐条结果\n\n```\n")
        f.write(render_table(results))
        f.write("\n```\n\n## 失败案例\n\n")
        fails = [r for r in results if not r["success"]]
        if not fails:
            f.write("无\n")
        for r in fails:
            f.write(f"- **{r['id']}** ({r['difficulty']}, {r['fault']}) "
                    f"terminator={r['terminator']} root_hit={r['root_hit']} refused={r['refused']}\n")
            f.write(f"  - answer: `{r['answer']}`\n")
    print(f"\nreport -> {args.out}")


if __name__ == "__main__":
    main()
