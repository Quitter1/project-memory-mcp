"""
生成审阅包 review-pack-phase-{n}.zip。

使用方法：
    python scripts/make_review_pack.py --phase <n> [--test "python -m pytest tests/ -v"]

功能：
1. 生成项目文件树 → progress/tree-phase-{n}.txt
2. 生成 git 状态 → progress/git-status-phase-{n}.txt
3. 生成 git diff → progress/git-diff-phase-{n}.patch
4. 运行指定测试 → progress/test-output-phase-{n}.txt
5. 打包 review-pack-phase-{n}.zip（测试失败时不打包）
6. 自动排除无关目录和缓存文件
"""

import os
import sys
import shlex
import subprocess
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# 排除的目录
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "data", "qdrant", "node_modules", "dist", "build",
    ".idea", ".vscode",
    "*.egg-info", "src/*.egg-info",
}

# 排除的扩展名
EXCLUDE_EXTS = {".pyc", ".pyo", ".db", ".db-journal", ".db-wal", ".log"}

# 排除的根目录文件
EXCLUDE_ROOT_FILES = {"review-pack-phase-"}


def run_cmd(cmd_str: str) -> tuple[int, str, str]:
    """运行命令，返回 (returncode, stdout, stderr)。"""
    # Windows 下用 shell=True 保证 pytest 等工具可用
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        cmd_str,
        cwd=PROJECT_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        env=env,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def generate_tree(phase: int) -> Path:
    """生成项目文件树。"""
    rc, stdout, _ = run_cmd("git ls-files --cached --others --exclude-standard")
    if rc != 0:
        stdout = "(git 命令失败，使用目录扫描)\n"

    lines = []
    for line in sorted(stdout.strip().split("\n")):
        if not line:
            continue
        parts = Path(line).parts
        if not parts:
            continue
        top = parts[0]
        if top in EXCLUDE_DIRS:
            continue
        if any(line.endswith(ext) for ext in EXCLUDE_EXTS):
            continue
        lines.append(line)

    out_path = PROJECT_ROOT / "progress" / f"tree-phase-{phase}.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_git_status(phase: int) -> Path:
    """生成 git 状态文件。"""
    _, stdout, _ = run_cmd("git status")
    out_path = PROJECT_ROOT / "progress" / f"git-status-phase-{phase}.txt"
    out_path.write_text(stdout, encoding="utf-8")
    return out_path


def generate_git_diff(phase: int) -> Path:
    """生成 git diff patch。"""
    out_path = PROJECT_ROOT / "progress" / f"git-diff-phase-{phase}.patch"

    # 先检查是否有 commit
    rc, _, _ = run_cmd("git rev-parse HEAD")
    has_commits = (rc == 0)

    if has_commits:
        _, stdout, _ = run_cmd("git diff --staged")
        if not stdout.strip():
            _, stdout, _ = run_cmd("git diff")
            if not stdout.strip():
                stdout = (
                    "(无 diff — 所有变更已提交，且工作区干净)\n"
                )
    else:
        stdout = (
            "当前仓库无 commit。untracked 文件不会出现在 git diff 中。\n"
            "完整源码已包含在 review-pack zip 内，请直接查看 src/ 目录。\n"
        )

    out_path.write_text(stdout, encoding="utf-8")
    return out_path


def run_tests(phase: int, test_cmd: str) -> tuple[bool, Path]:
    """运行测试并保存输出。返回 (passed, output_path)。"""
    out_path = PROJECT_ROOT / "progress" / f"test-output-phase-{phase}.txt"

    if not test_cmd:
        out_path.write_text("(未指定测试命令)", encoding="utf-8")
        return True, out_path

    # Windows 下 pytest 可能不在 PATH，统一用 python -m pytest
    if test_cmd.startswith("pytest"):
        test_cmd = "python -m " + test_cmd

    print(f"  运行: {test_cmd}")
    rc, stdout, stderr = run_cmd(test_cmd)
    output = stdout + "\n" + stderr
    out_path.write_text(output, encoding="utf-8")

    if rc != 0:
        print(f"  测试失败 (exit={rc})，已保存输出到 {out_path}")
        return False, out_path

    print(f"  测试通过")
    return True, out_path


def create_zip(phase: int) -> tuple[Path, int]:
    """打包 review-pack-phase-{n}.zip。返回 (path, file_count)。"""
    review_dir = PROJECT_ROOT / "reviews"
    review_dir.mkdir(exist_ok=True)
    zip_path = review_dir / f"review-pack-phase-{phase}.zip"
    # 移走上一次的同名 zip 到备份
    backup_dir = review_dir / "backups"
    backup_dir.mkdir(exist_ok=True)
    if zip_path.exists():
        import shutil
        shutil.move(str(zip_path), str(backup_dir / f"review-pack-phase-{phase}-old.zip"))
    count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # 过滤目录
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDE_DIRS
                and not d.startswith(".")
                and not d.endswith(".egg-info")
            ]

            for fname in files:
                # 过滤扩展名
                if any(fname.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                if fname.endswith(".pyc"):
                    continue
                # 过滤隐藏文件（保留 .gitignore）
                if fname.startswith(".") and fname != ".gitignore":
                    continue

                full_path = Path(root) / fname
                rel_path = str(full_path.relative_to(PROJECT_ROOT))

                # 排除根目录的 review-pack
                if any(rel_path.startswith(prefix) for prefix in EXCLUDE_ROOT_FILES):
                    continue

                parts = Path(rel_path).parts
                if len(parts) == 0:
                    continue

                top = parts[0]
                allowed_tops = {
                    "README.md", "CLAUDE.md", "pyproject.toml", ".gitignore",
                    "config", "docs", "src", "tests", "scripts", "progress", "sandbox",
                }
                if top not in allowed_tops:
                    continue

                zf.write(full_path, rel_path)
                count += 1

    return zip_path, count


def main():
    """主入口。"""
    phase = 0
    test_cmd = ""

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--phase" and i + 1 < len(args):
            phase = int(args[i + 1])
            i += 2
        elif args[i] == "--test" and i + 1 < len(args):
            test_cmd = args[i + 1]
            i += 2
        else:
            i += 1

    if phase <= 0:
        print("用法: python scripts/make_review_pack.py --phase <n> [--test \"...\"]")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"生成 Phase {phase} 审阅包")
    print(f"{'='*60}\n")

    # 确保 progress 目录存在
    (PROJECT_ROOT / "progress").mkdir(exist_ok=True)

    # 检查阶段 summary 是否存在
    summary_path = PROJECT_ROOT / "progress" / f"phase-{phase}-summary.md"
    if not summary_path.exists():
        print(f"错误: 缺少阶段 summary 文件: {summary_path}")
        print("请先创建 progress/phase-{phase}-summary.md")
        sys.exit(1)

    # 1-3: 生成辅助文件
    print("[1/5] 生成文件树...")
    tree_path = generate_tree(phase)
    print(f"  {tree_path}")

    print("[2/5] 生成 git 状态...")
    status_path = generate_git_status(phase)
    print(f"  {status_path}")

    print("[3/5] 生成 git diff...")
    diff_path = generate_git_diff(phase)
    print(f"  {diff_path}")

    # 4: 运行测试
    print("[4/5] 运行测试...")
    passed, test_path = run_tests(phase, test_cmd)

    if not passed:
        print(f"\n测试未通过，不生成审阅包。")
        print(f"测试输出: {test_path}")
        sys.exit(1)

    # 5: 打包
    print("[5/5] 打包 zip...")
    zip_path, count = create_zip(phase)

    print(f"\n审阅包: {zip_path}")
    print(f"包含文件数: {count}")
    print(f"完成!")


if __name__ == "__main__":
    main()
