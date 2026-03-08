"""Shared utility functions for AgentForge."""

from __future__ import annotations

import re
from pathlib import Path


def safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename, preventing path traversal.

    Strips path separators, .., and non-alphanumeric characters except
    hyphens, underscores, and dots. Returns a safe, filesystem-friendly string.
    """
    # Remove path traversal components
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    # Keep only alphanumeric, hyphens, underscores, dots
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    # Fallback if empty
    return name or "unnamed_agent"


def safe_output_path(output_dir: Path, filename: str) -> Path:
    """Build a safe output path, ensuring it stays within output_dir."""
    safe_name = safe_filename(filename)
    target = (output_dir / safe_name).resolve()
    output_resolved = output_dir.resolve()
    if not str(target).startswith(str(output_resolved)):
        raise ValueError(f"Path traversal detected: {filename!r} escapes {output_dir}")
    return target
