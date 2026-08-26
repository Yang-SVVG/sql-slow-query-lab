#!/usr/bin/env python3
"""慢查询实验台：把「分钟级 → 秒级」拆成三个可复现的实验。

三个实验各自回答一个常见问题：
    实验 1  加了时间过滤还是慢？      —— 单表全表扫描 vs 索引范围查找
    实验 2  为什么加了 WHERE 也不管用？ —— 相关子查询把明细表扫了 N 遍
    实验 3  看板为什么每天都要重算？    —— 现算聚合 vs 预聚合表

每个变体重复 N 次取中位数，同时打印执行计划（plan），结果写入 results/benchmark.md。

用法：
    python bench/gen_data.py --orders 300000 --customers 40000   # 先备数据
    python bench/run_bench.py                                    # 跑全部实验
    python bench/run_bench.py --runs 5
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "lab.db"
RESULT_PATH = ROOT / "results" / "benchmark.md"

# 实验切片：3 天 + 一个区域，结果集小而固定，差异只来自执行方式
FROM_DAY, TO_DAY = "2025-06-01", "2025-06-04"
MONTH_FROM, MONTH_TO = "2025-07-01", "2026-01-01"
REGION = "华东"

SQL_E1 = f"""
SELECT COUNT(*), ROUND(SUM(pay_amount), 2)
FROM f_orders
WHERE paid_at >= '{FROM_DAY}' AND paid_at < '{TO_DAY}' AND status = 'paid'
"""

# 相关子查询：外表每命中一行，都要再扫一遍明细表找对应明细
SQL_E2 = f"""
SELECT o.order_id,
       ROUND(o.pay_amount, 2) AS amount,
       (SELECT ROUND(SUM(i.qty * i.unit_price), 2)
          FROM f_order_items i WHERE i.order_id = o.order_id) AS item_amount
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.paid_at >= '{FROM_DAY}' AND o.paid_at < '{TO_DAY}' AND c.region = '{REGION}'
"""

# 看板场景：按「月 × 区域」出半年报表
SQL_E3_LIVE = f"""
SELECT substr(o.paid_at, 1, 7) AS stat_month, c.region,
       COUNT(*) AS order_cnt, ROUND(SUM(o.pay_amount), 2) AS gmv
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.paid_at >= '{MONTH_FROM}' AND o.paid_at < '{MONTH_TO}' AND o.status = 'paid'
GROUP BY substr(o.paid_at, 1, 7), c.region
ORDER BY stat_month, gmv DESC
"""

SQL_E3_BUILD = """
DROP TABLE IF EXISTS dws_month_region;
CREATE TABLE dws_month_region AS
SELECT substr(o.paid_at, 1, 7) AS stat_month,
       c.region,
       COUNT(*)                    AS order_cnt,
       ROUND(SUM(o.pay_amount), 2) AS gmv
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.status = 'paid'
GROUP BY substr(o.paid_at, 1, 7), c.region;
CREATE UNIQUE INDEX idx_dws_month_region ON dws_month_region (stat_month, region);
"""

SQL_E3_PRE = """
SELECT stat_month, region, order_cnt, gmv
FROM dws_month_region
WHERE stat_month >= '2025-07' AND stat_month < '2026-01'
ORDER BY stat_month, gmv DESC
"""

INDEXES = {
    "idx_orders_paid_at": "CREATE INDEX idx_orders_paid_at ON f_orders (paid_at, status)",
    "idx_items_order_id": "CREATE INDEX idx_items_order_id ON f_order_items (order_id)",
}


@dataclass
class Result:
    label: str
    seconds: float
    rows: int
    plan: str
    note: str = ""


def plan_of(conn: sqlite3.Connection, sql: str) -> str:
    return " ｜ ".join(str(r[-1]) for r in conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall())


def timed(conn: sqlite3.Connection, sql: str, runs: int) -> tuple[float, int]:
    conn.execute("PRAGMA cache_size = -64000")
    samples: list[float] = []
    rows = 0
    for _ in range(runs):
        start = time.perf_counter()
        rows = len(conn.execute(sql).fetchall())
        samples.append(time.perf_counter() - start)
    return statistics.median(samples), rows


def fmt(sec: float) -> str:
    if sec < 0.001:
        return f"{sec * 1_000_000:.0f} µs"
    if sec < 1:
        return f"{sec * 1000:.1f} ms"
    if sec < 60:
        return f"{sec:.2f} s"
    return f"{sec / 60:.1f} min"


def main() -> None:
    parser = argparse.ArgumentParser(description="慢查询实验台")
    parser.add_argument("--runs", type=int, default=3, help="每个变体重复次数，取中位数")
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"找不到数据文件 {db_path}，先跑：python bench/gen_data.py")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA temp_store = MEMORY")
    orders, lo, hi = conn.execute(
        "SELECT COUNT(*), MIN(paid_at), MAX(paid_at) FROM f_orders"
    ).fetchone()
    items = conn.execute("SELECT COUNT(*) FROM f_order_items").fetchone()[0]
    print(f"数据规模：{orders:,} 订单 / {items:,} 明细 / {lo[:10]} → {hi[:10]}")
    print(f"实验切片：{FROM_DAY} ~ {TO_DAY} · 区域 {REGION}\n")

    results: dict[str, list[Result]] = {}

    # ---------- 实验 1：时间过滤 ----------
    for name in INDEXES:
        conn.execute(f"DROP INDEX IF EXISTS {name}")
    conn.commit()
    s, rows = timed(conn, SQL_E1, args.runs)
    results["E1"] = [Result("无索引 · 全表扫描", s, rows, plan_of(conn, SQL_E1))]
    conn.execute(INDEXES["idx_orders_paid_at"])
    conn.commit()
    f, _ = timed(conn, SQL_E1, args.runs)
    results["E1"].append(Result("有索引 · 范围查找", f, rows, plan_of(conn, SQL_E1)))

    # ---------- 实验 2：相关子查询 ----------
    conn.execute("DROP INDEX IF EXISTS idx_items_order_id")
    conn.commit()
    slow, rows2 = timed(conn, SQL_E2, args.runs)
    results["E2"] = [Result("相关子查询 · 明细无索引", slow, rows2, plan_of(conn, SQL_E2),
                            note="外表每行都 SCAN 一次明细表 → O(N×M)")]
    conn.execute(INDEXES["idx_items_order_id"])
    conn.commit()
    fast, _ = timed(conn, SQL_E2, args.runs)
    results["E2"].append(Result("相关子查询 · 明细有索引", fast, rows2, plan_of(conn, SQL_E2)))

    # ---------- 实验 3：预聚合 ----------
    live, rows3 = timed(conn, SQL_E3_LIVE, args.runs)
    results["E3"] = [Result("现算 · 扫明细再聚合", live, rows3, plan_of(conn, SQL_E3_LIVE))]
    start = time.perf_counter()
    conn.executescript(SQL_E3_BUILD)
    build_cost = time.perf_counter() - start
    pre, rows3b = timed(conn, SQL_E3_PRE, args.runs)
    results["E3"].append(Result("查预聚合表", pre, rows3b, plan_of(conn, SQL_E3_PRE)))
    results["E3"].append(Result("（预聚合表构建，仅一次）", build_cost, -1, "全表聚合 + 建唯一索引"))

    conn.close()

    titles = {
        "E1": "实验 1 · 时间范围过滤（单表全量）",
        "E2": "实验 2 · 相关子查询（外表每行再扫一遍明细）",
        "E3": "实验 3 · 看板取数：现算 vs 预聚合",
    }
    lines: list[str] = []
    for key, rows in results.items():
        lines.append(f"\n{titles[key]}")
        base = rows[0].seconds
        for r in rows:
            row_text = "" if r.rows < 0 else f"  ({r.rows} 行)"
            speed = "" if r.rows < 0 or r.seconds <= 0 else f"  ×{base / r.seconds:.0f}"
            lines.append(f"  {r.label:<28}{fmt(r.seconds):>10}{speed:>9}{row_text}")
            lines.append(f"      plan: {r.plan}")
            if r.note:
                lines.append(f"      note: {r.note}")

    report = "\n".join(lines)
    print(report)

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        "# 基准结果（本机实测 · SQLite）\n\n```" + report + "\n```\n\n"
        f"数据规模：{orders:,} 订单 / {items:,} 明细。\n",
        encoding="utf-8",
    )
    print(f"\n已写入 {RESULT_PATH}")


if __name__ == "__main__":
    main()
