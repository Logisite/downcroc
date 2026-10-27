from __future__ import annotations

import os
from dataclasses import dataclass

SERVICE = "downcroc"
ALLOWED = (
    "keyring.backends.SecretService",
    "keyring.backends.libsecret",
    "keyring.backends.Windows",
)
MODE = os.environ.get("DOWNCROC_KEYRING", "auto")


@dataclass(frozen=True)
class Store:
    available: bool
    name: str
    reason: str = ""


def _keyring():
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError:
        return None, None
    return keyring, KeyringError


def describe() -> Store:
    if MODE == "unavailable":
        return Store(False, "unavailable", "disabled by DOWNCROC_KEYRING")
    keyring, errors = _keyring()
    if keyring is None or errors is None:
        return Store(False, "unavailable", "the keyring package is not installed")
    try:
        current = keyring.get_keyring()
    except (errors, OSError, RuntimeError) as error:
        return Store(False, "unavailable", str(error))
    module = type(current).__module__
    if not any(module == allowed for allowed in ALLOWED):
        return Store(False, "unavailable", f"{module} is not a system store")
    return Store(True, _name(module))


def _name(module: str) -> str:
    if module.endswith("Windows"):
        return "windows credential manager"
    return "secret service"


def available() -> bool:
    return describe().available


def status() -> str:
    store = describe()
    if not store.available:
        return "unavailable"
    return f"on ({store.name})"


def get(account: str) -> str | None:
    if not available():
        return None
    keyring, errors = _keyring()
    if keyring is None or errors is None:
        return None
    try:
        return keyring.get_password(SERVICE, account)
    except errors, OSError, RuntimeError:
        return None


def set_password(account: str, password: str) -> bool:
    if not available():
        return False
    keyring, errors = _keyring()
    if keyring is None or errors is None:
        return False
    try:
        keyring.set_password(SERVICE, account, password)
        return True
    except errors, OSError, RuntimeError:
        return False


def delete(account: str) -> bool:
    if not available():
        return False
    keyring, errors = _keyring()
    if keyring is None or errors is None:
        return False
    try:
        keyring.delete_password(SERVICE, account)
        return True
    except errors, OSError, RuntimeError:
        return False
