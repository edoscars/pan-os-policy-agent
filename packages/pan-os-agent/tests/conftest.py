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
            r if isinstance(r, FakeParsedMessage) else FakeParsedMessage(r)
            for r in responses
        ]
        return FakeAnthropic(normalized)

    # Exposed on the builder so tests can construct refusals without importing
    # from conftest (which isn't an importable package path).
    _build.ParsedMessage = FakeParsedMessage
    return _build
