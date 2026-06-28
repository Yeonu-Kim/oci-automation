import re

from ..models import IssueData


_LABEL_TO_FIELD: dict[str, str] = {
    "팀 이름": "team",
    "GitHub 레포지토리 URL": "repo_url",
    "Prod 도메인": "prod_domain",
    "Dev 도메인": "dev_domain",
    "OCIR 이미지 이름": "image_name",
    "Valkey (Redis) 사용 여부": "use_valkey",
    "시크릿 키 목록": "secret_keys",
    "Prod DB 이름": "db_name_prod",
    "Dev DB 이름": "db_name_dev",
}


class IssueParserService:
    def parse(self, body: str) -> IssueData:
        raw = self._parse_sections(body)
        return IssueData(
            team=raw.get("team", ""),
            repo_url=raw.get("repo_url", ""),
            prod_domain=raw.get("prod_domain", ""),
            dev_domain=raw.get("dev_domain", ""),
            image_name=raw.get("image_name", ""),
            use_valkey=raw.get("use_valkey", "No").strip() == "Yes",
            secret_keys=self._parse_list(raw.get("secret_keys", "")),
            db_name_prod=raw.get("db_name_prod", ""),
            db_name_dev=raw.get("db_name_dev", ""),
        )

    def _parse_sections(self, body: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for section in re.split(r"^### ", body, flags=re.MULTILINE):
            if not section.strip():
                continue
            label, _, value = section.partition("\n")
            value = value.strip()
            if value == "_No response_":
                value = ""
            field = _LABEL_TO_FIELD.get(label.strip())
            if field:
                result[field] = value
        return result

    def _parse_list(self, raw: str) -> list[str]:
        return [line.strip() for line in raw.splitlines() if line.strip()]
