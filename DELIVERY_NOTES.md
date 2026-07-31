# Delivery Notes

This source tree is the lightweight dual-transport revision of Local Repo MCP.

## Main changes

- Keeps the project scoped to one local Git repository and one local user.
- Supports both STDIO and Streamable HTTP using the same MCP tools.
- Adds localhost-first HTTP defaults, Host/Origin controls, optional Bearer authentication, and request-size limits.
- Rebuilds the GUI around five pages: Home, MCP Server, ChatGPT Connection, Logs, and About.
- Replaces the previous environment-only test with a real MCP handshake, tool discovery, and `repo_git_status` call.
- Keeps OpenAI Secure MCP Tunnel optional and removes automatic tunnel-client downloads.
- Makes the OpenAI runtime API key memory-only.
- Removes Session, RBAC, risk scoring, policy YAML, automatic branch management, patch approval state, and Docker sandbox code.
- Retains repository confinement, sensitive-path filtering, fixed-string search, filtered Git status/diff, validated text patches, and predefined trusted-repository tests.

## Validation performed

- Python syntax/bytecode compilation completed for root scripts, `src/`, `gui/`, and `tests/`.
- `pytest -q`: 19 tests passed.
- Tests cover path traversal, absolute paths, symlinks, binary files, search option injection, sensitive Git status/diff filtering, unsupported patch types, common credential patterns, API-key persistence, subprocess shell usage, and test-command allowlisting.

## Environment limitation

The delivery environment does not have the `mcp` or `customtkinter` packages installed, so the live GUI and end-to-end SDK handshake could not be executed here. The transport and smoke-test code is aligned with the official MCP Python SDK 2.x interfaces and should be validated after installing `requirements.txt` in the target checkout.

## Apply to an existing checkout

1. Back up the current repository or create a Git branch.
2. Extract this package over the repository root.
3. Run `python apply_update.py` to remove legacy modules that may remain.
4. Recreate the virtual environment and install `requirements.txt`.
5. Run `python -m pytest -q`.
6. Run `python run_gui.py`.
7. Start in Read Only mode and run the real connection test for both STDIO and Streamable HTTP.
