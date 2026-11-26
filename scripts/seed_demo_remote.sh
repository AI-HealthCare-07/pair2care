#!/bin/bash
# 배포 서버(EC2)에 데모 시드 넣기 (scripts/seed_demo.py, #140 리뷰 3번)
#
# 운영 이미지에는 scripts/가 없고 DB 포트도 닫혀 있어서, 그때만 컨테이너 안에 넣어 한 번 돌리고 지움.
#   1) 시드 파일을 EC2로 복사
#   2) fastapi 컨테이너에 docker compose cp로 넣음 (seed_demo_on_server.sh, EC2에서 실행)
#   3) 컨테이너 안에서 실행 (DB·설정은 컨테이너 것을 그대로 씀)
#   4) 컨테이너와 EC2에서 복사본 지움
#
# 실행 (레포 루트, 로컬 맥에서):
#   ./scripts/seed_demo_remote.sh
#
# - 비밀번호는 화면에 안 보이게 입력받고, ssh 표준 입력으로만 넘김 (명령줄·서버 기록에 안 남게)
# - 가상 데이터만 넣음. 날짜가 "오늘 기준 4주"라 데모 당일 아침에 돌리는 걸 추천
set -eo pipefail

COLOR_GREEN=$(tput setaf 2)
COLOR_BLUE=$(tput setaf 4)
COLOR_RED=$(tput setaf 1)
COLOR_NC=$(tput sgr0)

cd "$(dirname "$0")/.."

echo "${COLOR_BLUE}EC2 ssh 키 파일명을 입력하세요 (예: ai_health_key.pem)${COLOR_NC}"
read -r -p "SSH 키 파일명: " ssh_key_file
echo "${COLOR_BLUE}EC2 IP를 입력하세요${COLOR_NC}"
read -r -p "EC2-IP: " ec2_ip
echo "${COLOR_BLUE}데모 계정 비밀번호를 정하세요 (영문·숫자·특수문자 8자 이상, 화면에 안 보여요)${COLOR_NC}"
read -r -s -p "DEMO_PASSWORD: " demo_password
echo ""
if [[ -z "${demo_password}" ]]; then
  echo "${COLOR_RED}비밀번호가 비어 있어요.${COLOR_NC}"
  exit 1
fi

ssh_target="ubuntu@${ec2_ip}"
ssh_key=~/.ssh/${ssh_key_file}

echo "${COLOR_BLUE}1) 시드 파일을 EC2로 복사${COLOR_NC}"
ssh -i "${ssh_key}" "${ssh_target}" "mkdir -p ~/project/seed/scripts"
scp -i "${ssh_key}" scripts/__init__.py scripts/seed_demo.py "${ssh_target}":~/project/seed/scripts/
scp -i "${ssh_key}" scripts/seed_demo_on_server.sh "${ssh_target}":~/project/seed/

echo "${COLOR_BLUE}2~4) 컨테이너에 넣고 실행한 뒤 지움${COLOR_NC}"
# 비밀번호는 표준 입력으로만 넘김 (ssh 명령 문자열·서버 셸 기록에 안 남게)
ssh -i "${ssh_key}" "${ssh_target}" "bash ~/project/seed/seed_demo_on_server.sh" <<<"${demo_password}"

echo "${COLOR_GREEN}데모 시드 완료! demo@example.com 으로 로그인해 보세요.${COLOR_NC}"
