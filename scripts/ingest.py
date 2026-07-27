from __future__ import annotations

import json

from app.config import get_settings
from app.service import RAGService


def main() -> None:
    result = RAGService(get_settings()).reindex()
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

