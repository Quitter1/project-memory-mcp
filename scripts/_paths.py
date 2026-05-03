"""scripts 公共路径 helper — 所有脚本统一使用。

用法：
    import _paths
    _paths.ensure_import_paths()
    config_dir, db_path = _paths.get_project_paths()

路径策略与 server.py 一致：
    1. 两个 ENV 都设置 → 分别使用
    2. 只设 CONFIG_DIR → db 跟随 config 所在项目根
    3. 只设 DB_PATH → config 跟随 db 所在项目根
    4. 都没设 → 项目根下 config/ + data/memory.db
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_import_paths():
    _src = _PROJECT_ROOT / "src"
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))


def get_project_paths() -> tuple[Path, Path]:
    env_config = os.environ.get("PROJECT_MEMORY_CONFIG_DIR")
    env_db = os.environ.get("PROJECT_MEMORY_DB_PATH")

    # 两个都设置
    if env_config and env_db:
        c = Path(env_config)
        d = Path(env_db)
        d.parent.mkdir(parents=True, exist_ok=True)
        return c, d

    # 只设 config_dir
    if env_config:
        c = Path(env_config)
        root = c.parent if c.name == "config" else c
        d = root / "data" / "memory.db"
        d.parent.mkdir(parents=True, exist_ok=True)
        return c, d

    # 只设 db_path
    if env_db:
        d = Path(env_db)
        root = d.parent.parent if d.parent.name == "data" else d.parent
        d.parent.mkdir(parents=True, exist_ok=True)
        return root / "config", d

    # 默认：项目根
    d = _PROJECT_ROOT / "data" / "memory.db"
    d.parent.mkdir(parents=True, exist_ok=True)
    return _PROJECT_ROOT / "config", d
