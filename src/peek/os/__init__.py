# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Operating system utilities module.

This module provides OS-related utilities including:
- File operations
- Process monitoring
"""

from peek.os.file import (
    ensure_dir,
    file_exists,
    read_file,
    write_file,
)

# Lazy import for monitor to avoid dependency issues
def get_monitor():
    """Get the monitor submodule."""
    from peek.os import monitor
    return monitor

__all__ = [
    "ensure_dir",
    "file_exists",
    "read_file",
    "write_file",
    "get_monitor",
]
