#!/usr/bin/env python3
"""生成基准测试用的合成数据（SQLite）。

规模可调，默认：6 万客户 / 60 万订单 / 约 150 万订单明细。
数据是随机的，但分布贴近真实电商：下单时间集中在 18 个月内的自然日，
金额与品类有少量热点，便于观察索引与聚合的选择性差异。

用法：
    python bench/gen_data.py                # 默认规模
    python bench/gen_data.py --orders 200000 --customers 20000
    python bench/gen_data.py --force        # 重建（覆盖已有 data/lab.db）
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "lab.db"

REGIONS = ["华东", "华南", "华北", "华中", "西南", "西北", "东北", "海外"]
CHANNELS = ["app", "mini_program", "h5", "offline"]
CATEGORIES = ["3C", "服饰", "食品", "家居", "美妆", "母婴"]

SCHEMA = """
DROP TABLE IF EXISTS f_order_items;
DROP TABLE IF EXISTS f_orders;
DROP TABLE IF EXISTS f_customers;

CREATE TABLE f_customers (
    customer_id INTEGER PRIMARY KEY,
    region      TEXT    NOT NULL,
    signup_date TEXT    NOT NULL
);

CREATE TABLE f_orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    channel     TEXT    NOT NULL,
    pay_amount  REAL    NOT NULL,
    cost_amount REAL    NOT NULL,
    paid_at     TEXT    NOT NULL,
    status      TEXT    NOT NULL
);

CREATE TABLE f_order_items (
    item_id      INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL,
    sku_id       INTEGER NOT NULL,
    category     TEXT    NOT NULL,
    qty          INTEGER NOT NULL,
    unit_price   REAL    NOT NULL,
    unit_cost    REAL    NOT NULL
);
"""


def build(orders: int, customers: int, items_ratio: float, seed: int) -> None:
    random.seed(seed)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")

    start = dt.date(2025, 1, 1)
    days = 540

    cust_rows = []
    for cid in range(1, customers + 1):
        signup = start - dt.timedelta(days=random.randint(0, 900))
        cust_rows.append((cid, random.choice(REGIONS), signup.isoformat()))
    conn.executemany("INSERT INTO f_customers VALUES (?, ?, ?)", cust_rows)

    order_rows, item_rows = [], []
    item_id = 0
    for oid in range(1, orders + 1):
        cid = random.randint(1, customers)
        day = start + dt.timedelta(days=random.randint(0, days - 1))
        hour = random.choices(range(24), weights=[1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8,
                                                  8, 7, 7, 7, 8, 10, 12, 14, 12, 9, 5, 3])[0]
        paid_at = f"{day.isoformat()} {hour:02d}:{random.randint(0, 59):02d}:00"
        amount = round(random.lognormvariate(4.2, 0.75), 2)
        cost = round(amount * random.uniform(0.45, 0.82), 2)
        status = random.choices(["paid", "refunded", "cancelled"], weights=[88, 7, 5])[0]
        order_rows.append((oid, cid, random.choice(CHANNELS), amount, cost, paid_at, status))

        n_items = max(1, int(random.gauss(items_ratio, 0.8)))
        for _ in range(n_items):
            item_id += 1
            qty = random.choices([1, 2, 3, 5], weights=[70, 20, 7, 3])[0]
            unit_price = round(amount / n_items / qty * random.uniform(0.6, 1.4), 2)
            item_rows.append((item_id, oid, random.randint(1, 5000),
                              random.choice(CATEGORIES), qty, unit_price,
                              round(unit_price * random.uniform(0.4, 0.8), 2)))

        if len(order_rows) >= 20000:
            conn.executemany("INSERT INTO f_orders VALUES (?, ?, ?, ?, ?, ?, ?)", order_rows)
            conn.executemany("INSERT INTO f_order_items VALUES (?, ?, ?, ?, ?, ?, ?)", item_rows)
            order_rows.clear()
            item_rows.clear()

    if order_rows:
        conn.executemany("INSERT INTO f_orders VALUES (?, ?, ?, ?, ?, ?, ?)", order_rows)
        conn.executemany("INSERT INTO f_order_items VALUES (?, ?, ?, ?, ?, ?, ?)", item_rows)

    conn.commit()
    for table in ("f_customers", "f_orders", "f_order_items"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<14} {count:>10,} rows")
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"  {'file':<14} {size_mb:>10.1f} MB  ->  {DB_PATH}")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 SQLite 基准数据")
    parser.add_argument("--orders", type=int, default=600_000)
    parser.add_argument("--customers", type=int, default=60_000)
    parser.add_argument("--items-ratio", type=float, default=2.5)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--force", action="store_true", help="已存在则重建")
    args = parser.parse_args()

    if DB_PATH.exists() and not args.force:
        print(f"{DB_PATH} 已存在，跳过（加 --force 重建）")
        return

    print(f"生成 {args.orders:,} 订单 / {args.customers:,} 客户 ...")
    build(args.orders, args.customers, args.items_ratio, args.seed)


if __name__ == "__main__":
    main()
