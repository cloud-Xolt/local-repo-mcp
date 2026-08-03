# Local Repo MCP 1.2.2

A focused, security-oriented MCP server for exactly one local Git repository.

## Main changes

- Windows-safe unified diff transport: LF-normalized UTF-8 bytes are passed
  directly to `git apply`.
- Dirty-worktree checks are target-scoped; unrelated files no longer block
  every patch.
- Predefined tests remove unresolved `%VAR%` values, use an external temporary
  directory, and disable pytest cache creation.
- Streamable HTTP always requires Bearer authentication, including localhost.
- Audit records include event, process, transport, mode and repository metadata.
- Tool responses report the actual configured repository root.
- GUI connection tests verify that the MCP process is attached to the expected
  repository.
- The desktop UI now uses one native design system instead of runtime widget
  overrides: warm neutral surfaces, a readable 232 px navigation rail, consistent
  44 px controls, a 15 px body type baseline, balanced 3:2 form grids, and matching
  light/dark themes.
- `sitecustomize.py` is obsolete and must be deleted.

## Desktop UI

Launch it with `python run_gui.py` (or `start_gui.bat` on Windows). The layout
keeps repository scope and permission mode visible, groups uncommon settings in
collapsed sections, and separates service, ChatGPT Tunnel, and log workflows.
Styling tokens live in `gui/theme.py`; `gui/ui_overrides.py` remains only as a
no-op compatibility import for older launchers.
The supplied monochrome M artwork is used consistently in the navigation rail
and native desktop window icon. Its source and exported PNG/ICO sizes live in
`gui/assets/`.

## Manual replacement

Stop the GUI and `tunnel-client`. Copy all files from `replacement/` into the
repository root while preserving paths and overwrite existing files.

Run `cleanup_legacy_residue.ps1` once from the package directory. It removes
only these failed-update artifacts:

```text
sitecustomize.py
conftest.py
%SystemDrive%/
.pytest_cache/local_repo_update/
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Security boundary

Local Repo MCP is a single-user local tool for one configured Git repository.
It does not provide a general-purpose shell, unrestricted writes, automatic
commits, Git push/reset/rebase/checkout, multi-user RBAC, or a sandbox for
untrusted test code.

STDIO uses the local parent/child process boundary. With OpenAI Secure MCP
Tunnel, the Runtime API Key authenticates `tunnel-client` to the OpenAI control
plane. ChatGPT showing “No authentication” means no second MCP OAuth flow; it
does not mean anonymous public access.

Streamable HTTP requires:

```text
HTTP_AUTH_MODE=bearer
HTTP_AUTH_TOKEN=<random token>
```
