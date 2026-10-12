# ZCode MCP Bridge Connect

**Release:** v0.1.0 | **Transport:** stdio (no listening port) | **Stack:** Python 3.11+ standard library

## What
Connect MCP clients to an installed ZCode runtime. This fork adds manual Coding Plan and version-pinned Windows managed-account compatibility to the upstream bridge. Other backend implementations remain in source but are outside this release's live acceptance scope.

## Quick Start

```bash
./setup.sh              # Check Python and compile project files
./setup.sh --test       # Run offline fixture tests
python3 server.py       # Serve MCP over stdin/stdout
```

Windows: `./setup.ps1`, `./setup.ps1 -Test`, then `python server.py`.
The setup scripts do not install ZCode, log in, or change model/client settings.

## Commands

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -p 'test_*.py'
python3 server.py --probe
python3 scripts/check_connection.py
```

`--probe` discovers installed runtimes; it does not prove model authentication. The connection check uses the registered `vibe_bridge` from the current user's Codex configuration, sends one tool-free GLM-5.3 model request, and writes a private report under `scripts/`. It consumes existing provider allowance. Never commit that report.

## Architecture

```text
server.py                  MCP stdio entry point and nine agent-* tools
backend_manager.py         Backend selection/discovery
agent_control_plane.py     Unified lifecycle across retained backends
control_plane.py           ZCode lifecycle and permission projection
zcode_protocol.py          Native app-server transport and manual plan projection
legacy_account.py          Fingerprinted Windows installed-account adapter
modern_account.py          Shared account helpers and experimental PAT adapter
resource_leases.py         Cross-process SQLite resource ownership
scripts/check_connection.py Real connection acceptance with close/lease checks
tests/                     Offline fixtures; standalone live scripts are separate
```

MCP requests enter the control plane and invoke ZCode's bundled app-server. Credentials stay device-local and go only to the native process/authentication endpoint. Temporary manual provider projections are removed during shutdown.

## Configuration

The bridge does not load `.env` automatically. Set variables in the MCP client's environment; see [.env.example](.env.example) and [README.en.md](README.en.md).

| Variable | Required | Purpose |
|---|---|---|
| `AGENT_MCP_DEFAULT_BACKEND` | Recommended | Set `zcode` for this release |
| `ZCODE_APP_PATH` | If undiscoverable | Native installation root |
| `ZCODE_BINARY`, `ZCODE_CLI_BUNDLE` | If undiscoverable | Absolute native runtime and bundled CLI paths |
| `ZCODE_BRIDGE_MODERN_PROTOCOL` | CLI 0.16.9 | Explicitly set `1` |
| `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` | Modern mode | Installed `resources/config/provider/zcode-builtin.json` |
| `ZCODE_BRIDGE_DESKTOP_OAUTH` | Managed mode | Enables account adapter only when explicitly set `1` |
| `ZCODE_BRIDGE_PRODUCT_VERSION`, `ZCODE_BRIDGE_INSTALLED_ACCOUNT` | Installed managed mode | Both `3.14.5`; native host/CLI fingerprints must also match |
| `AGENT_MCP_TIMEOUT` | No | Default run timeout, seconds |
| `AGENT_MCP_MAX_CONCURRENCY` | No | `0` unlimited, positive value sets a backend limit |
| `AGENT_MCP_LOG`, `AGENT_MCP_LEASE_DB` | No | Private runtime paths |

## Working Rules

- Read the supported-mode table before modifying protocol/authentication behavior.
- Keep credentials, local configs, database files, logs, and reports out of Git.
- Preserve the same-user account binding and fingerprint checks; never silently switch account providers to manual or metered API access.
- PAT authentication is experimental and has no live acceptance claim.
- Use fixture tests for ordinary changes. Real connection tests require the operator's intended existing model/account.
- Keep stdout strictly MCP NDJSON when serving; diagnostics belong on stderr.
- Preserve upstream MIT copyright and commit provenance.
- Follow [CONTRIBUTING.md](CONTRIBUTING.md); no package manager, Docker, or build server is required.
