from gui.config import AppConfig
from gui.runtime_config import merge_environment


def test_explicit_http_environment_wins_over_stale_gui_config() -> None:
    stale = AppConfig(
        repo_root="",
        transport="streamable-http",
        http_auth_token="weak",
    )
    explicit = {
        "REPO_ROOT": "C:/repos/project",
        "MCP_TRANSPORT": "streamable-http",
        "HTTP_AUTH_MODE": "bearer",
        "HTTP_AUTH_TOKEN": "x" * 32,
    }
    merged = merge_environment(stale, explicit, override=False)
    assert merged["REPO_ROOT"] == "C:/repos/project"
    assert merged["MCP_TRANSPORT"] == "streamable-http"
    assert merged["HTTP_AUTH_TOKEN"] == "x" * 32
