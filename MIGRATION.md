# Migration to the lightweight dual-transport version

This version keeps the project focused on one local Git repository and adds two official MCP transports:

- `stdio` for local MCP clients and process-based Secure MCP Tunnel profiles;
- `streamable-http` for URL-based and network MCP clients.

## Breaking changes

- Session, RBAC, risk scoring, policy YAML, automatic branches, patch approval state, and Docker sandbox code are removed.
- Modes are limited to `read`, `write`, and `test`.
- STDIO has no host or port. Host/port/path apply only to Streamable HTTP.
- The GUI no longer downloads `tunnel-client`.
- The OpenAI runtime API key is memory-only and never persisted.
- HTTP Bearer tokens are stored separately with restrictive filesystem permissions.

## Recommended update process

1. Back up your current configuration.
2. Delete the paths listed in `REMOVE_OLD_FILES.txt`.
3. Copy the new source tree over the repository.
4. Create a new virtual environment and install `requirements.txt`.
5. Start the GUI and select the target repository again.
6. Begin in `read` mode and run the real MCP connection test.
