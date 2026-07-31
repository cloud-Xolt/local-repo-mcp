import pytest

from repo.git import reject_unsupported_patch_types
from security.scanner import SecretScanner


@pytest.mark.parametrize("marker", [
    "GIT binary patch",
    "rename from old.txt",
    "copy to new.txt",
    "new file mode 120000",
    "new file mode 160000",
])
def test_rejects_unsupported_patch_types(marker: str) -> None:
    with pytest.raises(PermissionError):
        reject_unsupported_patch_types(marker)


def test_blocks_common_credentials_in_added_lines() -> None:
    patch = """--- a/config.py
+++ b/config.py
@@ -0,0 +1 @@
+API_KEY = \"ghp_abcdefghijklmnopqrstuvwxyz012345\"
"""
    with pytest.raises(PermissionError):
        SecretScanner().require_clean_patch(patch)
