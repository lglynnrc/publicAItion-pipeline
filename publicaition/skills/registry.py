"""Skill registry — maps section_type strings to skill classes and builds instances."""
from __future__ import annotations

from publicaition.orchestrator.dag import DAGNode
from publicaition.orchestrator.state import ProjectInputs
from publicaition.services.container import Services
from publicaition.skills.abstract import AbstractSkill as AbstractSectionSkill
from publicaition.skills.base import AbstractSkill
from publicaition.skills.citations import CitationsSkill
from publicaition.skills.cohesion import CohesionSkill
from publicaition.skills.conclusion import ConclusionSkill
from publicaition.skills.discussion import DiscussionSkill
from publicaition.skills.introduction import IntroductionSkill
from publicaition.skills.methods import MethodsSkill
from publicaition.skills.pls import PLSSkill
from publicaition.skills.results import ResultsSkill

REGISTRY: dict[str, type[AbstractSkill]] = {
    "methods":      MethodsSkill,
    "results":      ResultsSkill,
    "discussion":   DiscussionSkill,
    "introduction": IntroductionSkill,
    "conclusion":   ConclusionSkill,
    "abstract":     AbstractSectionSkill,
    "cohesion":     CohesionSkill,
    "pls":          PLSSkill,
    "citations":    CitationsSkill,
}


def build_skill(
    node: DAGNode,
    inputs: ProjectInputs,
    services: Services,
    library_ids: list[str],
) -> AbstractSkill:
    cls = REGISTRY.get(node.section_type)
    if cls is None:
        raise ValueError(f"No skill registered for section_type: '{node.section_type}'")

    brief = inputs.brief_for(node.section_type)
    bp_chunk = inputs.bp_chunks.get(node.section_type, "")
    ko_guide = inputs.ko_guides.get(node.section_type, "")

    return cls(
        brief=brief,
        context=inputs.context,
        services=services,
        library_ids=library_ids,
        bp_chunk=bp_chunk,
        ko_guide=ko_guide,
    )
