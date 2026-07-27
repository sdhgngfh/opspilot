from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver


def build_checkpointer(local_path: Path) -> tuple[BaseCheckpointSaver, sqlite3.Connection]:
    checkpoint_path = Path(local_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return saver, connection
