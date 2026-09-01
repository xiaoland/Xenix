"""Typed runtime profile resolved before application composition.

The launcher resolves this before importing the application so the home, the
home-scoped single-instance mutex, and the external-capability denials are all
fixed before any service is composed. Capability denials are enforced where
adapters are composed; they are not ambient environment-variable conventions.
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
_ISOLATED_HOME_NAME_PATTERN = re.compile(r"^xenix-(agent-dev|ephemeral)-[0-9a-f]{12}$")


class RuntimeProfile(StrEnum):
    PRODUCTION = "production"
    AGENT_DEV = "agent-dev"
    EPHEMERAL = "ephemeral"


@dataclass(frozen=True)
class Capabilities:
    """External capabilities admitted for a run.

    Every field defaults to the production-allowed value. Agent-safe profiles
    disable each remote edge explicitly; a denial is a composition decision,
    not a convention the caller must remember.
    """

    update: bool = True
    remote_otlp: bool = True
    remote_ml_workers: bool = True
    ssh_worker_setup: bool = True
    live_llm: bool = True

    @classmethod
    def agent_safe(cls) -> "Capabilities":
        return cls(
            update=False,
            remote_otlp=False,
            remote_ml_workers=False,
            ssh_worker_setup=False,
            live_llm=False,
        )


@dataclass(frozen=True)
class RuntimeProfileContext:
    profile: RuntimeProfile
    runtime_home: Path
    capabilities: Capabilities
    run_id: str
    isolated_home: bool

    def mutex_name(self) -> str:
        """A single-instance mutex scoped to this normalized home.

        Two runs sharing a home contend on one mutex; runs with different homes
        are independent. This is the rule for production and agent-safe modes
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
            "capabilities": {
                "update": self.capabilities.update,
                "remote_otlp": self.capabilities.remote_otlp,
                "remote_ml_workers": self.capabilities.remote_ml_workers,
                "ssh_worker_setup": self.capabilities.ssh_worker_setup,
                "live_llm": self.capabilities.live_llm,
            },
        }


def is_isolated_home_path(path: Path) -> bool:
    """Whether ``path`` is a directory name Xenix itself minted for an isolated run.

    This is the single source of truth used by cleanup before any recursive
    removal.  It is intentionally strict: the name must be exactly
    ``xenix-<agent-dev|ephemeral>-<12 lowercase hex digits>``.
    """

    return _ISOLATED_HOME_NAME_PATTERN.fullmatch(path.name) is not None


def resolve_runtime_profile(
    *,
    agent_dev: bool = False,
    ephemeral: bool = False,
    smoke_test: bool = False,
    temp_root: Path | None = None,
) -> RuntimeProfileContext:
    """Resolve the run profile and freeze its home, mutex, and capabilities.

    Frozen priority:

    1. --agent-dev and --ephemeral compose into an agent-safe run with a unique
       fresh home under the system temp root. --ephemeral names the profile
       EPHEMERAL; otherwise --agent-dev names it AGENT_DEV. Either way the
       real user home is never read, migrated, or written.
    2. Without a profile flag, the existing XENIX_APP_HOME override (when set)
       wins, else the platform default home. --smoke-test alone does not
       isolate the home; it only selects startup-validation behavior.
    """
    del smoke_test  # smoke-test changes run behavior, not profile resolution.
    isolated = agent_dev or ephemeral
    if isolated:
        profile = RuntimeProfile.EPHEMERAL if ephemeral else RuntimeProfile.AGENT_DEV
        root = temp_root or Path(tempfile.gettempdir())
        run_id = uuid4().hex
        runtime_home = (root / f"xenix-{profile.value}-{run_id[:12]}").resolve()
        capabilities = Capabilities.agent_safe()
    else:
        profile = RuntimeProfile.PRODUCTION
        run_id = uuid4().hex
        runtime_home = default_app_home().resolve()
        capabilities = Capabilities()
    return RuntimeProfileContext(
        profile=profile,
        runtime_home=runtime_home,
        capabilities=capabilities,
        run_id=run_id,
        isolated_home=isolated,
    )
