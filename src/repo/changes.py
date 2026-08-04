from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChangeRecord:
    status: str
    paths: tuple[str, ...]

    @property
    def display_path(self) -> str:
        return self.paths[0] if self.paths else ""

    @property
    def is_rename_or_copy(self) -> bool:
        return self.status[:1] in {"R", "C"}


def _path(value: str) -> str:
    return value.replace("\\", "/")


def parse_porcelain_v1_z(raw: str) -> list[ChangeRecord]:
    tokens = [token for token in raw.split("\0") if token]
    records: list[ChangeRecord] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if len(token) < 3:
            continue
        status = token[:2]
        destination = token[3:] if token[2:3] == " " else token[2:]
        paths = [_path(destination)]
        if status[:1] in {"R", "C"} and index < len(tokens):
            paths.append(_path(tokens[index]))
            index += 1
        records.append(ChangeRecord(status=status, paths=tuple(paths)))
    return records


def parse_name_status_z(raw: str) -> list[ChangeRecord]:
    tokens = [token for token in raw.split("\0") if token]
    records: list[ChangeRecord] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if index >= len(tokens):
            break
        if status[:1] in {"R", "C"}:
            if index + 1 >= len(tokens):
                break
            new_path = _path(tokens[index])
            old_path = _path(tokens[index + 1])
            index += 2
            records.append(ChangeRecord(status=status, paths=(new_path, old_path)))
        else:
            records.append(ChangeRecord(status=status, paths=(_path(tokens[index]),)))
            index += 1
    return records
