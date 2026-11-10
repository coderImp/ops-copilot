"""注入一个故障到本地数据目录，供 Agent 查询。

用法（二选一，等价）：
    python -m sim.inject pool_exhaust
    python sim/inject.py pool_exhaust
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from sim.target import FAULTS, inject
except ModuleNotFoundError:  # 允许 `python sim/inject.py` 直接运行
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sim.target import FAULTS, inject  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="注入故障到本地靶场")
    ap.add_argument("fault", choices=sorted(FAULTS), help="故障类型")
    ap.add_argument("--out", default="data", help="数据目录（默认 data）")
    ap.add_argument("--minutes", type=int, default=15, help="故障持续分钟数")
    ap.add_argument("--seed", type=int, default=7, help="随机种子，保证可复现")
    ap.add_argument("--no-clean", action="store_true", help="保留旧数据（默认先清空）")
    args = ap.parse_args()

    info = inject(args.fault, out_dir=args.out, minutes=args.minutes,
                  seed=args.seed, clean=not args.no_clean)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
