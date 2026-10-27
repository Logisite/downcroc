from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from downcroc.cli.errors import CliError


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().absolute()


def resolve_input(path: str | Path, *, field: str = "path") -> Path:
    resolved = expand(path)
    if not resolved.exists():
        raise CliError(
            f"{field} does not exist",
            code="input_unreadable",
            fields={field: str(resolved)},
            hint="check the path, or run this command from its directory",
        )
    if not resolved.is_file():
        raise CliError(
            f"{field} is not a file",
            code="input_unreadable",
            fields={field: str(resolved)},
        )
    return resolved


def read_text(path: str | Path, *, field: str = "path") -> str:
    resolved = resolve_input(path, field=field)
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError as error:
        raise CliError(
            "the file cannot be read",
            code="input_unreadable",
            fields={field: str(resolved)},
            hint=error.strerror or str(error),
        ) from error
    except UnicodeDecodeError as error:
        raise CliError(
            "the file is not valid UTF-8",
            code="input_unreadable",
            fields={field: str(resolved)},
        ) from error


def resolve_output(
    path: str | Path | None,
    *,
    default_dir: Path,
    default_name: str,
    directory_ok: bool = True,
    field: str = "path",
) -> Path:
    if path is None:
        target = default_dir / default_name
    else:
        target = expand(path)
        text = str(path)
        if target.is_dir() or text.endswith(os.sep):
            if not directory_ok:
                raise CliError(
                    f"{field} must be a file",
                    code="input_invalid",
                    fields={field: str(target)},
                )
            target = target / default_name
    parent = target.parent
    if not parent.is_dir():
        raise CliError(
            "the parent directory does not exist",
            code="input_invalid",
            fields={field: str(parent)},
            hint="create it first, or pass --mkdir where supported",
        )
    return target


def read_secret(path: str | Path, *, field: str = "password-file") -> str:
    resolved = expand(path)
    try:
        info = resolved.lstat()
    except OSError as error:
        raise CliError(
            "the password file cannot be read",
            code="input_unreadable",
            fields={field: str(resolved)},
            hint=error.strerror or str(error),
        ) from error
    if stat.S_ISLNK(info.st_mode):
        raise CliError(
            "the password file must not be a symlink",
            code="input_insecure",
            fields={field: str(resolved)},
        )
    if not stat.S_ISREG(info.st_mode):
        raise CliError(
            "the password file must be a regular file",
            code="input_insecure",
            fields={field: str(resolved)},
        )
    if info.st_mode & 0o077:
        raise CliError(
            "the password file is readable by other users",
            code="input_insecure",
            fields={field: oct(info.st_mode & 0o777)},
            hint="run `chmod 600` on it, or pass --password-stdin",
        )
    try:
        return _secret_text(resolved.read_text(encoding="utf-8"), field=field)
    except OSError as error:
        raise CliError(
            "the password file cannot be read",
            code="input_unreadable",
            fields={field: str(resolved)},
        ) from error


def read_secret_stdin(stream=None) -> str:
    handle = stream or sys.stdin
    text = handle.read()
    return _secret_text(text, field="--password-stdin")


def _secret_text(text: str, *, field: str) -> str:
    lines = text.splitlines()
    if not lines or not lines[0]:
        raise CliError(
            "a password is required",
            code="input_invalid",
            fields={field: "empty"},
        )
    extra = [line for line in lines[1:] if line.strip()]
    if extra:
        raise CliError(
            "the password input has more than one line",
            code="input_invalid",
            fields={field: f"{len(extra) + 1} lines"},
            hint="pass exactly one line, or use --password-file",
        )
    return lines[0]


def ensure_mode(path: Path, mode: int = 0o600) -> None:
    if path.exists():
        current = stat.S_IMODE(path.stat().st_mode)
        if current != mode:
            path.chmod(mode)
