import os
from github import Github
from datetime import datetime

def create_remediation_pr(
    patched_file_path: str,
    original_file_path: str,
    repo_full_name: str,
    pr_title: str = "Automated Remediation Patch",
    pr_body: str = "This PR contains automated security/configuration remediations.",
    base_branch: str = "main"
):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_REPO = repo_full_name
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("GITHUB_TOKEN or GITHUB_REPO not set in environment.")
        return

    with open(patched_file_path, "r") as f:
        file_content = f.read()
    
    filename = original_file_path
    
    try:
        g = Github(GITHUB_TOKEN)
        github_repo = g.get_repo(GITHUB_REPO)
        
        branch_name = f"remediation-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        base_ref = github_repo.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha
        
        github_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        
        try:
            existing_file = github_repo.get_contents(filename, ref=branch_name)
            github_repo.update_file(
                path=filename,
                message=pr_title,
                content=file_content,
                sha=existing_file.sha,
                branch=branch_name
            )
        except:
            github_repo.create_file(
                path=filename,
                message=pr_title,
                content=file_content,
                branch=branch_name
            )
        
        pr = github_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=base_branch
        )
        print(f"Pull request created: {pr.html_url}")
        return pr.html_url
        
    except Exception as e:
        print(f"Error creating PR: {e}")
        return None
