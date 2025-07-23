import os
import requests
import hashlib
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime


class GitHubAPIUtils:
    """
    A utility class for interacting with GitHub repositories via the GitHub REST API.
    This replaces the need for local Git operations and system dependencies.
    """
    
    def __init__(self, *, token: str, owner: str, repo: str, branch: str = "main"):
        """
        Initialize the GitHub API client.
        
        Args:
            token: GitHub personal access token with repo permissions
            owner: GitHub username or organization name
            repo: Repository name
            branch: Target branch (default: "main")
        """
        self.token = token
        self.owner = owner
        self.repo_name = repo
        self.branch = branch
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TSR-BlogBot/1.0"
        }
        
        # Cache for file SHAs to optimize API calls
        self._file_sha_cache = {}
    
    def _hash(self, content: bytes) -> str:
        """Generate SHA256 hash of content for comparison."""
        return hashlib.sha256(content).hexdigest()
    
    def _get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from GitHub API.
        
        Args:
            file_path: Path to the file in the repository
            
        Returns:
            Dictionary with file info or None if file doesn't exist
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/contents/{file_path}"
        params = {"ref": self.branch}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching file info for {file_path}: {e}", flush=True)
            return None
    
    def _get_existing_hash(self, file_path: str) -> Optional[str]:
        """
        Get the hash of an existing file in the repository.
        
        Args:
            file_path: Path to the file in the repository
            
        Returns:
            SHA256 hash of the file content or None if file doesn't exist
        """
        file_info = self._get_file_info(file_path)
        if not file_info:
            return None
        
        try:
            # Decode base64 content and hash it
            content = base64.b64decode(file_info["content"])
            return self._hash(content)
        except Exception as e:
            print(f"Error decoding file content for {file_path}: {e}", flush=True)
            return None
    
    def file_changed(self, file_path: str, new_content: bytes) -> bool:
        """
        Check if a file has changed by comparing hashes.
        
        Args:
            file_path: Path to the file in the repository
            new_content: New content to compare
            
        Returns:
            True if the file has changed or doesn't exist, False otherwise
        """
        existing_hash = self._get_existing_hash(file_path)
        new_hash = self._hash(new_content)
        return existing_hash != new_hash
    
    def download_image(self, url: str) -> tuple[bytes, str]:
        """
        Download an image from a URL.
        
        Args:
            url: URL of the image to download
            
        Returns:
            Tuple of (image_bytes, file_extension)
        """
        print(f"Downloading image from: {url}", flush=True)
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        content = response.content
        content_type = response.headers.get("Content-Type", "").lower()
        
        print(f"Downloaded {len(content)} bytes, Content-Type: {content_type}", flush=True)
        
        # Determine file extension from content type
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            # Default to jpg if we can't determine
            ext = ".jpg"
            print(f"Unknown content type {content_type}, defaulting to .jpg", flush=True)
        
        print(f"Using file extension: {ext}", flush=True)
        return content, ext
    
    def _get_latest_commit_sha(self) -> str:
        """
        Get the SHA of the latest commit on the target branch.
        
        Returns:
            SHA of the latest commit
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/ref/heads/{self.branch}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()["object"]["sha"]
    
    def _create_blob(self, content: bytes, encoding: str = "base64") -> str:
        """
        Create a blob for binary content.
        
        Args:
            content: Raw bytes content
            encoding: Encoding type (base64 for binary files)
            
        Returns:
            SHA of the created blob
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/blobs"
        
        if encoding == "base64":
            content_str = base64.b64encode(content).decode("utf-8")
            print(f"Created base64 blob with {len(content)} bytes -> {len(content_str)} base64 chars", flush=True)
        else:
            content_str = content.decode("utf-8") if isinstance(content, bytes) else content
        
        data = {
            "content": content_str,
            "encoding": encoding
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        response.raise_for_status()
        blob_sha = response.json()["sha"]
        print(f"Created blob with SHA: {blob_sha}", flush=True)
        return blob_sha

    def _create_tree(self, files: List[Dict[str, Any]], base_tree_sha: str) -> str:
        """
        Create a new tree with the specified files.
        
        Args:
            files: List of file dictionaries with path, content, and encoding
            base_tree_sha: SHA of the base tree to build upon
            
        Returns:
            SHA of the created tree
        """
        tree_items = []
        
        for file_info in files:
            path = file_info["path"]
            content = file_info["content"]
            encoding = file_info["encoding"]
            
            # For binary files (images), create a blob first
            if encoding == "base64":
                print(f"Creating blob for binary file: {path}", flush=True)
                blob_sha = self._create_blob(content, "base64")
                tree_item = {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                }
            else:
                # For text files, include content directly in tree
                if isinstance(content, bytes):
                    content_str = content.decode("utf-8")
                else:
                    content_str = content
                
                tree_item = {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content_str
                }
            
            tree_items.append(tree_item)
        
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/trees"
        data = {
            "base_tree": base_tree_sha,
            "tree": tree_items
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        response.raise_for_status()
        return response.json()["sha"]
    
    def _create_commit(self, tree_sha: str, parent_sha: str, message: str, 
                      author_name: str, author_email: str) -> str:
        """
        Create a new commit.
        
        Args:
            tree_sha: SHA of the tree for this commit
            parent_sha: SHA of the parent commit
            message: Commit message
            author_name: Author name
            author_email: Author email
            
        Returns:
            SHA of the created commit
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/commits"
        data = {
            "message": message,
            "tree": tree_sha,
            "parents": [parent_sha],
            "author": {
                "name": author_name,
                "email": author_email,
                "date": datetime.utcnow().isoformat() + "Z"
            },
            "committer": {
                "name": author_name,
                "email": author_email,
                "date": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        response.raise_for_status()
        return response.json()["sha"]
    
    def _update_ref(self, commit_sha: str) -> bool:
        """
        Update the branch reference to point to the new commit.
        
        Args:
            commit_sha: SHA of the commit to point to
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/refs/heads/{self.branch}"
        data = {"sha": commit_sha}
        
        try:
            response = requests.patch(url, json=data, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error updating ref: {e}", flush=True)
            return False
    
    def commit_files(self, files: List[Dict[str, Any]], commit_message: str, 
                    author_name: str = "BlogBot", author_email: str = "blogbot@example.com") -> bool:
        """
        Commit multiple files to the repository.
        
        Args:
            files: List of file dictionaries with 'path', 'content', and 'encoding' keys
            commit_message: Commit message
            author_name: Author name
            author_email: Author email
            
        Returns:
            True if successful, False otherwise
        """
        if not files:
            return False
        
        try:
            # Get the latest commit SHA
            latest_commit_sha = self._get_latest_commit_sha()
            
            # Get the tree SHA from the latest commit
            commit_url = f"{self.base_url}/repos/{self.owner}/{self.repo_name}/git/commits/{latest_commit_sha}"
            commit_response = requests.get(commit_url, headers=self.headers)
            commit_response.raise_for_status()
            base_tree_sha = commit_response.json()["tree"]["sha"]
            
            # Create new tree with the files
            tree_sha = self._create_tree(files, base_tree_sha)
            
            # Create new commit
            commit_sha = self._create_commit(
                tree_sha, latest_commit_sha, commit_message, author_name, author_email
            )
            
            # Update the branch reference
            return self._update_ref(commit_sha)
            
        except Exception as e:
            print(f"Error committing files: {e}", flush=True)
            return False
    
    def commit_blog_post(self, slug: str, markdown: str, image_url: str) -> bool:
        """
        Commit a single blog post with its markdown and featured image.
        
        Args:
            slug: Blog post slug (used for directory name)
            markdown: Markdown content
            image_url: URL of the featured image
            
        Returns:
            True if successful, False otherwise
        """
        files_to_commit = []
        changed = False
        
        post_dir = f"content/posts/{slug}"
        
        # Check markdown file
        markdown_path = f"{post_dir}/index.md"
        markdown_bytes = markdown.encode("utf-8")
        if self.file_changed(markdown_path, markdown_bytes):
            files_to_commit.append({
                "path": markdown_path,
                "content": markdown_bytes,  # bytes object
                "encoding": "utf-8"
            })
            changed = True
        
        # Check featured image
        try:
            image_bytes, ext = self.download_image(image_url)
            image_path = f"{post_dir}/featured{ext}"
            if self.file_changed(image_path, image_bytes):
                files_to_commit.append({
                    "path": image_path,
                    "content": image_bytes,  # bytes object from download
                    "encoding": "base64"
                })
                changed = True
        except Exception as e:
            print(f"Error downloading image for {slug}: {e}", flush=True)
            # Continue with just the markdown if image fails
        
        if not changed:
            print(f"No changes detected for blog post: {slug}", flush=True)
            return True
        
        return self.commit_files(
            files_to_commit,
            f"ci(ops): publish post `{slug}`",
            author_email="bot@teamspiralracing.com",
            author_name="TSR Service Account [Bot]"
        )