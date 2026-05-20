from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Any

from .yaml_store import load_yaml, save_yaml


ACTIVE_PROJECT_FILE = ".active_project"
DEFAULT_PROJECT_NAME = "current_project"


def slugify_project_name(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug[:60] or DEFAULT_PROJECT_NAME


@dataclass(frozen=True)
class ProjectPaths:
    app_root: Path
    project_name: str

    @property
    def projects_dir(self) -> Path:
        return self.app_root / "projects"

    @property
    def runtime_root(self) -> Path:
        return self.projects_dir / self.project_name

    @property
    def state_dir(self) -> Path:
        return self.runtime_root / "state"

    @property
    def configs_dir(self) -> Path:
        return self.app_root / "configs"

    @property
    def templates_dir(self) -> Path:
        return self.app_root / "templates"

    @property
    def outputs_dir(self) -> Path:
        return self.runtime_root / "outputs"

    @property
    def input_dir(self) -> Path:
        return self.runtime_root / "input"

    @property
    def active_project_file(self) -> Path:
        return self.app_root / ACTIVE_PROJECT_FILE

    def state_file(self, name: str) -> Path:
        return self.state_dir / name

    @property
    def workflow_state_file(self) -> Path:
        return self.state_file("workflow_state.yml")

    @property
    def paper_details_dir(self) -> Path:
        return self.state_dir / "paper_details"


class Project:
    def __init__(self, app_root: Path, project_name: str | None = None) -> None:
        resolved_name = project_name or self._load_active_project_name(app_root) or DEFAULT_PROJECT_NAME
        self.paths = ProjectPaths(app_root=app_root, project_name=resolved_name)

    @property
    def project_name(self) -> str:
        return self.paths.project_name

    def set_active_project(self, project_name: str) -> None:
        save_yaml(self.paths.active_project_file, {"project_name": project_name})

    def load_state(self, filename: str, default: Any | None = None) -> Any:
        runtime_file = self.paths.state_file(filename)
        if runtime_file.exists():
            return load_yaml(runtime_file, default=default)
        template_file = self.paths.app_root / "state" / filename
        if template_file.exists():
            return load_yaml(template_file, default=default)
        return {} if default is None else default

    def save_state(self, filename: str, data: Any) -> None:
        save_yaml(self.paths.state_file(filename), data)

    def load_config(self, filename: str, default: Any | None = None) -> Any:
        return load_yaml(self.paths.configs_dir / filename, default=default)

    def load_workflow_state(self) -> dict[str, Any]:
        return self.load_state("workflow_state.yml", default={})

    def save_workflow_state(self, data: dict[str, Any]) -> None:
        save_yaml(self.paths.workflow_state_file, data)

    def load_example(self, filename: str, default: Any | None = None) -> Any:
        return load_yaml(self.paths.app_root / "examples" / filename, default=default)

    def reset_runtime_state(self) -> None:
        if self.paths.runtime_root.exists():
            shutil.rmtree(self.paths.runtime_root)
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        self.paths.paper_details_dir.mkdir(parents=True, exist_ok=True)
        self.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.input_dir.mkdir(parents=True, exist_ok=True)

    def save_user_input_snapshot(self, source_path: Path | None = None, content: str | None = None) -> None:
        self.paths.input_dir.mkdir(parents=True, exist_ok=True)
        if source_path is not None and source_path.exists():
            shutil.copyfile(source_path, self.paths.input_dir / source_path.name)
            return
        if content is not None:
            (self.paths.input_dir / "user_input.txt").write_text(content, encoding="utf-8")

    @staticmethod
    def _load_active_project_name(app_root: Path) -> str | None:
        active_file = app_root / ACTIVE_PROJECT_FILE
        data = load_yaml(active_file, default={})
        project_name = data.get("project_name") if isinstance(data, dict) else None
        if project_name:
            return str(project_name)
        return None
