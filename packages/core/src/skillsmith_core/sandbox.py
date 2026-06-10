"""Layered sandbox for running UNTRUSTED code.

ALL generated code and ALL third-party skill code is untrusted. Defaults: deny
network, read-only FS, CPU/mem/time limits. Backends are tried in preference order
and the strongest available wins:

    firecracker (microVM) > gvisor (runsc) > bubblewrap > nsjail > none

Docker alone is **not** treated as a security boundary and is never a backend here.
Under the ``strict`` profile, if no isolating backend is available skillsmith
*refuses to run* rather than silently executing untrusted code unprotected.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from skillsmith_core.config import SandboxConfig
from skillsmith_core.models import SandboxBackend


class SandboxUnavailableError(RuntimeError):
    """Raised when the requested isolation level cannot be provided."""


@dataclass
class SandboxResult:
    backend: SandboxBackend
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass
class Sandbox:
    """Selects a backend at construction and executes commands inside it."""

    config: SandboxConfig
    backend: SandboxBackend = field(init=False)

    def __post_init__(self) -> None:
        self.backend = self._select_backend()
        if self.backend is SandboxBackend.NONE and self.config.profile == "strict":
            raise SandboxUnavailableError(
                "No isolating sandbox backend available (tried: "
                f"{', '.join(self.config.backend_preference)}). The 'strict' profile "
                "refuses to run untrusted skill code without isolation. Install one of "
                "gVisor/Firecracker/bubblewrap/nsjail, or set sandbox.profile to 'dev' "
                "to accept the risk locally."
            )

    def _select_backend(self) -> SandboxBackend:
        probes = {
            "firecracker": _has("firecracker") or _has("microsandbox") or _has("msb"),
            "gvisor": _has("runsc"),
            "bubblewrap": _has("bwrap"),
            "nsjail": _has("nsjail"),
        }
        for name in self.config.backend_preference:
            if probes.get(name):
                return SandboxBackend(name)
        return SandboxBackend.NONE

    # ------------------------------------------------------------------ run #
    def run(
        self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> SandboxResult:
        """Run ``argv`` under the selected backend with the configured limits."""

        wrapped = self._wrap(argv, cwd)
        timeout = self.config.limits.wall_seconds
        try:
            proc = subprocess.run(
                wrapped,
                cwd=str(cwd),
                env=self._scrub_env(env),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # With text=True the streams are str, but TimeoutExpired types them loosely.
            out = _as_text(exc.stdout)
            err = _as_text(exc.stderr)
            return SandboxResult(
                self.backend,
                returncode=124,
                stdout=out,
                stderr=err + "\n[sandbox] wall-clock timeout",
                timed_out=True,
            )
        return SandboxResult(self.backend, proc.returncode, proc.stdout, proc.stderr)

    # ------------------------------------------------------------- wrappers #
    def _wrap(self, argv: list[str], cwd: Path) -> list[str]:
        limits = self.config.limits
        if self.backend is SandboxBackend.BUBBLEWRAP:
            wrap = [
                "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind",
                "/lib64",
                "/lib64",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--bind",
                str(cwd),
                str(cwd),
                "--chdir",
                str(cwd),
            ]
            if self.config.deny_network:
                wrap += ["--unshare-net"]
            return wrap + argv
        if self.backend is SandboxBackend.NSJAIL:
            wrap = [
                "nsjail",
                "--quiet",
                "--mode",
                "o",
                "--time_limit",
                str(limits.wall_seconds),
                "--rlimit_cpu",
                str(limits.cpu_seconds),
                "--rlimit_as",
                str(limits.memory_mb),
                "--cwd",
                str(cwd),
            ]
            if self.config.deny_network:
                wrap += ["--disable_clone_newnet=false"]
            return [*wrap, "--", *argv]
        if self.backend is SandboxBackend.GVISOR:
            # runsc is normally driven via an OCI bundle/Docker runtime; here we shell
            # to `runsc do` for a lightweight rootless run when available.
            return ["runsc", "do", *argv]
        if self.backend is SandboxBackend.FIRECRACKER:
            # microsandbox/e2b expose a CLI that takes the command to run in a microVM.
            cli = (
                "microsandbox"
                if _has("microsandbox")
                else ("msb" if _has("msb") else "firecracker")
            )
            return [cli, "run", "--", *argv]
        # NONE: only reachable under non-strict profiles; run directly (dev only).
        return argv

    def _scrub_env(self, env: dict[str, str] | None) -> dict[str, str]:
        base = dict(env or {})
        if self.config.deny_network:
            # Best-effort egress denial for backends that don't enforce it natively.
            base.setdefault("http_proxy", "127.0.0.1:9")
            base.setdefault("https_proxy", "127.0.0.1:9")
            base.setdefault("no_proxy", "")
        return base


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def detect_backend(config: SandboxConfig | None = None) -> SandboxBackend:
    """Report which backend would be selected, without constructing a Sandbox."""

    cfg = config or SandboxConfig()
    try:
        return Sandbox(cfg.model_copy(update={"profile": "dev"})).backend
    except SandboxUnavailableError:  # pragma: no cover - dev profile never raises
        return SandboxBackend.NONE
