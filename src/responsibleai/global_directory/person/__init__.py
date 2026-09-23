# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Universal person resolution — a name is a query, not an identity."""

__all__ = ["PersonResolutionPipeline"]


def __getattr__(name: str):  # noqa: ANN001
    if name == "PersonResolutionPipeline":
        from responsibleai.global_directory.person.pipeline import PersonResolutionPipeline

        return PersonResolutionPipeline
    raise AttributeError(name)
