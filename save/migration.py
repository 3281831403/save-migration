"""存档迁移：版本链、校验与原子替换：待实现的核心模块。"""


def version_chain(from_version, to_version):
    """版本链逐级递增。"""
    raise NotImplementedError

def checksum(data):
    """校验和确定性。"""
    raise NotImplementedError

def migrate_field(field, mapping):
    """字段改名按映射。"""
    raise NotImplementedError

def atomic_swap(temp_exists, target):
    """临时文件存在才替换。"""
    raise NotImplementedError

def backup_policy(version, keep):
    """保留前 N 个版本。"""
    raise NotImplementedError

def downgrade_check(from_version, to_version):
    """降级方向判断。"""
    raise NotImplementedError

def schema_diff(old_keys, new_keys):
    """schema 差异对称。"""
    raise NotImplementedError

def partial_merge(base, patch):
    """局部补丁合并。"""
    raise NotImplementedError

def validate_version(version, supported):
    """版本白名单校验。"""
    raise NotImplementedError

def commit_save(statuses):
    """批量存档全部成功才提交。"""
    raise NotImplementedError
