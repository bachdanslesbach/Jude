"""The network tripwire: nothing leaves the plugin process."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile

import pytest

from jude.mcp import netguard


@pytest.fixture
def guard():
    was = netguard.installed()
    netguard.install()
    try:
        yield netguard
    finally:
        if not was:
            netguard.uninstall()


def test_netguard_refuses_non_loopback_connect_and_getaddrinfo(guard):
    with pytest.raises(netguard.NetworkRefused):
        socket.getaddrinfo("example.invalid", 443)
    with pytest.raises(netguard.NetworkRefused):
        socket.getaddrinfo("192.0.2.1", 80)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(netguard.NetworkRefused):
            s.connect(("192.0.2.1", 80))
        with pytest.raises(netguard.NetworkRefused):
            s.connect_ex(("192.0.2.1", 80))
    finally:
        s.close()
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(netguard.NetworkRefused):
            u.sendto(b"x", ("192.0.2.1", 53))
    finally:
        u.close()
    with pytest.raises(netguard.NetworkRefused):
        socket.create_connection(("192.0.2.1", 80), timeout=1)


def test_netguard_refuses_gethostbyname_family_and_sendmsg(guard):
    with pytest.raises(netguard.NetworkRefused):
        socket.gethostbyname("example.invalid")
    with pytest.raises(netguard.NetworkRefused):
        socket.gethostbyname_ex("example.invalid")
    with pytest.raises(netguard.NetworkRefused):
        socket.gethostbyaddr("192.0.2.1")
    with pytest.raises(netguard.NetworkRefused):
        socket.getnameinfo(("192.0.2.1", 80), 0)
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(netguard.NetworkRefused):
            u.sendmsg([b"x"], [], 0, ("192.0.2.1", 53))
    finally:
        u.close()


def test_netguard_allows_loopback_and_unix(guard, tmp_path):
    assert socket.getaddrinfo("127.0.0.1", 0)
    assert socket.getaddrinfo("localhost", 0)
    assert socket.gethostbyname("localhost") in ("127.0.0.1", "::1")
    assert socket.getnameinfo(("127.0.0.1", 80), socket.NI_NUMERICHOST)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        c = socket.create_connection(("127.0.0.1", srv.getsockname()[1]), timeout=2)
        c.close()
    finally:
        srv.close()
    short_dir = tempfile.mkdtemp(prefix="jn")  # AF_UNIX paths are limited to ~100 bytes
    path = f"{short_dir}/s.sock"
    us = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        us.bind(path)
        us.listen(1)
        uc = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        uc.connect(path)
        uc.close()
    finally:
        us.close()
        shutil.rmtree(short_dir, ignore_errors=True)
    guard.uninstall()
    assert not netguard.installed()
    guard.install()
    assert netguard.installed()


def test_server_module_import_does_not_import_detectors():
    code = (
        "import sys\n"
        "import jude.mcp.server\n"
        "print('jude.detect' in sys.modules, 'spacy' in sys.modules)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert proc.stdout.strip() == "False False"
