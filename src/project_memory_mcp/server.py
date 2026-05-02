"""
MCP Server — 工具注册 + 参数校验 + 业务分发

基于 MCP Python SDK FastMCP 实现，不手写 JSON-RPC 协议层。
日志全部写 stderr，stdout 由 MCP SDK 管理。

注意：此文件是结构骨架，实际实现需根据已安装的 mcp 包版本调整 API。
当前基于 mcp==1.27.0 的 FastMCP。
"""

from pathlib import Path


def _get_config_dir() -> Path:
    """获取配置文件目录。"""
    return Path(__file__).parent.parent.parent / "config"


def create_and_run_server() -> None:
    """
    创建 FastMCP 实例、注册工具、启动 stdio server。
    具体实现在阶段 5 完成。
    """
    # TODO: 阶段 5 实现
    pass
