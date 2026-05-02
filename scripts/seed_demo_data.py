"""
填充演示数据。

使用方法：
    python scripts/seed_demo_data.py [--project-id biaopai-erp] [--all]

为指定项目（或全部项目）创建示例知识条目，方便开发调试。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    """填充演示数据。"""
    # TODO: 阶段 6 实现
    print("演示数据填充脚本 — 阶段 6 实现")
    print("使用方法: python scripts/seed_demo_data.py [--project-id <id>] [--all]")


if __name__ == "__main__":
    main()
