"""savemig —— 老玩家存档迁移库（初始为桩实现，见 :mod:`savemig.migrate`）。"""

from .migrate import MigrationError

__all__ = ["MigrationError"]
__version__ = "0.1.0"
