FROM python:3.13-slim

WORKDIR /app

# 1. uv 설치 (공식 이미지에서 복사해오는 가장 깔끔한 방법)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일을 컨테이너 내부에 복사합니다.
COPY pyproject.toml uv.lock ./

# 3. pyproject.toml에 명시된 의존성 패키지 중에서 'app' 그룹만 설치합니다.
RUN uv sync --group ai --no-dev --frozen

# 4. 로컬 소스 코드를 컨테이너 내부로 복사합니다.
# 패키지 이름(ai_worker)대로 복사해야 `from ai_worker...` import가 됨
COPY ./ai_worker ./ai_worker

# 5. 해당 이미지를 활용하여 도커컨테이너 실행시 실행되는 명령어입니다.
# Redis Stream 소비자(ai_worker/main.py)를 실행합니다. --no-sync는 app Dockerfile과 같은 이유
CMD ["uv", "run", "--no-sync", "python", "-m", "ai_worker.main"]
