from __future__ import annotations

import os
from importlib.metadata import version

__version__ = version("downcroc")
API_VERSION = "v1"
COMMIT = os.environ.get("DOWNCROC_COMMIT", "")
