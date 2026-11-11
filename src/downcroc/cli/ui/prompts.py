from __future__ import annotations

import getpass
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from downcroc.cli.errors import Cancelled, CliError, no_terminal
from downcroc.cli.ui import ansi
from downcroc.cli.ui.edit import edit_line
from downcroc.cli.ui.select import Choice, OptionsRequest, Quit, select
from downcroc.cli.ui.session import Ui, editor

YES = {"y", "yes"}
NO = {"n", "no", ""}


@dataclass(frozen=True)
class Option:
    label: str
    value: object = None
    detail: str = ""
    badge: str = ""

    def line(self) -> str:
        parts = [self.label]
        if self.badge:
            parts.append(self.badge)
        return "  ".join(parts) + (f"    {self.detail}" if self.detail else "")


@dataclass
class Form:
    """Collects answers and prints them again as a summary."""

    title: str
    answers: list[tuple[str, str]] = field(default_factory=list)

    def remember(self, label: str, value: str) -> None:
        self.answers.append((label, value))

    def show(self, ui: Ui) -> None:
        if not self.answers:
            return
        width = max(len(label) for label, _ in self.answers)
        print(ui.paint(self.title, "good"))
        for label, value in self.answers:
            print(f"  {label:<{width}}  {value}")


def _keyboard(ui: Ui) -> bool:
    return ui.interactive and ansi.raw_available() and sys.stdin.isatty()


def _plain(
    label: str,
    *,
    default: str | None,
    required: bool,
    field: str | None,
) -> str:
    if not ui_interactive():
        if default is not None:
            return default
        raise CliError(
            f"{label.rstrip(':')} is required",
            code="usage",
            hint=f"pass {field}" if field else None,
            exit_code=2,
        )
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            answer = input(f"{label}{suffix}: ").strip()
        except EOFError as error:
            raise Cancelled() from error
        if answer:
            return answer
        if default is not None:
            return default
        if not required:
            return ""
        print("  a value is required, or press ctrl-c to cancel")


def ui_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def ask(
    label: str,
    *,
    ui: Ui,
    default: str | None = None,
    required: bool = True,
    field: str | None = None,
) -> str:
    if not ui.interactive:
        return _plain(label, default=default, required=required, field=field)
    if not _keyboard(ui):
        return _plain(label, default=default, required=required, field=field)
    paths = (
        (field or "") in {"FILE", "--client", "--path"}
        or "path" in label.casefold()
        or "file" in label.casefold()
    )
    return edit_line(
        ui,
        label,
        default=default,
        required=required,
        complete_paths=paths,
    )


def ask_secret(
    label: str,
    *,
    ui: Ui,
    flag: str = "--password-stdin",
    required: bool = True,
) -> str:
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise no_terminal(flag)
    if _keyboard(ui):
        return edit_line(ui, label, mask=True, required=required)
    try:
        value = getpass.getpass(f"{label}: ")
    except (EOFError, KeyboardInterrupt) as error:
        raise Cancelled() from error
    except Exception as error:  # getpass raises platform errors without a tty
        raise no_terminal(flag) from error
    if not value:
        if not required:
            return ""
        raise CliError("a password is required", code="input_invalid")
    return value


def confirm(
    question: str,
    *,
    ui: Ui,
    default: bool = False,
    yes_flag: bool = False,
) -> bool:
    if yes_flag:
        return True
    if not ui.interactive:
        raise CliError(
            "this action changes data and needs confirmation",
            code="confirmation_required",
            hint="pass --yes to confirm in a script",
        )
    if not _keyboard(ui):
        return _confirm_plain(question, default=default)
    choices = [Choice("Yes", True), Choice("No", False)]
    chosen = select(
        ui,
        question,
        choices,
        default=0 if default else 1,
        back=False,
        filterable=False,
        shortcuts={"y": 0, "Y": 0, "n": 1, "N": 1},
    )
    return bool(chosen)


def _confirm_plain(question: str, *, default: bool) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        try:
            answer = input(f"{question}{suffix}").strip().lower()
        except EOFError as error:
            raise Cancelled() from error
        if answer in YES:
            return True
        if answer in NO:
            return default
        print("  enter y or n")


def confirm_word(
    word: str,
    question: str,
    *,
    ui: Ui,
    yes_flag: bool = False,
    stream=None,
) -> None:
    if yes_flag:
        return
    out = stream or sys.stderr
    if not ui.interactive:
        raise CliError(
            "this action replaces data and needs confirmation",
            code="confirmation_required",
            hint="pass --yes to confirm in a script",
        )
    print(question, file=out)
    if not _keyboard(ui):
        _confirm_word_plain(word, out)
        return
    while True:
        answer = edit_line(
            ui,
            f"type {word} to continue",
            required=False,
        )
        if answer == word:
            return
        print(ui.paint(f"  type {word} exactly, or press ctrl-c to cancel", "warn"))


def _confirm_word_plain(word: str, out) -> None:
    while True:
        try:
            answer = input(f"type {word} to continue: ").strip()
        except (EOFError, KeyboardInterrupt) as error:
            raise Cancelled() from error
        if answer == word:
            return
        print(f"  type {word} exactly, or press ctrl-c to cancel", file=out)


def choose(
    title: str,
    options: list[Option],
    *,
    ui: Ui,
    default: int | None = None,
    back: bool = True,
    quit_: bool = False,
    options_key: bool = False,
) -> object | None:
    if not options:
        return None
    if not ui.interactive:
        if default is None:
            raise CliError(
                "a choice is required",
                code="usage",
                hint="run this command on a terminal",
                exit_code=2,
            )
        return options[default].value
    if not _keyboard(ui):
        return _choose_plain(
            title,
            options,
            ui=ui,
            default=default,
            back=back,
            quit_=quit_,
            options_key=options_key,
        )
    choices = [
        Choice(option.label, option.value, option.detail, option.badge)
        for option in options
    ]
    return select(
        ui,
        title,
        choices,
        default=default,
        back=back,
        quit_=quit_,
        options=options_key,
    )


def _choose_plain(
    title: str,
    options: list[Option],
    *,
    ui: Ui,
    default: int | None,
    back: bool,
    quit_: bool,
    options_key: bool,
) -> object | None:
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"  {index}) {option.line()}")
    prompt = f"select 1-{len(options)}"
    if default is not None:
        prompt += f" [{default + 1}]"
    while True:
        try:
            answer = input(f"  {prompt}: ").strip()
        except EOFError as error:
            raise Cancelled() from error
        lowered = answer.lower()
        if lowered in {"q", "quit"}:
            if quit_:
                raise Quit()
            if back:
                return None
        if lowered == "o" and options_key:
            return OptionsRequest(default or 0)
        if not answer and default is not None:
            return options[default].value
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1].value
        print(f"  enter a number between 1 and {len(options)}")


def choose_many(
    title: str,
    options: list[Option],
    *,
    ui: Ui,
) -> list[object]:
    if not ui.interactive or not options:
        return []
    if not _keyboard(ui):
        return _choose_many_plain(title, options)
    choices = [
        Choice(option.label, option.value, option.detail, option.badge)
        for option in options
    ]
    chosen = select(ui, title, choices, multi=True, filterable=False)
    indexes = chosen if isinstance(chosen, list) else []
    return [options[index].value for index in indexes]


def _choose_many_plain(title: str, options: list[Option]) -> list[object]:
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"  {index}) {option.line()}")
    while True:
        try:
            answer = input("  select numbers, comma separated, or blank: ").strip()
        except EOFError as error:
            raise Cancelled() from error
        if not answer:
            return []
        chosen: list[object] = []
        valid = True
        for part in answer.split(","):
            part = part.strip()
            if not part.isdigit() or not 1 <= int(part) <= len(options):
                valid = False
                break
            chosen.append(options[int(part) - 1].value)
        if valid:
            return chosen
        print("  enter numbers from the list")


def open_editor(text: str, *, ui: Ui, suffix: str = ".txt") -> str:
    command, name = editor()
    if not command:
        raise CliError(
            "no editor is configured",
            code="no_editor",
            hint="set $EDITOR, or write the body with --text",
        )
    del ui
    with tempfile.NamedTemporaryFile(
        "w+", suffix=suffix, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        path = Path(handle.name)
    try:
        print(f"  opening {path} in {name} ...")
        hints = {
            "nano": "save with Ctrl+O then Enter; exit with Ctrl+X",
            "vim": "save and exit with :wq",
            "vi": "save and exit with :wq",
            "emacs": "save with Ctrl+X Ctrl+S; exit with Ctrl+X Ctrl+C",
        }
        print(f"  {hints.get(name, 'save the file, then close the editor')}")
        subprocess.run([*command, str(path)], check=False)
        return path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)


def next_step(ui: Ui, command: str) -> None:
    if ui.interactive and not ui.quiet:
        print(f"next: {command}")
