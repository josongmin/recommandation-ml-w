#!/usr/bin/env bash
# Copy credentials from source profile to project .aws/credentials (wine-rec-dev)
set -e
PROFILE="${1:-default}"
AWS_DIR="$(cd "$(dirname "$0")/.." && pwd)/.aws"
CREDS="$AWS_DIR/credentials"

mkdir -p "$AWS_DIR"
ACCESS_KEY=$(aws configure get aws_access_key_id --profile "$PROFILE" 2>/dev/null) || { echo "No credentials for profile '$PROFILE'. Run: aws configure --profile $PROFILE"; exit 1; }
SECRET_KEY=$(aws configure get aws_secret_access_key --profile "$PROFILE" 2>/dev/null) || { echo "No secret for profile '$PROFILE'"; exit 1; }

cat > "$CREDS" << EOF
[wine-rec-dev]
aws_access_key_id = $ACCESS_KEY
aws_secret_access_key = $SECRET_KEY
EOF
chmod 600 "$CREDS"
echo "✓ Credentials copied from [$PROFILE] → .aws/credentials [wine-rec-dev]"
