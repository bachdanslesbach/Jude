"""Jude as a Claude Desktop plugin (an MCP server over stdio).

The lawyer says "analyse the memo for this matter"; Claude calls
``prepare_document``; Jude opens a local browser tab where the lawyer
picks the matter and the file, reads the exact pseudonymised text and
approves; Claude then collects that text once through
``fetch_approved`` and shows its answer with the real names, locally,
through ``show_answer``. Nothing confidential — matter names, file
names, real names, the pseudonym mapping — is ever placed in a tool
argument or a tool result.

Modules: ``reviews`` (state machine), ``window`` (the local HTTP page),
``server`` (the three tools and ``main()``), ``strings`` (every string,
en/fr), ``env`` (offline flags, pass-through variables, settings),
``models`` (which language components are missing), ``logfilter``
(nothing confidential on stderr), ``netguard`` (no outbound network),
``install``/``doctor``/``launch`` (the CLI).

``import jude.mcp`` does not import the ``mcp`` SDK; ``jude.mcp.server``
does, so the ``[mcp]`` extra is needed only to run the server.
"""

from __future__ import annotations

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    from .server import main as _main

    return _main(argv)
