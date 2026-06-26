from pydantic import BaseModel, ConfigDict

class HermeneiaObject(BaseModel):
    """Canonical immutable ontology base."""
    model_config=ConfigDict(frozen=True,extra="forbid",validate_assignment=False)
