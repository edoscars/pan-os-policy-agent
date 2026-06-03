"""Domain models for the policy-authoring gauntlet.

These are the structured outputs each stage produces. They are plain Pydantic
data models (JSON-serializable) so they can live inside PolicyDraftState and be
dumped to a trace. Stage-specific report models are added alongside their stage.
"""

from pydantic import BaseModel


class StructuredIntent(BaseModel):
    """A natural-language policy intent parsed into security-rule terms.

    Fields default empty because a raw intent ("finance needs Salesforce")
    rarely names zones or services — later stages fill the gaps. This holds
    only what was stated; coherence/halting is decided by the intent stage.
    """

    summary: str = ""
    source_user: str = ""
    source_zones: list[str] = []
    source_addresses: list[str] = []
    destination_zones: list[str] = []
    destination_addresses: list[str] = []
    applications: list[str] = []
    services: list[str] = []
    action: str = "allow"
