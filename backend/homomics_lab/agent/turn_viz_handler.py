"""Backward-compatible re-export of :class:`VisualizationEditHandler`.

The implementation moved to ``turn_responder`` when the turn collaborators
were consolidated; this shim stays because ``turn_intent_router`` (owned by
another task) imports the handler from here.
"""

from homomics_lab.agent.turn_responder import VisualizationEditHandler

__all__ = ["VisualizationEditHandler"]
