"""PolicyDraftState: the single object threaded through the gauntlet.

State is immutable and grows append-only. Stages never mutate in place; they
call advance() or halt() to get a new state with their output attached and a
trace breadcrumb appended. The whole object is JSON-serializable, so dumping
model_dump_json() yields a complete, replayable trace of a run.
"""

from pydantic import BaseModel, ConfigDict

from pan_os_agent.models import PrerequisiteReport, RedundancyReport, StructuredIntent


class TraceEntry(BaseModel):
    """One breadcrumb per stage: which stage ran and a human-readable summary."""

    stage: str
    summary: str


class PolicyDraftState(BaseModel):
    """The draft policy as it moves through the four stages.

    Output fields are Optional and start None; each stage fills its own. New
    stage outputs are added here as the stages are built.
    """

    model_config = ConfigDict(frozen=True)

    intent_text: str
    structured_intent: StructuredIntent | None = None
    prerequisites: PrerequisiteReport | None = None
    redundancy: RedundancyReport | None = None

    halted: bool = False
    halt_reason: str = ""
    trace: list[TraceEntry] = []

    def advance(self, *, stage: str, summary: str, **updates) -> "PolicyDraftState":
        """Return a copy with `updates` applied and a trace entry appended."""
        return self.model_copy(
            update={
                **updates,
                "trace": [*self.trace, TraceEntry(stage=stage, summary=summary)],
            }
        )

    def halt(self, *, stage: str, reason: str, **updates) -> "PolicyDraftState":
        """Return a halted copy: sets the flag/reason and traces the halt."""
        return self.advance(
            stage=stage,
            summary=f"halted: {reason}",
            halted=True,
            halt_reason=reason,
            **updates,
        )
