from github import Github, GithubException, InputGitTreeElement

from .base_github_repository import BaseGitHubRepository


class GitHubRepository(BaseGitHubRepository):
    def __init__(self, token: str, repo_name: str) -> None:
        self._repo = Github(token).get_repo(repo_name)

    def create_pr(self, files: dict[str, str], team: str, issue_number: int) -> str:
        branch_name = f"onboarding/{team}"
        base_sha = self._repo.get_branch("main").commit.sha

        try:
            self._repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        except GithubException as e:
            if e.status == 422:
                branch_name = f"onboarding/{team}-{issue_number}"
                self._repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
            else:
                raise

        tree_elements = []
        for path, content in files.items():
            blob = self._repo.create_git_blob(content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(path=path, mode="100644", type="blob", sha=blob.sha)
            )

        base_tree = self._repo.get_git_tree(base_sha)
        new_tree = self._repo.create_git_tree(tree_elements, base_tree)
        parent_commit = self._repo.get_git_commit(base_sha)
        new_commit = self._repo.create_git_commit(
            message=f"feat: onboard {team} to OCI",
            tree=new_tree,
            parents=[parent_commit],
        )
        self._repo.get_git_ref(f"refs/heads/{branch_name}").edit(new_commit.sha)

        pr = self._repo.create_pull(
            title=f"feat: onboard {team} to OCI",
            body=(
                f"Closes #{issue_number}\n\n"
                f"온보딩 이슈 #{issue_number}에서 자동 생성된 매니페스트 PR입니다.\n\n"
                "> 시크릿 값을 OCI Vault에 등록한 후 이 PR을 머지해 주세요."
            ),
            head=branch_name,
            base="main",
        )
        pr.add_to_labels("manifest-review")
        return pr.html_url
