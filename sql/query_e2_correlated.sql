-- 实验 2：加了 WHERE 还是慢 —— 慢在相关子查询，不在主查询。
-- 外表命中 N 行，子查询就执行 N 次；没有索引时每次都是一次全表扫描。

EXPLAIN QUERY PLAN
SELECT o.order_id,
       ROUND(o.pay_amount, 2) AS amount,
       (SELECT ROUND(SUM(i.qty * i.unit_price), 2)
          FROM f_order_items i
         WHERE i.order_id = o.order_id) AS item_amount
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.paid_at >= '2025-06-01'
  AND o.paid_at <  '2025-06-04'
  AND c.region   =  '华东';

-- 计划里的关键片段：
--   无索引  ...  CORRELATED SCALAR SUBQUERY 1 ... SCAN i
--   有索引  ...  CORRELATED SCALAR SUBQUERY 1 ... SEARCH i USING INDEX idx_items_order_id (order_id=?)

-- 同一件事换写法不一定更快：JOIN + GROUP BY 改写在 30 万订单上实测 43.3 ms，
-- 比带索引的相关子查询（2.2 ms）慢 20 倍 —— 优化器把 f_order_items 放到了外层整表扫描。
-- 详见 docs/case-notes.md「反例：改写不一定更快」。
