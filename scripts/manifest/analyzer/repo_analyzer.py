import re
import subprocess
import tempfile
from pathlib import Path

from ..models import RepoAnalysis
from .base_repo_analyzer import BaseRepoAnalyzer


_FILES_TO_READ = [
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "src/main/resources/application.yml",
    "src/main/resources/application.yaml",
    "src/main/resources/application.properties",
    "Dockerfile",
]


class RepoAnalyzerService(BaseRepoAnalyzer):
    def analyze(self, repo_url: str) -> RepoAnalysis:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["git", "clone", "--depth=1", repo_url, tmpdir],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"Clone failed: {result.stderr}")
                return RepoAnalysis(framework="unknown", port=8080, health_path="/health")

            file_contents: dict[str, str] = {}
            for rel in _FILES_TO_READ:
                path = Path(tmpdir) / rel
                if path.exists():
                    try:
                        file_contents[rel] = path.read_text(errors="replace")[:3000]
                    except Exception:
                        pass

            return _detect_framework(file_contents)


def _detect_framework(file_contents: dict[str, str]) -> RepoAnalysis:
    framework = "unknown"
    port = 8080
    health_path = "/health"

    gradle = "build.gradle" in file_contents or "build.gradle.kts" in file_contents
    if "pom.xml" in file_contents or gradle:
        framework, port, health_path = "spring-boot", 8080, "/actuator/health"

        for yml in ("src/main/resources/application.yml", "src/main/resources/application.yaml"):
            if yml in file_contents:
                m = re.search(r"port:\s*(\d+)", file_contents[yml])
                if m:
                    port = int(m.group(1))
                break

        props = "src/main/resources/application.properties"
        if props in file_contents:
            m = re.search(r"server\.port\s*=\s*(\d+)", file_contents[props])
            if m:
                port = int(m.group(1))

    elif "requirements.txt" in file_contents or "pyproject.toml" in file_contents:
        combined = file_contents.get("requirements.txt", "") + file_contents.get("pyproject.toml", "")
        if "django" in combined.lower():
            framework, port, health_path = "django", 8000, "/health/"
        elif "fastapi" in combined.lower():
            framework, port, health_path = "fastapi", 8000, "/health"
        else:
            framework, port, health_path = "python", 8000, "/health"

    elif "package.json" in file_contents:
        pkg = file_contents["package.json"]
        framework = "nestjs" if "@nestjs" in pkg else ("express" if "express" in pkg else "node")
        port, health_path = 3000, "/health"

    if framework == "unknown" and "Dockerfile" in file_contents:
        m = re.search(r"EXPOSE\s+(\d+)", file_contents["Dockerfile"])
        if m:
            port = int(m.group(1))

    return RepoAnalysis(
        framework=framework,
        port=port,
        health_path=health_path,
        detected_files=list(file_contents.keys()),
    )
