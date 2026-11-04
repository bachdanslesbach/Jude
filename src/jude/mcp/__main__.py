"""``python -m jude.mcp`` — what the Claude Desktop configuration runs.

The network tripwire is installed before the server module is imported,
so no library can capture an unguarded ``socket.socket``.
"""

from __future__ import annotations

import sys

from . import netguard

netguard.install()

from .server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
