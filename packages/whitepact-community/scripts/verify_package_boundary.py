#!/usr/bin/env python3
"""Fail-closed community package boundary verifier.

Inspects real wheel/sdist archives (not merely pyproject.toml) and fails if:
- any denylisted private/commercial module path is present
- known confidential business documents are present
- credential-like filenames are present
- import closure of installed package pulls non-community modules
- console script entrypoints are missing from metadata
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENYLIST_PATH = ROOT / "security" / "PRIVATE_MODULE_DENYLIST.txt"
ALLOWED_TOP_LEVEL = frozenset({"whitepact_community"})
REQUIRED_SCRIPTS = frozenset(
    {"whitepact-community", "wpc", "whitepact-community-mcp"}
)
CREDENTIAL_NAME_RE = re.compile(
    r"(^|/)(\.env|credentials|secrets?|id_rsa|private[_-]?key)(/|$|\.)",
    re.IGNORECASE,
)
# Match credential *values*, not documentation that merely names forbidden keys.
SECRET_CONTENT_RE = re.compile(
    r"(?i)("
    r"aws_secret_access_key\s*[=:]\s*['\"][A-Za-z0-9/+=]{20,}"
    r"|stripe_secret_key\s*[=:]\s*['\"]sk_(live|test)_[A-Za-z0-9]+"
    r"|BEGIN (RSA |OPENSSH )?PRIVATE KEY"
    r"|ghp_[A-Za-z0-9]{36}"
    r")"
)


def load_denylist() -> list[str]:
    items: list[str] = []
    for line in DENYLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(line)
    return items


def iter_archive_names(path: Path) -> list[str]:
    if path.suffix == ".whl" or path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    if path.suffixes[-2:] == [".tar", ".gz"] or path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as tf:
            return [m.name for m in tf.getmembers() if m.isfile()]
    raise SystemExit(f"Unsupported archive type: {path}")


def read_archive_text_files(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith((".py", ".txt", ".md", ".toml", ".json", ".html")):
                    try:
                        out[name] = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:  # noqa: BLE001
                        continue
    else:
        with tarfile.open(path, "r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                if member.name.endswith((".py", ".txt", ".md", ".toml", ".json", ".html")):
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    out[member.name] = extracted.read().decode("utf-8", errors="replace")
    return out


def check_denylist(names: list[str], denylist: list[str]) -> list[str]:
    hits: list[str] = []
    for name in names:
        for pattern in denylist:
            if pattern in name:
                hits.append(f"{name} matches denylist {pattern!r}")
    return hits


def check_credentials(names: list[str], texts: dict[str, str]) -> list[str]:
    hits: list[str] = []
    for name in names:
        if CREDENTIAL_NAME_RE.search(name):
            hits.append(f"credential-like archive member: {name}")
    for name, text in texts.items():
        if SECRET_CONTENT_RE.search(text):
            hits.append(f"secret-like content in archive member: {name}")
    return hits


def check_metadata_scripts(path: Path) -> list[str]:
    hits: list[str] = []
    if not path.name.endswith(".whl"):
        return hits
    with zipfile.ZipFile(path) as zf:
        entry_points = None
        for name in zf.namelist():
            if name.endswith("entry_points.txt"):
                entry_points = zf.read(name).decode("utf-8")
                break
        if entry_points is None:
            return ["wheel missing entry_points.txt"]
        present = set()
        in_console = False
        for line in entry_points.splitlines():
            if line.strip() == "[console_scripts]":
                in_console = True
                continue
            if line.startswith("["):
                in_console = False
                continue
            if in_console and "=" in line:
                present.add(line.split("=", 1)[0].strip())
        missing = REQUIRED_SCRIPTS - present
        if missing:
            hits.append(f"missing console scripts: {sorted(missing)}")
    return hits


def static_import_closure(package_root: Path) -> tuple[set[str], list[str]]:
    """Parse community package AST imports; flag non-allowed external project imports."""
    imports: set[str] = set()
    problems: list[str] = []
    forbidden_prefixes = (
        "responsibleai",
        "biasbuster",
        "privacylabel",
        "rai_client",
        "stripe",
    )
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
                    for prefix in forbidden_prefixes:
                        if alias.name == prefix or alias.name.startswith(prefix + "."):
                            problems.append(f"{path}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
                for prefix in forbidden_prefixes:
                    if node.module == prefix or node.module.startswith(prefix + "."):
                        problems.append(f"{path}: imports {node.module}")
    return imports, problems


def runtime_import_check() -> list[str]:
    hits: list[str] = []
    try:
        mod = importlib.import_module("whitepact_community")
    except Exception as exc:  # noqa: BLE001
        return [f"failed to import whitepact_community: {exc}"]
    for name in (
        "GovernanceClient",
        "ActionRequest",
        "AuthorityGrant",
        "GovernanceDecision",
    ):
        if not hasattr(mod, name):
            hits.append(f"missing export {name}")
    # Ensure enterprise modules are not already imported as a side effect.
    for banned in ("responsibleai", "stripe", "biasbuster"):
        if banned in sys.modules:
            hits.append(f"banned module present in sys.modules after import: {banned}")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archives",
        nargs="*",
        type=Path,
        help="Wheel and/or sdist paths to inspect",
    )
    parser.add_argument(
        "--package-src",
        type=Path,
        default=ROOT / "src" / "whitepact_community",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    denylist = load_denylist()
    report: dict[str, object] = {
        "ok": True,
        "archives": [],
        "static_imports": [],
        "problems": [],
    }
    problems: list[str] = []

    imports, import_problems = static_import_closure(args.package_src)
    report["static_imports"] = sorted(imports)
    problems.extend(import_problems)

    problems.extend(runtime_import_check())

    for archive in args.archives:
        names = iter_archive_names(archive)
        texts = read_archive_text_files(archive)
        archive_problems = []
        archive_problems.extend(check_denylist(names, denylist))
        archive_problems.extend(check_credentials(names, texts))
        archive_problems.extend(check_metadata_scripts(archive))
        # Ensure only community package top-level is shipped in wheel.
        if archive.name.endswith(".whl"):
            top_levels = {
                n.split("/")[0]
                for n in names
                if "/" in n and not n.split("/")[0].endswith(".dist-info")
            }
            unexpected = top_levels - ALLOWED_TOP_LEVEL - {""}
            # dist-info directory name varies; filter those.
            unexpected = {
                t for t in unexpected if not t.endswith(".dist-info") and t != "whitepact_community"
            }
            if unexpected:
                archive_problems.append(f"unexpected wheel top-level packages: {sorted(unexpected)}")
        entry = {
            "path": str(archive),
            "member_count": len(names),
            "problems": archive_problems,
        }
        report["archives"].append(entry)
        problems.extend(f"{archive.name}: {p}" for p in archive_problems)

    report["problems"] = problems
    report["ok"] = not problems
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
