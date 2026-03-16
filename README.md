# 禅道任务管理 MCP Server

在 Claude Code / Claude Desktop 中直接操作禅道：查看执行、任务列表、批量创建/更新/关闭任务。

## 功能

| 工具 | 说明 |
|------|------|
| `zentao_list_executions` | 列出所有执行/迭代（Sprint） |
| `zentao_list_tasks` | 列出指定执行下的所有任务 |
| `zentao_list_users` | 列出所有用户（用于填写负责人） |
| `zentao_publish_yaml` | 从 YAML 批量创建/更新/关闭任务 |

## 安装

**依赖：Python 3.9+**

```bash
cd zentao-mcp
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，填入你的禅道信息：

```bash
cp .env.example .env
```

编辑 `.env`：

```
ZENTAO_URL=https://你的禅道地址
ZENTAO_ACCOUNT=你的账号
ZENTAO_PASSWORD=你的密码
```

## 配置到 Claude Code

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "zentao": {
      "command": "python",
      "args": ["/path/to/zentao-mcp/server.py"],
      "env": {}
    }
  }
}
```

> 也可以不用 `.env`，直接在 `env` 字段里填：
> ```json
> "env": {
>   "ZENTAO_URL": "https://你的禅道地址",
>   "ZENTAO_ACCOUNT": "你的账号",
>   "ZENTAO_PASSWORD": "你的密码"
> }
> ```

## YAML 格式示例

```yaml
execution: 5          # 执行/迭代 ID
defaults:             # 任务默认值（可省略）
  type: devel
  assignedTo: admin
  pri: 2
  estStarted: "2026-03-16"
  deadline: "2026-03-31"
tasks:
  - name: "新功能开发"
    estimate: 4
    desc: |
      <h3>需求描述</h3>
      <p>具体内容...</p>

  - id: 123           # 有 id 则更新已有任务
    name: "修复 Bug"
    pri: 1

  - id: 456
    close: "已完成，功能验证通过"   # 关闭任务
```

## 支持的禅道版本

禅道 17.x 及以上（需开启 API 访问）。
