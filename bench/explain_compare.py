#!/usr/bin/env python3
"""只比执行计划，不测耗时：把三个实验的 plan 打印成对照表。

适合在 CI / PR 里跑（毫秒级完成），用来发现「索引被删了」「查询写法被改坏了」。

用法：
    python bench/explain_compare.py                # 用 data/lab.db
    python bench/explain_compare.py --db bench.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "lab.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_bench import INDEXES, SQL_E1, SQL_E2, SQL_E3_LIVE  # noqa: E402


def plan(conn: sqlite3.Connection, sql: str) -> list[str]:
    return [str(row[-1]) for row in conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()]


CASES = [
    ("实验 1 · 时间过滤", SQL_E1, "idx_orders_paid_at"),
    ("实验 2 · 相关子查询", SQL_E2, "idx_items_order_id"),
    ("实验 3 · 看板聚合", SQL_E3_LIVE, "idx_orders_paid_at"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="对照三个实验的执行计划")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"找不到 {db}，先跑 python bench/gen_data.py")

    conn = sqlite3.connect(db)
    for title, sql, index_name in CASES:
        print(f"\n{title}")
        conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        before = plan(conn, sql)
        conn.execute(INDEXES[index_name])
        after = plan(conn, sql)
        print("  无索引：")
        for line in before:
            print(f"    {line}")
        print("  有索引：")
        for line in after:
            print(f"    {line}")
        print("  ✓ 计划已改变" if before != after else "  ✗ 计划未变化（索引没被用上）")
    conn.close()


if __name__ == "__main__":
    main()
