import os
import requests
import hashlib
from pathlib import Path
from git import Repo, Actor
from typing import Optional


class GitUtils:
    def __init__(self, *, token: str, owner: str, repo: str, branch: str = "main", local_path: Optional[str] = "/tmp/gitrepo"):
        self.token = token
        self.owner = owner
        self.repo_name = repo
        self.branch = branch
        self.repo_path = Path(local_path)

        if not self.repo_path.exists():
            repo_url = f"https://{token}@github.com/{owner}/{repo}.git"
            self.repo = Repo.clone_from(repo_url, self.repo_path, branch=branch)
        else:
            self.repo = Repo(self.repo_path)

        self.remote = self.repo.remotes.origin

    def _hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _get_existing_hash(self, file_path: str) -> Optional[str]:
        abs_path = self.repo_path / file_path
        if not abs_path.exists():
            return None
        return self._hash(abs_path.read_bytes())

    def file_changed(self, rel_path: str, new_content: bytes) -> bool:
        return self._get_existing_hash(rel_path) != self._hash(new_content)

    def write_file(self, rel_path: str, content: bytes):
        abs_path = self.repo_path / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)

    def download_image(self, url: str) -> tuple[bytes, str]:
        resp = requests.get(url)
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("Content-Type", "")
        ext = ".jpg" if "jpeg" in content_type else ".png"
        return content, ext

    def commit_files(self, changed_files: list[str], commit_message: str, author_name="BlogBot", author_email="blogbot@example.com"):
        if not changed_files:
            return False
        self.repo.index.add(changed_files)
        actor = Actor(author_name, author_email)
        self.repo.index.commit(commit_message, author=actor, committer=actor)
        self.remote.push(refspec=f"{self.branch}:{self.branch}")
        return True

    def commit_blog_post(self, slug: str, markdown: str, image_url: str) -> bool:
        changed = []
        post_dir = f"content/posts/{slug}"

        # index.md
        markdown_path = f"{post_dir}/index.md"
        markdown_bytes = markdown.encode("utf-8")
        if self.file_changed(markdown_path, markdown_bytes):
            self.write_file(markdown_path, markdown_bytes)
            changed.append(markdown_path)

        # featured image
        image_bytes, ext = self.download_image(image_url)
        image_path = f"{post_dir}/featured{ext}"
        if self.file_changed(image_path, image_bytes):
            self.write_file(image_path, image_bytes)
            changed.append(image_path)

        return self.commit_files(
            changed,
            f"ci(ops): publish post `{slug}`",
            author_email="bot@teamspiralracing.com",
            author_name="TSR Service Account [Bot]"
        )
