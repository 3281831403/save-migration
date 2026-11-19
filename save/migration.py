"""存档迁移：版本链、校验与原子替换：核心实现。"""

import hashlib


def version_chain(from_version, to_version):
    """版本链逐级递增。

    返回从 ``from_version`` 的下一版开始、到 ``to_version``（含）为止的
    逐级版本号列表。降级或版本相同时返回空列表，绝不跳级。
    """
    if to_version <= from_version:
        return []
    return list(range(from_version + 1, to_version + 1))


def _canonical(data):
    """把嵌套结构规范化：字典按键排序，稳定 ``repr`` 结果。"""
    if isinstance(data, dict):
        return {key: _canonical(data[key]) for key in sorted(data, key=repr)}
    if isinstance(data, list):
        return [_canonical(item) for item in data]
    if isinstance(data, tuple):
        return tuple(_canonical(item) for item in data)
    return data


def checksum(data):
    """校验和确定性。

    对规范化后的 ``repr`` 计算 SHA-1，取前 16 个十六进制字符。同一份
    数据无论字典键的插入顺序如何、运行多少次，都得到相同结果，不依赖
    进程级随机化。
    """
    digest = hashlib.sha1(repr(_canonical(data)).encode("utf-8")).hexdigest()
    return digest[:16]


def migrate_field(field, mapping):
    """字段改名按映射。

    字段名在 ``mapping`` 中时返回映射后的新名字，否则原样返回。
    """
    return mapping.get(field, field)


def atomic_swap(temp_exists, target):
    """临时文件存在才替换。

    只有临时文件写入成功后才把目标路径交还给调用方；临时文件缺失时
    返回 ``None``，不触碰原存档。
    """
    if not temp_exists:
        return None
    return target


def backup_policy(version, keep):
    """保留前 N 个版本。

    返回当前版本之前最近的 ``keep`` 个版本号（不含当前版本）。
    版本号从 1 开始，不会返回无效的非正版本号。
    """
    start = max(1, version - keep)
    return list(range(start, version))


def downgrade_check(from_version, to_version):
    """降级方向判断。

    目标版本不低于当前版本时返回 ``True``（不是降级）；否则为降级，
    返回 ``False``。
    """
    return to_version >= from_version


def schema_diff(old_keys, new_keys):
    """schema 差异对称。

    返回两个键集合的对称差，排序后给出，双边新增与缺失的键都不会漏掉。
    """
    return sorted(set(old_keys) ^ set(new_keys))


def partial_merge(base, patch):
    """局部补丁合并。

    以 ``base`` 为底、用 ``patch`` 覆盖同名字段，未出现在补丁中的键保持
    原值，不会丢字段。
    """
    merged = dict(base)
    merged.update(patch)
    return merged


def validate_version(version, supported):
    """版本白名单校验。"""
    return version in supported


def commit_save(statuses):
    """批量存档全部成功才提交。

    所有存档步骤都成功时才返回 ``True``；任意一步失败即整体不提交。
    """
    return all(statuses)
