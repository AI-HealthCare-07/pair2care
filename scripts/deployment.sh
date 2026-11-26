#!/bin/bash
set -eo pipefail

COLOR_GREEN=$(tput setaf 2)
COLOR_BLUE=$(tput setaf 4)
COLOR_RED=$(tput setaf 1)
COLOR_NC=$(tput sgr0)

cd "$(dirname "$0")/.."
source ./envs/.prod.env

# ---------- 도커 이미지 빌드 및 푸시 함수 ----------
build_and_push () {
  local docker_user=$1
  local docker_repo=$2
  local name=$3
  local tag=$4
  local dockerfile=$5
  local context=$6
  local tag_base=""

  if [[ "$name" == "FastAPI" ]]; then
    tag_base="app"
  else
    tag_base="ai"
  fi
  echo "${COLOR_BLUE}${name} Docker Image Build Start.${COLOR_NC}"
  docker build --platform linux/amd64 -t ${docker_user}/${docker_repo}:${tag_base}-${tag} -f ${dockerfile} ${context}

  echo "${COLOR_BLUE}${name} Docker Image Push Start.${COLOR_NC}"
  docker push ${docker_user}/${docker_repo}:${tag_base}-${tag}

  echo "${COLOR_GREEN}${name} Done.${COLOR_NC}"
  echo ""
}

# ---------- Docker login Prompt ----------
echo "${COLOR_BLUE}도커 유저네임과 비밀번호(PAT)을 입력해주세요.${COLOR_NC}"
read -p "username: " docker_user
read -p "password: " docker_pw
echo ""


# ---------- Docker Login ----------
echo "${COLOR_BLUE}Docker login${COLOR_NC}"
if ! docker login -u ${docker_user} -p ${docker_pw} ; then
  echo "${COLOR_RED}도커 로그인에 실패했습니다. 도커 유저네임과 비밀번호를 확인해주세요.${COLOR_NC}"
  exit 1
fi
echo "${COLOR_GREEN}도커 로그인 성공!${COLOR_NC}"
echo ""

# ---------- Docker Repository Input Prompt ----------
echo "${COLOR_BLUE}도커 이미지를 업로드할 레포지토리 이름을 입력해주세요.${COLOR_NC}"
read -p "Docker Repository Name: " docker_repo
echo ""

# ---------- Select Prompt ----------
echo "${COLOR_BLUE}배포 전 빌드 & 푸시할 이미지를 선택하세요(복수선택 가능, 띄어쓰기로 구분)${COLOR_NC}"
echo "1) fastapi"
echo "2) ai_worker"
echo "3) frontend (화면)"
read -p "선택 (예: 1 2): " selections
echo ""


# ---------- Docker Image Build & Push ----------
DEPLOY_SERVICES=()

for choice in $selections; do
  case $choice in
    1)
      echo "${COLOR_BLUE}FastAPI 앱의 배포 버젼을 입력하세요(ex. v1.0.0)${COLOR_NC}"
      read -p "FastAPI 앱 버젼: " fastapi_version
      build_and_push ${docker_user} ${docker_repo} "FastAPI" ${fastapi_version} "app/Dockerfile" "."
      # EC2 compose는 .env의 APP_VERSION 태그를 받으므로, 방금 올린 버전으로 맞춤 (안 맞추면 옛 이미지가 뜸)
      sed -i '' "s/^APP_VERSION=.*/APP_VERSION=${fastapi_version}/" envs/.prod.env
      DEPLOY_SERVICES+=("fastapi")
      ;;
    2)
      echo "${COLOR_BLUE}AI-worker 앱의 배포 버젼을 입력하세요(ex. v1.0.0)${COLOR_NC}"
      read -p "AI-worker 앱 버젼: " ai_version
      build_and_push ${docker_user} ${docker_repo} "AI Worker" ${ai_version} "ai_worker/Dockerfile" "."
      sed -i '' "s/^AI_WORKER_VERSION=.*/AI_WORKER_VERSION=${ai_version}/" envs/.prod.env
      DEPLOY_SERVICES+=("ai-worker")
      ;;
    3)
      # 프론트는 이미지 없이 빌드 결과(dist)를 EC2에 복사해서 nginx가 바로 서빙함
      echo "${COLOR_BLUE}Frontend Build Start.${COLOR_NC}"
      (cd frontend && npm ci && npm run build)
      DEPLOY_FRONTEND=true
      echo "${COLOR_GREEN}Frontend Done.${COLOR_NC}"
      ;;
    *)
      echo "${COLOR_RED}잘못된 선택입니다: $choice${COLOR_NC}"
      exit 1
      ;;
  esac
done

echo "${COLOR_GREEN}모든 선택된 이미지 빌드 & 푸시 완료! 🎉${COLOR_NC}"
echo "${COLOR_BLUE}배포 대상 서비스: ${DEPLOY_SERVICES[*]}${COLOR_NC}"
echo ""

# ---------- SSH 접속 정보 입력 prompt ----------
echo "${COLOR_BLUE}EC2 인스턴스 생성시 발급받은 ssh key 파일의 파일명을 입력하세요.(ex. ai_health_key.pem)${COLOR_NC}"
read -p "SSH 키 파일명: " ssh_key_file
echo ""

echo "${COLOR_BLUE}EC2 인스턴스의 IP를 입력하세요.${COLOR_NC}"
read -p "EC2-IP: " ec2_ip
echo ""

echo "${COLOR_BLUE}배포중인 서버의 https 여부를 선택하세요.${COLOR_NC}"
echo "1) http 사용중"
echo "2) https 사용중"
read -p "선택(ex. 1): " is_https
echo ""

# ---------- EC2 내에 배포 준비 파일 복사  ----------
# 첫 배포면 폴더가 없어서 scp가 실패함 → 먼저 만듦
ssh -i ~/.ssh/${ssh_key_file} ubuntu@${ec2_ip} "mkdir -p ~/project/nginx ~/project/frontend"
scp -i ~/.ssh/${ssh_key_file} envs/.prod.env ubuntu@${ec2_ip}:~/project/.env
scp -i ~/.ssh/${ssh_key_file} infra/docker/docker-compose.prod.yml ubuntu@${ec2_ip}:~/project/docker-compose.yml
# nginx 설정 복사본 (스크립트가 끝나면 지움)
nginx_conf=$(mktemp)
trap 'rm -f "${nginx_conf}"' EXIT
if [[ "$is_https" == "1" ]] ; then
  # ---------- prod_http.conf의 server_name을 IP로 바꾼 복사본을 보냄 ----------
  # 원본(git 추적 파일)을 직접 고치면 배포할 때마다 변경이 남아서 실수로 커밋될 수 있음 → 임시 파일에만 반영
  sed "s/server_name .*/server_name ${ec2_ip};/g" infra/nginx/prod_http.conf > "${nginx_conf}"
  scp -i ~/.ssh/${ssh_key_file} "${nginx_conf}" ubuntu@${ec2_ip}:~/project/nginx/default.conf
else
  echo "${COLOR_BLUE} 사용중인 도메인을 입력하세요. (ex. api.ozcoding.site)${COLOR_NC}"
  read -p "Domain: " domain
  # ---------- prod_https.conf의 server_name·인증서 경로를 도메인으로 바꾼 복사본을 보냄 (원본은 그대로) ----------
  sed -e "s/server_name .*/server_name ${domain};/g" \
      -e "s|/etc/letsencrypt/live/[^/]*|/etc/letsencrypt/live/${domain}|g" \
      infra/nginx/prod_https.conf > "${nginx_conf}"
  scp -i ~/.ssh/${ssh_key_file} "${nginx_conf}" ubuntu@${ec2_ip}:~/project/nginx/default.conf
fi

# ---------- 프론트 빌드 결과 복사 (3번 선택 시) ----------
if [[ "$DEPLOY_FRONTEND" == "true" ]] ; then
  # 폴더째 지우면 nginx 바인드 마운트가 지워진 옛 폴더를 계속 붙잡음 → 폴더는 두고 안의 파일만 비움
  ssh -i ~/.ssh/${ssh_key_file} ubuntu@${ec2_ip} "mkdir -p ~/project/frontend && find ~/project/frontend -mindepth 1 -delete"
  scp -i ~/.ssh/${ssh_key_file} -r frontend/dist/. ubuntu@${ec2_ip}:~/project/frontend/
fi

# ---------- EC2 배포 자동화  ----------
echo "${COLOR_BLUE}EC2 인스턴스에 SSH 접속을 시도합니다.${COLOR_NC}"
chmod 400 ~/.ssh/${ssh_key_file}
ssh -i ~/.ssh/${ssh_key_file} ubuntu@${ec2_ip} \
  "DOCKER_USERNAME=${docker_user} \
   DOCKER_PAT=${docker_pw} \
   DEPLOY_SERVICES='${DEPLOY_SERVICES[*]}' \
   bash -s" << 'EOF'
  set -e
  cd project

  echo "Docker login"
  docker login -u "$DOCKER_USERNAME" -p "$DOCKER_PAT"

  if [[ -z "$(docker compose ps -q)" ]]; then
    # 첫 배포(떠 있는 컨테이너 없음): mysql·redis까지 전부 띄움
    echo "First deploy: starting all services"
    docker compose up -d --pull always
  elif [[ -n "$DEPLOY_SERVICES" ]]; then
    echo "Deploying services: $DEPLOY_SERVICES"
    docker compose up -d --pull always --no-deps $DEPLOY_SERVICES
  fi

  # 새 마이그레이션 반영. 이미 다 적용됐으면 아무것도 안 해서 매번 돌려도 안전함
  echo "aerich upgrade"
  docker compose exec -T fastapi uv run --no-sync aerich upgrade

  # 새 nginx 설정·프론트 마운트를 반영하려고 nginx 컨테이너를 항상 다시 만듦 (몇 초 끊김)
  docker compose up -d --no-deps --force-recreate nginx

  docker image prune -af
EOF

echo "✅ Deployment finished."
