"""
KonaDB Storage Engine

Handles persistence of database state to .kona files (gzip-compressed JSON)
and provides atomic save/load operations.
"""

import gzip
import json
import os
import tempfile
import time

from kona.utils.logger import get_logger

logger = get_logger("kona.storage")


class StorageEngine:
    """
    JSON-based persistence layer for KonaDB.

    .kona files are gzip-compressed JSON containing all database state:
    tables, schemas, indexes, views, collections, and metadata.
    """

    def __init__(self, filepath=None, auto_save=True):
        """
        Initialize the storage engine.

        Args:
            filepath: Path to .kona file, or None for in-memory mode
            auto_save: If True, save to disk on every write operation
        """
        self.filepath = filepath
        self.auto_save = auto_save
        self.is_memory = filepath is None or filepath == ":memory:"

    def load(self):
        """
        Load database state from .kona file.

        Returns:
            dict with keys: tables, schemas, indexes, views,
            collections, metadata. Returns empty state if file
            doesn't exist.
        """
        empty_state = {
            "tables": {},
            "schemas": {},
            "indexes": {},
            "views": {},
            "collections": {},
            "auto_increments": {},
            "metadata": {
                "version": "1.0.0",
                "created_at": time.time(),
                "last_modified": time.time(),
            },
        }

        if self.is_memory:
            return empty_state

        if not os.path.exists(self.filepath):
            return empty_state

        # Handle empty files
        if os.path.getsize(self.filepath) == 0:
            return empty_state

        try:
            with gzip.open(self.filepath, "rt", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded database from %s", self.filepath)
            # Ensure all keys exist (backward compatibility)
            for key in empty_state:
                if key not in data:
                    data[key] = empty_state[key]
            return data
        except (gzip.BadGzipFile, json.JSONDecodeError):
            # Try reading as plain JSON (for debugging)
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key in empty_state:
                    if key not in data:
                        data[key] = empty_state[key]
                return data
            except Exception as e:
                logger.error("Failed to load database: %s", e)
                raise RuntimeError(f"Corrupted database file: {self.filepath}") from e

    def save(self, state):
        """
        Save database state to .kona file atomically.

        Uses temp file + rename for crash safety.

        Args:
            state: dict containing full database state
        """
        if self.is_memory:
            return

        state["metadata"]["last_modified"] = time.time()

        dir_name = os.path.dirname(os.path.abspath(self.filepath))
        os.makedirs(dir_name, exist_ok=True)

        try:
            # Write to temp file first for atomic operation
            fd, tmp_path = tempfile.mkstemp(
                dir=dir_name, suffix=".kona.tmp"
            )
            os.close(fd)  # Close the fd, we'll use the path
            try:
                with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
                    json.dump(state, f, default=str, ensure_ascii=False)
                # Atomic rename
                os.replace(tmp_path, self.filepath)
                logger.debug("Saved database to %s", self.filepath)
            except Exception:
                # Clean up temp file on failure
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as e:
            logger.error("Failed to save database: %s", e)
            raise

    def save_if_auto(self, state):
        """Save only if auto_save is enabled."""
        if self.auto_save:
            self.save(state)

    def export_json(self, data, filepath):
        """Export data to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    def import_json(self, filepath):
        """Import data from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def export_csv(self, rows, columns, filepath):
        """Export rows to a CSV file."""
        import csv

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col) for col in columns})

    def import_csv(self, filepath):
        """Import data from a CSV file. Returns (rows, columns)."""
        import csv

        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = list(reader)
        return rows, columns
