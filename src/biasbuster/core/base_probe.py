from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from biasbuster.core.result import ProbeResult
    from biasbuster.providers.base import BaseProvider


class BaseProbe(ABC):
    """
    Abstract base for all bias probes.

    To create a custom probe, subclass this and define the three class
    attributes plus the ``run`` coroutine::

        class MyProbe(BaseProbe):
            name = "my-bias"
            description = "Detects X bias in LLM outputs."
            default_threshold = 0.25

            async def run(self, provider: BaseProvider) -> ProbeResult:
                ...

    The ``name`` is used as the probe identifier in reports and the CLI.
    The ``default_threshold`` is the score above which the probe is
    considered failing (0.0 = no bias, 1.0 = maximum bias).
    """

    name: ClassVar[str]
    description: ClassVar[str]
    default_threshold: ClassVar[float] = 0.25

    def __init__(self, threshold: float | None = None) -> None:
        self._threshold = threshold if threshold is not None else self.default_threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    @abstractmethod
    async def run(self, provider: BaseProvider) -> ProbeResult:
        """Execute the probe against the given provider and return a result."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(threshold={self._threshold})"
