from dataclasses import dataclass, field


@dataclass
class IssueData:
    team: str
    repo_url: str
    prod_domain: str
    dev_domain: str
    image_name: str
    use_valkey: bool
    secret_keys: list[str]
    db_name_prod: str
    db_name_dev: str


@dataclass
class RepoAnalysis:
    framework: str
    port: int
    health_path: str
    detected_files: list[str] = field(default_factory=list)
