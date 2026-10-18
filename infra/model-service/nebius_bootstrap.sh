#!/usr/bin/env bash
# Start the model service on a Nebius Serverless endpoint without a custom image.
# Base image: pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime (same digest as the Dockerfile).
# The script fetches the service files from a pinned commit and checks each SHA-256.
# It then follows the Dockerfile steps: locked install, model download, uvicorn.
set -euo pipefail

export SERVICE_COMMIT="${SERVICE_COMMIT:-0199f1380a89b30089fbd735a518e6c9f1a05c29}"
export SERVICE_BASE="https://raw.githubusercontent.com/surmatt/nemotron-agentic-ai-challenge/${SERVICE_COMMIT}/infra/model-service"
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1

mkdir -p /service
cd /service
echo "Fetching service files from commit ${SERVICE_COMMIT}"
python - <<'PY'
import hashlib, os, urllib.request

FILES = {
    "app.py": "9112719813b04cf9a7cd211f4d45007c09819709fffc5330a95191669339033c",
    "backend.py": "5b4c14b31c068a6f8590f214db911765bf66aa5b3c58f9d93d1b0e725d76d9d0",
    "contracts.py": "7794d1949910f669bd1973d07a34791e1b5eb13f77e3996f7cec641d8af5ee29",
    "model_pins.py": "3f40b4a7662285596aef47710727ff8775718f65daf0b8bf7bf24969c452fe73",
    "download_models.py": "30248fd6f76d1e62359079c647c124b58ea58c3c95b3f9eb7c42c34922550967",
    "requirements.lock": "74d4df897f89c81c9ffd9126d577891b61107c0fa54f5f8e5d93bf49badd3e79",
}
for name, digest in FILES.items():
    data = urllib.request.urlopen(f"{os.environ['SERVICE_BASE']}/{name}", timeout=120).read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(f"{name}: SHA-256 differs from the pinned value")
    with open(name, "wb") as stream:
        stream.write(data)
    print(f"Verified {name}", flush=True)
PY

python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -c "import torch, torchvision, transformers; assert torch.__version__.split('+')[0] == '2.8.0'; assert torch.version.cuda == '12.8'; assert torchvision.__version__.split('+')[0] == '0.23.0'; assert transformers.__version__ == '4.56.2'; assert 'sm_120' in torch._C._cuda_getArchFlags().split(); print('CUDA package and sm_120 build checks passed')"
python download_models.py --destination /opt/models

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/huggingface \
  HF_MODULES_CACHE=/tmp/huggingface/modules MODEL_ROOT=/opt/models
exec python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 \
  --limit-concurrency 16 --timeout-keep-alive 5
