from __future__ import annotations

import json
import sys
from pathlib import Path


repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / 'src'))

from ustracker.versioning import sync_version


if __name__ == '__main__':
    print(json.dumps(sync_version(repo_root), ensure_ascii=False))
