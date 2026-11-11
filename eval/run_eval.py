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
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.core.llm import OpenAICompatLLM, OraclePlanner  # noqa: E402
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


def score_scenario(*, answer: str, exp: dict, terminator: str,
                   tools_used: list[str]) -> dict:
    """统一判分。

    任务组：根因关键词命中 + 必需工具都调过 + 正常收敛 + 不是"纯拒答"。
    拒答组(misdirect)：不能凭空点名真实根因（forbidden_root_cause）；
        只说"该服务自身没有证据、建议看上游"是正确表现。

    为什么不再用"出现某个词就判拒答"：真实模型常写"目前无法确定具体对象，但根因是
    Full GC"——既是正确结论又含"无法确定"，旧逻辑会把正确答案判成拒答（S16/S17 就
    是这么被冤枉的）。
    """
    low = answer.lower()
    if exp.get("must_refuse"):
        leaked = [k for k in exp.get("forbidden_root_cause", []) if k.lower() in low]
        restrained = not leaked
        return {"success": restrained and terminator == "final",
                "root_hit": False, "tools_ok": True,
                "restrained": restrained, "leaked": leaked}

    root_hit = any(k.lower() in low for k in exp.get("root_cause_any", []))
    tools_ok = all(t in tools_used for t in exp.get("tools", []))
    pure_refusal = len(answer) < 200 and any(m in answer for m in REFUSAL_MARKERS)
    success = root_hit and tools_ok and terminator == "final" and not pure_refusal
    return {"success": success, "root_hit": root_hit, "tools_ok": tools_ok,
            "restrained": pure_refusal, "leaked": []}


def evaluate_one(sc: dict, planner: Any) -> dict:
    """每个场景用独立临时目录注入故障，跑完立即清理，避免在仓库留下残留目录。"""
    tmp = tempfile.mkdtemp(prefix="opscop-")
    try:
        return _evaluate(sc, tmp, planner)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _evaluate(sc: dict, tmp: str, planner: Any) -> dict:
    # 固定种子：必须可复现（不能用 hash(str)，Python 字符串 hash 每进程带随机盐）
    seed = int("".join(ch for ch in sc["id"] if ch.isdigit()) or 0)
    inject(sc["fault"], out_dir=tmp, minutes=15, seed=seed, clean=True)
    os.environ["OPS_DATA_DIR"] = tmp

    registry = build_registry()

    started = time.time()
    traj = run(sc["task"], registry, planner, max_steps=sc.get("max_steps", 6))
    latency_ms = (time.time() - started) * 1000

    exp = sc["expect"]
    answer = traj.answer or ""
    scored = score_scenario(answer=answer, exp=exp,
                            terminator=traj.terminator, tools_used=traj.tools_used)

    tool_calls = len(registry.call_log)
    tool_ok = sum(1 for c in registry.call_log if c.get("ok"))

    return {
        "id": sc["id"], "difficulty": sc["difficulty"], "fault": sc["fault"],
        "terminator": traj.terminator, "steps": traj.steps,
        "tokens": traj.tokens, "latency_ms": round(latency_ms),
        "root_hit": scored["root_hit"], "tools_ok": scored["tools_ok"],
        "refused": scored["restrained"], "leaked": scored["leaked"],
        "must_refuse": bool(exp.get("must_refuse")),
        "success": scored["success"],
        "tool_calls": tool_calls, "tool_ok_calls": tool_ok,
        "answer": answer[:160].replace("\n", " "),
        "answer_full": answer,
        "call_log": registry.call_log,
        "task": sc["task"],
        "expect": exp,
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
        # 分母必须是任务组（n_task）—— 拒答场景不该算进"任务成功"
        "task_success_rate": rate(live, "success") if live else None,
        "root_cause_hit_rate": rate(live, "root_hit") if live else None,
        # 拒答组两个口径必须分开：
        #   no_fabrication_rate = 没有凭空点名真实根因（克制）
        #   refusal_accuracy    = 克制 + 正常收敛（完整通过）
        "refusal_accuracy": rate(refu, "success") if refu else None,
        "no_fabrication_rate": rate(refu, "refused") if refu else None,
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
    ap.add_argument("--trace", default=None,
                    help="把每条场景的完整轨迹(工具调用/参数/结果/完整回答)写进指定 JSONL 文件")
    ap.add_argument("--from-trace", default=None,
                    help="从已有 trace JSONL 重算指标，不重新调用模型")
    args = ap.parse_args()

    if args.planner == "oracle" and not args.from_trace:
        print("=" * 72)
        print("[重要] 当前使用 OraclePlanner —— 启发式基线，只用于验证")
        print("       靶场 / 工具 / 评测链路是否正常，**不代表模型能力**。")
        print("       简历里的数字必须来自真实模型：设置 LLM_API_KEY 后加 --planner llm。")
        print("=" * 72 + "\n")

    scenarios = load_scenarios(args.only)

    if args.from_trace:
        # 从已有轨迹重算指标（判分逻辑变更后不必重新烧钱跑模型）。
        # 注意：判分规则以当前 scenarios.json 为准，trace 只提供证据（回答/调用链/终止方式）。
        # 否则改了 scenarios.json 的 expect 也不会生效（trace 里存的是旧规则）。
        cur = {s["id"]: s for s in load_scenarios(None)}
        results = []
        with open(args.from_trace, encoding="utf-8") as tf:
            for line in tf:
                if not line.strip():
                    continue
                r = json.loads(line)
                latest = cur.get(r.get("id", ""))
                if latest:
                    r["expect"] = latest["expect"]
                    r["difficulty"] = latest["difficulty"]
                    r["fault"] = latest["fault"]
                    r["max_steps"] = latest.get("max_steps", r.get("max_steps"))
                tools_used = [c.get("tool") for c in r.get("call_log", [])]
                s = score_scenario(answer=r.get("answer_full", ""), exp=r.get("expect", {}),
                                   terminator=r.get("terminator", ""), tools_used=tools_used)
                r.update({"success": s["success"], "root_hit": s["root_hit"],
                          "tools_ok": s["tools_ok"], "refused": s["restrained"],
                          "leaked": s["leaked"]})
                results.append(r)
        actual_planner = f"recomputed-from-trace({os.path.basename(args.from_trace)})"
        model_name = "n/a"
        print(f"recomputed {len(results)} results from {args.from_trace}")
        print("(scoring rules taken from eval/scenarios.json)\n")
    else:
        # 真正决定用哪个 planner（此前这里硬编码 Oracle，导致 --planner llm 名不副实）
        if args.planner == "llm":
            planner: Any = OpenAICompatLLM(model=os.getenv("LLM_MODEL", "deepseek-chat"))
            print(f"planner = {type(planner).__name__}({planner.model}) @ {planner.base_url}\n")
        else:
            planner = OraclePlanner()
            print(f"planner = {type(planner).__name__}\n")

        print(f"running {len(scenarios)} scenarios ...\n")
        results = [evaluate_one(sc, planner) for sc in scenarios]
        actual_planner = type(planner).__name__
        model_name = getattr(planner, "model", "n/a")

    summary = summarize(results)

    if args.trace:
        with open(args.trace, "w", encoding="utf-8") as tf:
            for r in results:
                tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"traces -> {args.trace}")

    print(render_table(results))
    print("\n=== 汇总 ===")
    for k, v in summary.items():
        print(f"  {k:24s} {'N/A' if v is None else v}")

    with open(args.out, "w", encoding="utf-8") as f:
        # 记录"实际用的 planner/来源"，而不是命令行参数
        actual = actual_planner
        model = model_name
        subset = args.only or "all"
        fp = hashlib.sha1(open(SCENARIOS, "rb").read()).hexdigest()[:8]
        f.write("# Agent 离线评测报告\n\n")
        f.write(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}｜场景数：{summary['n']}"
                f"｜子集：**{subset}**｜实际规划器：**{actual}**（model: {model}）"
                f"｜场景集指纹：`{fp}`\n\n")
        if actual == "OraclePlanner":
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
