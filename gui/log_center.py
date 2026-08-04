from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

TOOL_TITLES = {
    "repo_list_files": ("列出文件", "List files"),
    "repo_read_file": ("读取文件", "Read file"),
    "repo_search_code": ("搜索代码", "Search code"),
    "repo_git_status": ("查看 Git 状态", "Read Git status"),
    "repo_git_diff": ("查看 Git 差异", "Read Git diff"),
    "repo_apply_patch": ("应用 Patch", "Apply patch"),
    "repo_run_test": ("运行测试", "Run tests"),
}
EVENT_TITLES = {
    "server_start": ("MCP 服务启动", "MCP server started"),
    "server_stop": ("MCP 服务停止", "MCP server stopped"),
    "server_error": ("MCP 服务异常", "MCP server error"),
    "http_listen": ("HTTP 开始监听", "HTTP listener started"),
    "http_authentication": ("HTTP 认证", "HTTP authentication"),
    "process_output": ("进程输出", "Process output"),
    "tunnel_detect": ("Tunnel 环境检测", "Tunnel environment check"),
    "tunnel_doctor": ("Tunnel Doctor", "Tunnel Doctor"),
    "tunnel_start": ("Tunnel 启动", "Tunnel started"),
}
STATUS = {
    "success": ("成功", "Success", "✓"),
    "running": ("运行中", "Running", "●"),
    "warning": ("警告", "Warning", "!"),
    "failed": ("失败", "Failed", "✕"),
    "error": ("失败", "Failed", "✕"),
    "denied": ("拒绝", "Denied", "⛔"),
    "unavailable": ("环境不可用", "Unavailable", "?"),
}
_PROCESS_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$")
_EXIT_CODE = re.compile(r"exited with code\s+(-?\d+)", re.IGNORECASE)


def read_tail_lines(path_text: str, *, max_lines: int = 1000, max_bytes: int = 1_000_000) -> list[str]:
    if not path_text.strip():
        return []
    path = Path(path_text).expanduser()
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            data = handle.read(max_bytes)
    except OSError:
        return []
    if start and b"\n" in data:
        data = data.split(b"\n", 1)[1]
    return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]


def _timestamp(event: dict[str, Any]) -> float:
    try:
        return float(event.get("timestamp", 0))
    except (TypeError, ValueError):
        return 0.0


def level_of(event: dict[str, Any]) -> str:
    explicit = str(event.get("level", "")).upper()
    if explicit in {"DEBUG", "INFO", "WARN", "ERROR", "SECURITY"}:
        return explicit
    status = str(event.get("status", "success")).lower()
    if status == "denied":
        return "SECURITY"
    if status in {"failed", "error", "unavailable"}:
        return "ERROR"
    if status in {"warning", "warn"}:
        return "WARN"
    return "INFO"


def parse_jsonl(lines: Iterable[str], source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {"status": "failed", "event": "invalid_log_record", "message": line}
        if not isinstance(value, dict):
            value = {"status": "failed", "event": "invalid_log_record", "message": line}
        event = dict(value)
        event.setdefault("source", source)
        event["level"] = level_of(event)
        event["_raw"] = line
        records.append(event)
    return records


def parse_process_lines(lines: Iterable[str], source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        match = _PROCESS_TIMESTAMP.match(text)
        timestamp = 0.0
        message = text
        if match:
            message = match.group(2)
            try:
                timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                pass
        lowered = message.lower()
        status = "success"
        exit_match = _EXIT_CODE.search(message)
        if (
            "failed" in lowered
            or "error" in lowered
            or (exit_match is not None and int(exit_match.group(1)) != 0)
        ):
            status = "failed"
        elif "warning" in lowered:
            status = "warning"
        elif "started" in lowered or "starting" in lowered:
            status = "running"
        event = {
            "timestamp": timestamp,
            "source": source,
            "category": "process",
            "event": "process_output",
            "status": status,
            "message": message,
            "_raw": line,
        }
        event["level"] = level_of(event)
        records.append(event)
    return records


def merge_events(*groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(item) for group in groups for item in group]
    result.sort(key=_timestamp, reverse=True)
    return result


def filter_events(
    events: Iterable[dict[str, Any]],
    *,
    query: str = "",
    level: str = "ALL",
    security_only: bool = False,
    limit: int = 500,
) -> list[dict[str, Any]]:
    needle = query.strip().casefold()
    expected = level.strip().upper()
    output: list[dict[str, Any]] = []
    for event in events:
        if event.get("hidden"):
            continue
        event_level = level_of(event)
        if expected != "ALL" and event_level != expected:
            continue
        if security_only and event_level != "SECURITY":
            continue
        if needle and needle not in json.dumps(event, ensure_ascii=False, sort_keys=True).casefold():
            continue
        output.append(event)
        if len(output) >= limit:
            break
    return output


def _localized(pair: tuple[str, str], language: str) -> str:
    return pair[0] if language == "zh" else pair[1]


def event_title(event: dict[str, Any], language: str) -> str:
    tool = str(event.get("tool", ""))
    if tool:
        return _localized(TOOL_TITLES.get(tool, (tool, tool)), language)
    action = str(event.get("event") or event.get("action") or "")
    if action:
        return _localized(EVENT_TITLES.get(action, (action, action)), language)
    return str(event.get("message") or "Event")


def event_time(event: dict[str, Any]) -> str:
    iso = str(event.get("timestamp_iso", ""))
    if iso:
        return iso.replace("T", " ")[:23]
    value = _timestamp(event)
    if not value:
        return "---- -- -- --:--:--"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def event_row(event: dict[str, Any], language: str) -> str:
    status = str(event.get("status", "success")).lower()
    label = STATUS.get(status, (status, status, "•"))
    status_text = label[0] if language == "zh" else label[1]
    if status == "denied":
        kind = str(event.get("denial_kind", ""))
        if kind == "permission_mode":
            status_text = "权限拒绝" if language == "zh" else "Permission denied"
        elif kind == "policy":
            status_text = "策略拒绝" if language == "zh" else "Policy denied"
    source = str(event.get("source", "mcp")).upper()[:6]
    target = str(event.get("target") or event.get("repository") or "")
    targets = event.get("targets")
    if not target and isinstance(targets, list) and targets:
        target = ", ".join(str(item) for item in targets[:2])
        if len(targets) > 2:
            target += f" +{len(targets) - 2}"
    suffix = f"  ·  {target}" if target else ""
    return f"{event_time(event)[11:19]}  {label[2]} {status_text:<4}  {source:<6}  {event_title(event, language)}{suffix}"


def event_details(event: dict[str, Any], language: str, *, raw: bool = False) -> str:
    if raw:
        return str(event.get("_raw") or json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True))
    status = str(event.get("status", "success")).lower()
    pair = STATUS.get(status, (status, status, "•"))
    fields = [
        (("时间", "Time"), event_time(event)),
        (("来源", "Source"), str(event.get("source", "mcp")).upper()),
        (("级别", "Level"), level_of(event)),
        (("状态", "Status"), f"{pair[2]} {pair[0] if language == 'zh' else pair[1]}"),
        (("操作", "Action"), event_title(event, language)),
    ]
    for key, labels in (
        ("target", ("目标", "Target")),
        ("duration_ms", ("耗时", "Duration")),
        ("mode", ("权限模式", "Permission mode")),
        ("transport", ("传输", "Transport")),
        ("process_id", ("进程", "Process")),
        ("event_id", ("事件 ID", "Event ID")),
        ("denial_kind", ("拒绝类型", "Denial kind")),
        ("failure_kind", ("失败类型", "Failure kind")),
        ("reason", ("原因", "Reason")),
        ("result_code", ("退出码", "Exit code")),
        ("error_type", ("错误类型", "Error type")),
        ("message", ("消息", "Message")),
    ):
        value = event.get(key)
        if value not in (None, ""):
            fields.append((labels, f"{value} ms" if key == "duration_ms" else str(value)))
    targets = event.get("targets")
    if isinstance(targets, list) and targets:
        fields.append((("目标", "Targets"), "\n  ".join(str(item) for item in targets)))
    lines: list[str] = []
    for labels, value in fields:
        lines.extend((_localized(labels, language), f"  {value}", ""))
    return "\n".join(lines).rstrip()


def _compact_details(event: dict[str, Any]) -> str:
    details: list[str] = []
    for key in ("transport", "mode"):
        value = event.get(key)
        if value:
            details.append(str(value).upper())
    if event.get("process_id"):
        details.append(f"PID {event['process_id']}")
    if isinstance(event.get("duration_ms"), int):
        details.append(f"{event['duration_ms']} ms")
    targets = event.get("targets")
    if isinstance(targets, list) and targets:
        visible = ", ".join(str(item) for item in targets[:3])
        if len(targets) > 3:
            visible += f" +{len(targets) - 3}"
        details.append(visible)
    if event.get("error_type"):
        details.append(str(event["error_type"]))
    message = str(event.get("message", "")).strip()
    if message and event.get("event") in {"process_output", "invalid_log_record"}:
        details.append(message)
    return " · ".join(details)


def format_events(
    events: Iterable[dict[str, Any]],
    language: str,
    *,
    raw: bool = False,
) -> str:
    rendered: list[str] = []
    for event in events:
        if raw:
            rendered.append(
                str(event.get("_raw") or json.dumps(event, ensure_ascii=False, sort_keys=True))
            )
            continue
        row = event_row(event, language)
        date = event_time(event)[:10]
        rendered.append(f"{date}  {row}" if not date.startswith("----") else row)
        details = _compact_details(event)
        if details:
            rendered.append(f"    {details}")
        rendered.append("")
    return "\n".join(rendered).rstrip()


def format_jsonl(
    lines: Iterable[str], language: str, *, raw: bool = False, source: str = "mcp"
) -> str:
    return format_events(parse_jsonl(lines, source), language, raw=raw)


def format_process_lines(
    lines: Iterable[str], language: str, *, raw: bool = False, source: str = "process"
) -> str:
    return format_events(parse_process_lines(lines, source), language, raw=raw)


def combine_log_sections(*sections: str) -> str:
    return "\n\n".join(
        section for section in sections if section.strip()
    )
