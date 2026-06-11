"""Tests for tools/secrets.py credential fetch logic (offline, no network calls)."""
import pytest
from unittest import mock
from tools import secrets


def test_get_secret_reads_keychain_first():
    with mock.patch("tools.secrets._from_keychain", return_value="kc-value") as kc:
        secrets._CACHE.clear()
        assert secrets.get_secret("BITES_ANTHROPIC_API_KEY") == "kc-value"
        kc.assert_called_once()


def test_get_secret_caches_result():
    secrets._CACHE.clear()
    secrets._CACHE["BITES_ANTHROPIC_API_KEY"] = "cached-value"
    with mock.patch("tools.secrets._from_keychain") as kc, \
         mock.patch("tools.secrets._from_gcp") as gcp:
        result = secrets.get_secret("BITES_ANTHROPIC_API_KEY")
        assert result == "cached-value"
        kc.assert_not_called()
        gcp.assert_not_called()


def test_get_secret_falls_back_to_gcp_when_keychain_fails():
    with mock.patch("tools.secrets._from_keychain", side_effect=RuntimeError("not in keychain")), \
         mock.patch("tools.secrets._from_gcp", return_value="gcp-value") as gcp:
        secrets._CACHE.clear()
        result = secrets.get_secret("BITES_ANTHROPIC_API_KEY")
        assert result == "gcp-value"
        gcp.assert_called_once()


def test_missing_secret_raises_with_setup_hint():
    with mock.patch("tools.secrets._from_keychain", side_effect=RuntimeError), \
         mock.patch("tools.secrets._from_gcp", side_effect=RuntimeError):
        secrets._CACHE.clear()
        with pytest.raises(RuntimeError, match="bites-anthropic-api-key"):
            secrets.get_secret("BITES_ANTHROPIC_API_KEY")


def test_get_secret_caches_gcp_result():
    secrets._CACHE.clear()
    with mock.patch("tools.secrets._from_keychain", side_effect=RuntimeError), \
         mock.patch("tools.secrets._from_gcp", return_value="gcp-value"):
        secrets.get_secret("BITES_ANTHROPIC_API_KEY")
    assert secrets._CACHE.get("BITES_ANTHROPIC_API_KEY") == "gcp-value"
