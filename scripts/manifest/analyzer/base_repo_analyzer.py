from abc import ABC, abstractmethod

from ..models import RepoAnalysis


class BaseRepoAnalyzer(ABC):
    @abstractmethod
    def analyze(self, repo_url: str) -> RepoAnalysis: ...
