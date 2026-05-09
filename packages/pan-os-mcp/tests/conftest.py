"""Shared pytest fixtures for pan-os-mcp tests."""

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(filename: str) -> ET.Element:
    """Parse an XML fixture file and return its root element."""
    # TODO: read the file at FIXTURES_DIR / filename, parse with ET.parse,
    # return the root element
    return ET.parse(FIXTURES_DIR / filename).getroot()


class FakeFirewallClient:
    """Stand-in for panos.firewall.Firewall.

    Its op() method returns canned XML loaded from a fixture file
    based on the command string. Each test sets up which fixture
    answers which command via the fixture_map argument.
    """

    def __init__(self, fixture_map: dict[str, str]) -> None:
        self._fixture_map = fixture_map

    def op(self, cmd: str, xml: bool = False) -> ET.Element:
        if cmd in self._fixture_map:
            filename = self._fixture_map[cmd]
            return load_fixture(filename)
        else:
            raise KeyError(f"No fixture configure for cmd: {cmd}")

class FakeFirewallConn:
    """Stand-in for pan_os_mcp.panos.FirewallConn."""

    def __init__(self, fixture_map: dict[str, str]) -> None:
        self._client = FakeFirewallClient(fixture_map)

    @property
    def client(self) -> FakeFirewallClient:
        return self._client


@pytest.fixture
def fake_firewall(monkeypatch):
    """Replace get_firewall() with a fake whose responses come from fixture files.

    Tests that use this fixture get a builder function: call it with
    a fixture_map dict like {'show system info': 'show_system_info.xml'}
    and the patched get_firewall() will return a FakeFirewallConn
    that serves XML from those files.
    """
    def _build(fixture_map: dict[str, str]) -> FakeFirewallConn:
        fake = FakeFirewallConn(fixture_map)
        monkeypatch.setattr("pan_os_mcp.tools.system.get_firewall", lambda:fake)
        return fake

    return _build