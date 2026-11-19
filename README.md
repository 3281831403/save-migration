# 存档迁移：版本链、校验与原子替换

老存档升级后角色属性清零、回滚失败：版本链跳级，校验和算法不稳定，字段改名没映射，原子替换没有检查临时文件，备份策略保留版本错，降级判断反，schema 差异漏键，局部补丁覆盖整表，版本白名单没校验，批量存档只提交一半。

## 目录结构

```
README.md
conftest.py
.gitignore
save/__init__.py
save/migration.py
tests/test_migration.py
```

## 当前状态

`save/migration.py` 中所有函数只保留签名与文档字符串，函数体统一
`raise NotImplementedError`。`tests/test_migration.py` 有 15 个参数化用例，
初始全部失败。

## 需要修复的 10 个问题

1. 版本链逐级递增
2. 校验和确定性
3. 字段改名按映射
4. 原子替换检查临时文件
5. 备份策略保留前 N 版
6. 降级方向判断
7. schema 差异对称
8. 局部补丁合并
9. 版本白名单校验
10. 批量存档统一提交

## 验收

```bash
python -m pytest -q
```

初始应得到 `15 failed`，且没有 collection error。实现 `save/migration.py`
后 15 条用例应全部通过。
