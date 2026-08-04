# Deployment Guide

## Deployment models

### STDIO

Use STDIO when the MCP client launches the server as a child process. The generated client configuration points to the packaged launcher and works in both source and installed layouts.

### Secure MCP Tunnel

The optional `tunnel-client` launches the same STDIO command. Runtime API keys remain in process memory and are not written to Local Repo MCP configuration files.

### Native HTTPS

Required settings:

```text
MCP_TRANSPORT=streamable-http
HTTP_HOST=0.0.0.0
HTTP_PORT=8443
HTTP_PATH=/mcp
HTTP_PUBLIC_URL=https://mcp.example.com/mcp
HTTP_AUTH_MODE=bearer
HTTP_AUTH_TOKEN=<random-token>
HTTP_ALLOWED_HOSTS=mcp.example.com
HTTP_TLS_CERTFILE=/etc/local-repo-mcp/server.crt
HTTP_TLS_KEYFILE=/etc/local-repo-mcp/server.key
```

Optional mTLS:

```text
HTTP_TLS_CLIENT_CA=/etc/local-repo-mcp/client-ca.crt
```

When the GUI itself connects to an mTLS server, configure its client certificate and private key in the HTTP advanced settings.

### TLS reverse proxy

The backend may bind to loopback, a private address, or `0.0.0.0` inside a container or Kubernetes pod.

```text
MCP_TRANSPORT=streamable-http
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
HTTP_PATH=/mcp
HTTP_PUBLIC_URL=https://mcp.example.com/mcp
HTTP_TLS_TERMINATED_PROXY=true
HTTP_PROXY_TRUSTED_IPS=10.0.0.0/8
HTTP_AUTH_MODE=bearer
HTTP_AUTH_TOKEN=<random-token>
HTTP_ALLOWED_HOSTS=mcp.example.com
```

The proxy must:

- terminate HTTPS;
- preserve the configured MCP path;
- forward the Authorization header;
- prevent direct public access to the backend;
- originate from an address in `HTTP_PROXY_TRUSTED_IPS`.

`HTTP_PUBLIC_URL` must use HTTPS, contain no credentials/query/fragment, and have the same path as `HTTP_PATH`.

## systemd

Copy `systemd/local-repo-mcp-http.service` and create the environment file from `systemd/mcp.env.example`. Review repository paths, certificate paths, proxy ranges, Host/Origin allowlists, and file permissions before enabling the service.

## Containers and Kubernetes

Mount the target repository and certificates read-only where applicable. Persist or share the Git metadata directory if multiple Local Repo MCP processes can target the same working tree; the mutation lock is stored there.

## Runtime and audit logs

Configure separate files for operational MCP events and security audit events:

```text
MCP_LOG=/var/log/local-repo-mcp/mcp.jsonl
AUDIT_LOG=/var/log/local-repo-mcp/audit.jsonl
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=3
```

Each JSONL record is written under a cross-process file lock. Files rotate when they reach `LOG_MAX_BYTES`; numbered backups are retained up to `LOG_BACKUP_COUNT`. The GUI reads only a bounded tail, so opening the log center does not load the complete file. Ensure the log directory is included in the service account's writable paths. Process and Tunnel output is redacted for common Bearer tokens and API-key formats before it reaches the GUI.

## Readiness and release inputs

For native TLS, the GUI probes the local listener while using the hostname from `HTTP_PUBLIC_URL` for TLS SNI and the HTTP Host header. This avoids certificate mismatches on wildcard bindings without requiring public-DNS hairpin routing. Reverse-proxy mode continues to probe the public HTTPS endpoint.

Replace `HTTP_AUTH_TOKEN=CHANGE_ME` with a generated random token; placeholder and low-variation values are rejected. Write and test deployments must configure `AUDIT_LOG` and should keep `AUDIT_REQUIRED=true`.

Source bootstrap installs the exact top-level versions in `requirements.lock`. Wheel validation installs the built artifact outside the source checkout and runs the packaged GUI smoke entry.

