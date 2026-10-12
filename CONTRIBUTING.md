# Contributing

This public repository focuses on ZCode connection compatibility. Python code for other upstream backends remains available, but this release makes no live acceptance claim for those backends.

## Development setup

Use Python 3.11 or newer. No third-party Python packages are required.

```bash
git clone https://github.com/Cooperiano/zcode-mcp-bridge-connect.git
cd zcode-mcp-bridge-connect
./setup.sh --test
```

On Windows, use `./setup.ps1 -Test`. Install Node.js to run the retained Pi JavaScript fixture checks; those checks skip if Node is absent. Setup never downloads ZCode or performs a login.

## Branches and pull requests

Create a branch for a focused change, run the fixture suite, and submit a pull request describing the trigger, resulting behavior, and checks performed. Separate offline test results from real native runtime acceptance. Include the ZCode product/CLI version and operating system for compatibility changes, without private installation paths or account details.

## Code conventions

Keep standard-library Python, explicit error propagation, bounded subprocess/network waits, and MCP NDJSON stdout. Use stderr for diagnostics. Add focused fixtures for protocol changes and preserve cleanup of process ownership, leases, and private provider projections. Authentication changes must preserve same-device/current-account identity binding, version/fingerprint validation, and fail-closed behavior.

The `modern_account.py` PAT path is experimental; do not advertise it as a verified replacement for installed managed accounts. The supported Windows adapter reuses the user's native current-account credential in memory and checks the active subscription. It never copies credentials between computers.

## Verification

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -p 'test_*.py'
```

CI runs fixture tests on Ubuntu and Windows with Python 3.11/3.13 and Node.js. Fixture success does not prove login or provider availability. `tests/test_mcp.py` is a separate live upstream script; ordinary unittest discovery does not execute its `main()`.

For a deliberately authorized live check, register `vibe_bridge` first, then run:

```bash
python3 scripts/check_connection.py
```

This makes one tool-free GLM-5.3 request against the existing account and may consume allowance. The generated `scripts/connection-report.json` is private and ignored by Git. Never include keys, tokens, native settings, full logs, or credential databases in issues or pull requests.

## Reporting issues

Use the issue templates. Give product/CLI versions, platform, selected compatibility mode, a sanitized failure category, and reproducible steps. A valid desktop subscription and a working stdio transport are distinct from a successful native model request; state which step failed.

## Using Codex

[AGENTS.md](AGENTS.md) supplies project context and verified commands for Codex. Use it as the shared instruction source; [CLAUDE.md](CLAUDE.md) points to the same file for other coding assistants.

## Attribution and license

Preserve [LICENSE](LICENSE) and the original Deslord319 MIT copyright. This fork starts from upstream commit `23ecf0a5f3be1916bb856e56fac5d313e07a05c4`. Public fork maintainer: Julian Cooper.
