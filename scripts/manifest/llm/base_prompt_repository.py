from abc import ABC, abstractmethod


class BasePromptRepository(ABC):
    @abstractmethod
    def get_system_prompt(self) -> str: ...
