import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SESSIONS_FILE = PROJECT_ROOT / "sessions.json"

PERMISSION_LEVELS = {
    "read": 1,
    "write": 2,
    "test": 3,
    "execute": 3,
    "ship": 4,
}


@dataclass
class Session:
    session_id: str
    user: str
    repo: str
    branch: str
    permission: str
    role: str
    created: int
    approved_patch_hash: str = ""

    def allows(self, required: str) -> bool:
        return PERMISSION_LEVELS.get(self.permission, 0) >= PERMISSION_LEVELS.get(required, 0)


class SessionManager:
    def __init__(self, repo_root: Path, sessions_file: Path | None = None) -> None:
        self.repo_root = repo_root
        if sessions_file is None:
            env_path = os.environ.get("SESSIONS_FILE", "")
            sessions_file = Path(env_path) if env_path else DEFAULT_SESSIONS_FILE
        self.sessions_file = sessions_file
        self._sessions: dict[str, Session] = {}
        self._load()

    def _load(self) -> None:
        if not self.sessions_file.exists():
            return
        data = json.loads(self.sessions_file.read_text(encoding="utf-8"))
        for item in data:
            item.setdefault("role", "developer")
            session = Session(**item)
            self._sessions[session.session_id] = session

    def _save(self) -> None:
        payload = [asdict(s) for s in self._sessions.values()]
        self.sessions_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, user: str, permission: str, branch: str, role: str = "developer") -> Session:
        session_id = f"agent-{uuid.uuid4().hex[:12]}"
        session = Session(
            session_id=session_id,
            user=user,
            repo=str(self.repo_root),
            branch=branch,
            permission=permission,
            role=role,
            created=int(time.time()),
        )
        self._sessions[session_id] = session
        self._save()
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str, required_permission: str) -> Session:
        if not session_id:
            raise PermissionError("session_id is required for this operation")
        session = self._sessions.get(session_id)
        if not session:
            raise PermissionError(f"unknown session: {session_id}")
        if not session.allows(required_permission):
            raise PermissionError(
                f"session permission={session.permission} insufficient for {required_permission}"
            )
        return session

    def update_branch(self, session_id: str, branch: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.branch = branch
            self._save()

    def approve_patch(self, session_id: str, patch_hash: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            raise PermissionError(f"unknown session: {session_id}")
        session.approved_patch_hash = patch_hash
        self._save()

    def require_approved_patch(self, session_id: str, patch_hash: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            raise PermissionError(f"unknown session: {session_id}")
        if session.approved_patch_hash != patch_hash:
            raise PermissionError("patch not approved; call repo_approve_patch after repo_prepare_patch")

    def end(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._save()
