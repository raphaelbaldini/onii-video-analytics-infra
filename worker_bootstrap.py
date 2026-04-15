"""EC2 user-data and AMI defaults for video workers (stack-specific; not in pulumi-aws-modules)."""

# Default Amazon Linux 2 AMI lookup when neither worker_ami_id nor SSM parameter is set.
DEFAULT_WORKER_AMI_NAME_PATTERN = "amzn2-ami-hvm-*-x86_64-gp2"
DEFAULT_WORKER_AMI_OWNERS = ["amazon"]


def worker_user_data(prefix: str) -> str:
    """Bootstrap script for unified video worker nodes."""
    return f"""#!/bin/bash
set -euo pipefail
echo "Bootstrapping unified video worker node"
yum update -y
yum install -y python3 jq awscli
cat >/opt/video-worker-role.txt <<'EOF'
unified-stage-worker
EOF
# Placeholder for pulling and launching your analysis application.
# Example:
# aws s3 cp s3://{prefix}-artifacts/video-worker/latest/worker.tar.gz /tmp/worker.tar.gz
# tar -xzf /tmp/worker.tar.gz -C /opt/video-worker
# systemctl enable --now video-worker
"""
