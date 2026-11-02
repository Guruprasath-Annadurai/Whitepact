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

from responsibleai import *  # noqa: F401,F403 -- intentional full re-export, see module docstring
from responsibleai import __all__ as __all__
from responsibleai import __version__ as __version__
