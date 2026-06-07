"""Shared pytest fixtures for pan-os-agent tests."""

import pytest


class FakeParsedMessage:
    """Stand-in for the result of AsyncAnthropic().messages.parse.

    Stages read `.parsed_output` (the schema-validated Pydantic instance) and,
    for refusals, `.stop_reason`. Model only those two fields.
    """

    def __init__(self, parsed_output, stop_reason: str = "end_turn") -> None:
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class FakeMessages:
    """Stand-in for AsyncAnthropic().messages — the `.parse` sub-API.

    Replays canned responses in call order (a queue). Records each call's kwargs
    on `.calls` so a test can assert what the stage sent to Claude (model,
    system prompt, user content) — often the real point of a stage test.
    """

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[dict] = []

    async def parse(self, **kwargs) -> FakeParsedMessage:
        self.calls.append(kwargs)
        if self._index >= len(self._responses):
            raise AssertionError(
                "FakeMessages.parse called more times than canned responses"
            )
        response = self._responses[self._index]
        self._index += 1
        # A canned exception (e.g. an APIStatusError) is raised, to model the
        # gateway rejecting a call — like a Portkey guardrail denial.
        if isinstance(response, BaseException):
            raise response
        return response


class FakeAnthropic:
    """Stand-in for anthropic.AsyncAnthropic. Exposes `.messages.parse`."""

    def __init__(self, responses: list) -> None:
        self.messages = FakeMessages(responses)


@pytest.fixture
def fake_anthropic():
    """Builder: pass a list of canned outputs, get a FakeAnthropic.

    Mirrors the `fake_firewall` builder-fixture pattern in pan-os-mcp: the test
    supplies the canned data, the fixture wires up the fake. Each item may be a
    FakeParsedMessage (to control stop_reason, e.g. a refusal) or a bare
    Pydantic instance, which is wrapped as a normal parsed_output.
    """

    def _build(responses: list) -> FakeAnthropic:
        normalized = [
            r if isinstance(r, (FakeParsedMessage, BaseException)) else FakeParsedMessage(r)
            for r in responses
        ]
        return FakeAnthropic(normalized)

    # Exposed on the builder so tests can construct refusals without importing
    # from conftest (which isn't an importable package path).
    _build.ParsedMessage = FakeParsedMessage
    return _build


class FakeMcpClient:
    """Stand-in for McpClient: returns canned tool results keyed by tool name.

    Mirrors the fixture_map idea from pan-os-mcp's FakeFirewallClient — the test
    declares which result each tool call returns. Records calls for assertions.
    """

    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    async def call_tool(self, name: str, arguments: dict | None = None) -> object:
        self.calls.append((name, arguments))
        if name not in self._responses:
            raise KeyError(f"no fake MCP response configured for tool {name!r}")
        return self._responses[name]


@pytest.fixture
def fake_mcp():
    """Builder: pass {tool_name: result} (results shaped like the real tools)."""

    def _build(responses: dict[str, object]) -> FakeMcpClient:
        return FakeMcpClient(responses)

    return _build
