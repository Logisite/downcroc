from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from downcroc.api.app import create_app
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import resolve


def run(output: Path | None) -> int:
    paths = resolve()
    app = create_app(
        Settings(),
        paths,
        EventLogger(logging.getLogger("downcroc.openapi")),
    )
    document = json.dumps(app.openapi(), indent=2) + "\n"
    if output is None:
        sys.stdout.write(document)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(document, encoding="utf-8")
        print(f"wrote {output}")
    return 0
