import os
from github import Github
import git
from datetime import datetime

def create_remediation_pr(
    patched_file_path: str,
    pr_title: str = "Automated Remediation Patch",
    pr_body: str = "This PR contains automated security/configuration remediations.",
    base_branch: str = "main"
):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_REPO = os.getenv("GITHUB_REPO")
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("GITHUB_TOKEN or GITHUB_REPO not set in environment.")
        return

    repo = git.Repo(".")
    origin = repo.remote(name="origin")
    repo.git.checkout(base_branch)
    repo.git.pull()
    branch_name = f"remediation-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    repo.git.checkout("-b", branch_name)
    repo.git.add(patched_file_path)
    repo.git.commit("-m", pr_title)
    repo.git.push("--set-upstream", "origin", branch_name)

    g = Github(GITHUB_TOKEN)
    github_repo = g.get_repo(GITHUB_REPO)
    pr = github_repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=base_branch
    )
    print(f"Pull request created: {pr.html_url}")
    return pr.html_url