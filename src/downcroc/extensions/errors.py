from __future__ import annotations


class ExtensionError(Exception):
    code = "extension_error"
    hint = "check the extension manifest and config"


class ManifestError(ExtensionError):
    code = "extension_manifest_invalid"


class CapabilityDenied(ExtensionError):
    code = "extension_capability_denied"
    hint = "grant the capability in config.toml"


class ExtensionTimeout(ExtensionError):
    code = "extension_timeout"


class ExtensionCrashed(ExtensionError):
    code = "extension_crashed"


class ExtensionNotFound(ExtensionError):
    code = "extension_not_found"
