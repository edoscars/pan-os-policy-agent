"""Shared pytest fixtures for pan-os-agent tests."""

import pytest


class FakeTextBlock:
    """Minimal stand-in for an anthropic TextBlock: `.type` + `.text`."""

    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class FakeMessage:
    """Stand-in for anthropic.types.Message.

    Models only what stages read: a `.content` list of blocks and a
    `.stop_reason`. The common case is a single text block holding the
    JSON Claude returned, so construct it from a plain string; pass
    `content=` explicitly to model multi-block or tool-use responses.
    """

    def __init__(
        self,
        text: str = "",
        *,
        content: list | None = None,
        stop_reason: str = "end_turn",
    ) -> None:
        self.content = content if content is not None else [FakeTextBlock(text)]
        self.stop_reason = stop_reason


class FakeMessages:
    """Stand-in for AsyncAnthropic().messages — the `.create` sub-API.

    Replays canned responses in call order (a queue). Records each call's
    kwargs on `.calls` so a test can assert what the stage sent to Claude
    (model, system prompt, messages) — often the real point of the test.
    """

    def __init__(self, responses: list[FakeMessage]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[dict] = []

    async def create(self, **kwargs) -> FakeMessage:
        self.calls.append(kwargs)
        if self._index >= len(self._responses):
            raise AssertionError(
                "FakeMessages.create called more times than canned responses"
            )
        response = self._responses[self._index]
        self._index += 1
        return response


class FakeAnthropic:
    """Stand-in for anthropic.AsyncAnthropic. Exposes `.messages.create`."""

    def __init__(self, responses: list[FakeMessage]) -> None:
        self.messages = FakeMessages(responses)


@pytest.fixture
def fake_anthropic():
    """Builder: pass a list of FakeMessages (or plain strings), get a FakeAnthropic.

    Mirrors the `fake_firewall` builder-fixture pattern in pan-os-mcp: the
    test supplies the canned data, the fixture wires up the fake. Strings
    are normalized into single-text-block FakeMessages for convenience.
    """

    def _build(responses: list) -> FakeAnthropic:
        normalized = [
            r if isinstance(r, FakeMessage) else FakeMessage(r) for r in responses
        ]
        return FakeAnthropic(normalized)

    return _build
