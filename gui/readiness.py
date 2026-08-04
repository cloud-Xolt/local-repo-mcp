from __future__ import annotations

import http.client
import json
import socket
import ssl
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from gui.config import AppConfig


def health_url(config: AppConfig) -> str:
    if config.http_tls_terminated_proxy:
        endpoint = urlsplit(config.endpoint_url())
        return urlunsplit((endpoint.scheme, endpoint.netloc, "/healthz", "", ""))
    return config.runtime_health_url()


def tls_context(config: AppConfig, url: str) -> ssl.SSLContext:
    parsed = urlsplit(url)
    cafile = None
    if parsed.scheme == "https" and not config.http_tls_terminated_proxy:
        cafile = config.http_tls_certfile.strip() or None
    context = ssl.create_default_context(cafile=cafile)
    if config.http_client_certfile.strip() and config.http_client_keyfile.strip():
        context.load_cert_chain(
            config.http_client_certfile,
            config.http_client_keyfile,
        )
    return context


def native_tls_probe_target(config: AppConfig) -> tuple[str, int, str, str]:
    public = urlsplit(config.http_public_url.strip())
    if public.scheme != "https" or not public.hostname:
        raise ValueError("native TLS readiness requires a valid HTTPS public URL")
    connect_host = config.http_host.strip() or "127.0.0.1"
    if connect_host == "0.0.0.0":
        connect_host = "127.0.0.1"
    elif connect_host == "::":
        connect_host = "::1"
    return connect_host, config.http_port, public.hostname, public.netloc


class _SNIHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        connect_host: str,
        port: int,
        *,
        server_hostname: str,
        context: ssl.SSLContext,
        timeout: float,
    ) -> None:
        super().__init__(connect_host, port, context=context, timeout=timeout)
        self._server_hostname = server_hostname

    def connect(self) -> None:
        raw = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(
                raw,
                server_hostname=self._server_hostname,
            )
        except BaseException:
            raw.close()
            raise


def read_health_payload(config: AppConfig, timeout: float = 1.5) -> dict:
    if (
        config.http_tls_certfile.strip()
        and config.http_public_url.strip()
        and not config.http_tls_terminated_proxy
    ):
        connect_host, port, server_name, host_header = native_tls_probe_target(config)
        connection = _SNIHTTPSConnection(
            connect_host,
            port,
            server_hostname=server_name,
            context=tls_context(config, config.http_public_url),
            timeout=timeout,
        )
        try:
            connection.request(
                "GET",
                "/healthz",
                headers={
                    "Host": host_header,
                    "Authorization": f"Bearer {config.http_auth_token}",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise OSError(f"health endpoint returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    url = health_url(config)
    parsed = urlsplit(url)
    handlers = [ProxyHandler({})]
    if parsed.scheme == "https":
        handlers.append(HTTPSHandler(context=tls_context(config, url)))
    request = Request(
        url,
        headers={"Authorization": f"Bearer {config.http_auth_token}"},
        method="GET",
    )
    with build_opener(*handlers).open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

