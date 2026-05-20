from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {} if default is None else default
    return data


def save_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )
    path.write_text(serialized, encoding="utf-8")
