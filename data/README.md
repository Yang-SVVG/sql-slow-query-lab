# data/

这个目录里的 `lab.db` 是 `bench/gen_data.py` 生成的合成数据（30 万订单约 42 MB），
已经在 `.gitignore` 里排除，不随仓库分发。需要时自己生成：

```bash
python bench/gen_data.py --orders 300000 --customers 40000
```

想跑更小/更大的规模，改 `--orders` 即可；`--seed` 固定随机种子，同参数结果可复现。
