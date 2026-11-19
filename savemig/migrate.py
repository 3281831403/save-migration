"""存档版本迁移核心模块。

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

import hashlib
import json
import os
import tempfile
import zlib

SUPPORTED_VERSIONS = (1, 2, 3)

# 各版本引入字段的默认值（嵌套结构按版本逐级补齐）。
V1_DEFAULTS = {
    "gold": 0,
    "player": {"name": "anonymous", "hp": 100.0},
}
V2_DEFAULTS = {
    "player": {"health": 100.0},
    "settings": {"music": 0.8, "effects": True},
}
V3_DEFAULTS = {
    "achievements": [],
    "player": {"level": 1},
}


class MigrationError(Exception):
    """存档读取、校验、压缩或迁移失败时抛出的异常。"""


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _is_supported_version(value) -> bool:
    """版本号必须是 int（bool 不算）且在支持范围内。"""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value in SUPPORTED_VERSIONS
    )


def _is_number(value) -> bool:
    """数字判定：int/float 都算，但 ``bool`` 不算（不做字符串比较）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clone(value):
    """对 JSON 兼容数据做深拷贝，避免迁移过程修改入参。"""
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value


def _ensure_player(data: dict) -> dict:
    player = data.get("player")
    if player is None:
        player = {}
        data["player"] = player
    elif not isinstance(player, dict):
        raise MigrationError("player 必须是 dict")
    return player


def _ensure_settings(data: dict) -> dict:
    settings = data.get("settings")
    if settings is None:
        settings = {}
        data["settings"] = settings
    elif not isinstance(settings, dict):
        raise MigrationError("settings 必须是 dict")
    return settings


# ---------------------------------------------------------------------------
# 版本链逐级迁移
# ---------------------------------------------------------------------------

def _apply_v1_defaults(data: dict) -> None:
    """补齐 v1 引入的缺失字段：gold、player.name、player.hp。"""
    if "gold" not in data:
        data["gold"] = V1_DEFAULTS["gold"]
    player = _ensure_player(data)
    if "name" not in player:
        player["name"] = V1_DEFAULTS["player"]["name"]
    if "hp" not in player:
        player["hp"] = V1_DEFAULTS["player"]["hp"]


def _migrate_v1_to_v2(data: dict) -> None:
    """v1 -> v2：player.hp 改名为 player.health，引入 settings。"""
    player = _ensure_player(data)
    if "hp" in player:
        # 改名：已有 health 时保留 health，hp 仍然移除。
        player.setdefault("health", player.pop("hp"))
    player.pop("hp", None)
    if "health" not in player:
        player["health"] = V2_DEFAULTS["player"]["health"]

    settings = _ensure_settings(data)
    if "music" not in settings:
        settings["music"] = V2_DEFAULTS["settings"]["music"]
    if "effects" not in settings:
        settings["effects"] = V2_DEFAULTS["settings"]["effects"]

    data["version"] = 2


def _migrate_v2_to_v3(data: dict) -> None:
    """v2 -> v3：引入 achievements 与 player.level。"""
    if "achievements" not in data:
        data["achievements"] = list(V3_DEFAULTS["achievements"])
    player = _ensure_player(data)
    if "level" not in player:
        player["level"] = V3_DEFAULTS["player"]["level"]

    data["version"] = 3


_STEPS = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
}


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
    if not isinstance(save, dict):
        raise MigrationError("存档必须是 JSON 对象")
    if "version" not in save:
        raise MigrationError("存档缺少 version 字段")
    current_version = save["version"]
    if not _is_supported_version(current_version):
        raise MigrationError(f"不支持的存档版本: {current_version!r}")
    if not _is_supported_version(target_version):
        raise MigrationError(f"不支持的目标版本: {target_version!r}")
    if target_version < current_version:
        raise MigrationError(
            f"不能降级迁移: {current_version} -> {target_version}"
        )

    data = _clone(save)

    # 先补齐当前版本（v1）自身的缺失默认值。
    if current_version == 1:
        _apply_v1_defaults(data)

    # 沿版本链逐级执行，跨级时中间一步都不能漏。
    for version in range(current_version, target_version):
        _STEPS[version](data)

    data["version"] = target_version
    return data


# ---------------------------------------------------------------------------
# 校验与校验和
# ---------------------------------------------------------------------------

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
    problems: list[str] = []
    if not isinstance(save, dict):
        return ["存档顶层必须是 JSON 对象"]

    if "version" not in save:
        problems.append("version 字段缺失")
        version = None
    elif not _is_supported_version(save["version"]):
        problems.append(f"version 非法或不受支持: {save['version']!r}")
        version = None
    else:
        version = save["version"]

    player = save.get("player")
    if not isinstance(player, dict):
        problems.append("player 不是 dict")
        player = None

    if player is not None and version in (2, 3):
        if "health" not in player:
            problems.append("player.health 字段缺失")
        elif not _is_number(player["health"]):
            problems.append("player.health 不是数字（bool 不算数字）")

    settings = save.get("settings")
    if version in (2, 3):
        if not isinstance(settings, dict):
            if settings is not None:
                problems.append("settings 不是 dict")
        elif "music" not in settings:
            problems.append("settings.music 字段缺失")
        elif not _is_number(settings["music"]):
            problems.append("settings.music 不是数字（bool 不算数字）")

    if version == 3:
        if "achievements" not in save:
            problems.append("achievements 字段缺失")
        elif not isinstance(save["achievements"], list):
            problems.append("achievements 不是 list")

    if "checksum" in save and save["checksum"] != checksum(save):
        problems.append("checksum 与存档内容不一致")

    return problems


def checksum(save: dict) -> str:
    """对 ``save`` 的规范化 JSON 取 sha256，返回 64 位小写十六进制字符串。

    规范化：``json.dumps(..., sort_keys=True, separators=(",", ":"),
    ensure_ascii=False)``，浮点统一按其 ``repr`` 形式参与序列化；
    顶层 ``checksum`` 字段不参与计算，因此 :func:`validate` 可以核对
    写盘前存下的校验和。同一内容、不同键顺序必须得到同一哈希。
    """
    payload = {key: value for key, value in save.items() if key != "checksum"}
    # json 对 float 直接使用 float.__repr__（最短往返表示），
    # sort_keys 递归排序所有层级的键，保证同内容同哈希。
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 原子写盘与备份回退
# ---------------------------------------------------------------------------

def atomic_write(path, data: dict) -> None:
    """原子地把 ``data``（dict，写成 JSON）保存到 ``path``。

    * ``path`` 可以是 str 或 pathlib.Path；
    * 先写同目录临时文件，再用 ``os.replace`` 覆盖目标；
    * 写入成功后目录里只剩目标文件，不残留临时文件；
    * 序列化失败（例如 data 含 set）或写入失败时删除临时文件、
      保留原有目标文件（若存在），并抛 ``MigrationError``：绝不留半文件。
    """
    target = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(target))

    # 先序列化：失败时连临时文件都不会创建，原文件不受影响。
    try:
        payload = json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise MigrationError(f"存档序列化失败: {exc}") from exc

    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=".savemig-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise MigrationError(f"存档写入失败: {exc}") from exc


def _load_json_object(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise MigrationError(f"存档顶层不是 JSON 对象: {path}")
    return data


def read_with_recovery(path) -> dict:
    """读取存档 JSON；主文件损坏时回退到备份 ``<path>.bak``。

    * ``path`` 可以是 str 或 pathlib.Path；返回读取到的 dict；
    * 主文件缺失、不是合法 JSON、或顶层不是 JSON 对象时，尝试读取
      备份文件（原路径加上 ``.bak`` 后缀）；
    * 主文件和备份都不可用时抛 ``MigrationError``。
    """
    main_path = os.fspath(path)
    try:
        return _load_json_object(main_path)
    except (OSError, json.JSONDecodeError, MigrationError):
        pass

    backup_path = main_path + ".bak"
    try:
        return _load_json_object(backup_path)
    except (OSError, json.JSONDecodeError, MigrationError) as exc:
        raise MigrationError(
            f"主文件与备份均不可用: {main_path}"
        ) from exc


# ---------------------------------------------------------------------------
# 压缩 / 解压
# ---------------------------------------------------------------------------

def compress(save: dict, level: int = 6) -> bytes:
    """把 ``save`` 序列化为 JSON 后用 zlib 压缩，返回 bytes。

    ``level`` 原样传给 ``zlib.compress``。语义上必须能与
    :func:`decompress` 往返，得到相等的内容。
    """
    payload = json.dumps(save, ensure_ascii=False).encode("utf-8")
    return zlib.compress(payload, level)


def decompress(raw: bytes) -> dict:
    """``compress`` 的逆操作：zlib 解压 + JSON 解析，返回 dict。

    * 解压失败或 JSON 解析失败时抛 ``MigrationError``；
    * 解压结果必须校验版本：缺少 ``version`` 或 ``version`` 不在 {1, 2, 3}
      时抛 ``MigrationError``，旧档不得被当成新档使用。
    """
    try:
        data = json.loads(zlib.decompress(raw).decode("utf-8"))
    except (zlib.error, json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise MigrationError(f"压缩存档解析失败: {exc}") from exc

    if not isinstance(data, dict) or not _is_supported_version(
        data.get("version")
    ):
        raise MigrationError("解压结果缺少合法 version，存档版本不受支持")
    return data


# ---------------------------------------------------------------------------
# 默认值合并与批量迁移
# ---------------------------------------------------------------------------

def merge_defaults(save: dict, defaults: dict) -> dict:
    """把 ``defaults`` 中 ``save`` 缺失的键补进去，返回新的 dict。

    * 只补缺失键，已有值（包括 ``0``、``""``、``False``、``None``）一律保留；
    * ``defaults`` 里是 dict 的键递归合并，子对象缺键也要补上；
    * 不修改传入的 ``save`` 与 ``defaults``。
    """
    merged = dict(save)
    for key, default_value in defaults.items():
        if key not in merged:
            # 深拷贝默认值，避免多个存档共享同一个 list/dict。
            merged[key] = _clone(default_value)
        elif isinstance(merged[key], dict) and isinstance(default_value, dict):
            merged[key] = merge_defaults(merged[key], default_value)
    return merged


def migrate_batch(saves: dict[str, dict], target_version: int) -> dict:
    """批量迁移并落盘：全部成功才写，任何一条失败都不写。

    ``saves`` 是 ``{文件路径: 存档 dict}``，按插入顺序逐条 :func:`migrate`，
    全部成功后再用 :func:`atomic_write` 写回各自路径（不得边迁边写）。

    * 全部成功：``{"ok": True, "saves": {路径: 迁移后的存档, ...}}``，
      返回的键顺序与 ``saves`` 的插入顺序一致；
    * 任意一条迁移失败（抛 ``MigrationError``）：
      ``{"ok": False, "failed": [失败的路径, ...]}``，且一个文件都不写。
    """
    migrated: dict[str, dict] = {}
    failed: list[str] = []

    # 第一阶段：只迁移、不落盘，收集全部结果与失败路径。
    for path, save in saves.items():
        try:
            migrated[path] = migrate(save, target_version)
        except MigrationError:
            failed.append(path)

    if failed:
        return {"ok": False, "failed": failed}

    # 第二阶段：全部迁移成功后才逐条原子落盘。
    for path, data in migrated.items():
        atomic_write(path, data)

    return {"ok": True, "saves": migrated}
