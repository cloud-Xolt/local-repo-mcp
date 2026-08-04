from __future__ import annotations

import hmac
import ipaddress
from dataclasses import dataclass
from typing import Callable

from starlette.responses import JSONResponse


@dataclass(frozen=True)
class HttpSecuritySettings:
    token: str
    protected_path: str
    proxy_mode: bool
    trusted_networks: tuple[ipaddress._BaseNetwork, ...]

    @classmethod
    def build(
        cls,
        *,
        token: str,
        protected_path: str,
        proxy_mode: bool,
        trusted_values: list[str],
    ) -> "HttpSecuritySettings":
        if len(token) < 32:
            raise RuntimeError(
                "HTTP_AUTH_TOKEN must contain at least 32 characters"
            )
        networks: list[ipaddress._BaseNetwork] = []
        for value in trusted_values:
            try:
                networks.append(ipaddress.ip_network(value, strict=False))
            except ValueError as exc:
                raise RuntimeError(
                    f"invalid trusted proxy IP/network: {value}"
                ) from exc
        if proxy_mode and not networks:
            raise RuntimeError(
                "TLS proxy mode requires HTTP_PROXY_TRUSTED_IPS"
            )
        path = protected_path.rstrip("/") or "/"
        return cls(token, path, proxy_mode, tuple(networks))

    def protects(self, request_path: str) -> bool:
        return (
            self.protected_path == "/"
            or request_path == self.protected_path
            or request_path.startswith(self.protected_path + "/")
            or request_path == "/healthz"
        )


class HttpSecurityMiddleware:
    """Streaming-safe authentication and HTTPS enforcement.

    Uvicorn owns immediate-peer trust through forwarded_allow_ips. After its
    proxy-header middleware runs, scope["client"] may represent the end user,
    so application code must not reinterpret it as the proxy address.
    """

    def __init__(
        self,
        application,
        settings: HttpSecuritySettings,
        audit: Callable[..., None],
    ) -> None:
        self.application = application
        self.settings = settings
        self.audit = audit

    async def _reject(
        self,
        scope,
        receive,
        send,
        *,
        reason: str,
        status: int,
    ) -> None:
        client = scope.get("client")
        client_host = client[0] if client else ""
        self.audit(
            event="http_security",
            status="denied",
            reason=reason,
            client_host=client_host,
        )
        response = JSONResponse(
            {"error": reason},
            status_code=status,
            headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
        )
        await response(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.application(scope, receive, send)
            return
        request_path = str(scope.get("path", ""))
        if not self.settings.protects(request_path):
            await self.application(scope, receive, send)
            return

        if (
            self.settings.proxy_mode
            and str(scope.get("scheme", "")).lower() != "https"
        ):
            await self._reject(
                scope,
                receive,
                send,
                reason="https_required",
                status=403,
            )
            return

        headers = {
            key.lower(): value for key, value in scope.get("headers", [])
        }
        supplied = headers.get(b"authorization", b"").decode(
            "latin-1",
            errors="replace",
        )
        expected = f"Bearer {self.settings.token}"
        if not hmac.compare_digest(supplied, expected):
            await self._reject(
                scope,
                receive,
                send,
                reason="unauthorized",
                status=401,
            )
            return
        await self.application(scope, receive, send)
