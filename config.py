"""애플리케이션 실행 설정."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# 기본값은 프로젝트의 best.pt이며, 배포 환경에서는 WIND_MODEL_PATH로 교체할 수 있다.
MODEL_PATH = Path(
    os.getenv("WIND_MODEL_PATH", str(BASE_DIR / "best.pt"))
).expanduser().resolve()

