from repo.search import build_ripgrep_command


def test_query_is_always_a_pattern_not_an_option() -> None:
    for query in ("--files", "--pre=touch /tmp/pwn", "-g", "--hidden"):
        command = build_ripgrep_command(query)
        index = command.index("-e")
        assert command[index + 1] == query
        assert command[index + 2] == "--"
        assert command[-1] == "."
