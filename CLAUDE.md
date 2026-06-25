# Waffle World OCI 자동화

## 레포 구조

.github/
├── ISSUE_TEMPLATE/
│ └── oci-onboarding.yml # 온보딩 요청 이슈 템플릿 (자동으로 `onboarding` 라벨 부착)
├── prompts/
│ └── manifest-generation.md # Claude에게 넘길 시스템 프롬프트
└── workflows/
├── generate-manifest.yml # CI #1: `onboarding` 라벨 이슈 → 매니페스트 PR 생성
└── provision-resources.yml # CI #2: `manifest-review` 라벨 PR 머지 → OCI/AWS 리소스 생성
scripts/
├── generate-manifest.py # Elice API 호출 + 파일 생성 스크립트
├── oci/ # OCI 초기 리소스 생성 스크립트
└── aws/ # Route53 등록 스크립트

```

---

## 자동화 계획

### 1. 매니페스트 생성 자동화 (핵심)

앱팀이 GitHub 이슈를 올리는 즉시 CI가 매니페스트 PR을 자동 생성하고,
인프라팀이 시크릿 등록 완료 후 PR을 머지하면 리소스 생성 CI가 돌아갑니다.

```

앱팀: GitHub Issue 작성 (이슈 템플릿)
↓
[CI #1] 이슈 파싱 → Elice API 호출 → 매니페스트 PR 자동 생성 + `manifest-review` 라벨 부착
↓ (병렬)
인프라팀: 시크릿 값을 DM으로 수신 → OCI Vault에 등록 인프라팀: 생성된 PR 내용 검토
↓
인프라팀: manifest PR 머지
↓
[CI #2] OCI 초기 리소스 생성 (OCIR, IAM, Vault) + Route53 등록

```

#### `.github/ISSUE_TEMPLATE/oci-onboarding.yml` — 이슈 템플릿

GitHub YAML form 방식으로 구성해 CI에서 파싱하기 쉽게 합니다.
템플릿 자체에 `labels: [onboarding]`을 선언해 이슈 생성 시 자동으로 라벨이 붙도록 합니다.
CI #1은 이 라벨 유무를 확인해 온보딩 이슈가 아닌 일반 이슈에서는 동작하지 않습니다.

수집해야 할 항목:

| 필드 | 비고 |
|---|---|
| `team` | 서비스 영문명 소문자 kebab-case (예: `my-service`) |
| `repo_name` | GitHub 레포 이름 (예: `my-service-server`) — URL은 `https://github.com/wafflestudio/{repo_name}`으로 자동 조합 |
| `prod_domain` | prod 도메인 (예: `my-service-api.wafflestudio.com`) |
| `dev_domain` | dev 도메인 (예: `my-service-api-dev.wafflestudio.com`) |
| `image_name` | OCIR 이미지 이름 (예: `my-service-prod/my-service-server`) |
| `use_valkey` | Valkey 사용 여부 (`Yes` / `No`) — `Yes`이면 `{team}-valkey.yaml` 생성 |
| `secret_keys` | 환경변수 키 목록 (**값은 인프라팀 DM으로 전달**) |
| `db_name_prod` | Prod DB 이름 — CI #2 MySQL 생성용, 매니페스트에는 미포함 |
| `db_name_dev` | Dev DB 이름 — CI #2 MySQL 생성용, 매니페스트에는 미포함 |

> 프레임워크·포트·헬스체크 경로는 CI #1에서 `repo_url` 레포를 클론해 코드에서 자동 파악합니다.
> 시크릿 **값**은 이슈에 작성하지 않습니다. 인프라팀이 DM으로 받아 Vault에 별도 등록합니다.

#### `.github/prompts/manifest-generation.md` — 시스템 프롬프트

CI가 Elice API를 호출할 때 넘기는 프롬프트 파일입니다.

구성:
1. **역할 지시 및 온보딩 규칙**: Kubernetes 매니페스트 생성 전문가, 규칙·주의사항 전체 포함
2. **Few-shot 예시**: 기존 서비스 파일 1~2개 (예: `argocd/airbnb-prod/`, `argocd/moiming-prod/`)
4. **출력 형식 지정**:
```

--- FILE: argocd/{team}-prod/app.yaml ---
(내용)
--- FILE: argocd/{team}-dev/app.yaml ---
(내용)
...

````
5. **이슈 내용 주입**: 파싱된 이슈 데이터 (JSON)
6. **주의사항**:
- dev/prod namespace, name, domain 반드시 구분
- `nodeSelector: kubernetes.io/arch: arm64` 필수
- `resources.limits.cpu` 일반 서버에는 지정하지 않음
- `revisionHistoryLimit: 4` 설정
- 시크릿 키 이름이 있으면 `{team}-secret.yaml` 생성 (값은 placeholder)
- `use_valkey: Yes`이면 dev/prod 양쪽에 `{team}-valkey.yaml` 생성 (StatefulSet + ClusterIP Service, `sidecar.istio.io/inject: "false"` 어노테이션 필수)
- prod VirtualService에 `X-Forwarded-Proto: "https"` 헤더 포함

#### `.github/workflows/generate-manifest.yml` — CI #1 워크플로

트리거: 이슈가 열릴 때 (`opened`), `onboarding` 라벨이 있는 이슈에만 동작

```yaml
on:
issues:
 types: [opened]
jobs:
generate:
 if: contains(github.event.issue.labels.*.name, 'onboarding')
 steps:
   - uses: actions/checkout@v4
   - name: Generate manifests and create PR
     run: python scripts/generate-manifest.py
     env:
       ISSUE_BODY: ${{ github.event.issue.body }}
       ISSUE_NUMBER: ${{ github.event.issue.number }}
       ELICE_API_KEY: ${{ secrets.ELICE_API_KEY }}
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
# 스크립트 내에서 PR 생성 시 `manifest-review` 라벨 자동 부착
````

#### `.github/workflows/provision-resources.yml` — CI #2 워크플로

트리거: `manifest-review` 라벨이 붙은 PR이 main에 머지될 때

```yaml
on:
  pull_request:
    types: [closed]
    branches: [main]
jobs:
  provision:
    if: |
      github.event.pull_request.merged == true &&
      contains(github.event.pull_request.labels.*.name, 'manifest-review')
    steps:
      - uses: actions/checkout@v4
      - name: Provision OCI resources
        run: bash scripts/oci/provision.sh
        env:
          OCI_CLI_USER: ${{ secrets.OCI_CLI_USER }}
          OCI_CLI_FINGERPRINT: ${{ secrets.OCI_CLI_FINGERPRINT }}
          OCI_CLI_KEY_CONTENT: ${{ secrets.OCI_CLI_KEY_CONTENT }}
      - name: Register Route53 DNS
        run: bash scripts/aws/register-dns.sh
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  # PR에 포함된 team 이름은 변경된 파일 경로(argocd/{team}-prod/)에서 파싱
```

#### `scripts/generate-manifest.py` — API 호출 스크립트

순서:

1. `ISSUE_BODY` 파싱 (GitHub form YAML → dict)
2. `repo_url` 레포 클론 → 주요 파일 읽기 (`pom.xml`, `build.gradle`, `requirements.txt`, `package.json`, `application.yml` 등)으로 프레임워크·포트·헬스체크 경로 파악
3. `.github/prompts/manifest-generation.md` 읽기
4. Few-shot 예시 파일 읽기
5. Elice API 호출 (이슈 데이터 + 코드 분석 결과 포함)
6. 응답에서 `--- FILE: path ---` 구분자로 파일 분리
7. 브랜치 생성 + 파일 커밋 + PR 생성 (제목: `feat: onboard {team} to OCI`) + `manifest-review` 라벨 부착

---

### 2. OCI 초기 리소스 생성 자동화

manifest PR 머지 시 CI #2에서 순서대로 실행합니다.
스크립트는 `scripts/oci/` 하위에 분리하고, `scripts/oci/provision.sh`가 순서 제어합니다.

| 스크립트                         | 처리 내용                                           |
| -------------------------------- | --------------------------------------------------- |
| `scripts/oci/create-ocir.sh`     | OCIR 레포지토리 생성 (prod/dev 각각)                |
| `scripts/oci/create-iam.sh`      | IAM Group 생성 및 OCID 반환                         |
| `scripts/oci/register-secret.sh` | OCI Vault 시크릿 등록 (값은 GitHub Secret에서 주입) |
| `scripts/oci/create-mysql.sh`    | MySQL DB 생성 (필요한 경우)                         |

> OCI CLI (`oci` 커맨드) 사용. CI에 OCI 인증 설정 필요 (`OCI_CLI_USER`, `OCI_CLI_FINGERPRINT` 등).

---

### 3. AWS Route53 DNS 등록 자동화

`scripts/aws/register-dns.sh`로 분리하며, CI #2 (manifest PR 머지)에서 OCI 리소스 생성과 함께 실행합니다.

- OCI NLB Public IP 조회 → Route53 A 레코드 등록 (prod/dev 각각)
- AWS CLI 사용. CI에 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 필요.

---

### 4. GitHub 슬랙봇

- GitHub의 공식 Slack 앱으로 PR/이슈 알림은 대부분 커버 가능:
  `/github subscribe wafflestudio/waffle-world-oci`
- 담당자 자동 배정: `CODEOWNERS` + GitHub Actions으로 처리
  (`github.event.issue.created` 트리거 → 팀 룰에 따라 assignee 지정)

---

### 5. 용량 조정 배치

현재 배포된 서버의 실제 리소스 사용량을 점검하고, 과도하게 여유 있으면 PR을 자동 생성합니다.

```
Prometheus metrics API에서 실제 CPU/Memory 사용량 조회
    ↓
argocd/{team}-*/의 requests/limits와 비교
    ↓
n% 이하 사용 중이면 → manifest 수정 + PR 생성
```

구현:

- `scripts/capacity-check/check-capacity.py`
- GitHub Actions CronJob (월 2,000분 무료 내로 주 1회 또는 월 1회)
- `schedule: "0 2 * * 1"` (UTC 월요일 02:00)

---

## 주요 상수

| 항목                     | 값                                    |
| ------------------------ | ------------------------------------- |
| OCIR 레지스트리          | `yny.ocir.io`                         |
| OCI Tenancy OCID prefix  | `ax1dvc8vmenm`                        |
| 클러스터 아키텍처        | `arm64`                               |
| Argo CD URL              | `https://argocd-oci.wafflestudio.com` |
| 도메인 패턴 (prod)       | `{team}-api.wafflestudio.com`         |
| 도메인 패턴 (dev)        | `{team}-api-dev.wafflestudio.com`     |
| Vault ClusterSecretStore | `oci-vault`                           |
| Istio 게이트웨이         | `istio-ingress/waffle-ingressgateway` |

---

## 매니페스트 수정 시 주의사항

- `argocd/argocd/values.yaml`에 신규 팀 AppProject 추가 필요 (`extraObjects` 목록)
- `argocd/platform-rbac/resources.yaml`에 dev/prod 양쪽 RoleBinding 추가 필요
- `renovate.json`의 `kubernetes.managerFilePatterns`에 패턴 추가 필요
- `app.yaml`을 제외한 나머지 파일은 반드시 `{team}-`으로 시작해야 함
  (`include: '{team}-*.yaml'` 패턴으로 로드되기 때문)
- `resources.limits.cpu`는 일반 서버에 지정하지 않음 (CronJob만 예외)
