# ZCode MCP Bridge Connect

English | [简体中文](README.md)

Connect Codex and other MCP clients to an installed ZCode runtime, using the device's existing Coding Plan and managing native task startup, observation, and shutdown. Maintained by Julian Cooper.

**Release: v0.1.0.** Based on [Deslord319/coder-mcp-bridge](https://github.com/Deslord319/coder-mcp-bridge/tree/23ecf0a5f3be1916bb856e56fac5d313e07a05c4), fixed upstream commit `23ecf0a5f3be1916bb856e56fac5d313e07a05c4`. This fork preserves the upstream MIT copyright and multiple backend implementations. This release's live acceptance scope covers ZCode. The MCP engine retains its upstream reported version `0.5.0-dev`, separate from this compatibility package's release version.

## Supported modes

| Mode | Configuration | Live acceptance |
|---|---|---|
| Legacy CLI protocol | CLI 0.16.5, existing `~/.zcode/cli/config.json`; modern switch unset | Legacy protocol connection verified |
| Modern manual Coding Plan | CLI 0.16.9, existing legacy CLI configuration or selected manual BigModel Coding Plan in `~/.zcode/v2/provider_config.json`; modern switch enabled | macOS product 3.15.1, Linux product 3.14.4, Windows CLI 0.16.9; GLM-5.3 request and close verified |
| Windows installed managed personal account | Product 3.14.5, CLI 0.16.9, existing native scan login; explicit installed adapter and matching host/CLI fingerprints | GLM-5.3 request, native close, and lease release verified |
| Newer source PAT account interface | Experimental implementation retained in `modern_account.py` | **No live acceptance; enabling it is not recommended** |

These verified versions and modes do not establish compatibility with every ZCode release. The installed managed adapter reads only the same device's current user/account credential, reuses it in memory, and verifies the active subscription. It retains the account provider and does not convert the account to a manual or metered API provider. Unsupported fingerprints, account changes, credential-refresh requests, and failed entitlement checks cause an error.

Modern manual mode requires an explicit `zhipu-coding-plan-api-key` access type, a validated plan endpoint, and selected `GLM-5.3`. It supports `high` / `max`, creates a private provider projection, and removes that projection on normal close, startup failure, or server exit. Authentication and native model configuration remain local to each device.

## Quick start

Use **Python 3.11+**. The Python bridge uses only the standard library; no `pip install` is needed. Live connections also require an installed ZCode runtime and working device-local login or model configuration.

```bash
git clone https://github.com/Cooperiano/zcode-mcp-bridge-connect.git
cd zcode-mcp-bridge-connect
./setup.sh
```

Windows PowerShell:

```powershell
./setup.ps1
# If Python is outside PATH, pass its device-local absolute path:
./setup.ps1 -Python "C:/absolute/path/to/python.exe"
```

Setup checks Python and compiles source. Add `--test` (`-Test` on PowerShell) to run offline fixtures. Retained JavaScript fixture checks run when Node.js is available. Setup does not download ZCode, log in, create keys, overwrite client settings, or call a model.

## Register with Codex

Add one `vibe_bridge` entry to the current user's `~/.codex/config.toml`, or update the existing entry with that name. Replace `/absolute/...` placeholders with actual absolute paths on this device. `.env.example` is reference material; the program does not automatically load `.env`.

macOS modern manual example:

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

Windows uses its own executable and installation paths. Forward slashes avoid TOML backslash escaping:

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

For the **Windows 3.14.5 managed personal account** with supported fingerprints, add all three values to that environment block:

```toml
ZCODE_BRIDGE_DESKTOP_OAUTH = "1"
ZCODE_BRIDGE_PRODUCT_VERSION = "3.14.5"
ZCODE_BRIDGE_INSTALLED_ACCOUNT = "3.14.5"
```

Set these together. Enabling only the OAuth switch selects the unaccepted experimental PAT path, not the installed managed-account adapter.

Linux modern mode uses the same variable names. Point `ZCODE_APP_PATH` to the installed root, CLI to `resources/glm/zcode.cjs`, builtin to `resources/config/provider/zcode-builtin.json`, and `ZCODE_BINARY` to a local runtime verified to execute the bundle (live acceptance used Node.js). For legacy CLI 0.16.5, leave modern, OAuth, and installed-account switches unset.

**Restart or reload the MCP client** after saving. This stdio server listens on no network port; the client starts it using the registration.

## Verify a connection

First inspect runtime discovery:

```bash
python3 server.py --probe
```

A successful probe shows runtime discovery, not model authentication. After registration and client reload, run live acceptance:

```bash
python3 scripts/check_connection.py
```

Use `python scripts/check_connection.py` on Windows. The script reads the current user's registered `vibe_bridge`, sends one random-nonce echo request with tools disallowed, and checks the nine tools, `GLM-5.3`, exact echo, native close, lease release, and normal bridge exit. It consumes existing provider allowance.

The report is written to `scripts/connection-report.json`. It contains local runtime information, is private, and is ignored by Git; do not commit it or paste it unchanged into an issue. The script does not register a client, log in, or change accounts. Provider unavailability, exhausted allowance, and network failures can still cause a check to fail.

## Nine MCP tools

| Tool | Purpose |
|---|---|
| `agent-config` | Inspect runtimes and select a backend |
| `agent-start` | Start a task |
| `agent-wait` | Wait for a revision change |
| `agent-observe` | Read task state |
| `agent-control` | Guide, interrupt, or cancel |
| `agent-recover` | Resume a session |
| `agent-branch` | Branch a session |
| `agent-context` | Manage context |
| `agent-close` | Close the native session and release resources |

The server registration name is `vibe_bridge`; transport is MCP JSON-RPC over stdio. Retained OpenCode/Pi implementations and fixtures do not establish live acceptance for those backends in this release.

## Configuration

See [.env.example](.env.example) for the full optional list and generated environment-variable groups.

| Variable | Purpose |
|---|---|
| `AGENT_MCP_TIMEOUT` | Default task timeout in seconds; default `900` |
| `AGENT_MCP_MAX_CONCURRENCY` | Backend cap; `0` adds no bridge limit |
| `AGENT_MCP_LOG` / `AGENT_MCP_LEASE_DB` | Optional private log and SQLite lease paths |
| `ZCODE_APP_PATH` / `ZCODE_BINARY` / `ZCODE_CLI_BUNDLE` | Local installation root, runtime, CLI |
| `ZCODE_BRIDGE_MODERN_PROTOCOL` | Explicit CLI 0.16.9 compatibility switch |
| `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` | Modern mode requires the current install's builtin provider file |
| `ZCODE_BRIDGE_DESKTOP_OAUTH` / `ZCODE_BRIDGE_PRODUCT_VERSION` / `ZCODE_BRIDGE_INSTALLED_ACCOUNT` | Installed managed-account switches/version |

Do not copy another device's login cache, keys, databases, or native configuration to register a connection. Updating ZCode may invalidate the installed-account fingerprint; verify compatibility again after an update.

## Development

```bash
./setup.sh --test
python3 -m unittest discover -s tests -p 'test_*.py'
```

See [AGENTS.md](AGENTS.md) for commands/architecture and [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow. CI runs offline fixtures on Ubuntu/Windows with Python 3.11/3.13, without account or provider secrets. Report fixture checks separately from real model acceptance.

## Using with Codex

Start Codex in the repository directory and use [AGENTS.md](AGENTS.md) for project context, accurate commands, and authentication boundaries. [CLAUDE.md](CLAUDE.md) points other coding assistants to the same instructions.

Broader upstream harness documentation remains available as reference: [English](docs/HARNESS-CONTEXT-ENGINEERING.en.md), [中文](docs/HARNESS-CONTEXT-ENGINEERING.zh-CN.md). It does not expand this release's supported scope.

## License

[MIT](LICENSE), preserving Deslord319's original copyright. This repository distributes neither ZCode native binaries nor device credentials.
