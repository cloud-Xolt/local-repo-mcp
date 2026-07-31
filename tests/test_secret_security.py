import pytest

from security.scanner import SecretScanner


@pytest.fixture
def scanner() -> SecretScanner:
    return SecretScanner()


def test_block_aws_key(scanner: SecretScanner) -> None:
    patch = """\
diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1 +1,2 @@
 x = 1
+AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE
"""
    with pytest.raises(PermissionError, match="secret scanner"):
        scanner.require_clean_patch(patch)


def test_block_github_token(scanner: SecretScanner) -> None:
    patch = """\
diff --git a/t.py b/t.py
--- a/t.py
+++ b/t.py
@@ -1 +1,2 @@
 pass
+TOKEN = ghp_1234567890123456789012345678901234AB
"""
    with pytest.raises(PermissionError):
        scanner.require_clean_patch(patch)


def test_block_private_key(scanner: SecretScanner) -> None:
    patch = """\
diff --git a/k.pem b/k.pem
--- a/k.pem
+++ b/k.pem
@@ -0,0 +1,2 @@
+-----BEGIN RSA PRIVATE KEY-----
+MIIBogIBAAJBALRi
"""
    with pytest.raises(PermissionError):
        scanner.require_clean_patch(patch)


def test_allow_clean_patch(scanner: SecretScanner) -> None:
    patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 x = 1
+x = 2
"""
    scanner.require_clean_patch(patch)
