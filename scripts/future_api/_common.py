"""Tiện ích chung cho Phương án B. KHÔNG gọi mạng. Chỉ đọc cấu hình từ .env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path=ROOT / ".env"):
    """Đọc .env (KEY=VALUE) vào dict; không in giá trị key ra màn hình."""
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k in env})
    return env


def plan_b_not_enabled(name):
    raise SystemExit(
        f"{name}: Phương án B chưa được bật. Script này chỉ là khung TODO và không gọi API.\n"
        "Chỉ triển khai khi được yêu cầu rõ; tuân BUDGET_PER_EPISODE_USD và MAX_RETRIES_PER_SHOT."
    )
