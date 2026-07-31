import re


class PatchValidator:
    PATCH_STAT_LINE = re.compile(r"^\s(.+?)\s+\|\s+\d+\s+[+-]+$")

    def __init__(self, run_git) -> None:
        self.run_git = run_git

    def targets_from_git_stat(self, patch: str) -> list[str]:
        result = self.run_git(
            ["apply", "--check", "--stat", "--whitespace=nowarn"],
            input_text=patch,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git apply --stat --check failed:\n{result.stderr}")

        paths: list[str] = []
        for line in result.stdout.splitlines():
            match = self.PATCH_STAT_LINE.match(line)
            if match:
                path = match.group(1).strip()
                if path and path != "/dev/null":
                    paths.append(path)
        if not paths:
            raise ValueError("no target files found in patch (git apply --stat)")
        return sorted(set(paths))
