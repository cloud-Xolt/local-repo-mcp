import os
import subprocess
from pathlib import Path

TEST_COMMANDS = {
    "python_pytest": {
        "image": "python:3.11-slim",
        "setup": "pip install -q pytest && pytest -q",
    },
    "go_test": {
        "image": "golang:1.22",
        "setup": "go test ./...",
    },
    "node_test": {
        "image": "node:20-slim",
        "setup": "npm test",
    },
    "node_lint": {
        "image": "node:20-slim",
        "setup": "npm run lint",
    },
    "maven_test": {
        "image": "maven:3.9-eclipse-temurin-17",
        "setup": "mvn test",
    },
    "gradle_test": {
        "image": "gradle:8-jdk17",
        "setup": "./gradlew test",
    },
}

SANDBOX_MEMORY = os.environ.get("SANDBOX_MEMORY", "2g")
SANDBOX_CPUS = os.environ.get("SANDBOX_CPUS", "2")
SANDBOX_TMPFS_MB = int(os.environ.get("SANDBOX_TMPFS_MB", "512"))


class SandboxExecutor:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def run_test(self, command_key: str, timeout_seconds: int) -> dict:
        if command_key not in TEST_COMMANDS:
            raise PermissionError(f"command_key not allowed: {command_key}")

        spec = TEST_COMMANDS[command_key]
        repo_mount = f"{self.repo_root}:/workspace:ro"
        shell_cmd = f"cd /workspace && {spec['setup']}"

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            SANDBOX_MEMORY,
            "--cpus",
            SANDBOX_CPUS,
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,noexec,size={SANDBOX_TMPFS_MB}m",
            "-v",
            repo_mount,
            "-w",
            "/workspace",
            spec["image"],
            "bash",
            "-lc",
            shell_cmd,
        ]

        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )

        return {
            "command": f"docker sandbox: {command_key}",
            "image": spec["image"],
            "returncode": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-20000:],
        }
