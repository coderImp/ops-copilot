"""工具：错误日志聚合查询。

输出的价值不在"原始日志"，而在**归一化后的错误签名 + 计数**：
    3 万行日志里可能只有 5 种签名，模型需要的是这 5 种，不是 3 万行。
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta

def _data_dir() -> str:
    return os.getenv("OPS_DATA_DIR", "data")

_HEX = re.compile(r"\b[0-9a-f]{8,}\b")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_NUM = re.compile(r"\d+(\.\d+)?")        # 注意：不加 \b，"31850ms" 也能被替换
_QUOTED = re.compile(r"\"[^\"]*\"")


def normalize(msg: str) -> str:
    """把动态部分抹掉，得到可聚合的签名。

    面试点：为什么不能直接用原文聚合？因为 traceId/行号/耗时都不相同，
    原文一行一个签名，聚合结果永远是 count=1，模型会被噪声淹没。
    """
    s = _UUID.sub("<uuid>", msg)
    s = _HEX.sub("<hex>", s)
    s = _QUOTED.sub('"<v>"', s)
    s = _NUM.sub("<n>", s)
    return s.strip()[:200]


def query_logs(service: str, level: str = "", since_minutes: int = 15,
               keyword: str = "", limit: int = 50) -> str:
    path = os.path.join(_data_dir(), "logs", f"{service}.log")
    if not os.path.exists(path):
        raise FileNotFoundError(f"log file not found: {path}")

    cutoff = datetime.now() - timedelta(minutes=since_minutes)
    groups: Counter[str] = Counter()
    samples: dict[str, dict] = {}
    total = 0
    matched = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = datetime.fromisoformat(rec["ts"])
            except (KeyError, ValueError):
                continue
            if ts < cutoff:
                continue
            if level and rec.get("level") != level:
                continue
            msg = rec.get("msg") or ""
            if keyword and keyword.lower() not in msg.lower():
                continue
            matched += 1
            sig = normalize(msg)
            groups[sig] += 1
            samples.setdefault(sig, rec)

    top = [{"signature": sig, "count": cnt,
            "sample": {"ts": samples[sig].get("ts"),
                       "logger": samples[sig].get("logger"),
                       "msg": (samples[sig].get("msg") or "")[:160]}}
           for sig, cnt in groups.most_common(3)]

    return json.dumps({
        "service": service,
        "window_minutes": since_minutes,
        "level_filter": level or "ANY",
        "total_lines": total,
        "matched_lines": matched,
        "distinct_signatures": len(groups),
        "top_signatures": top,
        "note": "按归一化签名聚合，count 越大越可能是主因" if top else "窗口内无匹配日志",
    }, ensure_ascii=False, indent=1)
