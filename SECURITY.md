# Security Policy

Local Repo MCP is a single-user local tool for one configured Git repository.
It is not a multi-tenant security boundary.

Expected controls include repository-root confinement, sensitive-path
blocking, no general-purpose shell, bounded output, filtered Git inspection,
validated text patches, target-scoped dirty-file protection, and mandatory
Bearer authentication for Streamable HTTP.

STDIO has no application-level login because the MCP server communicates with
its parent process over stdin/stdout. With OpenAI Secure MCP Tunnel,
`tunnel-client` authenticates to the OpenAI control plane using the Runtime API
Key. ChatGPT showing “No authentication” means no additional MCP OAuth flow is
configured; it does not make the local server an anonymous public endpoint.

Test mode executes repository code and must be enabled only for repositories
the user trusts. Credential-pattern detection is defense in depth and is not a
complete secret-scanning solution.
