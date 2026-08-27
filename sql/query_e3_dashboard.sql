-- 实验 3：看板每天重算半年数据 —— 现算 vs 预聚合。
-- 现算版本：每次打开看板都扫一遍订单 + 关联客户 + 分组聚合。

EXPLAIN QUERY PLAN
SELECT substr(o.paid_at, 1, 7) AS stat_month,
       c.region,
       COUNT(*)                    AS order_cnt,
       ROUND(SUM(o.pay_amount), 2) AS gmv
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.paid_at >= '2025-07-01'
  AND o.paid_at <  '2026-01-01'
  AND o.status   =  'paid'
GROUP BY substr(o.paid_at, 1, 7), c.region
ORDER BY stat_month, gmv DESC;

-- 预聚合版本：把「月 × 区域」提前算成一张宽表，看板只查这张表。
-- 建表脚本见 sql/dws_month_region.sql，查询变成：
--   SELECT stat_month, region, order_cnt, gmv FROM dws_month_region
--   WHERE stat_month >= '2025-07' AND stat_month < '2026-01';
-- 代价：预聚合表要构建（285 ms）、要调度刷新，且只对「固定维度」的看板有效。
