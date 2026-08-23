"""
app/context package.

Aryntra Synapse — Sprint 1
Context representation layer.
"""
from app.context.representation import (
    BaseContextRepresenter,
    FlatRepresenter,
    StructuredRepresenterV1,
    get_representer,
)

__all__ = [
    "BaseContextRepresenter",
    "FlatRepresenter",
    "StructuredRepresenterV1",
    "get_representer",
]
