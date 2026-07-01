from pr_repair.redaction import redact_secrets


def test_redacts_url_credentials() -> None:
    out = redact_secrets("cloning https://user:s3cr3t@github.com/o/r.git failed")
    assert "s3cr3t" not in out
    assert "https://***:***@github.com/o/r.git" in out


def test_redacts_bearer_and_key_value() -> None:
    out = redact_secrets("Authorization: Bearer abc.def.ghi\nAPI_KEY=supersecretvalue")
    assert "abc.def.ghi" not in out
    assert "supersecretvalue" not in out
    assert "***REDACTED***" in out


def test_redacts_known_token_prefixes() -> None:
    text = "leaked ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 and sk-ABCDEFGHIJKLMNOPQRSTUV"
    out = redact_secrets(text)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in out
    assert "sk-ABCDEFGHIJKLMNOPQRSTUV" not in out


def test_leaves_ordinary_stderr_intact() -> None:
    text = "AssertionError: expected 3 got 4 at test_foo.py:12"
    assert redact_secrets(text) == text
