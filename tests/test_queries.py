"""保证「慢查询 → 快查询」不只是跑分，而是结果不变、计划确实变了。

用很小的数据（3000 单）跑，秒级完成，适合进 CI。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import gen_data  # noqa: E402
import run_bench  # noqa: E402


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("data") / "small.db"
    gen_data.DB_PATH = path
    gen_data.build(orders=3000, customers=600, items_ratio=2.5, seed=7)
    return path


@pytest.fixture()
def conn(db: Path):
    connection = sqlite3.connect(db)
    for name in run_bench.INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {name}")
    connection.commit()
    yield connection
    connection.close()


def rows(connection: sqlite3.Connection, sql: str) -> list[tuple]:
    return [tuple(r) for r in connection.execute(sql).fetchall()]


def plan(connection: sqlite3.Connection, sql: str) -> str:
    return " | ".join(str(r[-1]) for r in connection.execute("EXPLAIN QUERY PLAN " + sql))


def test_e1_index_keeps_result_and_changes_plan(conn):
    before = rows(conn, run_bench.SQL_E1)
    slow_plan = plan(conn, run_bench.SQL_E1)
    conn.execute(run_bench.INDEXES["idx_orders_paid_at"])
    after = rows(conn, run_bench.SQL_E1)
    fast_plan = plan(conn, run_bench.SQL_E1)

    assert before == after, "建索引不能改变查询结果"
    assert "SCAN f_orders" in slow_plan
    assert "SEARCH f_orders USING INDEX idx_orders_paid_at" in fast_plan
    assert before[0][0] > 0, "测试数据应覆盖 2025-06-01~04 的切片"


def test_e2_index_keeps_result_and_changes_plan(conn):
    conn.execute(run_bench.INDEXES["idx_orders_paid_at"])
    before = rows(conn, run_bench.SQL_E2)
    slow_plan = plan(conn, run_bench.SQL_E2)
    conn.execute(run_bench.INDEXES["idx_items_order_id"])
    after = rows(conn, run_bench.SQL_E2)
    fast_plan = plan(conn, run_bench.SQL_E2)

    assert before == after
    assert "CORRELATED SCALAR SUBQUERY" in slow_plan.upper()
    assert "idx_items_order_id" in fast_plan
    assert len(before) > 0


def test_e3_preaggregation_matches_live_result(conn):
    live = sorted(rows(conn, run_bench.SQL_E3_LIVE))
    conn.executescript(run_bench.SQL_E3_BUILD)
    pre = sorted(
        tuple(r)
        for r in conn.execute(
            """
            SELECT stat_month, region, order_cnt, gmv FROM dws_month_region
            WHERE stat_month >= '2025-07' AND stat_month < '2026-01'
            """
        ).fetchall()
    )
    live_in_slice = [row for row in live if "2025-07" <= row[0] < "2026-01"]
    assert live_in_slice == pre, "预聚合与现算必须一致，否则看板会悄悄变数"
    assert len(pre) > 0


def test_preaggregation_query_uses_the_small_table(conn):
    conn.executescript(run_bench.SQL_E3_BUILD)
    query_plan = plan(conn, run_bench.SQL_E3_PRE)
    assert "dws_month_region" in query_plan
