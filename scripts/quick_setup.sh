#!/usr/bin/env bash
# Quick setup script for wine-rec project
set -e

echo "🚀 Wine-Rec 프로젝트 빠른 설정 시작..."
echo ""

# 1. Python 환경 체크
echo "1️⃣  Python 환경 확인..."
if ! command -v python &> /dev/null; then
    echo "❌ Python이 설치되어 있지 않습니다."
    exit 1
fi
echo "✓ Python: $(python --version)"

# 2. uv 체크
echo ""
echo "2️⃣  uv 확인..."
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv가 설치되어 있지 않습니다. 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "✓ uv: $(uv --version)"

# 3. 의존성 설치
echo ""
echo "3️⃣  의존성 설치..."
uv venv
uv pip install -e ".[all]"
echo "✓ 의존성 설치 완료"

# 4. AWS 설정
echo ""
echo "4️⃣  AWS 설정..."
if [ ! -f .aws/config ]; then
    echo "⚠️  AWS config가 없습니다. just aws-setup을 실행하세요."
else
    echo "✓ AWS config 존재"
fi

# 5. 데이터 생성
echo ""
echo "5️⃣  데이터 생성..."
just data-init

# 6. 완료
echo ""
echo "✅ 설정 완료!"
echo ""
echo "다음 명령어로 시작하세요:"
echo "  just serve       # API 서버 시작"
echo "  just test        # 테스트 실행"
echo "  just data-stats  # 데이터 통계 확인"
echo "  just status      # 전체 상태 확인"
