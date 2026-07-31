# Security Policy

## Supported versions

Security fixes are applied to the latest release line.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public issue. Contact the maintainer privately through the security-reporting channel listed on the GitHub repository.

Include:

- affected version or commit;
- operating system;
- reproduction steps;
- expected and actual behavior;
- security impact;
- a minimal proof of concept when safe to provide.

## Security boundary

Local Repo MCP is a single-user local tool for one configured Git repository. It is not a multi-tenant security boundary.

Expected controls include repository-root confinement, sensitive-path blocking, no general-purpose shell, validated text patches, bounded outputs, filtered Git inspection, and optional HTTP authentication.

Expected limitations include execution of repository code in test mode and incomplete credential-pattern detection. These limitations are documented in the README and are not by themselves vulnerabilities.
