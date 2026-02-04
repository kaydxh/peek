#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""File operation utilities."""

import os
import json
from pathlib import Path
from typing import Optional, Union


def make_dir_all(name: str) -> None:
    """Create directory and all parent directories.

    Args:
        name: Directory path to create.
    """
    if not os.path.exists(name):
        os.makedirs(name, mode=0o755)


# Alias for compatibility
ensure_dir = make_dir_all


def file_exists(path: Union[str, Path]) -> bool:
    """Check if a file exists.

    Args:
        path: Path to check.

    Returns:
        True if file exists, False otherwise.
    """
    return os.path.isfile(path)


def read_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
    """Read entire file content as string.

    Args:
        path: Path to file.
        encoding: File encoding.

    Returns:
        File content as string.
    """
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def write_file(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
) -> None:
    """Write string content to file.

    Args:
        path: Path to file.
        content: Content to write.
        encoding: File encoding.
        create_dirs: Whether to create parent directories if they don't exist.
    """
    if create_dirs:
        parent = os.path.dirname(path)
        if parent:
            ensure_dir(parent)

    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def dump_json(output_file: Union[str, Path], json_data: dict, indent: int = 4) -> None:
    """Dump JSON data to file.

    Args:
        output_file: Output file path.
        json_data: Data to serialize.
        indent: JSON indentation level.
    """
    data = json.dumps(json_data, indent=indent)
    write_file(output_file, data)


# Keep old name for backward compatibility
DumpJson = dump_json
    
