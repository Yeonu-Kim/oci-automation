from pathlib import Path

from .base_prompt_repository import BasePromptRepository


class FilePromptRepository(BasePromptRepository):
    def __init__(self, root: Path) -> None:
        self._path = root / ".github" / "prompts" / "manifest-generation.md"

    def get_system_prompt(self) -> str:
        return self._path.read_text()
