"""靶场：Python 版故障模拟器。

为什么不用 Docker + Spring Boot：
    本机无 Docker/JDK。但"排障"需要的是**真实的故障现象**——真实格式的
    JSON 日志 + 时序指标 + 噪声日志，而不是真实进程。用模拟器可以：
      1) 零依赖开箱即跑（你换台电脑也能继续）
      2) 故障可复现、可回放、可批量跑评测（这恰恰是评测最需要的）
    W6 再把 Java 服务换成真的（见 docs/java-layer.md），日志/指标格式保持不变，
    Agent 侧一行代码都不用改——这就是"适配器"设计的价值。
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import time
import uuid
from datetime import datetime, timedelta

SERVICES = ("gateway", "order-service", "user-service")

# 每个故障：注入后服务会表现成什么样
FAULTS: dict[str, dict] = {
    "pool_exhaust": {
        "service": "order-service",
        "metric_spike": {"pool_active": (17, 20), "error_rate": (0.02, 0.31),
                         "p99_latency_ms": (130, 3200)},
        "level": "ERROR",
        "logger": "com.zaxxer.hikari.HikariPool",
        "msg": "HikariPool-1 - Connection is not available, request timed out after "
               "30000ms (total=20, active=20, idle=0, waiting={waiting})",
        "root": "连接池耗尽",
    },
    "slow_sql": {
        "service": "order-service",
        "metric_spike": {"p99_latency_ms": (130, 4820), "error_rate": (0.02, 0.08),
                         "db_slow_query_count": (0, 37)},
        "level": "WARN",
        "logger": "com.demo.mapper.OrderMapper.selectByUserId",
        "msg": "SlowQuery elapsed={elapsed}ms sql=SELECT * FROM t_order WHERE user_id = ? "
               "rows={rows} (no index on user_id)",
        "root": "慢查询",
    },
    "npe": {
        "service": "order-service",
        "metric_spike": {"error_rate": (0.02, 0.22), "http_5xx_rate": (0.01, 0.19)},
        "level": "ERROR",
        "logger": "com.demo.service.OrderService.calc",
        "msg": "NullPointerException: Cannot invoke \"BigDecimal.multiply(BigDecimal)\" "
               "because \"unitPrice\" is null at OrderService.calc(OrderService.java:{line})",
        "root": "空指针",
    },
    "cascade_timeout": {
        "service": "gateway",
        "metric_spike": {"p99_latency_ms": (90, 5100), "error_rate": (0.01, 0.27),
                         "http_5xx_rate": (0.01, 0.24)},
        "level": "ERROR",
        "logger": "com.demo.gateway.ProxyFilter",
        "msg": "FeignTimeout calling user-service /api/user/{id}: read timed out after "
               "{elapsed}ms (retry {retry}/3)",
        "root": "下游服务超时",
    },
    "redis_down": {
        "service": "order-service",
        "metric_spike": {"redis_hit_rate": (0.93, 0.02), "error_rate": (0.02, 0.18),
                         "p99_latency_ms": (130, 1800)},
        "level": "ERROR",
        "logger": "org.springframework.data.redis.RedisConnectionFailureException",
        "msg": "RedisConnectionFailureException: Unable to connect to Redis; "
               "nested exception is java.net.ConnectException: Connection refused",
        "root": "Redis 不可用",
    },
    "gc_pause": {
        "service": "order-service",
        "metric_spike": {"gc_pause_ms": (30, 2100), "p99_latency_ms": (130, 2600)},
        "level": "WARN",
        "logger": "gc.log",
        "msg": "Full GC (Allocation Failure) {pause}ms, heap 3.8G->3.7G (4G), "
               "young 1.1G->0.2G",
        "root": "GC 停顿",
    },
}

NOISE = [
    ("INFO", "com.demo.filter.AccessLog", "GET /api/order/list status=200 cost={cost}ms"),
    ("INFO", "com.demo.service.StockService", "stock check ok sku={sku} qty={qty}"),
    ("WARN", "com.demo.http.HttpClient", "retryable GET /api/price sku={sku} attempt=1"),
    ("DEBUG", "com.demo.cache.LocalCache", "cache miss key=price:{sku}"),
]


def _path(out_dir: str, *parts: str) -> str:
    p = os.path.join(out_dir, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def reset(out_dir: str = "data") -> None:
    for svc in SERVICES:
        open(_path(out_dir, "logs", f"{svc}.log"), "w", encoding="utf-8").close()
    db = _path(out_dir, "metrics.db")
    if os.path.exists(db):
        os.remove(db)
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS metrics(
        ts TEXT, service TEXT, metric TEXT, value REAL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_m ON metrics(service, metric, ts)")
    conn.commit()
    conn.close()


def _write_logs(out_dir: str, fault: dict, service: str, minutes: int,
                started: datetime, rng: random.Random) -> None:
    lines: list[dict] = []
    # 真实故障：按分钟铺开，数量随机
    for i in range(minutes):
        ts = started + timedelta(minutes=i)
        for _ in range(rng.randint(1, 4)):
            params = {
                "waiting": rng.randint(12, 19),
                "elapsed": rng.randint(29000, 33000),
                "rows": rng.randint(8000, 40000),
                "line": rng.choice([88, 91, 120]),
                "retry": rng.randint(1, 3),
                "pause": rng.randint(1500, 2400),
                "id": rng.randint(100000, 999999),
                "cost": rng.randint(8, 120),
                "sku": rng.randint(1000, 9999),
                "qty": rng.randint(1, 5),
            }
            msg = fault["msg"].format(**params)
            lines.append({
                "ts": (ts + timedelta(seconds=rng.randint(0, 59))).isoformat(timespec="milliseconds"),
                "service": service, "level": fault["level"],
                "logger": fault["logger"], "msg": msg,
                "trace_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16],
                "thread": f"http-nio-8080-exec-{rng.randint(1, 20)}",
            })
    # 噪声日志：让"过滤"成为必要动作
    for i in range(minutes * 3):
        ts = started + timedelta(minutes=rng.randint(0, minutes - 1))
        lvl, logger, msg = rng.choice(NOISE)
        lines.append({
            "ts": (ts + timedelta(seconds=rng.randint(0, 59))).isoformat(timespec="milliseconds"),
            "service": service, "level": lvl, "logger": logger,
            "msg": msg.format(cost=rng.randint(8, 120), sku=rng.randint(1000, 9999),
                              qty=rng.randint(1, 5)),
            "trace_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16],
            "thread": f"http-nio-8080-exec-{rng.randint(1, 20)}",
        })
    lines.sort(key=lambda x: x["ts"])
    path = _path(out_dir, "logs", f"{service}.log")
    with open(path, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")


def _write_metrics(out_dir: str, fault: dict, service: str, minutes: int,
                   started: datetime, rng: random.Random) -> None:
    spike = fault["metric_spike"]
    base = {"error_rate": 0.02, "p99_latency_ms": 130, "http_5xx_rate": 0.01,
            "pool_active": 4, "redis_hit_rate": 0.93, "gc_pause_ms": 30,
            "db_slow_query_count": 0, "qps": 120}
    rows = []
    for i in range(minutes):
        ts = (started + timedelta(minutes=i)).isoformat(timespec="seconds")
        for metric, (lo, hi) in spike.items():
            t = i / max(minutes - 1, 1)
            val = lo + (hi - lo) * t
            val *= (1 + rng.uniform(-0.12, 0.12))
            rows.append((ts, service, metric, round(val, 3)))
        for metric, v in base.items():
            if metric in spike:
                continue
            rows.append((ts, service, metric, round(v * (1 + rng.uniform(-0.15, 0.15)), 3)))
    conn = sqlite3.connect(_path(out_dir, "metrics.db"))
    conn.executemany("INSERT INTO metrics(ts,service,metric,value) VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()


def inject(fault_name: str, out_dir: str = "data", minutes: int = 15,
           seed: int = 7, clean: bool = True) -> dict:
    if fault_name not in FAULTS:
        raise KeyError(f"unknown fault: {fault_name}. choose from {list(FAULTS)}")
    if clean:
        reset(out_dir)
    rng = random.Random(seed)
    fault = FAULTS[fault_name]
    service = fault["service"]
    started = datetime.now() - timedelta(minutes=minutes)
    _write_logs(out_dir, fault, service, minutes, started, rng)
    _write_metrics(out_dir, fault, service, minutes, started, rng)
    return {"fault": fault_name, "service": service,
            "root": fault["root"], "window_minutes": minutes,
            "since": started.isoformat(timespec="seconds")}


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "pool_exhaust"
    info = inject(name)
    print(json.dumps(info, ensure_ascii=False, indent=2))
