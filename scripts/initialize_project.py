"""Create the project's package directories and package markers.

Run with: python scripts/initialize_project.py
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORIES = (
    "config",
    "database",
    "src",
    "src/agents",
    "src/api",
    "src/security",
    "src/workflow",
    "src/utils",
    "tests",
)


def initialize_project() -> None:
    """Create the expected directory structure and empty ``__init__.py`` files."""

    for relative_directory in PACKAGE_DIRECTORIES:
        directory = PROJECT_ROOT / relative_directory
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").touch(exist_ok=True)


if __name__ == "__main__":
    initialize_project()
