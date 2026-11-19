# save-migration

老玩家的存档升级到新版本后，开始丢进度：迁移只执行目标版本的步骤，跨两版漏掉中间字段；缺字段不补默认值，读取方 KeyError；校验和包含未排序键，同内容不同哈希；直接覆盖写，进程中断留下半文件；主文件损坏直接抛异常，不读备份；压缩后不校验版本，旧档被当新档；merge_defaults 覆盖已有值，玩家设置被重置；批量迁移边写边迁，失败留半成品；浮点字段按字符串比较，1.0 与 1 判定不一致；嵌套默认值不递归，子对象缺键。savemig/migrate.py 是核心，tests/test_migrate.py 15个红。要修的是：沿 v1→v2→v3 版本链逐级迁移并补齐默认值（含嵌套对象）、按排序键与浮点 repr 计算 sha256 校验和、临时文件 + os.replace 原子写盘、主文件损坏时回退 `.bak`、解压后校验版本、merge_defaults 只补缺失键且递归合并、批量迁移全部成功后才落盘，让 15 条测试全部转绿。

## 运行方式

在仓库根目录执行（Python 3.10+，只需要 pytest）：

```powershell
python -m pytest tests -q
```

初始状态必须恰好是下面这一行，且不允许出现 collection / import / syntax error：

```text
15 failed
```

修复完成后的目标是 `15 passed`。

## 目录结构

```text
save-migration/
  README.md  conftest.py  .gitignore
  savemig/__init__.py  savemig/migrate.py
  tests/test_migrate.py
```

- `savemig/migrate.py`：8 个待实现函数（`migrate`、`validate`、`checksum`、`atomic_write`、`read_with_recovery`、`compress`/`decompress`、`merge_defaults`、`migrate_batch`）加异常类 `MigrationError`，当前全部 `raise NotImplementedError`，docstring 写清了契约。
- `tests/test_migrate.py`：15 条测试 = 10 个缺陷各 1 条 + 5 条组合/契约测试；全部调用桩，存档用内联 dict，落盘一律用 `tmp_path`。
- `conftest.py`：把仓库根目录加入 `sys.path`，保证 `import savemig` 可用。
- `.gitignore`：三行，忽略 `__pycache__/`、`*.py[cod]`、`.pytest_cache/`。

## 版本链与默认值

| 版本 | 变化 | 新增默认值 |
| --- | --- | --- |
| v1 | 初始结构 `player.name`、`player.hp`、`gold` | `player.name="anonymous"`、`player.hp=100.0`、`gold=0` |
| v2 | `player.hp` 改名为 `player.health`，引入 `settings` | `player.health=100.0`、`settings.music=0.8`、`settings.effects=True` |
| v3 | 引入 `achievements` 与 `player.level` | `achievements=[]`、`player.level=1` |

跨级迁移（如 v1 → v3）必须逐级执行：先做 v1 → v2 的字段改名，再做 v2 → v3 的新增字段，不能跳过中间步骤。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 其他 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 约束

- 只用标准库（`json`、`hashlib`、`os`、`tempfile`、`zlib`）与 `pytest`；离线、无随机。
- **`tests/test_migrate.py` 不可修改**，所有修复只发生在 `savemig/migrate.py`。
- 不执行 `git init` / `git push`，不联网。
