"""工具：Runbook 知识库检索（BM25，纯标准库）。

不用向量库的理由（面试要能自圆其说）：
    1) 排障知识库只有几十篇文档，BM25 的关键词命中（错误类名/异常名）比
       语义检索更准——"HikariPool" 这种标识符向量化会丢精度。
    2) 零依赖、可复现、可离线跑评测。
    向量检索留到文档数 >500 或用户用自然语言提问时再上，届时用 RRF 融合。
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter


def _kb_dir() -> str:
    return os.getenv("OPS_KB_DIR", os.path.join("agent", "data", "runbook"))

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.]{1,}|[\u4e00-\u9fff]{2,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _load_docs() -> list[dict]:
    kb_dir = _kb_dir()
    if not os.path.isdir(kb_dir):
        raise FileNotFoundError(f"kb dir not found: {kb_dir}")
    docs = []
    for fn in sorted(os.listdir(kb_dir)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(kb_dir, fn), encoding="utf-8") as f:
            text = f.read()
        title = next((line.lstrip("# ").strip() for line in text.splitlines()
                      if line.startswith("#")), fn)
        docs.append({"id": fn, "title": title, "text": text,
                     "tokens": _tokenize(text)})
    return docs


def search_kb(query: str, top_k: int = 3) -> str:
    docs = _load_docs()
    if not docs:
        return json.dumps({"query": query, "hits": []}, ensure_ascii=False)

    q = _tokenize(query)
    if not q:
        return json.dumps({"query": query, "hits": [],
                           "note": "query 无有效关键词"}, ensure_ascii=False)

    # BM25
    k1, b = 1.5, 0.75
    avg_len = sum(len(d["tokens"]) for d in docs) / len(docs)
    df = Counter()
    for d in docs:
        for t in set(d["tokens"]):
            df[t] += 1
    n = len(docs)

    scored = []
    for d in docs:
        tf = Counter(d["tokens"])
        score = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            denom = tf[t] + k1 * (1 - b + b * len(d["tokens"]) / avg_len)
            score += idf * tf[t] * (k1 + 1) / denom
        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: -x[0])
    hits = []
    for score, d in scored[:top_k]:
        body = " ".join(line.strip() for line in d["text"].splitlines()
                        if line.strip())[:220]
        hits.append({"doc": d["id"], "title": d["title"],
                     "score": round(score, 3), "snippet": body})
    return json.dumps({"query": query, "hits": hits,
                       "note": "hits 为空说明知识库没有对应 runbook，应回答无法定位"},
                      ensure_ascii=False, indent=1)
