#!/usr/bin/env python3
"""
CI #1: GitHub 온보딩 이슈 → Kubernetes 매니페스트 PR 자동 생성

환경변수:
  ELICE_API_KEY       - Elice API 키
  ELICE_BASE_URL      - Elice API 엔드포인트 (예: https://mlapi.run/abc-1234-xyz/v1)
  GITHUB_TOKEN        - GitHub 토큰 (PR 생성 권한 필요)
  GITHUB_REPOSITORY   - 레포 full name (예: wafflestudio/waffle-world-oci)
  ISSUE_BODY          - GitHub 이슈 본문 (CI에서 자동 주입)
  ISSUE_NUMBER        - GitHub 이슈 번호 (CI에서 자동 주입)
"""

import os
from pathlib import Path

from .analyzer.repo_analyzer import RepoAnalyzerService
from .github.github_repository import GitHubRepository
from .llm.elice_llm_provider import EliceLLMProvider
from .llm.file_prompt_repository import FilePromptRepository
from .service import ManifestService


def main() -> None:
    root = Path(__file__).parent.parent.parent

    service = ManifestService(
        llm=EliceLLMProvider(
            base_url=os.environ["ELICE_BASE_URL"],
            api_key=os.environ["ELICE_API_KEY"],
        ),
        github=GitHubRepository(
            token=os.environ["GITHUB_TOKEN"],
            repo_name=os.environ["GITHUB_REPOSITORY"],
        ),
        prompt_repo=FilePromptRepository(root=root),
        repo_analyzer=RepoAnalyzerService(),
    )

    pr_url = service.run(
        issue_body=os.environ["ISSUE_BODY"],
        issue_number=int(os.environ["ISSUE_NUMBER"]),
    )
    print(f"PR created: {pr_url}")


if __name__ == "__main__":
    main()
