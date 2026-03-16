#!/usr/bin/env python3
"""
禅道任务发布 MCP Server

工具列表:
  zentao_publish_yaml   - 从 YAML 字符串发布任务（创建/更新）
  zentao_list_tasks     - 列出执行下的任务
  zentao_list_executions - 列出所有执行/迭代
  zentao_list_users     - 列出所有用户
"""

import io
import os
import sys

import yaml
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# 项目根目录加入 path，保证能 import zentao_client / publish
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from zentao_client import ZentaoClient
import publish as pub

mcp = FastMCP("禅道任务管理")


def _client() -> ZentaoClient:
    url = os.environ["ZENTAO_URL"]
    account = os.environ.get("ZENTAO_ACCOUNT") or os.environ["ZENTAO_USER"]
    password = os.environ.get("ZENTAO_PASSWORD") or os.environ["ZENTAO_PASS"]
    c = ZentaoClient(url, account, password)
    c.login()
    c.login_web()
    return c


# ── 工具定义 ──────────────────────────────────────────


@mcp.tool()
def zentao_list_executions() -> str:
    """列出禅道所有执行/迭代（Sprint），返回 ID、名称、状态、起止日期"""
    client = _client()
    rows = []
    for e in client.list_executions():
        rows.append(
            f"ID={e.get('id')}  [{e.get('status')}]  {e.get('name')}  "
            f"{e.get('begin')} ~ {e.get('end')}"
        )
    return "\n".join(rows) if rows else "无执行记录"


@mcp.tool()
def zentao_list_users() -> str:
    """列出禅道所有用户账号，用于填写 assignedTo 字段"""
    client = _client()
    rows = []
    for u in client.list_users():
        rows.append(f"{u.get('account')}  {u.get('realname')}  ({u.get('role')})")
    return "\n".join(rows) if rows else "无用户"


@mcp.tool()
def zentao_list_tasks(execution_id: int) -> str:
    """列出指定执行下的所有任务

    Args:
        execution_id: 执行/迭代 ID（可先用 zentao_list_executions 查询）
    """
    client = _client()
    tasks = client.list_tasks(execution_id)
    rows = []
    for t in tasks:
        assigned = t.get("assignedTo", "")
        if isinstance(assigned, dict):
            assigned = assigned.get("realname") or assigned.get("account", "?")
        rows.append(
            f"ID={t.get('id')}  [{t.get('status')}] P{t.get('pri')}  "
            f"{t.get('name')}  -> {assigned or '未指派'}"
        )
    return "\n".join(rows) if rows else f"执行 #{execution_id} 无任务"


@mcp.tool()
def zentao_publish_yaml(yaml_content: str, dry_run: bool = False) -> str:
    """从 YAML 内容发布任务到禅道（创建或更新）

    YAML 格式示例：
      execution: 5
      defaults:
        type: devel
        assignedTo: ckx
        pri: 2
        estStarted: "2026-03-16"
        deadline: "2026-03-18"
      tasks:
        - name: "任务名称"
          estimate: 2
          desc: |
            <h3>描述</h3>
            <p>内容</p>
          videos:
            - /path/to/recording.mp4
          images:
            - path: /path/to/screenshot.jpg
              label: 截图说明

    支持字段：
      - id: 有则更新，无则创建
      - close: 关闭任务（填写关闭原因）
      - videos: 视频文件路径列表（附件可在禅道直接下载）
      - images: 图片文件路径列表（嵌入任务描述）

    Args:
        yaml_content: YAML 格式的任务定义字符串
        dry_run: True 时只预览不执行（默认 False）
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"YAML 解析失败: {e}"

    if not data or not data.get("tasks"):
        return "错误: YAML 中未找到 tasks 字段"

    if dry_run:
        # 预览模式：捕获 stdout
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            pub.preview(data, "<inline>")
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    # 执行模式
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        pub.execute(data, "<inline>")
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


if __name__ == "__main__":
    mcp.run(transport="stdio")
