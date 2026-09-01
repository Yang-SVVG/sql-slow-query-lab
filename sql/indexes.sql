-- 实验用到的索引：只建两个，对应两个真实瓶颈
-- 1) 时间范围过滤：报表绝大多数查询都带 paid_at 区间
CREATE INDEX IF NOT EXISTS idx_orders_paid_at ON f_orders (paid_at, status);

-- 2) 订单明细回查：子查询 / 明细汇总按 order_id 找行
CREATE INDEX IF NOT EXISTS idx_items_order_id ON f_order_items (order_id);

-- 说明：
-- * (paid_at, status) 的复合顺序不能反：先按时间范围定位，再按状态过滤，
--   反过来（status, paid_at）在只有 3 个取值、88% 都是 paid 的列上没有选择性。
-- * 明细表只给 order_id 建索引；sku_id / category 的组合查询在本实验不在范围内，
--   多建索引会让 gen_data.py 的写入路径变慢，也会误导「索引越多越快」的印象。
