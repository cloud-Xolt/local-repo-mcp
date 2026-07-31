from security.scanner import SecretScanner


def test_blocks_aws_key() -> None:
    scanner = SecretScanner()
    patch = """--- a/x.txt
+++ b/x.txt
@@ -0,0 +1 @@
+AKIAIOSFODNN7EXAMPLE
"""
    assert scanner.scan_patch(patch)


def test_blocks_private_key() -> None:
    scanner = SecretScanner()
    patch = """--- a/x.txt
+++ b/x.txt
@@ -0,0 +1 @@
+-----BEGIN RSA PRIVATE KEY-----
"""
    assert scanner.scan_patch(patch)
