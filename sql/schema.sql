-- 合成电商库结构（与 bench/gen_data.py 里的 SCHEMA 保持一致）
-- 三张表：客户、订单、订单明细，星型的最小形态。

CREATE TABLE f_customers (
    customer_id INTEGER PRIMARY KEY,
    region      TEXT    NOT NULL,   -- 华东 / 华南 / ... / 海外
    signup_date TEXT    NOT NULL    -- 注册日期，YYYY-MM-DD
);

CREATE TABLE f_orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,   -- 指向 f_customers，故意不建外键（见文末说明）
    channel     TEXT    NOT NULL,   -- app / mini_program / h5 / offline
    pay_amount  REAL    NOT NULL,
    cost_amount REAL    NOT NULL,
    paid_at     TEXT    NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS'，报表的主要过滤列
    status      TEXT    NOT NULL    -- paid / refunded / cancelled
);

CREATE TABLE f_order_items (
    item_id    INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL,    -- 指向 f_orders
    sku_id     INTEGER NOT NULL,
    category   TEXT    NOT NULL,
    qty        INTEGER NOT NULL,
    unit_price REAL    NOT NULL,
    unit_cost  REAL    NOT NULL
);

-- 说明：
-- * paid_at 用 TEXT 存（SQLite 没有原生 datetime），格式固定为
--   'YYYY-MM-DD HH:MM:SS'，这样字符串比较等价于时间比较，索引可直接用于范围扫描。
-- * 不建外键：本实验关注查询计划，外键会额外增加写入开销与检查。
-- * 明细表没有 (order_id, sku_id) 的唯一约束：合成数据允许同单多行同 SKU。
