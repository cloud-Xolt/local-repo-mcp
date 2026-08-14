from repo.file_scope import RepoFileScope
from repo.search import build_ripgrep_command


def test_query_is_always_a_pattern_not_an_option(tmp_path) -> None:
    scope = RepoFileScope(tmp_path)
    for query in ("--files", "--pre=touch /tmp/pwn", "-g", "--hidden"):
        command = build_ripgrep_command(
            query,
            scope,
            use_files_from=True,
            max_file_bytes=1000,
        )
        index = command.index("-e")
        assert command[index + 1] == query
        assert command[index + 2] == "--"
        assert command[-1] == "."
        assert "--files-from" in command
