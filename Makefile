PY ?= python3

.PHONY: help data plan bench test clean

help:
	@echo "make data   生成 30 万订单的合成数据（约 4.5 s）"
	@echo "make plan   只比执行计划（毫秒级，适合 CI）"
	@echo "make bench  跑三个实验并写 results/benchmark.md"
	@echo "make test   跑 pytest"
	@echo "make clean  删除生成的数据与缓存"

data:
	$(PY) bench/gen_data.py --orders 300000 --customers 40000 --force

plan:
	$(PY) bench/explain_compare.py

bench:
	$(PY) bench/run_bench.py --runs 3

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/*.db .pytest_cache/ __pycache__/ bench/__pycache__/ tests/__pycache__/
