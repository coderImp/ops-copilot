"""工具：时序指标查询。

结构化通道（对应方案里的"双通道"设计）：
    指标走 SQL 精确聚合，日志走 RAG/签名聚合。
    用户问"错误率多少"必须给数字，不能让模型从日志里"感觉"。
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta

def _data_dir() -> str:
    return os.getenv("OPS_DATA_DIR", "data")


def _connect() -> sqlite3.Connection:
    path = os.path.join(_data_dir(), "metrics.db")
    if not os.path.exists(path):
        raise FileNotFoundError(f"metrics db not found: {path}")
    return sqlite3.connect(path)


def query_metrics(service: str, metric: str = "all", window_minutes: int = 15) -> str:
    cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat(timespec="seconds")
    conn = _connect()
    try:
        if metric == "all":
            rows = conn.execute(
                "SELECT metric, ts, value FROM metrics WHERE service=? AND ts>=? ORDER BY metric, ts",
                (service, cutoff),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT metric, ts, value FROM metrics WHERE service=? AND metric=? AND ts>=? "
                "ORDER BY ts",
                (service, metric, cutoff),
            ).fetchall()
    finally:
        conn.close()

    series: dict[str, list[float]] = {}
    stamps: dict[str, list[str]] = {}
    for m, ts, v in rows:
        series.setdefault(m, []).append(float(v))
        stamps.setdefault(m, []).append(ts)

    summary = []
    anomalies = []
    for m, vals in series.items():
        if not vals:
            continue
        head = vals[: max(1, len(vals) // 5)]      # 前 20% 当基线
        base = sum(head) / len(head)
        peak = max(vals)
        latest = vals[-1]
        # 基线为 0 时不能用比值（会得到 Infinity 假异常），改用绝对阈值
        if base <= 1e-9:
            ratio = None
            is_anomaly = peak > 0
        else:
            ratio = round(peak / base, 2)
            is_anomaly = ratio >= 1.8
        summary.append({
            "metric": m,
            "baseline_avg": round(base, 3),
            "peak": round(peak, 3),
            "latest": round(latest, 3),
            "peak_over_baseline": ratio,
            "trend": "rising" if latest > base * 1.2 else "flat",
        })
        if is_anomaly:
            anomalies.append({"metric": m, "peak_over_baseline": ratio,
                              "baseline": round(base, 3), "peak": round(peak, 3)})

    anomalies.sort(key=lambda x: -(x["peak_over_baseline"] or 999))

    return json.dumps({
        "service": service,
        "window_minutes": window_minutes,
        "metrics": summary,
        "anomalies": anomalies,
        "note": "anomalies 为空说明该服务指标未异常，应换服务或换指标",
    }, ensure_ascii=False, indent=1)
