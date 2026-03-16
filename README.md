# 禅道任务管理 MCP Server

在 Claude Code / Claude Desktop 中用自然语言操作禅道：查看执行和任务、批量创建/更新/关闭任务，支持上传图片和视频附件。

## 功能一览

| 工具 | 说明 |
|------|------|
| `zentao_list_executions` | 列出所有执行/迭代（Sprint） |
| `zentao_list_tasks` | 列出指定执行下的全部任务（含状态、优先级、负责人） |
| `zentao_list_users` | 列出所有用户账号（用于填 assignedTo） |
| `zentao_publish_yaml` | 从 YAML 批量**创建 / 更新 / 关闭**任务，支持上传图片和视频 |

---

## 安装

**要求：Python 3.9+**

```bash
git clone https://github.com/ruan11223344/zentao-mcp.git
cd zentao-mcp
pip install -r requirements.txt
```

---

## 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```env
ZENTAO_URL=https://your-zentao-server.com
ZENTAO_ACCOUNT=your_account
ZENTAO_PASSWORD=your_password
```

---

## 配置到 Claude Code

在 `~/.claude/settings.json` 的 `mcpServers` 中添加：

```json
{
  "mcpServers": {
    "zentao": {
      "command": "python",
      "args": ["/path/to/zentao-mcp/server.py"]
    }
  }
}
```

> 也可以不用 `.env`，直接在配置里写：
> ```json
> {
>   "mcpServers": {
>     "zentao": {
>       "command": "python",
>       "args": ["/path/to/zentao-mcp/server.py"],
>       "env": {
>         "ZENTAO_URL": "https://your-zentao-server.com",
>         "ZENTAO_ACCOUNT": "your_account",
>         "ZENTAO_PASSWORD": "your_password"
>       }
>     }
>   }
> }
> ```

---

## 使用方法（MCP 工具）

### 查询执行列表

让 Claude 调用 `zentao_list_executions`，返回所有迭代的 ID、名称、状态和起止日期：

```
帮我查下禅道执行列表
```

### 查询任务列表

```
列出执行 #5 的所有任务
```

### 查询用户列表

```
禅道里有哪些用户？
```

---

### 创建任务

YAML 中**不填 `id`** 即为创建新任务：

```yaml
execution: 5
defaults:
  type: devel
  assignedTo: zhangsan
  pri: 2
  estStarted: "2026-03-16"
  deadline: "2026-03-31"
tasks:
  - name: "用户登录功能开发"
    estimate: 8
    desc: |
      <h3>需求</h3>
      <p>实现用户名/密码登录，支持记住密码。</p>

  - name: "首页 Banner 接口"
    estimate: 4
    assignedTo: lisi     # 单独覆盖负责人
    pri: 1
```

> **去重保护**：同名任务已存在时自动跳过，不会重复创建。加 `force: true` 可强制创建。

---

### 更新任务

YAML 中填写 `id` 即为更新已有任务：

```yaml
execution: 5
tasks:
  - id: 123
    name: "用户登录功能开发（更新）"
    pri: 1
    deadline: "2026-03-20"
    desc: |
      <h3>更新说明</h3>
      <p>增加手机号登录支持。</p>
```

---

### 关闭任务

填写 `id` + `close` 字段即关闭任务，`close` 的值作为关闭原因：

```yaml
execution: 5
tasks:
  - id: 123
    close: "功能已开发完成，测试通过"

  - id: 124
    close: "需求变更，不再实现"
```

---

### 上传图片（嵌入描述）

图片会上传后嵌入到任务描述中：

```yaml
execution: 5
tasks:
  - name: "UI 还原问题修复"
    desc: "<p>以下为设计稿与实现对比：</p>"
    images:
      - path: ./screenshots/design.png
        label: "设计稿"
      - path: ./screenshots/actual.png
        label: "实际效果"
```

---

### 上传视频（任务附件）

视频会作为文件附件上传到任务，在禅道界面可直接下载：

```yaml
execution: 5
tasks:
  - id: 123
    videos:
      - ./recordings/bug-demo.mp4
```

---

### 预览（dry_run）

`dry_run: true` 只预览不执行，用于确认任务内容：

```
帮我预览以下 YAML，不要实际创建：
execution: 5
tasks:
  - name: "测试任务"
    assignedTo: admin
```

---

### 混合操作（一次 YAML 同时创建/更新/关闭）

```yaml
execution: 5
defaults:
  assignedTo: zhangsan
  pri: 3
tasks:
  # 创建新任务
  - name: "新功能 A"
    estimate: 6

  # 更新已有任务
  - id: 100
    name: "已有任务（修改名称）"
    pri: 1

  # 关闭任务
  - id: 101
    close: "已完成"
```

---

## 命令行使用（不依赖 Claude）

也可以直接用命令行操作：

```bash
# 预览任务（不执行）
python publish.py tasks/my_tasks.yaml

# 执行创建/更新/关闭
python publish.py tasks/my_tasks.yaml --execute

# 覆盖执行 ID
python publish.py tasks/my_tasks.yaml --execute --execution 8

# 强制创建（跳过去重检查）
python publish.py tasks/my_tasks.yaml --execute --force

# 查看执行列表
python publish.py --list-executions

# 查看任务列表
python publish.py --list-tasks 5

# 查看用户列表
python publish.py --list-users
```

---

## YAML 字段说明

### 顶层字段

| 字段 | 说明 |
|------|------|
| `execution` | 执行/迭代 ID（必填） |
| `defaults` | 任务默认值，被 tasks 中的字段覆盖 |
| `tasks` | 任务列表 |

### 任务字段

| 字段 | 说明 |
|------|------|
| `id` | 有则更新，无则创建 |
| `name` | 任务名称 |
| `assignedTo` | 负责人账号 |
| `pri` | 优先级（1=紧急 2=高 3=中 4=低） |
| `estimate` | 预估工时（小时） |
| `type` | 类型（devel/design/test/doc 等） |
| `estStarted` | 预计开始日期（YYYY-MM-DD） |
| `deadline` | 截止日期（YYYY-MM-DD） |
| `desc` | 描述（支持 HTML） |
| `images` | 图片列表（嵌入描述） |
| `videos` | 视频列表（任务附件） |
| `close` | 填写则关闭任务（值为关闭原因，需同时填 id） |

---

## 支持的禅道版本

禅道 17.x 及以上，需开启 API 访问权限。
