#!/usr/bin/env python3
"""
禅道任务统一发布器

用法:
  # 预览任务 (dry-run)
  python publish.py tasks/kanban_bugs.yaml

  # 创建任务
  python publish.py tasks/kanban_bugs.yaml --execute

  # 更新已有任务 (YAML中需有id字段)
  python publish.py tasks/bugfix_update.yaml --execute

  # 覆盖执行ID
  python publish.py tasks/xxx.yaml --execute --execution 5

  # 强制创建 (不检查同名去重)
  python publish.py tasks/xxx.yaml --execute --force

  # 查看执行/任务/用户列表
  python publish.py --list-executions
  python publish.py --list-tasks 5
  python publish.py --list-users

YAML 格式:
  execution: 5
  defaults:              # 可选, 任务默认值
    type: devel
    assignedTo: ckx
    pri: 2
  tasks:
    - name: 任务名称
      estimate: 2
      desc: |
        <h3>描述</h3>
        <p>内容</p>
      images:
        - path: /path/to/screenshot.jpg
          label: 截图说明
      videos:
        - /path/to/recording.mp4
"""

import argparse
import os
import sys

import yaml
from dotenv import load_dotenv
from zentao_client import ZentaoClient


def get_client() -> ZentaoClient:
    load_dotenv()
    url = os.getenv("ZENTAO_URL")
    account = os.getenv("ZENTAO_ACCOUNT")
    password = os.getenv("ZENTAO_PASSWORD")
    if not all([url, account, password]):
        print("错误: 请在 .env 文件中配置 ZENTAO_URL, ZENTAO_ACCOUNT, ZENTAO_PASSWORD")
        sys.exit(1)
    client = ZentaoClient(url, account, password)
    client.login()
    client.login_web()  # 获取 zentaosid cookie，视频 web 表单上传必须
    return client


# ── 查询命令 ──────────────────────────────────────────

def cmd_list_executions(client: ZentaoClient):
    print("\n=== 执行/迭代列表 ===")
    for e in client.list_executions():
        print(f"  ID: {e.get('id')}  {e.get('name')}  [{e.get('status')}]  {e.get('begin')} ~ {e.get('end')}")


def cmd_list_tasks(client: ZentaoClient, execution_id: int):
    print(f"\n=== 执行 #{execution_id} 的任务列表 ===")
    tasks = client.list_tasks(execution_id)
    for t in tasks:
        assigned = t.get("assignedTo", "")
        if isinstance(assigned, dict):
            assigned = assigned.get("realname") or assigned.get("account", "?")
        print(f"  ID: {t.get('id')}  [{t.get('status')}] P{t.get('pri')} {t.get('name')}  -> {assigned or '未指派'}")
    print(f"\n  共 {len(tasks)} 个任务")


def cmd_list_users(client: ZentaoClient):
    print("\n=== 用户列表 ===")
    for u in client.list_users():
        print(f"  {u.get('account')}  {u.get('realname')}  ({u.get('role')})")


# ── YAML 解析 ────────────────────────────────────────

def load_tasks_yaml(yaml_file: str) -> dict:
    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        print(f"错误: YAML 文件为空: {yaml_file}")
        sys.exit(1)
    return data


def resolve_path(path: str, base_dir: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def apply_defaults(task: dict, defaults: dict) -> dict:
    """用 defaults 填充 task 中缺失的字段"""
    merged = dict(defaults)
    merged.update(task)
    return merged


# ── 描述构建 ─────────────────────────────────────────

def build_desc(task_def: dict, image_infos: list, video_infos: list) -> str:
    """构建任务描述 HTML, 嵌入带标签的图片和视频链接"""
    parts = []

    # 基础描述文本
    desc = task_def.get("desc", "")
    if desc:
        parts.append(desc.strip())

    # 嵌入图片 (带标签)
    images_def = task_def.get("images", [])
    for img_def, info in zip(images_def, image_infos):
        label = img_def.get("label", "") if isinstance(img_def, dict) else ""
        url = info.get("url", "")
        fid = info.get("id", "")
        ext = ZentaoClient._get_file_ext(info)
        if label:
            parts.append(f'<p><b>{label}</b></p>')
        parts.append(f'<p><img src="{url}" alt="{fid}.{ext}" /></p>')

    # 视频提示
    if video_infos:
        parts.append("<h3>视频附件</h3>\n<p>见任务附件</p>")

    return "\n".join(parts)


# ── 预览 ─────────────────────────────────────────────

def preview(data: dict, yaml_file: str):
    defaults = data.get("defaults", {})
    tasks = data.get("tasks", [])
    execution = data.get("execution", "?")
    base_dir = os.path.dirname(os.path.abspath(yaml_file))

    print("=" * 60)
    print(f"  预览: {os.path.basename(yaml_file)}")
    print(f"  执行: #{execution}    任务数: {len(tasks)}")
    print("=" * 60)

    for i, t in enumerate(tasks, 1):
        t = apply_defaults(t, defaults)
        task_id = t.get("id")
        mode = "更新" if task_id else "创建"

        print(f"\n--- {mode} 任务 {i} ---")
        if task_id:
            print(f"  ID:     {task_id}")
        print(f"  名称:   {t.get('name', '?')}")
        print(f"  指派:   {t.get('assignedTo', '?')}")
        print(f"  优先级: P{t.get('pri', '?')}")
        print(f"  工时:   {t.get('estimate', '?')}h")
        print(f"  截止:   {t.get('deadline', '?')}")

        # 图片
        images = t.get("images", [])
        if images:
            print(f"  图片:   {len(images)} 张")
            for img in images:
                path = img.get("path", img) if isinstance(img, dict) else img
                path = resolve_path(path, base_dir)
                ok = "OK" if os.path.exists(path) else "NOT FOUND"
                print(f"    [{ok}] {os.path.basename(path)}")

        # 视频
        videos = t.get("videos", [])
        if videos:
            print(f"  视频:   {len(videos)} 个")
            for vid in videos:
                vid = resolve_path(vid, base_dir)
                ok = "OK" if os.path.exists(vid) else "NOT FOUND"
                print(f"    [{ok}] {os.path.basename(vid)}")

        # 关闭
        close = t.get("close")
        if close:
            print(f"  操作:   关闭 (原因: {close})")

    print(f"\n运行 'python publish.py {yaml_file} --execute' 执行")


# ── 执行 ─────────────────────────────────────────────

def execute(data: dict, yaml_file: str, execution_override: int = None, force: bool = False):
    defaults = data.get("defaults", {})
    tasks = data.get("tasks", [])
    execution = execution_override or data.get("execution")
    base_dir = os.path.dirname(os.path.abspath(yaml_file))

    if not execution:
        print("错误: 未指定 execution, 请在 YAML 或 --execution 参数中提供")
        sys.exit(1)

    client = get_client()

    # 去重: 加载已有任务
    existing_map = {}
    if not force:
        existing_tasks = client.list_tasks(execution)
        existing_map = {t["name"]: t for t in existing_tasks}

    success = 0
    failed = 0

    for i, t in enumerate(tasks, 1):
        t = apply_defaults(t, defaults)
        t.setdefault("execution", execution)  # web 表单上传视频时需要 execution 字段
        task_id = t.get("id")
        name = t.get("name", f"任务{i}")

        print(f"\n{'='*60}")

        # ── 变更状态 (status 字段直接设置) ──
        new_status = t.get("status")
        if new_status and task_id:
            print(f"  变更任务 ID {task_id} 状态为 {new_status}: {name}")
            try:
                client.update_task(task_id, {"status": new_status})
                print(f"  OK 已变更为 {new_status}")
                success += 1
            except Exception as e:
                print(f"  FAIL: {e}")
                failed += 1
            continue

        # ── 关闭任务 (close 字段映射到对应状态) ──
        close_reason = t.get("close")
        if close_reason and task_id:
            status_map = {
                "done": "closed",
                "cancel": "cancel",
                "pause": "pause",
            }
            target_status = status_map.get(close_reason, "cancel")
            print(f"  关闭任务 ID {task_id} ({close_reason} -> {target_status}): {name}")
            try:
                update_data = {"status": target_status}
                if close_reason == "cancel":
                    update_data["canceledReason"] = close_reason
                elif close_reason == "done":
                    update_data["closedReason"] = "done"
                client.update_task(task_id, update_data)
                print(f"  OK 已{close_reason}")
                success += 1
            except Exception as e:
                print(f"  FAIL: {e}")
                failed += 1
            continue

        # ── 更新任务 (有id字段) ──
        if task_id:
            print(f"  更新任务 ID {task_id}: {name}")
            update_data = {k: v for k, v in t.items()
                          if k not in ("id", "images", "videos", "close")}

            # 上传图片嵌入描述
            images = t.get("images", [])
            image_infos = _upload_images(client, images, base_dir)
            videos = t.get("videos", [])

            if image_infos or videos:
                update_data["desc"] = build_desc(t, image_infos, [])

            try:
                client.update_task(task_id, update_data)
                print(f"  OK 已更新")
                success += 1
            except Exception as e:
                print(f"  FAIL: {e}")
                failed += 1

            # 上传视频关联任务
            if videos:
                _upload_videos(client, videos, base_dir, task_id, t)
            continue

        # ── 创建任务 ──
        print(f"  创建任务 {i}: {name}")

        # 去重检查
        if not force and name in existing_map:
            eid = existing_map[name].get("id")
            print(f"  SKIP 同名任务已存在 (ID: {eid})")
            continue

        # 上传图片
        images = t.get("images", [])
        image_infos = _upload_images(client, images, base_dir)

        # 构建描述
        videos = t.get("videos", [])
        desc = build_desc(t, image_infos, [])

        # 创建
        task_data = {k: v for k, v in t.items()
                     if k not in ("id", "images", "videos", "close")}
        task_data["desc"] = desc

        try:
            result = client.create_task(execution, task_data)
            new_id = result.get("id", "?")
            print(f"  OK ID: {new_id}")
            success += 1

            # 上传视频关联到新创建的任务
            if videos and new_id != "?":
                _upload_videos(client, videos, base_dir, int(new_id), t)

        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  完成! 成功: {success}, 失败: {failed}, 共: {len(tasks)}")
    print(f"{'='*60}")


def _upload_images(client: ZentaoClient, images: list, base_dir: str) -> list:
    """上传图片列表, 返回文件信息"""
    if not images:
        return []
    paths = []
    for img in images:
        path = img.get("path", img) if isinstance(img, dict) else img
        paths.append(resolve_path(path, base_dir))

    valid = [p for p in paths if os.path.exists(p)]
    if not valid:
        return []
    print(f"  上传 {len(valid)} 张图片...")
    return client.upload_files(valid)


def _upload_videos(client: ZentaoClient, videos: list, base_dir: str, task_id: int, task_fields: dict = None):
    """通过 web 表单上传视频附件，附件在禅道界面可直接下载"""
    paths = [resolve_path(v, base_dir) for v in videos]
    valid = [p for p in paths if os.path.exists(p)]
    if not valid:
        return
    print(f"  上传 {len(valid)} 个视频附件 (web 表单方式)...")
    for path in valid:
        ok = client.upload_file_via_task_edit(task_id, path, task_fields or {})
        name = os.path.basename(path)
        print(f"    {'OK' if ok else 'WARN'} {name}")


# ── 主入口 ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="禅道任务统一发布器")
    parser.add_argument("yaml_file", nargs="?", help="YAML 任务定义文件")
    parser.add_argument("--execute", action="store_true", help="执行 (不加则为预览)")
    parser.add_argument("--execution", type=int, help="覆盖执行ID")
    parser.add_argument("--force", action="store_true", help="强制创建 (不检查去重)")
    parser.add_argument("--list-executions", action="store_true", help="列出执行/迭代")
    parser.add_argument("--list-tasks", type=int, metavar="EXEC_ID", help="列出任务")
    parser.add_argument("--list-users", action="store_true", help="列出用户")
    args = parser.parse_args()

    # 查询命令
    if args.list_executions or args.list_tasks or args.list_users:
        client = get_client()
        if args.list_executions:
            cmd_list_executions(client)
        if args.list_tasks:
            cmd_list_tasks(client, args.list_tasks)
        if args.list_users:
            cmd_list_users(client)
        return

    if not args.yaml_file:
        parser.print_help()
        return

    data = load_tasks_yaml(args.yaml_file)

    if args.execute:
        execute(data, args.yaml_file, args.execution, args.force)
    else:
        preview(data, args.yaml_file)


if __name__ == "__main__":
    main()
