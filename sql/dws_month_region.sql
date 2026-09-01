-- 看板「月 × 区域」预聚合表
-- 构建一次（285 ms @ 30 万订单），之后每次查询 144 µs，供日更看板使用。
DROP TABLE IF EXISTS dws_month_region;

CREATE TABLE dws_month_region AS
SELECT substr(o.paid_at, 1, 7) AS stat_month,   -- 'YYYY-MM'
       c.region,
       COUNT(*)                    AS order_cnt,
       ROUND(SUM(o.pay_amount), 2) AS gmv
FROM f_orders o
JOIN f_customers c ON c.customer_id = o.customer_id
WHERE o.status = 'paid'                          -- 口径：只看已支付，不含退款/取消
GROUP BY substr(o.paid_at, 1, 7), c.region;

CREATE UNIQUE INDEX idx_dws_month_region ON dws_month_region (stat_month, region);

-- 生产上还需要两件事，实验脚本里省略了：
-- 1) 调度：日更（或按支付流水的小时增量回刷），并记录 run_id 与完成时间；
-- 2) 回刷：退款、订单状态变更会改写历史月份，需要按 stat_month 重算而不是只追加。
