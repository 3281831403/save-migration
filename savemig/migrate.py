"""存档版本迁移核心模块（初始为桩，全部待实现）。

版本链
======
v1：``{"version": 1, "player": {"name": str, "hp": number}, "gold": number}``

v2：``player.hp`` 改名为 ``player.health``，并引入 ``settings``
（``{"music": 0.8, "effects": True}``）。

v3：新增 ``achievements``（默认 ``[]``）与 ``player.level``（默认 ``1``）。

默认值表
========
* ``player.name``      -> ``"anonymous"``（v1 起）
* ``player.hp``        -> ``100.0``（v1 起，仅 v1 结构使用）
* ``player.health``    -> ``100.0``（v2 起）
* ``gold``             -> ``0``（v1 起）
* ``settings.music``   -> ``0.8``（v2 起）
* ``settings.effects`` -> ``True``（v2 起）
* ``achievements``     -> ``[]``（v3 起）
* ``player.level``     -> ``1``（v3 起）

约束：只允许使用标准库（json、hashlib、os、tempfile、zlib）；离线、无随机。
"""


class MigrationError(Exception):
    """存档读取、校验、压缩或迁移失败时抛出的异常。"""


def migrate(save: dict, target_version: int) -> dict:
    """把 ``save`` 沿版本链逐级迁移到 ``target_version``，返回新的 dict。

    * 版本链为 v1 -> v2 -> v3；即使目标版本跨级（如 v1 -> v3）也必须逐级执行，
      不能只套用目标版本的步骤（v1 -> v3 必须先完成 v1 -> v2 的
      ``player.hp`` -> ``player.health`` 改名）。
    * 每一级都补齐该版本引入的缺失字段（见模块文档的默认值表），
      已有值保持不变；不得修改传入的 ``save``。
    * 结果 ``version`` 等于 ``target_version``；更晚版本才引入的字段不得提前出现。
    * ``save`` 缺少 ``version``、``target_version`` 不在 {1, 2, 3}、
      或 ``target_version`` 低于存档当前版本时，抛 ``MigrationError``。
    """
    raise NotImplementedError


def validate(save: dict) -> list[str]:
    """检查存档并返回问题描述列表；没有问题返回 ``[]``。

    必须报告以下问题（每条为字符串，且包含相关字段名）：

    * ``version`` 缺失、不是 int、或不在 {1, 2, 3}；
    * ``player`` 不是 dict；
    * ``player.health`` 不是数字（``bool`` 不算数字）；
    * ``settings.music`` 不是数字（``1`` 与 ``1.0`` 都必须接受，不得按字符串比较）；
    * ``achievements`` 不是 list；
    * 存在顶层 ``checksum`` 字段时，其值与 :func:`checksum` 算出的结果不一致。

    缺失的可选字段只在 ``version`` 允许的范围内视为问题，本函数不负责补默认值。
    """
    raise NotImplementedError


def checksum(save: dict) -> str:
    """对 ``save`` 的规范化 JSON 取 sha256，返回 64 位小写十六进制字符串。

    规范化：``json.dumps(..., sort_keys=True, separators=(",", ":"),
    ensure_ascii=False)``，浮点统一按其 ``repr`` 形式参与序列化；
    顶层 ``checksum`` 字段不参与计算，因此 :func:`validate` 可以核对
    写盘前存下的校验和。同一内容、不同键顺序必须得到同一哈希。
    """
    raise NotImplementedError


def atomic_write(path, data: dict) -> None:
    """原子地把 ``data``（dict，写成 JSON）保存到 ``path``。

    * ``path`` 可以是 str 或 pathlib.Path；
    * 先写同目录临时文件，再用 ``os.replace`` 覆盖目标；
    * 写入成功后目录里只剩目标文件，不残留临时文件；
    * 序列化失败（例如 data 含 set）或写入失败时删除临时文件、
      保留原有目标文件（若存在），并抛 ``MigrationError``：绝不留半文件。
    """
    raise NotImplementedError


def read_with_recovery(path) -> dict:
    """读取存档 JSON；主文件损坏时回退到备份 ``<path>.bak``。

    * ``path`` 可以是 str 或 pathlib.Path；返回读取到的 dict；
    * 主文件缺失、不是合法 JSON、或顶层不是 JSON 对象时，尝试读取
      备份文件（原路径加上 ``.bak`` 后缀）；
    * 主文件和备份都不可用时抛 ``MigrationError``。
    """
    raise NotImplementedError


def compress(save: dict, level: int = 6) -> bytes:
    """把 ``save`` 序列化为 JSON 后用 zlib 压缩，返回 bytes。

    ``level`` 原样传给 ``zlib.compress``。语义上必须能与
    :func:`decompress` 往返，得到相等的内容。
    """
    raise NotImplementedError


def decompress(raw: bytes) -> dict:
    """``compress`` 的逆操作：zlib 解压 + JSON 解析，返回 dict。

    * 解压失败或 JSON 解析失败时抛 ``MigrationError``；
    * 解压结果必须校验版本：缺少 ``version`` 或 ``version`` 不在 {1, 2, 3}
      时抛 ``MigrationError``，旧档不得被当成新档使用。
    """
    raise NotImplementedError


def merge_defaults(save: dict, defaults: dict) -> dict:
    """把 ``defaults`` 中 ``save`` 缺失的键补进去，返回新的 dict。

    * 只补缺失键，已有值（包括 ``0``、``""``、``False``、``None``）一律保留；
    * ``defaults`` 里是 dict 的键递归合并，子对象缺键也要补上；
    * 不修改传入的 ``save`` 与 ``defaults``。
    """
    raise NotImplementedError


def migrate_batch(saves: dict[str, dict], target_version: int) -> dict:
    """批量迁移并落盘：全部成功才写，任何一条失败都不写。

    ``saves`` 是 ``{文件路径: 存档 dict}``，按插入顺序逐条 :func:`migrate`，
    全部成功后再用 :func:`atomic_write` 写回各自路径（不得边迁边写）。

    * 全部成功：``{"ok": True, "saves": {路径: 迁移后的存档, ...}}``，
      返回的键顺序与 ``saves`` 的插入顺序一致；
    * 任意一条迁移失败（抛 ``MigrationError``）：
      ``{"ok": False, "failed": [失败的路径, ...]}``，且一个文件都不写。
    """
    raise NotImplementedError
