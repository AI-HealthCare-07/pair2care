# 로컬 개발 환경 세팅 (팀원용)

> 공식 가이드(노션 Project Setup Guide)를 우리 레포 기준으로 줄인 문서. 11/16 팀장이 직접 해보고 막힌 점까지 정리함.  
> 템플릿 일반 설명은 [README.md](../README.md) 참고.

## 0. 준비물
- PyCharm: [jetbrains.com](https://www.jetbrains.com)에서 설치 (Apple Silicon 맥은 Apple Silicon 버전). OZ 라이선스 배부 전에는 30일 평가판으로 사용함
- Docker Desktop: 설치 후 실행해 둠
- uv: `brew install uv` 또는 `pip install uv`
- Git 설정과 GitHub 로그인

```bash
git config --global user.name "GitHub 아이디"
git config --global user.email "GitHub 가입 이메일"
gh auth login
```

## 1. 레포 받기
- 레포 권한은 org 멤버라 **초대 메일 없이 바로 추가됨**. https://github.com/AI-HealthCare-07/pair2care 가 열리면 됨
- 템플릿이 아니라 **우리 레포**를 clone함. remote 변경(가이드 2-5)은 필요 없음

```bash
git clone https://github.com/AI-HealthCare-07/pair2care.git ~/PycharmProjects/pair2care
```

- PyCharm → 열기 → `~/PycharmProjects/pair2care` → 프로젝트 신뢰

## 2. 의존성 설치

```bash
cd ~/PycharmProjects/pair2care
uv sync --all-groups --frozen
```

- 오른쪽 아래 인터프리터가 `.venv`로 잡혔는지 확인함
- 맥에 Python 3.14가 있으면 `.venv`가 3.14로 만들어질 수 있음. 템플릿·CI 기준은 3.13 (팀 통일 방법은 추후 정함)

## 3. env 파일 만들기

```bash
cp envs/example.local.env envs/.local.env
cp envs/example.prod.env envs/.prod.env
ln -s envs/.local.env .env
```

`envs/.local.env` 값 (로컬 전용, 각자 정해도 됨)

| 키 | 값 |
|---|---|
| `DOCKER_USER` | 본인 Docker Hub 아이디 (로컬에선 이미지 이름표일 뿐이라 아무거나 가능) |
| `DOCKER_REPOSITORY` | `pair2care` |
| `APP_VERSION` | `v0.1.0` |
| `AI_WORKER_VERSION` | `v0.1.0` (예시 값이 `v1.0.0`이라 안 바꾸고 넘어가기 쉬움) |
| `SECRET_KEY` | 아래 명령으로 만든 랜덤 문자열 |
| `COOKIE_DOMAIN` | `localhost` |
| `DB_HOST` | `mysql` |
| `DB_PORT`, `DB_EXPOSE_PORT` | `3306` |
| `DB_USER`, `DB_NAME` | `pair2care` |
| `DB_PASSWORD`, `DB_ROOT_PASSWORD` | 로컬용 비번, 서로 다르게. 실제 쓰는 비번 재사용 금지 |

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # SECRET_KEY용
python3 -c "import secrets; print(secrets.token_urlsafe(16))"  # DB 비번용
```

- `SECRET_KEY`는 FastAPI가 로그인 토큰(JWT)에 서명할 때 쓰는 값이라 직접 만듦. OZ가 주는 키는 Claude·OpenAI·CLOVA 같은 **외부 API 키**로 별개임
- `.env`, `envs/.local.env`, `envs/.prod.env`는 `.gitignore`에 들어 있음. 그래도 커밋 전 `git status`에 안 보이는지 확인함
- env 값은 깃·노션·디스코드에 올리지 않음

## 4. 실행

```bash
docker compose up --build -d
docker ps
```

- `nginx`, `fastapi` → Up / `mysql`, `redis` → Up (healthy) 이면 정상
- `ai-worker` → Restarting 반복은 **정상** (아직 워커 코드가 없음)
- 브라우저에서 http://localhost/api/docs 열리면 성공
- 끌 때: `docker compose down` (DB까지 지우려면 `-v`)

## 5. 자주 막히는 곳

| 증상 | 원인·해결 |
|---|---|
| mysql·redis 컨테이너가 안 뜸 (포트 사용 중) | 다른 프로젝트 컨테이너가 3306·6379를 잡고 있음. 다른 컨테이너면 `docker ps`로 찾아 `docker stop 이름` (kill 불필요). brew로 설치한 MySQL·Redis면 `brew services stop mysql` / `brew services stop redis` |
| DB 접속 실패 (비번 바꾼 뒤) | 첫 실행 때 비번이 DB 볼륨에 저장됨. `docker compose down -v` 후 다시 up (로컬 데이터 삭제됨) |
| 이미지 이름이 `ai-v1.0.0` | `AI_WORKER_VERSION`을 `v0.1.0`으로 고치고 다시 up |
| `uv sync`가 오래 걸림 | `ai` 그룹에 torch가 있어서 첫 설치가 김. 정상 |

## 6. 작업 시작 규칙 (요약)
- `develop`에서 `feature/기능명` 브랜치를 만들어 작업 → PR → 리뷰 1명 후 merge
- `main`, `develop`은 직접 push가 막혀 있음
- 자세한 규칙은 [CLAUDE.md](../CLAUDE.md)
