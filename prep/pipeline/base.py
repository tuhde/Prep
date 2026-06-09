from dataclasses import dataclass
from typing import Protocol

from prep.core.path_model import PathCollection


class PipelineStepProtocol(Protocol):
    name: str
    order: int

    def process(self, collection: PathCollection) -> PathCollection: ...


@dataclass
class TraceEntry:
    label: str
    step: PipelineStepProtocol | None
    collection: PathCollection


class PipelineRegistry:
    _descriptors: dict
    _loaded: dict
    _trace: list

    def __init__(self) -> None:
        self._descriptors = {}
        self._loaded = {}
        self._trace = []

    def register(self, step: PipelineStepProtocol) -> None:
        self._loaded[step.name] = step

    def steps(self) -> list[PipelineStepProtocol]:
        return sorted(self._loaded.values(), key=lambda s: s.order)

    def run(self, collection: PathCollection) -> PathCollection:
        self._trace = [TraceEntry(label="input", step=None, collection=collection)]
        current = collection
        for step in self.steps():
            current = step.process(current)
            self._trace.append(TraceEntry(label=step.name, step=step, collection=current))
        return current

    def trace(self) -> list[TraceEntry]:
        return self._trace


_registry = PipelineRegistry()


def get_registry() -> PipelineRegistry:
    return _registry