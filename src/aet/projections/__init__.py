"""aet-work pluggable projections (one-way mirrors)."""

from aet.projections.base import Projection
from aet.projections.dispatcher import ProjectionDispatcher, resolve_projections

__all__ = ["Projection", "ProjectionDispatcher", "resolve_projections"]
