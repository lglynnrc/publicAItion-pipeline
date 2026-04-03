"""Review gates — pause points where a human or automated process makes a decision."""
from __future__ import annotations

from abc import ABC, abstractmethod

from publicaition.orchestrator.dag import DAGNode
from publicaition.orchestrator.state import PipelineState, PipelineStatus


class PipelinePaused(Exception):
    """Raised when the pipeline pauses at a gate awaiting external input."""
    def __init__(self, gate: str) -> None:
        self.gate = gate
        super().__init__(f"Pipeline paused at gate: {gate}")


class ReviewGate(ABC):
    @abstractmethod
    async def evaluate(self, node: DAGNode, state: PipelineState) -> str:
        """
        Evaluate the gate and return a decision string.
        For select/merge gates: returns the selected path_id (e.g. "1A", "1B").
        For approval gates: returns "approved".
        May raise PipelinePaused if human input is required.
        """


class AutoSelectGate(ReviewGate):
    """
    Used when a select/merge gate is disabled.
    Automatically selects the default_path without human input.
    """
    async def evaluate(self, node: DAGNode, state: PipelineState) -> str:
        default = (node.gate or {}).get("default_path", "1A")
        state.selected_paths[node.section_type] = default
        return default


class WebhookGate(ReviewGate):
    """
    Pauses the pipeline and waits for an external webhook to resume it.
    The caller is responsible for persisting state and re-invoking the runner
    with the resumed state once the webhook fires.
    """
    async def evaluate(self, node: DAGNode, state: PipelineState) -> str:
        state.status = PipelineStatus.PAUSED
        state.pending_gate = node.section_type
        raise PipelinePaused(node.section_type)


def gate_for(node: DAGNode, state: PipelineState) -> ReviewGate:
    """Return the appropriate gate implementation for a node."""
    gate_config = node.gate or node.review
    if not gate_config:
        return AutoSelectGate()

    gate_type = gate_config.get("type")
    enabled = gate_config.get("enabled", True)

    if not enabled:
        return AutoSelectGate()

    if gate_type == "webhook":
        return WebhookGate()

    if gate_type == "select_merge":
        # Enabled select/merge gate — human picks between paths.
        # In v1 all select/merge gates are disabled so this path is not reached.
        return WebhookGate()

    return AutoSelectGate()
