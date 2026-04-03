"""DAG loader — reads a manuscript type JSON, validates it, and produces an execution plan."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent / "config" / "manuscript_types"


@dataclass
class DAGNode:
    section_type: str
    label: str
    skill: str | None               # None for gates and assembly
    deps: list[str]
    enabled: bool
    multi_section: bool
    context: dict
    word_count: dict | None
    execution_paths: list[dict] | None
    gate: dict | None
    review: dict | None
    upstream_sections: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    healthgeo: bool = False
    disabled_reason: str = ""


@dataclass
class DAG:
    id: str
    label: str
    execution_mode: str             # "sequential" | "single_node"
    context_availability: dict      # {"source_materials": [...], "literature": [...]}
    nodes: dict[str, DAGNode]       # keyed by section_type
    outputs: list[str]

    def enabled_nodes(self) -> dict[str, DAGNode]:
        return {k: v for k, v in self.nodes.items() if v.enabled}

    def effective_deps(self, section_type: str) -> list[str]:
        """Deps with disabled nodes removed — rewired to the disabled node's own deps."""
        node = self.nodes[section_type]
        result: list[str] = []
        for dep in node.deps:
            if dep not in self.nodes:
                continue
            if self.nodes[dep].enabled:
                result.append(dep)
            else:
                # Rewire: pull in the disabled node's effective deps instead
                result.extend(self.effective_deps(dep))
        return list(dict.fromkeys(result))  # deduplicate, preserve order

    def topological_stages(self) -> list[list[str]]:
        """
        Kahn's algorithm over enabled nodes only.
        Returns a list of stages — each stage is a list of section_types
        whose effective deps are all satisfied by prior stages.
        Nodes within a stage can run in parallel.
        """
        enabled = set(self.enabled_nodes())
        in_deps = {s: [d for d in self.effective_deps(s) if d in enabled] for s in enabled}
        completed: set[str] = set()
        stages: list[list[str]] = []

        while len(completed) < len(enabled):
            ready = [
                s for s in enabled
                if s not in completed and all(d in completed for d in in_deps[s])
            ]
            if not ready:
                remaining = enabled - completed
                raise ValueError(f"DAG cycle or unresolvable deps in: {remaining}")
            stages.append(sorted(ready))  # sorted for determinism
            completed.update(ready)

        return stages

    def source_materials_sections(self) -> set[str]:
        return set(self.context_availability.get("source_materials", []))

    def literature_sections(self) -> set[str]:
        return set(self.context_availability.get("literature", []))


def load_dag(manuscript_type: str) -> DAG:
    path = CONFIG_DIR / f"{manuscript_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"No manuscript type config found: {path}")

    with path.open() as f:
        raw = json.load(f)

    execution_mode = raw.get("execution", {}).get("mode", "sequential")

    nodes: dict[str, DAGNode] = {}
    for n in raw["nodes"]:
        context = n.get("context") or {}
        nodes[n["section_type"]] = DAGNode(
            section_type=n["section_type"],
            label=n["label"],
            skill=n.get("skill"),
            deps=n.get("deps", []),
            enabled=n.get("enabled", True),
            multi_section=n.get("multi_section", False),
            context=context,
            word_count=n.get("word_count"),
            execution_paths=n.get("execution_paths"),
            gate=n.get("gate"),
            review=n.get("review"),
            upstream_sections=n.get("upstream_sections", context.get("upstream_sections", [])),
            outputs=n.get("outputs", []),
            healthgeo=n.get("healthgeo", False),
            disabled_reason=n.get("disabled_reason", ""),
        )

    _validate(nodes, raw)

    return DAG(
        id=raw["id"],
        label=raw["label"],
        execution_mode=execution_mode,
        context_availability=raw.get("context_availability", {}),
        nodes=nodes,
        outputs=raw.get("outputs", []),
    )


def _validate(nodes: dict[str, DAGNode], raw: dict) -> None:
    """Fail fast on obvious misconfigurations."""
    for section_type, node in nodes.items():
        for dep in node.deps:
            if dep not in nodes:
                raise ValueError(
                    f"Node '{section_type}' has unknown dep '{dep}'"
                )
        for upstream in node.upstream_sections:
            s = upstream if isinstance(upstream, str) else upstream.get("section_type", "")
            if s and s not in nodes:
                raise ValueError(
                    f"Node '{section_type}' has unknown upstream_section '{s}'"
                )
