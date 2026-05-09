"""Tests for pan_os_mcp.tools.system."""

import pytest

from pan_os_mcp.tools.system import get_system_info, SystemInfo

def test_get_system_info_returns_typed_result(fake_firewall):
    """get_system_info parses real PA-440 XML into a SystemInfo with stable fields."""
    fake_firewall({"show system info": "show_system_info.xml"})

    result = get_system_info()

    assert isinstance(result, SystemInfo)
    assert result.model == "PA-440"
    assert result.hostname == "PA-440"
    assert result.sw_version == "11.2.7-h4"
    assert result.serial == "021201115967"

    assert isinstance(result.uptime, str)
    assert len(result.uptime) > 0