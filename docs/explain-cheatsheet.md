# 读 EXPLAIN QUERY PLAN 的速查表

SQLite 的执行计划只有十几个关键字，真正需要认得的是下面这些。本仓库所有输出都能对上。

## 一、行怎么来

| 关键字 | 含义 | 什么时候出现 |
| --- | --- | --- |
| `SCAN t` | 全表扫描 t | 过滤列没索引，或优化器认为全扫更便宜 |
| `SEARCH t USING INDEX idx (cond)` | 用索引定位行 | 通常是好事：只读需要的行 |
| `SEARCH t USING COVERING INDEX idx` | 覆盖索引，连表都不用回 | 最好：索引里就有全部需要的列 |
| `SEARCH t USING INTEGER PRIMARY KEY` | 走 rowid | 主键点查 |
| `SCAN t USING INDEX idx` | 按索引顺序全扫 | 有 ORDER BY 时会用，注意这里**没有**减少读的量 |

判断快慢不要只看 `SCAN` 这个词：`SCAN` + 小表、`SCAN` + `LIMIT 1` 都可能很快。要看的是**读了多少行**。

## 二、聚合与排序

| 关键字 | 含义 | 代价 |
| --- | --- | --- |
| `USE TEMP B-TREE FOR GROUP BY` | 分组需要临时排序 | 大结果集时内存/磁盘双杀 |
| `USE TEMP B-TREE FOR ORDER BY` | 排序需要临时排序 | 同上 |
| `USE TEMP B-TREE FOR DISTINCT` | 去重需要排序 | 同上 |

出现 `TEMP B-TREE` 说明索引没帮上分组的忙：要么把 GROUP BY 的列做成索引前缀，要么接受一次排序。

## 三、子查询

| 关键字 | 含义 |
| --- | --- |
| `CORRELATED SCALAR SUBQUERY n` | 相关子查询：外层每行执行一次 |
| `CO-ROUTINE n` | 子查询被物化成协程（CTE / 子查询被展平） |
| `MATERIALIZE` | 子查询物化成临时表 |
| `SUBQUERY n` | 非相关子查询，只执行一次 |

看到 `CORRELATED SCALAR SUBQUERY` 且里面是 `SCAN`，基本就是本仓库实验 2 的形态：**O(外层行数 × 内表行数)**。

## 四、连接顺序

计划里的树序就是执行顺序（第一个子节点先跑）。`SCAN` 出现在内层还是外层，决定了复杂度是 N×M 还是 N+M。

一个真实的反例：把相关子查询改写成 `JOIN + GROUP BY` 后，计划变成

```text
SCAN f_order_items
SEARCH f_orders USING ...
```

优化器把 61 万行的明细表放到了外层，实测 43.3 ms，比原来的 2.2 ms 慢 20 倍。**改写要自己看计划，不能凭直觉。**

## 五、常用手段

```sql
ANALYZE;                       -- 收集统计信息，让优化器有依据（本仓库没跑，数据是合成的）
EXPLAIN QUERY PLAN <sql>;      -- 看计划
EXPLAIN <sql>;                 -- 看字节码（更细，通常不需要）
.time on                       -- sqlite3 CLI 里看耗时
```

`ANALYZE` 之后计划可能变，所以性能回归测试要固定数据与版本 —— `tests/test_queries.py` 就是用「小数据 + 断言计划里有 SEARCH」固定这一点。
