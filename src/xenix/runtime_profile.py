"""Typed runtime profile resolved before application composition.

The launcher resolves this before importing the application so the home and the
home-scoped single-instance mutex are fixed before any service is composed. An
isolated run uses a unique fresh home under the system temp root and never
reads, migrates, or writes the real user home.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import default_app_home

# The exact directory name Xenix mints for an isolated run.  Cleanup refuses to
# remove anything that does not match this, so a stray ``home`` value can never
# expand deletion to the user profile or an arbitrary directory.
_ISOLATED_HOME_NAME_PATTERN = re.compile(r"^xenix-isolated-[0-9a-f]{12}$")


class RuntimeProfile(StrEnum):
    PRODUCTION = "production"
    ISOLATED = "isolated"


@dataclass(frozen=True)
class RuntimeProfileContext:
    profile: RuntimeProfile
    runtime_home: Path
    run_id: str
    isolated_home: bool

    def mutex_name(self) -> str:
        """A single-instance mutex scoped to this normalized home.

        Two runs sharing a home contend on one mutex; runs with different homes
        are independent. This is the rule for production and isolated modes
        alike, so a smoke run against the real home can never bypass the
        production instance's lock.
        """
        fingerprint = hashlib.sha256(str(self.runtime_home).encode("utf-8")).hexdigest()[:24]
        return f"Local\\dev.lanzhijiang.xenix.{fingerprint}"

    def run_manifest(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "run_id": self.run_id,
            "runtime_home": str(self.runtime_home),
            "isolated_home": self.isolated_home,
        }


def is_isolated_home_path(path: Path) -> bool:
    """Whether ``path`` is a directory name Xenix itself minted for an isolated run.

    This is the single source of truth used by cleanup before any recursive
    removal.  It is intentionally strict: the name must be exactly
    ``xenix-isolated-<12 lowercase hex digits>``.
    """

    return _ISOLATED_HOME_NAME_PATTERN.fullmatch(path.name) is not None


def resolve_runtime_profile(
    *,
    isolated: bool = False,
    smoke_test: bool = False,
    temp_root: Path | None = None,
) -> RuntimeProfileContext:
    """Resolve the run profile and freeze its home and mutex.

    Frozen priority:

    1. --isolated composes into an isolated run with a unique fresh home under
       the system temp root; the real user home is never read, migrated, or
       written.
    2. Without --isolated, the existing XENIX_APP_HOME override (when set) wins,
       else the platform default home. --smoke-test alone does not isolate the
       home; it only selects startup-validation behavior.
    """
    del smoke_test  # smoke-test changes run behavior, not profile resolution.
    if isolated:
        profile = RuntimeProfile.ISOLATED
        root = temp_root or Path(tempfile.gettempdir())
        run_id = uuid4().hex
        runtime_home = (root / f"xenix-isolated-{run_id[:12]}").resolve()
    else:
        profile = RuntimeProfile.PRODUCTION
        run_id = uuid4().hex
        runtime_home = default_app_home().resolve()
    return RuntimeProfileContext(
        profile=profile,
        runtime_home=runtime_home,
        run_id=run_id,
        isolated_home=isolated,
    )
