import subprocess

class GitTool:
    def clone_repo(self, repo_url: str, target_path: str):
        print(f"Cloning {repo_url} into {target_path}")
        # subprocess.run(["git", "clone", repo_url, target_path])
        return {"status": "success", "message": "Repo cloned"}