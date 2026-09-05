# 基准结果（本机实测 · SQLite）

```
实验 1 · 时间范围过滤（单表全量）
  无索引 · 全表扫描                     13.3 ms       ×1  (1 行)
      plan: SCAN f_orders
  有索引 · 范围查找                      1.1 ms      ×12  (1 行)
      plan: SEARCH f_orders USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?)

实验 2 · 相关子查询（外表每行再扫一遍明细）
  相关子查询 · 明细无索引                   3.64 s       ×1  (216 行)
      plan: SEARCH o USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?) ｜ SEARCH c USING INTEGER PRIMARY KEY (rowid=?) ｜ CORRELATED SCALAR SUBQUERY 1 ｜ SCAN i
      note: 外表每行都 SCAN 一次明细表 → O(N×M)
  相关子查询 · 明细有索引                   1.5 ms    ×2386  (216 行)
      plan: SEARCH o USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?) ｜ SEARCH c USING INTEGER PRIMARY KEY (rowid=?) ｜ CORRELATED SCALAR SUBQUERY 1 ｜ SEARCH i USING INDEX idx_items_order_id (order_id=?)

实验 3 · 看板取数：现算 vs 预聚合
  现算 · 扫明细再聚合                   101.3 ms       ×1  (48 行)
      plan: SEARCH o USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?) ｜ SEARCH c USING INTEGER PRIMARY KEY (rowid=?) ｜ USE TEMP B-TREE FOR GROUP BY ｜ USE TEMP B-TREE FOR ORDER BY
  查预聚合表                           125 µs     ×810  (48 行)
      plan: SEARCH dws_month_region USING INDEX idx_dws_month_region (stat_month>? AND stat_month<?) ｜ USE TEMP B-TREE FOR LAST TERM OF ORDER BY
  （预聚合表构建，仅一次）                  220.5 ms         
      plan: 全表聚合 + 建唯一索引
```

数据规模：300,000 订单 / 609,090 明细。
