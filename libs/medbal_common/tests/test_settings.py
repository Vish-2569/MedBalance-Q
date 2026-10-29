import os

from medbal_common.settings import Settings


def test_placeholder_not_set(monkeypatch):
    monkeypatch.setenv("QPIAI_OPT_URL", "<paste-qpiai-opt-api-url>")
    monkeypatch.setenv("QPIAI_OPT_TOKEN", "<paste-qpiai-opt-token>")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("QPIAI_QCLOUD_API_KEY", "")
    s = Settings()
    assert s.has_qpiai_opt() is False
    assert s.has_gemini() is False
    assert s.has_qcloud() is False


def test_real_keys_set(monkeypatch):
    monkeypatch.setenv("QPIAI_OPT_URL", "https://real.url")
    monkeypatch.setenv("QPIAI_OPT_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "real-key")
    monkeypatch.setenv("QPIAI_QCLOUD_API_KEY", "real-key")
    s = Settings()
    assert s.has_qpiai_opt() is True
    assert s.has_gemini() is True
    assert s.has_qcloud() is True


def test_key_status_no_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    monkeypatch.setenv("QPIAI_OPT_URL", "")
    monkeypatch.setenv("QPIAI_OPT_TOKEN", "")
    monkeypatch.setenv("QPIAI_QCLOUD_API_KEY", "")
    s = Settings()
    ks = s.key_status()
    assert ks["GEMINI_API_KEY"] == "set"
    assert ks["QPIAI_OPT_URL"] == "missing"
    for v in ks.values():
        assert v in ("set", "missing")
    assert "super-secret" not in str(ks)
