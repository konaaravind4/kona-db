"""
KonaDB Connection Interface

User-facing interface wrapping KonaDB engine with transaction context manager,
document store access, import/export, and AI feature integration.
"""

from contextlib import contextmanager

from kona.core.database import KonaDB
from kona.utils.logger import get_logger

logger = get_logger("kona.connection")


class KonaConnection:
    """
    High-level connection interface for KonaDB.

    Provides SQL execution, transaction management, document store access,
    import/export capabilities, and AI-powered features.
    """

    def __init__(self, database_path=None, auto_save=True):
        self._db = KonaDB(database_path, auto_save)
        self._closed = False
        self._ai = None

    def _check_open(self):
        if self._closed:
            raise RuntimeError("Connection is closed")

    # === SQL Execution ===
    def execute(self, sql, params=None):
        """Execute a SQL statement and return results."""
        self._check_open()
        return self._db.execute(sql, params)

    def executemany(self, sql, param_list):
        """Execute a SQL statement with multiple parameter sets."""
        self._check_open()
        results = []
        for params in param_list:
            results.extend(self._db.execute(sql, params))
        return results

    def fetchone(self, sql, params=None):
        """Execute and return first result row."""
        results = self.execute(sql, params)
        return results[0] if results else None

    def fetchall(self, sql, params=None):
        """Execute and return all result rows."""
        return self.execute(sql, params)

    # === Transaction Management ===
    @contextmanager
    def transaction(self):
        """Context manager for ACID transactions."""
        self._check_open()
        self._db.start_transaction()
        try:
            yield self
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def begin(self):
        """Start a transaction manually."""
        self._check_open()
        self._db.start_transaction()

    def commit(self):
        """Commit the current transaction."""
        self._check_open()
        self._db.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self._check_open()
        self._db.rollback()

    # === Document Store ===
    def create_collection(self, name):
        """Create a new document collection."""
        self._check_open()
        self._db.create_collection(name)

    def drop_collection(self, name):
        """Drop a document collection."""
        self._check_open()
        self._db.drop_collection(name)

    def insert_document(self, collection, doc):
        """Insert a document into a collection."""
        self._check_open()
        return self._db.insert_document(collection, doc)

    def insert_many_documents(self, collection, docs):
        """Insert multiple documents into a collection."""
        self._check_open()
        return self._db.insert_many_documents(collection, docs)

    def find_documents(self, collection, query=None, projection=None,
                       sort=None, limit=None, skip=None):
        """Query documents from a collection."""
        self._check_open()
        return self._db.find_documents(collection, query, projection, sort, limit, skip)

    def update_documents(self, collection, query, update, multi=False):
        """Update documents in a collection."""
        self._check_open()
        return self._db.update_documents(collection, query, update, multi)

    def delete_documents(self, collection, query, multi=True):
        """Delete documents from a collection."""
        self._check_open()
        return self._db.delete_documents(collection, query, multi)

    def list_collections(self):
        """List all document collections."""
        self._check_open()
        return self._db.list_collections()

    def count_documents(self, collection, query=None):
        """Count documents in a collection."""
        self._check_open()
        return self._db.count_documents(collection, query)

    # === Import/Export ===
    def import_csv(self, table, filepath):
        """Import CSV data into a table."""
        self._check_open()
        rows, columns = self._db.storage.import_csv(filepath)
        if table.lower() not in self._db.tables:
            # Auto-create table with TEXT columns
            col_defs = ", ".join(f"`{c}` TEXT" for c in columns)
            self._db.execute(f"CREATE TABLE IF NOT EXISTS `{table}` ({col_defs})")
        for row in rows:
            cols = ", ".join(f"`{c}`" for c in columns)
            vals = ", ".join(f"'{str(row.get(c, '')).replace(chr(39), chr(39)+chr(39))}'" for c in columns)
            self._db.execute(f"INSERT INTO `{table}` ({cols}) VALUES ({vals})")
        return len(rows)

    def export_csv(self, table, filepath):
        """Export table data to CSV."""
        self._check_open()
        table = table.lower()
        if table not in self._db.tables:
            raise ValueError(f"Table '{table}' does not exist")
        rows = self._db.tables[table]
        columns = list(self._db.schemas.get(table, {}).keys())
        if not columns and rows:
            columns = list(rows[0].keys())
        self._db.storage.export_csv(rows, columns, filepath)
        return len(rows)

    def import_json(self, table_or_collection, filepath, as_collection=False):
        """Import JSON data into a table or collection."""
        self._check_open()
        data = self._db.storage.import_json(filepath)
        if as_collection:
            if table_or_collection.lower() not in self._db.collections:
                self._db.create_collection(table_or_collection)
            if isinstance(data, list):
                return len(self._db.insert_many_documents(table_or_collection, data))
            else:
                self._db.insert_document(table_or_collection, data)
                return 1
        else:
            if not isinstance(data, list):
                data = [data]
            if not data:
                return 0
            if table_or_collection.lower() not in self._db.tables:
                columns = set()
                for row in data:
                    columns.update(row.keys())
                col_defs = ", ".join(f"`{c}` TEXT" for c in columns)
                self._db.execute(f"CREATE TABLE IF NOT EXISTS `{table_or_collection}` ({col_defs})")
            for row in data:
                cols = list(row.keys())
                col_str = ", ".join(f"`{c}`" for c in cols)
                val_str = ", ".join(
                    f"'{str(row[c]).replace(chr(39), chr(39)+chr(39))}'" if row[c] is not None else "NULL"
                    for c in cols
                )
                self._db.execute(f"INSERT INTO `{table_or_collection}` ({col_str}) VALUES ({val_str})")
            return len(data)

    def export_json(self, table_or_collection, filepath, from_collection=False):
        """Export table or collection data to JSON."""
        self._check_open()
        if from_collection:
            name = table_or_collection.lower()
            if name not in self._db.collections:
                raise ValueError(f"Collection '{name}' does not exist")
            data = self._db.collections[name]
        else:
            name = table_or_collection.lower()
            if name not in self._db.tables:
                raise ValueError(f"Table '{name}' does not exist")
            data = self._db.tables[name]
        self._db.storage.export_json(data, filepath)
        return len(data)

    # === AI Features ===
    def _get_ai(self):
        if self._ai is None:
            from kona.ai.optimizer import KonaAI
            self._ai = KonaAI(self._db)
        return self._ai

    def ask(self, question):
        """Ask a natural language question about the database."""
        self._check_open()
        return self._get_ai().ask(question)

    def optimize(self, sql):
        """Get optimization recommendations for a SQL query."""
        self._check_open()
        return self._get_ai().optimize(sql)

    def design_schema(self, description):
        """Generate schema from a plain English description."""
        self._check_open()
        return self._get_ai().design_schema(description)

    def detect_anomalies(self, table):
        """Detect data quality issues in a table."""
        self._check_open()
        return self._get_ai().detect_anomalies(table)

    # === Utility ===
    def save(self):
        """Manually save database to disk."""
        self._check_open()
        self._db.save()

    def close(self):
        """Close the connection and save."""
        if not self._closed:
            self._db.save()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @property
    def tables(self):
        """List all table names."""
        return list(self._db.tables.keys())

    @property
    def collections(self):
        """List all collection names."""
        return list(self._db.collections.keys())
