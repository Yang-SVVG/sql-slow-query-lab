# 贡献指南

这个仓库的目的是「可复现的性能实验」，所以对新增内容有两条硬要求：

1. **每个结论都要有 plan 和数字。** 只写「加索引会变快」不算结论，要给出 `EXPLAIN QUERY PLAN`
   的输出，以及至少 3 次运行的中位数。
2. **数字要能复现。** 说明数据规模、SQLite 版本、机器的大致情况；`python bench/run_bench.py --runs 5`
   跑出来的结果贴进 PR 描述里。

## 想加一个新实验

1. 在 `bench/run_bench.py` 里加 `SQL_E4_*` 与对应的索引定义；
2. 在 `bench/explain_compare.py` 的 `CASES` 里登记，保证计划对照能覆盖；
3. 在 `tests/test_queries.py` 加一个「结果不变 + 计划变了」的用例；
4. 更新 `README.md` 的实验表与 `results/benchmark.md`。

反例（改写后更慢的写法）也欢迎，但请放进 `docs/case-notes.md`，不要放进基准表 ——
基准表只收推荐写法。
