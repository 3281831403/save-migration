"""savemig.migrate 的验收测试。

初始状态下本文件 15 条测试全红（全部打到 ``NotImplementedError`` 桩）。
请勿修改本文件：修复只发生在 ``savemig/migrate.py``。

对应关系：前 10 条一一对应题面的 10 个缺陷，后 5 条为组合/契约测试。
"""

import json

import pytest

from savemig.migrate import (
    MigrationError,
    atomic_write,
    checksum,
    compress,
    decompress,
    merge_defaults,
    migrate,
    migrate_batch,
    read_with_recovery,
    validate,
)

V3_SAVE = {
    "version": 3,
    "player": {"name": "Veteran", "health": 80.0, "level": 1},
    "gold": 5,
    "settings": {"music": 0.8, "effects": True},
    "achievements": [],
}


# 缺陷 1：迁移只执行目标版本的步骤，跨两版漏掉中间字段。
def test_migrate_v1_to_v2_renames_hp_to_health():
    save = {"version": 1, "player": {"name": "Veteran", "hp": 80.0}, "gold": 10}
    out = migrate(save, 2)
    assert out["version"] == 2
    assert out["player"] == {"name": "Veteran", "health": 80.0}
    assert out["settings"] == {"music": 0.8, "effects": True}
    assert "achievements" not in out
    # 不得原地修改入参
    assert save == {"version": 1, "player": {"name": "Veteran", "hp": 80.0}, "gold": 10}


# 缺陷 2：缺字段不补默认值，读取方 KeyError。
def test_migrate_fills_missing_fields_with_defaults():
    out = migrate({"version": 1, "player": {"hp": 50.0}, "gold": 7}, 3)
    assert out["player"]["name"] == "anonymous"
    assert out["player"]["health"] == 50.0
    assert out["player"]["level"] == 1
    assert out["gold"] == 7
    assert out["settings"] == {"music": 0.8, "effects": True}
    assert out["achievements"] == []


# 缺陷 3：校验和包含未排序键，同内容不同哈希。
def test_checksum_sorts_nested_keys():
    a = {
        "version": 3,
        "player": {"name": "Veteran", "health": 80.0},
        "settings": {"music": 0.8, "effects": True},
    }
    b = {
        "settings": {"effects": True, "music": 0.8},
        "player": {"health": 80.0, "name": "Veteran"},
        "version": 3,
    }
    digest = checksum(a)
    assert checksum(b) == digest
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)


# 缺陷 4：直接覆盖写，进程中断留下半文件。
def test_atomic_write_has_no_temp_residue(tmp_path):
    path = tmp_path / "save.json"
    atomic_write(path, {"version": 3, "player": {"name": "Veteran", "health": 80.0}})
    # 只留目标文件，没有临时文件残留
    assert [p.name for p in tmp_path.iterdir()] == ["save.json"]
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["version"] == 3


# 缺陷 5：主文件损坏直接抛异常，不读备份。
def test_read_with_recovery_falls_back_to_backup(tmp_path):
    main = tmp_path / "save.json"
    main.write_text('{"version": 3, "player": ', encoding="utf-8")
    backup = tmp_path / "save.json.bak"
    backup.write_text(
        json.dumps({"version": 2, "player": {"name": "Backup", "health": 70.0}}),
        encoding="utf-8",
    )
    recovered = read_with_recovery(main)
    assert recovered["version"] == 2
    assert recovered["player"]["name"] == "Backup"


# 缺陷 6：压缩后不校验版本，旧档被当新档。
def test_compress_roundtrip_and_decompress_checks_version():
    save = {"version": 2, "player": {"name": "Veteran", "health": 80.0}}
    assert decompress(compress(save, 6)) == save
    with pytest.raises(MigrationError):
        decompress(compress({"player": {"name": "Veteran"}}, 6))
    with pytest.raises(MigrationError):
        decompress(compress({"version": 99, "player": {}}, 6))


# 缺陷 7：merge_defaults 覆盖已有值，玩家设置被重置。
def test_merge_defaults_keeps_existing_values():
    save = {
        "player": {"name": "Veteran"},
        "gold": 0,
        "settings": {"music": 0.0, "effects": False},
    }
    defaults = {
        "player": {"name": "anonymous", "level": 1},
        "gold": 100,
        "settings": {"music": 0.8, "effects": True},
        "achievements": [],
    }
    merged = merge_defaults(save, defaults)
    assert merged == {
        "player": {"name": "Veteran", "level": 1},
        "gold": 0,
        "settings": {"music": 0.0, "effects": False},
        "achievements": [],
    }
    # 不修改入参
    assert save == {
        "player": {"name": "Veteran"},
        "gold": 0,
        "settings": {"music": 0.0, "effects": False},
    }


# 缺陷 8：批量迁移边写边迁，失败留半成品。
def test_migrate_batch_failure_writes_nothing(tmp_path):
    good = {"version": 1, "player": {"name": "Good", "hp": 10.0}, "gold": 1}
    bad = {"version": 99, "player": {"name": "Bad"}}
    good_path = tmp_path / "good.json"
    bad_path = tmp_path / "bad.json"
    good_path.write_text(json.dumps(good), encoding="utf-8")
    bad_path.write_text(json.dumps(bad), encoding="utf-8")

    result = migrate_batch({str(good_path): good, str(bad_path): bad}, 3)

    assert result["ok"] is False
    assert result["failed"] == [str(bad_path)]
    # 一条都不许写盘：两个文件都保持原样
    assert json.loads(good_path.read_text(encoding="utf-8")) == good
    assert json.loads(bad_path.read_text(encoding="utf-8")) == bad


# 缺陷 9：浮点字段按字符串比较，1.0 与 1 判定不一致。
def test_validate_treats_int_and_float_alike():
    assert validate(V3_SAVE) == []
    assert validate({**V3_SAVE, "settings": {"music": 1, "effects": True}}) == []
    assert validate({**V3_SAVE, "settings": {"music": 1.0, "effects": True}}) == []
    problems = validate({**V3_SAVE, "settings": {"music": "1.0", "effects": True}})
    assert any("music" in problem for problem in problems)


# 缺陷 10：嵌套默认值不递归，子对象缺键。
def test_merge_defaults_recurses_into_nested_dicts():
    merged = merge_defaults(
        {"settings": {"music": 0.5}},
        {"settings": {"music": 0.8, "effects": True}, "achievements": []},
    )
    assert merged == {
        "settings": {"music": 0.5, "effects": True},
        "achievements": [],
    }


# 组合 1：v1 -> v3 必须经过 v2 的字段改名，且与逐级迁移结果一致。
def test_v1_to_v3_runs_through_v2_rename():
    save = {"version": 1, "player": {"name": "Veteran", "hp": 42.0}, "gold": 3}
    direct = migrate(save, 3)
    stepwise = migrate(migrate(save, 2), 3)
    assert direct == stepwise
    assert direct["version"] == 3
    assert "hp" not in direct["player"]
    assert direct["player"]["health"] == 42.0
    assert "settings" in direct
    assert "achievements" in direct


# 组合 2：checksum 与键顺序无关、确定、且忽略已存的 checksum 字段。
def test_checksum_is_order_independent_and_ignores_stored_checksum():
    first = checksum(V3_SAVE)
    reordered = {
        "achievements": [],
        "settings": {"effects": True, "music": 0.8},
        "gold": 5,
        "player": {"level": 1, "health": 80.0, "name": "Veteran"},
        "version": 3,
    }
    assert checksum(reordered) == first
    assert checksum(V3_SAVE) == first
    assert checksum({**V3_SAVE, "checksum": "0" * 64}) == first
    assert checksum({**V3_SAVE, "gold": 6}) != first


# 组合 3：atomic_write 失败后目录无残留文件。
def test_atomic_write_failure_leaves_no_residue(tmp_path):
    path = tmp_path / "save.json"
    with pytest.raises(MigrationError):
        atomic_write(path, {"version": 3, "bad": {1, 2, 3}})
    assert list(tmp_path.iterdir()) == []


# 组合 4：read_with_recovery 主备都坏时抛 MigrationError。
def test_read_with_recovery_raises_when_both_files_broken(tmp_path):
    main = tmp_path / "save.json"
    main.write_text("not json at all", encoding="utf-8")
    (tmp_path / "save.json.bak").write_text("{broken", encoding="utf-8")
    with pytest.raises(MigrationError):
        read_with_recovery(main)


# 组合 5：批量全成功时返回顺序与输入一致，且逐条落盘。
def test_migrate_batch_preserves_input_order_on_success(tmp_path):
    first = {"version": 1, "player": {"name": "First", "hp": 10.0}, "gold": 1}
    second = {
        "version": 2,
        "player": {"name": "Second", "health": 20.0},
        "gold": 2,
        "settings": {"music": 0.5, "effects": True},
    }
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")

    result = migrate_batch({str(first_path): first, str(second_path): second}, 3)

    assert result["ok"] is True
    assert list(result["saves"]) == [str(first_path), str(second_path)]
    assert result["saves"][str(first_path)]["version"] == 3
    assert result["saves"][str(second_path)]["version"] == 3
    # 迁移结果已落盘
    on_disk = json.loads(second_path.read_text(encoding="utf-8"))
    assert on_disk["version"] == 3
    assert on_disk["settings"]["music"] == 0.5
