# SQL 慢查询实验台

把「报表查询从分钟级降到秒级」拆成三个可复现的实验：每个实验都给出**执行计划**和**实测耗时**，而不是只讲结论。

数据是脚本生成的合成电商库（SQLite）：客户、订单、订单明细三张表，规模可调。

## 三个实验在问什么

| 实验 | 问题 | 结论（本机实测，30 万订单） |
| --- | --- | --- |
| 1 · 时间过滤 | 只查 3 天，为什么还要全表扫？ | 13.3 ms → 1.1 ms（×12），`SCAN` 变 `SEARCH ... USING INDEX` |
| 2 · 相关子查询 | 加了 WHERE 还是慢，慢在哪？ | 3.64 s → 1.5 ms（×2386），子查询从「每行扫一遍明细」变「走索引」 |
| 3 · 看板取数 | 为什么每天都要重算一遍？ | 101.3 ms → 125 µs（×810），代价是预聚合表 220 ms 的一次性构建 |

## 快速开始

```bash
make data     # = python bench/gen_data.py --orders 300000 --customers 40000，约 4.5 s，生成 42 MB
make plan     # 只比执行计划（毫秒级，不测耗时）
make bench    # 三个实验依次跑，写 results/benchmark.md
make test     # 4 个用例：结果不变 + 计划确实变了
```

环境：Python 3.9+，**只用标准库**（`sqlite3`）；测试需要 `pytest`（`pip install -r requirements-dev.txt`）。

数据模型（`bench/gen_data.py`）：

```text
f_customers   customer_id, region, signup_date                    4 万行
f_orders      order_id, customer_id, channel, pay_amount,       30 万行
              cost_amount, paid_at, status
f_order_items item_id, order_id, sku_id, category, qty,          61 万行
              unit_price, unit_cost
```

## 实测输出（`results/benchmark.md`）

```text
实验 1 · 时间范围过滤（单表全量）
  无索引 · 全表扫描                      13.3 ms       ×1  (1 行)
      plan: SCAN f_orders
  有索引 · 范围查找                       1.1 ms      ×12  (1 行)
      plan: SEARCH f_orders USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?)

实验 2 · 相关子查询（外表每行再扫一遍明细）
  相关子查询 · 明细无索引                   3.64 s       ×1  (216 行)
      plan: ... ｜ CORRELATED SCALAR SUBQUERY 1 ｜ SCAN i
  相关子查询 · 明细有索引                   1.5 ms    ×2386  (216 行)
      plan: ... ｜ CORRELATED SCALAR SUBQUERY 1 ｜ SEARCH i USING INDEX idx_items_order_id

实验 3 · 看板取数：现算 vs 预聚合
  现算 · 扫明细再聚合                   101.3 ms       ×1  (48 行)
  查预聚合表                             125 µs     ×810  (48 行)
  （预聚合表构建，仅一次）                 220.5 ms
```

每行都打印 `EXPLAIN QUERY PLAN`，耗时取多次运行的中位数 —— 只报倍数不报计划，等于没解释为什么快。

## 三个结论

1. **过滤条件要能落到索引上。** 索引建在 `paid_at` 上，`SCAN` 才会变 `SEARCH`；倍数不算夸张（×12），但它是最便宜的一步。
2. **相关子查询的代价是 O(行数 × 明细扫描)。** 外表命中 216 行，每行再扫 61 万行明细，就是 3.64 秒的来源；给 `order_id` 建索引后同样的 SQL 直接 1.5 ms —— **SQL 不用改，索引改命的场景真实存在**。
3. **看板要预聚合，但预聚合有权重边界。** 半年 48 行的结果集每次现算要 101 ms；预聚合后 125 µs，代价是 220 ms 的构建与一份要维护的调度。维度一变（按渠道 × 品类），这张表就作废了。

## 目录结构

```text
sql-slow-query-lab/
├─ bench/
│  ├─ gen_data.py            # 合成数据（规模/种子可调，固定格式时间列）
│  ├─ run_bench.py           # 三个实验：建/删索引，计时 + 打计划，写 results/benchmark.md
│  └─ explain_compare.py     # 只打印「无索引 / 有索引」两份计划，CI 用
├─ sql/
│  ├─ schema.sql             # 三张表的 DDL 与设计说明
│  ├─ indexes.sql            # 两个索引，以及「复合索引列顺序不能反」的理由
│  ├─ query_e1_time_filter.sql
│  ├─ query_e2_correlated.sql
│  ├─ query_e3_dashboard.sql
│  └─ dws_month_region.sql   # 实验 3 的预聚合表
├─ docs/
│  ├─ explain-cheatsheet.md  # SCAN/SEARCH/COVERING/TEMP B-TREE/CORRELATED 的速查表
│  └─ case-notes.md          # 三个案例的症状→诊断→处理，含一个「改写更慢」的反例
├─ tests/test_queries.py     # 结果不变 + 计划变了 + 预聚合与现算一致
├─ results/benchmark.md      # 最近一次实测（由 run_bench.py 生成）
├─ data/README.md            # 为什么 42 MB 的库不进仓库
└─ .github/workflows/ci.yml  # 小数据跑全流程，计划没变就失败
```

## 顺手记下的坑

- **复合索引列顺序**：`(paid_at, status)` 不能写成 `(status, paid_at)` —— 后者在「88% 都是 paid」的列上没有选择性，等于没建。
- **改写不一定更快**：把实验 2 的相关子查询改写成 `JOIN + GROUP BY` 后，优化器把 61 万行明细放到外层，实测 43.3 ms，比带索引的原写法慢 30 倍。细节在 `docs/case-notes.md`。
- **预聚合的代价不只在第一次**：数据每天都在变，调度、回补、口径一致性都是成本。只有当「结果集远小于源数据 + 维度固定」时它才划算。

## 想拿去改

- 换成自己的库：改 `bench/gen_data.py` 的 `SCHEMA` 与 `build()`，其余脚本只依赖列名。
- 只想要计划对照：`python bench/explain_compare.py --db 你的.db`，两个索引名在 `bench/run_bench.py` 的 `INDEXES` 里。
- 想加实验：见 `CONTRIBUTING.md`（要求「结果不变 + 计划变了」的用例）。

## License

MIT
