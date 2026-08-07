"""Exceptions raised by the public lsmesher API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from lsmesher.results import MeshAttemptReport


class LsmesherError(RuntimeError):
    """Base class for recoverable lsmesher failures."""


class InvalidGeometryError(LsmesherError):
    """The input geometry cannot be meshed safely."""


class DependencyError(LsmesherError):
    """An optional runtime dependency required for an operation is unavailable."""


class UnsupportedSourceError(TypeError, LsmesherError):
    """The value passed to :func:`mesh` is not a supported mesh source."""


class AutomaticMeshingError(LsmesherError):
    """All automatic meshing attempts failed.

    The individual attempts are retained so applications can present useful
    diagnostics without parsing log files or exception strings.
    """

    def __init__(
        self,
        attempts: tuple[MeshAttemptReport, ...],
        last_error: Exception,
    ) -> None:
        super().__init__(
            f"Automatic meshing failed after {len(attempts)} attempts: {last_error}"
        )
        self.attempts = attempts
        self.last_error = last_error


class MesherNotFoundError(LsmesherError):
    """A required external mesher is unavailable."""

    def __init__(self, mesher: str) -> None:
        super().__init__(f"Required mesher executable was not found: {mesher}")
        self.mesher = mesher


class MesherError(LsmesherError):
    """An external mesher exited unsuccessfully."""

    def __init__(  # noqa: PLR0913
        self,
        mesher: str,
        command: tuple[str, ...],
        returncode: int,
        *,
        stdout: str = "",
        stderr: str = "",
        log_path: Path | None = None,
    ) -> None:
        details = [f"{mesher} failed with exit code {returncode}."]
        if stdout:
            details.append(f"stdout:\n{stdout}")
        if stderr:
            details.append(f"stderr:\n{stderr}")
        if log_path is not None:
            details.append(f"Log: {log_path}")
        super().__init__("\n\n".join(details))
        self.mesher = mesher
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.log_path = log_path


class TriangleError(MesherError):
    """Triangle failed to produce a usable 2D mesh."""


class TetGenError(MesherError):
    """TetGen failed to produce a usable tetrahedral mesh."""
