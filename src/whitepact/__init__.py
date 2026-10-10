# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact — compatibility alias for the ResponsibleAI governance engine.

See MIGRATION_WHITEPACT_V2.md Section 3. `import whitepact` re-exports
every public name from `responsibleai` — the exact same objects, not
copies, so `from whitepact import TrustScoreEngine` and `from
responsibleai import TrustScoreEngine` resolve to one identical class.
No logic lives here; this module is purely a redirect for the duration
of the migration window (target: at least the full v2.x series — see
the migration doc's backward-compatibility timeline).

Once `src/whitepact/` becomes the real implementation in a later minor
version, this direction reverses: `responsibleai` becomes the alias
re-exporting from `whitepact`, and this file's `from responsibleai
import *` becomes `from whitepact.<real submodule> import *` inside
`responsibleai/__init__.py` instead. That reversal is out of scope for
this commit — see the migration doc for why it isn't done in one step.
"""

from __future__ import annotations

from typing import Any

import responsibleai

__version__ = responsibleai.__version__
__all__ = responsibleai.__all__


def __getattr__(name: str) -> Any:
    if name == "WhitePactClient":
        from whitepact.client import WhitePactClient

        return WhitePactClient
    return getattr(responsibleai, name)


def __dir__() -> list[str]:
    return sorted(list(set(dir(responsibleai) + list(__all__) + ["WhitePactClient"])))
