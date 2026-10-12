# ZCode MCP Bridge Connect

[English](README.en.md) | 简体中文

把 Codex 等 MCP 客户端连接到本机已安装的 ZCode，使用现有 Coding Plan 完成模型任务，并管理原生会话的启动、观察和关闭。由 Julian Cooper 维护。

本发行版本为 **v0.1.0**，基于 [Deslord319/coder-mcp-bridge](https://github.com/Deslord319/coder-mcp-bridge/tree/23ecf0a5f3be1916bb856e56fac5d313e07a05c4) 的固定 commit `23ecf0a5f3be1916bb856e56fac5d313e07a05c4`。保留上游 MIT 版权和多 backend 源码；本发行的真实连接验收范围为 ZCode。MCP 引擎上报的 `0.5.0-dev` 沿用上游版本，与本兼容包发行版本分开。

## 支持范围

| 模式 | 配置与开关 | 真实验收范围 |
|---|---|---|
| 旧 CLI 协议 | CLI 0.16.5，现有 `~/.zcode/cli/config.json`；不启用 modern 开关 | 旧协议连接已验收 |
| 现代手工 Coding Plan | CLI 0.16.9，现有旧 CLI 配置或 `~/.zcode/v2/provider_config.json` 中选中的手工 BigModel Coding Plan；启用 modern 开关 | macOS 产品 3.15.1、Linux 产品 3.14.4、Windows CLI 0.16.9；GLM-5.3 请求与关闭已验收 |
| Windows 安装版托管个人账户 | 产品 3.14.5、CLI 0.16.9，原生扫码登录；显式选择安装版适配且 host/CLI 双指纹匹配 | GLM-5.3 请求、关闭与租约释放已验收 |
| 新版源码 PAT 账户接口 | `modern_account.py` 保留实验实现 | **未完成真实验收，不建议启用** |

这些是经过验收的版本和模式，不代表所有 ZCode 版本都兼容。安装版托管模式只读取同一台电脑、当前用户和当前账户的原生凭据，在内存中复用并实时验证套餐状态；保留 `account` provider，不改成手工或按量 API 模式。指纹不匹配、账户变更、凭据需要刷新或套餐验证失败时直接报错。

现代手工模式只接受明确的 `zhipu-coding-plan-api-key` 访问类型、有效套餐 endpoint 和选中的 `GLM-5.3`，支持 `high` / `max`。运行期间生成私有 provider 投影，正常关闭、启动失败和服务退出时清理该文件。认证和模型配置留在各自设备上。

## 快速开始

要求 Python **3.11+**；Python 部分只使用标准库，无需 `pip install`。真实连接还需要已安装的 ZCode，以及该设备上可用的登录或模型配置。

```bash
git clone https://github.com/Cooperiano/zcode-mcp-bridge-connect.git
cd zcode-mcp-bridge-connect
./setup.sh
```

Windows PowerShell：

```powershell
./setup.ps1
# 若 Python 不在 PATH，指定该设备的 Python 绝对路径：
./setup.ps1 -Python "C:/absolute/path/to/python.exe"
```

setup 只校验 Python 并编译源码。加 `--test`（PowerShell 为 `-Test`）可运行离线 fixture 测试；有 Node.js 时也运行保留的 JavaScript fixture。setup 不下载 ZCode、不登录、不创建密钥、不覆盖客户端配置，也不调用模型。

## 注册到 Codex

在当前用户的 `~/.codex/config.toml` 中添加一个 `vibe_bridge`，或修改已有同名条目。模板中的 `/absolute/...` 必须替换为本机真实绝对路径。`.env.example` 仅是参考，程序不会自动读取 `.env`。

以下为 macOS 的现代手工模式：

```toml
[mcp_servers.vibe_bridge]
command = "/absolute/path/to/python3"
args = ["/absolute/path/to/zcode-mcp-bridge-connect/server.py"]

[mcp_servers.vibe_bridge.env]
AGENT_MCP_DEFAULT_BACKEND = "zcode"
AGENT_MCP_TIMEOUT = "900"
ZCODE_APP_PATH = "/Applications/ZCode.app"
ZCODE_BINARY = "/Applications/ZCode.app/Contents/MacOS/ZCode"
ZCODE_CLI_BUNDLE = "/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"
ZCODE_BUILTIN_PROVIDER_CONFIG_FILE = "/Applications/ZCode.app/Contents/Resources/config/provider/zcode-builtin.json"
ZCODE_BRIDGE_MODERN_PROTOCOL = "1"
```

Windows 的 `command`、`args` 和环境变量均用该设备的绝对路径，TOML 建议用正斜杠：

```toml
[mcp_servers.vibe_bridge]
command = "C:/absolute/path/to/python.exe"
args = ["C:/absolute/path/to/zcode-mcp-bridge-connect/server.py"]

[mcp_servers.vibe_bridge.env]
AGENT_MCP_DEFAULT_BACKEND = "zcode"
AGENT_MCP_TIMEOUT = "900"
ZCODE_APP_PATH = "C:/absolute/path/to/ZCode"
ZCODE_BINARY = "C:/absolute/path/to/ZCode/ZCode.exe"
ZCODE_CLI_BUNDLE = "C:/absolute/path/to/ZCode/resources/glm/zcode.cjs"
ZCODE_BUILTIN_PROVIDER_CONFIG_FILE = "C:/absolute/path/to/ZCode/resources/config/provider/zcode-builtin.json"
ZCODE_BRIDGE_MODERN_PROTOCOL = "1"
```

对满足双指纹要求的 **Windows 3.14.5 托管个人账户**，在上面的环境变量块中额外添加：

```toml
ZCODE_BRIDGE_DESKTOP_OAUTH = "1"
ZCODE_BRIDGE_PRODUCT_VERSION = "3.14.5"
ZCODE_BRIDGE_INSTALLED_ACCOUNT = "3.14.5"
```

这三个值必须一起设置。只设置 OAuth 开关会进入未验收的 PAT 实验路径，不是安装版托管适配。

Linux 现代模式使用同样的环境变量名；将 `ZCODE_APP_PATH` 指向实际安装目录，CLI 指向 `resources/glm/zcode.cjs`，builtin 指向 `resources/config/provider/zcode-builtin.json`，`ZCODE_BINARY` 指向已验证可运行该 bundle 的本机 runtime（验收使用 Node.js）。旧 CLI 0.16.5 模式不设置 modern、OAuth 或 installed-account 开关。

保存后 **重启或重新加载 MCP 客户端**。stdio 服务没有监听端口；它由客户端按注册项启动。

## 连接验收

先检查安装发现：

```bash
python3 server.py --probe
```

`--probe` 成功只表示发现可用 runtime，不代表模型认证成功。完成注册并重新加载后，运行真实验收：

```bash
python3 scripts/check_connection.py
```

Windows 使用 `python scripts/check_connection.py`。脚本读取当前用户已注册的 `vibe_bridge`，对现有模型发送一次禁止工具调用的随机 nonce 回显请求，验证九个工具、`GLM-5.3`、精确回显、原生关闭、租约释放和桥正常退出。该请求会使用现有套餐额度。

验收报告写入 `scripts/connection-report.json`，包含本地运行信息，属于私有文件，已被 Git 忽略；不要提交或原样贴到 issue。脚本不注册客户端、不登录、不修改账号。模型不可用、套餐耗尽和网络故障仍可能导致失败。

## 九个 MCP 工具

| 工具 | 用途 |
|---|---|
| `agent-config` | 查看 runtime 与选择 backend |
| `agent-start` | 启动任务 |
| `agent-wait` | 按 revision 等待变化 |
| `agent-observe` | 获取任务状态 |
| `agent-control` | 引导、中断或取消 |
| `agent-recover` | 恢复会话 |
| `agent-branch` | 分支会话 |
| `agent-context` | 管理上下文 |
| `agent-close` | 关闭原生会话并释放资源 |

注册名为 `vibe_bridge`，传输为 MCP JSON-RPC over stdio。保留的 OpenCode/Pi 实现与 fixture 不构成本发行对它们的真实连接验收。

## 配置说明

完整可选项与内部环境变量分组见 [.env.example](.env.example)。主要配置如下：

| 变量 | 说明 |
|---|---|
| `AGENT_MCP_TIMEOUT` | 默认任务超时秒数，默认 `900` |
| `AGENT_MCP_MAX_CONCURRENCY` | backend 并发上限，`0` 表示桥不额外限制 |
| `AGENT_MCP_LOG` / `AGENT_MCP_LEASE_DB` | 私有日志与 SQLite 租约库的可选路径 |
| `ZCODE_APP_PATH` / `ZCODE_BINARY` / `ZCODE_CLI_BUNDLE` | 本机安装目录、runtime、CLI |
| `ZCODE_BRIDGE_MODERN_PROTOCOL` | CLI 0.16.9 显式适配开关 |
| `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` | 现代模式必须使用当前安装包的 builtin provider 文件 |
| `ZCODE_BRIDGE_DESKTOP_OAUTH` / `ZCODE_BRIDGE_PRODUCT_VERSION` / `ZCODE_BRIDGE_INSTALLED_ACCOUNT` | 安装版托管账户适配开关与版本 |

不要复制其他设备的登录缓存、密钥、数据库或 native 配置来完成注册。更换产品版本后，托管模式的旧指纹可能不再适用，应重新验证兼容性。

## 开发与 Codex

```bash
./setup.sh --test
python3 -m unittest discover -s tests -p 'test_*.py'
```

开发命令与结构见 [AGENTS.md](AGENTS.md)，贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。CI 在 Ubuntu/Windows 与 Python 3.11/3.13 上运行离线 fixture，不使用账号或 provider secrets。离线通过与真实模型请求成功分别报告。

### Using with Codex

在仓库目录启动 Codex，读取 [AGENTS.md](AGENTS.md) 获取上下文、准确命令与认证边界。其他 coding assistant 使用 [CLAUDE.md](CLAUDE.md) 指向同一份指令。

上游更广泛的 harness 方法文档保留为参考：[中文](docs/HARNESS-CONTEXT-ENGINEERING.zh-CN.md)、[English](docs/HARNESS-CONTEXT-ENGINEERING.en.md)。其内容不扩大本发行的支持范围。

## 许可证

[MIT](LICENSE)，保留原作者 Deslord319 版权。此仓库不分发 ZCode 原生程序或任何设备凭据。
