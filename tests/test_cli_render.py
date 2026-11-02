from __future__ import annotations

import re
import signal

from tests.harness.pty import Session

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
DOWN = b"\x1b[B"


def _plain(chunk: bytes) -> str:
    return ANSI.sub("", chunk.decode("utf-8", "replace"))


def test_provider_menu_redraws_in_place(stack_factory) -> None:
    stack = stack_factory()
    for width in (40, 100):
        session = Session(stack, "account", "add", width=width)
        try:
            session.wait_for(b"enter select")
            session.write(DOWN)
            anchor = session.filled()
            assert len(anchor) == 6
            assert anchor == list(range(anchor[0], anchor[0] + 6))
            for _ in range(10):
                session.write(DOWN)
                assert session.filled() == anchor
            assert session.bare_newlines() == 0
            assert "esc cancel" in session.screen()[anchor[-1]]
        finally:
            session.write(b"\x03")
            session.close()


def test_menu_redraws_after_resize(stack_factory) -> None:
    stack = stack_factory()
    session = Session(stack, "account", "add", width=100)
    try:
        session.wait_for(b"up/down move")
        session.resize(40)
        session.process.send_signal(signal.SIGWINCH)
        chunk = session.write(DOWN, 0.6)
        plain = _plain(chunk)
        assert "up/down move" not in plain
        assert "enter select" in plain
        for line in plain.split("\r\n"):
            assert len(line) <= 40, line
        assert session.bare_newlines() == 0
    finally:
        session.write(b"\x03")
        session.close()


def test_service_menu_shows_the_sending_hold(stack_factory) -> None:
    stack = stack_factory()
    stack.api.post("/api/service/pause", {"reason": "maintenance"})
    session = Session(stack, "service", width=100)
    try:
        session.wait_for(b"Pause sending")
        screen = "\n".join(session.screen())
        assert "Resume sending" in screen
        assert "paused since" in screen
        assert "maintenance" in screen
        assert session.bare_newlines() == 0
    finally:
        session.write(b"\x03")
        session.close()


def test_service_menu_renders_with_nerd_glyphs(stack_factory) -> None:
    stack = stack_factory()
    session = Session(stack, "service", "--glyphs", "nerd", width=100)
    try:
        session.wait_for(b"Pause sending")
        screen = "\n".join(session.screen())
        assert "Resume sending" in screen
        assert session.bare_newlines() == 0
    finally:
        session.write(b"\x03")
        session.close()


def test_editor_keeps_the_prompt_on_one_row(stack_factory) -> None:
    stack = stack_factory()
    session = Session(stack, "account", "add", width=40)
    try:
        session.wait_for(b"enter select")
        session.write(b"\r", 0.6)
        session.wait_for(b"Mailbox address")
        anchor = session.filled()
        for _ in range(10):
            session.write(DOWN)
            assert session.filled() == anchor
        session.write(b"a-very-long-address-that-keeps-going@example.com", 0.6)
        lines = session.screen()
        labels = [line for line in lines if line.startswith("? Mailbox address")]
        assert len(labels) == 1
        assert "@example.com" in "".join(lines)
        assert session.bare_newlines() == 0
    finally:
        session.write(b"\x03")
        session.close()
