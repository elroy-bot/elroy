"""Sidebar controller for the Textual app."""

from __future__ import annotations

from ..core.ctx import ElroyConfig
from ..core.sidebar_models import (
    DetailModalSpec,
    SidebarActionOrchestrator,
    SidebarBuilder,
    SidebarEntry,
    SidebarState,
)
from ..core.turn import ElroySession


class SidebarController:
    """Coordinates sidebar reads and sidebar-triggered mutations."""

    def __init__(self, ctx: ElroyConfig, session: ElroySession):
        self.ctx = ctx
        self.session = session
        self.builder = SidebarBuilder(ctx, session)
        self._actions: SidebarActionOrchestrator | None = None

    @property
    def actions(self) -> SidebarActionOrchestrator:
        if self._actions is None:
            self._actions = SidebarActionOrchestrator(self.ctx, self.session)
        return self._actions

    def build_state(self) -> SidebarState:
        return self.builder.build_sidebar_state()

    def build_detail_modal(self, entry: SidebarEntry) -> DetailModalSpec | None:
        return self.builder.build_detail_modal(entry)

    def apply_modal_result(self, modal: DetailModalSpec, action: str) -> bool:
        if action == "delete" and modal.can_delete:
            self.actions.delete(modal.ref)
            return True
        if action == "complete" and modal.can_complete:
            self.actions.complete(modal.ref)
            return True
        return False
