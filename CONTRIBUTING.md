# Contributing

Local Repo MCP intentionally stays small and security-focused.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Pull requests

- Keep changes inside the documented single-repository scope.
- Do not add a general-purpose shell or unrestricted file writes.
- Do not add automatic Git push, reset, rebase, checkout, or merge.
- Do not reintroduce RBAC, sessions, risk scoring, enterprise policy engines, or Docker sandbox orchestration.
- Add tests for security-sensitive changes.
- Update both English and Chinese documentation for user-facing changes.
- Use `shell=False` for subprocesses and pass arguments as arrays.

## Good contribution areas

- Windows, macOS, and Linux compatibility
- GUI usability and accessibility
- localization
- security regression tests
- packaging and release automation
- MCP-client configuration examples
- diagnostics and troubleshooting
