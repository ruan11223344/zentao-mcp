"""禅道 API 客户端 - 支持 v1 token 和 session 两种认证方式"""

import json
import os
import requests


class ZentaoClient:
    def __init__(self, base_url: str, account: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.account = account
        self.password = password
        self.session = requests.Session()
        self.token = None
        self.session_id = None
        self.session_name = None

    def _api_url(self, path: str) -> str:
        return f"{self.base_url}/api.php/v1/{path.lstrip('/')}"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Token"] = self.token
        return h

    # ── 认证 ──────────────────────────────────────────────

    def login(self) -> str:
        """登录 - 优先 token 方式, 失败则回退 session 方式"""
        try:
            return self._login_token()
        except Exception:
            return self._login_session()

    def _login_token(self) -> str:
        """Token 认证 (API v1)"""
        url = self._api_url("tokens")
        resp = self.session.post(url, json={
            "account": self.account,
            "password": self.password,
        }, headers={"Content-Type": "application/json"})
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise RuntimeError(data.get("error", f"HTTP {resp.status_code}"))
        self.token = data.get("token") or data.get("Token")
        if not self.token:
            raise RuntimeError(f"未获取到 token: {data}")
        print(f"[OK] Token 登录成功 (token: {self.token[:8]}...)")
        return self.token

    def _login_session(self) -> str:
        """Session 认证 (旧版兼容)"""
        # 1. 获取 sessionID
        r = self.session.get(f"{self.base_url}/api-getSessionID.json")
        r.raise_for_status()
        outer = r.json()
        inner = json.loads(outer["data"]) if isinstance(outer.get("data"), str) else outer["data"]
        self.session_name = inner["sessionName"]
        self.session_id = inner["sessionID"]

        # 2. 登录
        login_url = f"{self.base_url}/user-login.json?{self.session_name}={self.session_id}"
        r2 = self.session.post(login_url, data={
            "account": self.account,
            "password": self.password,
        })
        r2.raise_for_status()
        result = r2.json()
        if result.get("status") == "failed":
            raise RuntimeError(f"登录失败: {result.get('reason', result)}")

        # session 方式下设置 cookie
        self.session.cookies.set(self.session_name, self.session_id)
        print(f"[OK] Session 登录成功 (sid: {self.session_id[:8]}...)")
        return self.session_id

    # ── 通用请求 ──────────────────────────────────────────

    def _get(self, path: str) -> dict:
        if self.token:
            resp = self.session.get(self._api_url(path), headers=self._headers())
        else:
            url = f"{self.base_url}/{path}.json?{self.session_name}={self.session_id}"
            resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        if self.token:
            resp = self.session.post(self._api_url(path), json=body, headers=self._headers())
        else:
            url = f"{self.base_url}/{path}.json?{self.session_name}={self.session_id}"
            resp = self.session.post(url, json=body, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: dict) -> dict:
        if self.token:
            resp = self.session.put(self._api_url(path), json=body, headers=self._headers())
        else:
            url = f"{self.base_url}/{path}.json?{self.session_name}={self.session_id}"
            resp = self.session.put(url, json=body, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # ── 执行/迭代 ─────────────────────────────────────────

    def list_executions(self, project_id: int = 0) -> list:
        """列出执行/迭代"""
        path = f"projects/{project_id}/executions" if project_id else "executions"
        data = self._get(path)
        return data.get("executions", data) if isinstance(data, dict) else data

    def get_execution(self, execution_id: int) -> dict:
        """获取执行详情"""
        return self._get(f"executions/{execution_id}")

    # ── 任务 ──────────────────────────────────────────────

    def list_tasks(self, execution_id: int) -> list:
        """列出执行下所有任务"""
        data = self._get(f"executions/{execution_id}/tasks")
        return data.get("tasks", data) if isinstance(data, dict) else data

    def get_task(self, task_id: int) -> dict:
        """获取任务详情"""
        return self._get(f"tasks/{task_id}")

    def create_task(self, execution_id: int, task: dict) -> dict:
        """
        创建单个任务

        task 字段:
            name        (必填) 任务名称
            type        (必填) 类型: design|devel|request|test|study|discuss|ui|affair|misc
            assignedTo  (必填) 指派给
            estStarted  (必填) 预计开始日期 YYYY-MM-DD
            deadline    (必填) 截止日期 YYYY-MM-DD
            pri         (可选) 优先级 1-4
            estimate    (可选) 预计工时(小时)
            desc        (可选) 描述
            module      (可选) 所属模块ID
            story       (可选) 关联需求ID
        """
        return self._post(f"executions/{execution_id}/tasks", task)

    def update_task(self, task_id: int, updates: dict) -> dict:
        """
        更新任务

        可更新字段: name, type, assignedTo, estStarted, deadline, pri,
                    estimate, desc, status 等
        """
        return self._put(f"tasks/{task_id}", updates)

    def find_task_by_name(self, execution_id: int, name: str) -> dict | None:
        """按名称查找已有任务 (精确匹配), 用于去重"""
        tasks = self.list_tasks(execution_id)
        for t in tasks:
            if t.get("name") == name:
                return t
        return None

    def batch_create_tasks(
        self,
        execution_id: int,
        tasks: list[dict],
        skip_existing: bool = True,
        update_existing: bool = False,
    ) -> list[dict]:
        """
        批量创建任务

        Args:
            execution_id: 执行/迭代 ID
            tasks: 任务列表
            skip_existing: 跳过已存在的同名任务 (默认开启)
            update_existing: 更新已存在的同名任务 (与 skip_existing 配合使用)
        """
        results = []

        # 预加载已有任务用于去重
        existing_map = {}
        if skip_existing or update_existing:
            print("  加载已有任务列表...")
            existing = self.list_tasks(execution_id)
            existing_map = {t["name"]: t for t in existing}
            print(f"  已有 {len(existing_map)} 个任务\n")

        for i, task in enumerate(tasks, 1):
            name = task["name"]
            existing_task = existing_map.get(name)

            if existing_task:
                if update_existing:
                    # 更新已有任务
                    try:
                        tid = existing_task["id"]
                        result = self.update_task(tid, task)
                        print(f"  [{i}/{len(tasks)}] ~ 已更新: {name} (ID: {tid})")
                        results.append({"success": True, "action": "updated", "task": name, "data": result})
                    except requests.HTTPError as e:
                        error_body = self._extract_error(e)
                        print(f"  [{i}/{len(tasks)}] x 更新失败: {name} - {error_body}")
                        results.append({"success": False, "action": "update_failed", "task": name, "error": str(error_body)})
                elif skip_existing:
                    tid = existing_task.get("id", "?")
                    print(f"  [{i}/{len(tasks)}] - 已跳过 (已存在): {name} (ID: {tid})")
                    results.append({"success": True, "action": "skipped", "task": name, "data": existing_task})
                continue

            # 创建新任务
            try:
                result = self.create_task(execution_id, task)
                task_id = result.get("id", "?")
                print(f"  [{i}/{len(tasks)}] + 创建成功: {name} (ID: {task_id})")
                results.append({"success": True, "action": "created", "task": name, "data": result})
            except requests.HTTPError as e:
                error_body = self._extract_error(e)
                print(f"  [{i}/{len(tasks)}] x 创建失败: {name} - {error_body}")
                results.append({"success": False, "action": "create_failed", "task": name, "error": str(error_body)})

        return results

    @staticmethod
    def _extract_error(e: requests.HTTPError) -> str:
        if e.response is not None:
            try:
                return str(e.response.json())
            except Exception:
                return e.response.text
        return str(e)

    def login_web(self) -> str:
        """强制使用 session 方式登录，确保获得 zentaosid cookie（web 表单上传必须）"""
        return self._login_session()

    def upload_file_via_task_edit(self, task_id: int, file_path: str, task_fields: dict) -> bool:
        """
        通过禅道 web 表单（task-edit）上传文件，文件可被正常下载。

        原理：复现浏览器提交 task-edit-{id}.html?zin=1 的行为，
              文件以 files[] 字段上传，附件通过禅道原生 UI 可直接下载。

        Args:
            task_id:     目标任务 ID
            file_path:   本地文件路径
            task_fields: 任务字段 dict (name, assignedTo, type, desc, execution 等)

        Returns:
            True 表示成功（禅道返回 JSON 包含 result=success）
        """
        import mimetypes
        import secrets

        if not self.session_id:
            self._login_session()

        url = f"{self.base_url}/task-edit-{task_id}.html?zin=1"
        uid = secrets.token_hex(6)  # 类似浏览器生成的随机 uid

        # 基础表单字段
        data = {
            "name":          task_fields.get("name", ""),
            "color":         "",
            "desc":          task_fields.get("desc", ""),
            "uid":           uid,
            "story":         "",
            "lastEditedDate": "",
            "execution":     str(task_fields.get("execution", "")),
            "module":        "0",
            "parent":        "",
            "mode":          "single",
            "assignedTo":    task_fields.get("assignedTo", ""),
            "type":          task_fields.get("type", "devel"),
            "status":        task_fields.get("status", "wait"),
            "pri":           str(task_fields.get("pri", 2)),
            "keywords":      "",
            "mailto[]":      "",
            "contactList":   "",
            "estStarted":    task_fields.get("estStarted", ""),
            "deadline":      task_fields.get("deadline", ""),
            "estimate":      str(task_fields.get("estimate", "")),
            "consumed":      "0",
            "left":          str(task_fields.get("estimate", "")),
            "realStarted":   "",
            "finishedBy":    "",
            "finishedDate":  "",
            "canceledBy":    "",
            "canceledDate":  "",
            "closedBy":      "",
            "closedReason":  "",
            "closedDate":    "",
        }

        mime_type = mimetypes.guess_type(file_path)[0] or "video/mp4"
        filename  = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            resp = self.session.post(
                url,
                data=data,
                files={"files[]": (filename, f, mime_type)},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{self.base_url}/my.html",
                },
            )

        resp.raise_for_status()
        try:
            result = resp.json()
            return result.get("result") == "success"
        except Exception:
            # 有时返回 HTML，视为成功
            return resp.status_code == 200

    # ── 文件上传 ────────────────────────────────────────────

    def upload_file(self, file_path: str, object_type: str = "", object_id: int = 0) -> dict:
        """
        上传文件到禅道

        Args:
            file_path: 本地文件路径
            object_type: 关联对象类型 (task, bug, story 等)
            object_id: 关联对象 ID

        Returns:
            {"id": fileID, "url": "..."}
        """
        import mimetypes
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            data = {}
            if object_type:
                data["objectType"] = object_type
            if object_id:
                data["objectID"] = str(object_id)

            resp = self.session.post(
                self._api_url("files"),
                headers={"Token": self.token} if self.token else {},
                files={"imgFile": (filename, f, mime_type)},
                data=data,
            )
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") != "success":
            raise RuntimeError(f"上传失败: {result}")
        return result.get("data", result)

    def upload_files(self, file_paths: list[str], object_type: str = "", object_id: int = 0) -> list[dict]:
        """上传多个文件, 返回文件信息列表"""
        results = []
        for fp in file_paths:
            try:
                info = self.upload_file(fp, object_type=object_type, object_id=object_id)
                print(f"    + 上传成功: {os.path.basename(fp)} (ID: {info.get('id', '?')})")
                results.append(info)
            except Exception as e:
                print(f"    x 上传失败: {os.path.basename(fp)} - {e}")
        return results

    @staticmethod
    def _get_file_ext(file_info: dict) -> str:
        """从文件信息中提取扩展名 (禅道URL格式: t=png 或 t=jpg)"""
        url = file_info.get("url", "")
        # 禅道文件URL: pi.php?m=file&f=read&t=png&fileID=xxx
        import re
        m = re.search(r'[&?]t=(\w+)', url)
        if m:
            return m.group(1)
        for ext in ["jpg", "jpeg", "gif", "webp", "bmp"]:
            if f".{ext}" in url:
                return ext
        return "png"

    @staticmethod
    def build_desc_with_images(text: str, file_infos: list[dict]) -> str:
        """
        构建包含内嵌图片的 HTML 描述

        图片直接嵌入描述正文中, 使用完整 URL 引用
        """
        html_parts = []
        if text:
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    html_parts.append(f"<p>{line}</p>")

        for f in file_infos:
            url = f.get("url", "")
            fid = f.get("id", "")
            ext = ZentaoClient._get_file_ext(f)
            html_parts.append(f'<p><img src="{url}" alt="{fid}.{ext}" /></p>')

        return "\n".join(html_parts)

    # ── 用户 ──────────────────────────────────────────────

    def list_users(self) -> list:
        """列出所有用户"""
        data = self._get("users")
        return data.get("users", data) if isinstance(data, dict) else data

    # ── 项目 ──────────────────────────────────────────────

    def list_projects(self) -> list:
        """列出所有项目"""
        data = self._get("projects")
        return data.get("projects", data) if isinstance(data, dict) else data
