-- 实验 1：只查 3 天 + 只看已支付，为什么还是全表扫？
-- 关键点：过滤列上有没有索引，以及复合索引的列顺序。
-- 执行：sqlite3 data/lab.db < sql/query_e1_time_filter.sql

EXPLAIN QUERY PLAN
SELECT COUNT(*), ROUND(SUM(pay_amount), 2)
FROM f_orders
WHERE paid_at >= '2025-06-01'
  AND paid_at <  '2025-06-04'
  AND status   =  'paid';

-- 对照实验：把索引去掉再跑一次
--   DROP INDEX IF EXISTS idx_orders_paid_at;
-- 计划会从
--   SEARCH f_orders USING INDEX idx_orders_paid_at (paid_at>? AND paid_at<?)
-- 变回
--   SCAN f_orders
