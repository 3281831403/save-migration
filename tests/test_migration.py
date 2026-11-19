import pytest

from save import migration as mod

CASES = [
    ('version_chain', [1, 4], [2, 3, 4], False),
    ('version_chain', [4, 1], [], False),
    ('checksum', [{'a': 1}], '42248c8a0e0e4bfc', False),
    ('migrate_field', ['old_name', {'old_name': 'new_name'}], 'new_name', False),
    ('migrate_field', ['keep', {'old_name': 'new_name'}], 'keep', False),
    ('atomic_swap', [True, 'save.dat'], 'save.dat', False),
    ('atomic_swap', [False, 'save.dat'], None, False),
    ('backup_policy', [5, 2], [3, 4], False),
    ('downgrade_check', [2, 3], True, False),
    ('downgrade_check', [4, 3], False, False),
    ('schema_diff', [['a', 'b'], ['b', 'c']], ['a', 'c'], False),
    ('partial_merge', [{'a': 1, 'b': 2}, {'b': 3}], {'a': 1, 'b': 3}, False),
    ('validate_version', [2, [1, 2, 3]], True, False),
    ('validate_version', [4, [1, 2, 3]], False, False),
    ('commit_save', [[True, True]], True, False),
]


@pytest.mark.parametrize("func_name,args,expected,approx", CASES)
def test_migration_contract(func_name, args, expected, approx):
    func = getattr(mod, func_name)
    result = func(*args)
    if approx:
        assert result == pytest.approx(expected)
    else:
        assert result == expected
