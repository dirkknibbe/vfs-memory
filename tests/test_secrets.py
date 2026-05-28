from agent_vfs.secrets import looks_like_secret


def test_aws_key():
    assert looks_like_secret("My key is AKIAIOSFODNN7EXAMPLE!")


def test_github_pat():
    assert looks_like_secret("token: ghp_" + "A" * 36)
    assert looks_like_secret("token: ghs_" + "A" * 36)


def test_jwt():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-123_def"
    assert looks_like_secret(f"Authorization: Bearer {jwt}")


def test_clean_body():
    assert not looks_like_secret("This is just a normal note about something.")


def test_short_string_no_false_positive():
    assert not looks_like_secret("AKIA")
    assert not looks_like_secret("ghp_short")
