"""Credential loader for salescoach scripts running on the Mac mini.

Strategy:
  1. Check in-process cache first (avoid repeated Keychain/network calls).
  2. Try macOS Keychain (fast, local, no network).
     Keychain service name: lowercase, hyphens (e.g. bites-anthropic-api-key).
  3. Fall back to GCP Secret Manager if ADC is configured.

One-time setup:
    security add-generic-password -a $(whoami) -s bites-anthropic-api-key -w '<key>' -U
Or for GCP: gcloud auth application-default login
"""
from __future__ import annotations

import os
import re
import subprocess

_GCP_PROJECT = "bites-new-api-ga4-report"

_CACHE: dict[str, str] = {}

_KEYCHAIN_NAMES: dict[str, str] = {
    "BITES_ANTHROPIC_API_KEY": "bites-anthropic-api-key",
}


def _keychain_name(gcp_name: str) -> str:
    """Derive a Keychain service name from a GCP secret name.

    Checks the explicit map first, then falls back to lowercase-hyphen transform.
    Example fallback: BITES_SOME_KEY -> bites-some-key
    """
    if gcp_name in _KEYCHAIN_NAMES:
        return _KEYCHAIN_NAMES[gcp_name]
    return re.sub(r"[_]+", "-", gcp_name).lower()


def _from_keychain(name: str) -> str:
    """Read a secret from macOS Keychain by its GCP secret name.

    Resolves the Keychain service name via _keychain_name, then calls the
    'security' CLI tool. Raises RuntimeError on failure or empty result.
    """
    kc_name = _keychain_name(name)
    username = os.environ.get("USER", os.environ.get("LOGNAME", ""))
    result = subprocess.run(
        ["security", "find-generic-password", "-s", kc_name, "-a", username, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Keychain lookup failed for service '{kc_name}' (exit {result.returncode})"
        )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"Keychain entry '{kc_name}' is empty")
    return value


def _from_gcp(name: str) -> str:
    """Read a secret from GCP Secret Manager.

    Requires google-cloud-secret-manager and application default credentials.
    Raises RuntimeError if the secret cannot be retrieved.
    """
    try:
        from google.cloud import secretmanager  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-secret-manager is not installed. "
            "Run: pip install google-cloud-secret-manager"
        ) from exc
    client = secretmanager.SecretManagerServiceClient()
    resource = f"projects/{_GCP_PROJECT}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": resource})
    value = response.payload.data.decode("utf-8").strip()
    if not value:
        raise RuntimeError(f"GCP secret '{name}' is empty")
    return value


def get_secret(name: str) -> str:
    """Fetch a secret value, caching the result in-process.

    Order: in-process cache, macOS Keychain, GCP Secret Manager.
    Raises RuntimeError with setup instructions if all sources fail.
    """
    if name in _CACHE:
        return _CACHE[name]

    kc_name = _keychain_name(name)

    # 1. Try Keychain.
    try:
        value = _from_keychain(name)
        _CACHE[name] = value
        return value
    except RuntimeError:
        pass

    # 2. Try GCP Secret Manager.
    try:
        value = _from_gcp(name)
        _CACHE[name] = value
        return value
    except RuntimeError:
        pass

    raise RuntimeError(
        f"Secret {name!r} not found in Keychain or GCP Secret Manager.\n"
        f"Store it in Keychain:\n"
        f"  security add-generic-password -a $(whoami) -s {kc_name} -w '<value>' -U\n"
        f"Or authenticate to GCP: gcloud auth application-default login"
    )
