from abc import ABC, abstractmethod


class BaseGitHubRepository(ABC):
    @abstractmethod
    def create_pr(self, files: dict[str, str], team: str, issue_number: int) -> str: ...
