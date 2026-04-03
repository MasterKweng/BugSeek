"""Prepare a local code workspace from project repository settings."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.platform.db.base import Project

logger = logging.getLogger(__name__)


class RepositoryWorkspaceService:
    """Resolve and prepare a local workspace for code-lineage scanning."""

    def __init__(self, db: Optional[Session]):
        self.db = db

    def prepare_workspace(
        self,
        *,
        project_id: int,
        repository_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        repository = dict(repository_config or self._load_project_repository_config(project_id) or {})
        workspace_root = str(repository.get("workspace_root") or "").strip()
        if workspace_root:
            workspace_path = Path(workspace_root)
            if workspace_path.exists():
                return {
                    "workspace_root": str(workspace_path),
                    "repo_url": str(repository.get("repo_url") or ""),
                    "default_branch": str(repository.get("default_branch") or "main"),
                    "source": "configured_workspace",
                }

        repo_url = str(repository.get("repo_url") or "").strip()
        if not repo_url:
            return {
                "workspace_root": workspace_root or None,
                "repo_url": "",
                "default_branch": str(repository.get("default_branch") or "main"),
                "source": "missing_repository",
            }

        default_branch = str(repository.get("default_branch") or "main").strip() or "main"
        managed_root = self._managed_workspace_root(project_id=project_id, repo_url=repo_url)
        managed_root.parent.mkdir(parents=True, exist_ok=True)

        if (managed_root / ".git").exists():
            self._run_git(["git", "fetch", "--all", "--prune"], cwd=managed_root)
            self._run_git(["git", "checkout", default_branch], cwd=managed_root)
            self._run_git(["git", "pull", "--ff-only", "origin", default_branch], cwd=managed_root)
            source = "managed_workspace_update"
        else:
            self._run_git(
                ["git", "clone", "--branch", default_branch, "--depth", "1", repo_url, str(managed_root)],
                cwd=managed_root.parent,
            )
            source = "managed_workspace_clone"

        self._persist_workspace_root(project_id=project_id, workspace_root=str(managed_root))
        return {
            "workspace_root": str(managed_root),
            "repo_url": repo_url,
            "default_branch": default_branch,
            "source": source,
        }

    def _load_project_repository_config(self, project_id: int) -> Dict[str, Any]:
        if self.db is None:
            return {}
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {}
        asset_config = dict(project.asset_config or {})
        repository = asset_config.get("repository")
        return dict(repository or {})

    def _persist_workspace_root(self, *, project_id: int, workspace_root: str) -> None:
        if self.db is None:
            return
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        asset_config = dict(project.asset_config or {})
        repository = dict(asset_config.get("repository") or {})
        if repository.get("workspace_root") == workspace_root:
            return
        repository["workspace_root"] = workspace_root
        asset_config["repository"] = repository
        project.asset_config = asset_config
        self.db.commit()

    def _managed_workspace_root(self, *, project_id: int, repo_url: str) -> Path:
        backend_root = Path(__file__).resolve().parents[3]
        repo_name = self._repo_name_from_url(repo_url)
        return backend_root / "data" / "repositories" / f"project_{project_id}" / repo_name

    def _repo_name_from_url(self, repo_url: str) -> str:
        parsed = urlparse(repo_url)
        candidate = parsed.path.rstrip("/").split("/")[-1] if parsed.path else ""
        if not candidate:
            candidate = "repository"
        if candidate.endswith(".git"):
            candidate = candidate[:-4]
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in candidate).strip("._")
        return safe or "repository"

    def _run_git(self, command: list[str], *, cwd: Path) -> None:
        logger.info("Preparing repository workspace via git: cwd=%s cmd=%s", cwd, " ".join(command))
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            detail = stderr or stdout or f"git exited with {completed.returncode}"
            raise RuntimeError(detail)
