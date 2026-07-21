"""Exceptions raised by the public lsmesher API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class LsmesherError(RuntimeError):
    """Base class for recoverable lsmesher failures."""


class InvalidGeometryError(LsmesherError):
    """The input geometry cannot be meshed safely."""


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
