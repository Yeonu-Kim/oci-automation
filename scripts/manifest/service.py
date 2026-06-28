import json
import re

from .models import IssueData, RepoAnalysis
from .llm.base_llm_provider import BaseLLMProvider
from .llm.base_prompt_repository import BasePromptRepository
from .github.base_github_repository import BaseGitHubRepository
from .analyzer.base_repo_analyzer import BaseRepoAnalyzer
from .parser.issue_parser import IssueParserService


class ManifestService:
    def __init__(
        self,
        llm: BaseLLMProvider,
        github: BaseGitHubRepository,
        prompt_repo: BasePromptRepository,
        repo_analyzer: BaseRepoAnalyzer,
    ) -> None:
        self._llm = llm
        self._github = github
        self._prompt_repo = prompt_repo
        self._repo_analyzer = repo_analyzer
        self._issue_parser = IssueParserService()

    def run(self, issue_body: str, issue_number: int) -> str:
        print("Parsing issue body...")
        issue_data = self._issue_parser.parse(issue_body)
        print(json.dumps(issue_data.__dict__, ensure_ascii=False, indent=2))

        print("Analyzing repository...")
        repo_analysis = self._repo_analyzer.analyze(issue_data.repo_url)
        print(json.dumps(repo_analysis.__dict__, indent=2))

        print("Reading system prompt...")
        system_prompt = self._prompt_repo.get_system_prompt()

        print("Calling LLM...")
        user_content = self._build_user_content(issue_data, repo_analysis)
        response = self._llm.generate(system_prompt, user_content)

        print("Parsing generated files...")
        files = self._parse_files(response)
        if not files:
            print("ERROR: API 응답에서 파일을 파싱하지 못했습니다.")
            print("Response preview:", response[:500])
            raise RuntimeError("No files parsed from LLM response")
        print(f"Generated: {list(files.keys())}")

        print("Creating pull request...")
        return self._github.create_pr(files, issue_data.team, issue_number)

    def _build_user_content(self, issue_data: IssueData, repo_analysis: RepoAnalysis) -> str:
        return (
            "다음 정보를 바탕으로 Kubernetes 매니페스트 파일을 생성해 주세요.\n\n"
            "## 이슈 데이터\n"
            f"```json\n{json.dumps(issue_data.__dict__, ensure_ascii=False, indent=2)}\n```\n\n"
            "## 레포지토리 분석 결과\n"
            f"```json\n{json.dumps(repo_analysis.__dict__, indent=2)}\n```\n"
        )

    def _parse_files(self, response: str) -> dict[str, str]:
        files: dict[str, str] = {}
        pattern = re.compile(r"^---\s*FILE:\s*(.+?)\s*---$", re.MULTILINE)
        matches = list(pattern.finditer(response))
        for i, match in enumerate(matches):
            path = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(response)
            files[path] = response[start:end].strip()
        return files
