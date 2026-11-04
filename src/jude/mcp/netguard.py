"""Tripwire against outbound network calls from the plugin process.

Jude's MCP server makes no network call by design: strict mode never
looks anything up, smart mode uses the offline context chain, model
weights are loaded from the local cache with the Hugging Face offline
flags set. This module makes a regression loud instead of silent: once
``install()`` has run, any attempt to connect, resolve or send to a
non-loopback address raises ``NetworkRefused`` (a ``PermissionError``)
before a packet leaves.

Guarded: ``socket.socket.connect``, ``connect_ex``, ``sendto``,
``sendmsg``; ``socket.getaddrinfo``, ``gethostbyname``,
``gethostbyname_ex``, ``gethostbyaddr``, ``getnameinfo``.

Loopback (``127.0.0.1``, ``::1``, ``localhost``) stays open: the review
window listens there and ``jude mcp open`` talks to it. Unix sockets are
untouched. ``install()`` must run before the detection stack is imported
(``server.main()`` step 2, ``__main__`` before importing the server), so
no library captures an unguarded ``socket.socket``.

``uninstall()`` restores the original ``socket`` names; tests use it.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

_ORIGINAL: dict[str, Any] = {}
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", ""})
_GUARDED_RESOLVERS = (
    "getaddrinfo",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
    "getnameinfo",
)


class NetworkRefused(PermissionError):  # noqa: N818
    """Raised by the guard. Carries the host only, never a payload."""


def _host_allowed(host: object) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode()
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    h = host.strip().lower()
    if h in _LOOPBACK_NAMES:
        return True
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    try:
        return ipaddress.ip_address(h.split("%")[0]).is_loopback
    except ValueError:
        return False


def _address_allowed(address: object) -> bool:
    # AF_UNIX: a path (str or bytes) — not the network.
    if isinstance(address, (str, bytes)):
        return True
    if isinstance(address, tuple) and address:
        return _host_allowed(address[0])
    return False


def _refuse(address: object) -> NetworkRefused:
    host = address[0] if isinstance(address, tuple) and address else "?"
    return NetworkRefused(f"jude netguard: outbound connection to {host!s} refused")


def _refuse_name(name: object) -> NetworkRefused:
    return NetworkRefused(f"jude netguard: name resolution of {name!s} refused")


def install() -> None:
    """Patch ``socket.socket`` and the resolver functions. Idempotent."""

    if _ORIGINAL:
        return
    original_socket = socket.socket
    _ORIGINAL["socket"] = original_socket
    for name in _GUARDED_RESOLVERS:
        _ORIGINAL[name] = getattr(socket, name)
    original_gai = _ORIGINAL["getaddrinfo"]
    original_gethostbyname = _ORIGINAL["gethostbyname"]
    original_gethostbyname_ex = _ORIGINAL["gethostbyname_ex"]
    original_gethostbyaddr = _ORIGINAL["gethostbyaddr"]
    original_getnameinfo = _ORIGINAL["getnameinfo"]

    class GuardedSocket(original_socket):  # type: ignore[misc,valid-type]
        __slots__ = ()

        def connect(self, address: Any) -> None:
            if not _address_allowed(address):
                raise _refuse(address)
            super().connect(address)

        def connect_ex(self, address: Any) -> int:
            if not _address_allowed(address):
                raise _refuse(address)
            return super().connect_ex(address)

        def sendto(self, data: Any, *args: Any) -> int:
            address = args[-1] if args else None
            if not _address_allowed(address):
                raise _refuse(address)
            return super().sendto(data, *args)

        def sendmsg(self, buffers: Any, *args: Any) -> int:
            # sendmsg(buffers[, ancdata[, flags[, address]]]): an explicit
            # address is the fourth positional argument.
            if len(args) >= 3:
                address = args[2]
                if address is not None and not _address_allowed(address):
                    raise _refuse(address)
            return super().sendmsg(buffers, *args)

    def guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host is not None and not _host_allowed(host):
            raise _refuse_name(host.decode() if isinstance(host, bytes) else host)
        return original_gai(host, port, *args, **kwargs)

    def guarded_gethostbyname(host: Any) -> Any:
        if not _host_allowed(host):
            raise _refuse_name(host)
        return original_gethostbyname(host)

    def guarded_gethostbyname_ex(host: Any) -> Any:
        if not _host_allowed(host):
            raise _refuse_name(host)
        return original_gethostbyname_ex(host)

    def guarded_gethostbyaddr(ip: Any) -> Any:
        if not _host_allowed(ip):
            raise _refuse_name(ip)
        return original_gethostbyaddr(ip)

    def guarded_getnameinfo(sockaddr: Any, flags: Any) -> Any:
        if not _address_allowed(sockaddr):
            raise _refuse(sockaddr)
        return original_getnameinfo(sockaddr, flags)

    GuardedSocket.__name__ = "socket"
    GuardedSocket.__qualname__ = "socket"
    socket.socket = GuardedSocket  # type: ignore[misc]
    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.gethostbyname = guarded_gethostbyname  # type: ignore[assignment]
    socket.gethostbyname_ex = guarded_gethostbyname_ex  # type: ignore[assignment]
    socket.gethostbyaddr = guarded_gethostbyaddr  # type: ignore[assignment]
    socket.getnameinfo = guarded_getnameinfo  # type: ignore[assignment]


def uninstall() -> None:
    if not _ORIGINAL:
        return
    socket.socket = _ORIGINAL.pop("socket")  # type: ignore[misc]
    for name in _GUARDED_RESOLVERS:
        setattr(socket, name, _ORIGINAL.pop(name))


def installed() -> bool:
    return bool(_ORIGINAL)
