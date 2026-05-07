"""
Comprehensive test suite for KonaDB.
Covers DDL, DML, aggregations, joins, transactions,
document store, import/export, persistence, and utility commands.
"""

import json
import os
import tempfile
import pytest
import kona


@pytest.fixture
def conn():
    """Create an in-memory KonaDB connection for each test."""
    c = kona.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def populated_conn(conn):
    """Connection with pre-populated test data."""
    conn.execute("CREATE TABLE users (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL, email VARCHAR(255), age INT)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@example.com', 30)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Bob', 'bob@example.com', 25)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Carol', 'carol@example.com', 35)")
    conn.execute("CREATE TABLE orders (id INT PRIMARY KEY AUTO_INCREMENT, user_id INT, product VARCHAR(100), amount FLOAT)")
    conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (1, 'Widget', 9.99)")
    conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (1, 'Gadget', 24.99)")
    conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (2, 'Widget', 9.99)")
    conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (3, 'Thingamajig', 49.99)")
    return conn


# ===========================
# DDL Tests
# ===========================
class TestDDL:
    def test_create_table(self, conn):
        result = conn.execute("CREATE TABLE test (id INT PRIMARY KEY, name TEXT)")
        assert result[0]["status"] == "Table 'test' created"
        assert "test" in conn.tables

    def test_create_table_if_not_exists(self, conn):
        conn.execute("CREATE TABLE test (id INT)")
        result = conn.execute("CREATE TABLE IF NOT EXISTS test (id INT)")
        assert "already exists" in result[0]["status"]

    def test_create_table_duplicate_error(self, conn):
        conn.execute("CREATE TABLE test (id INT)")
        with pytest.raises(ValueError, match="already exists"):
            conn.execute("CREATE TABLE test (id INT)")

    def test_drop_table(self, conn):
        conn.execute("CREATE TABLE test (id INT)")
        result = conn.execute("DROP TABLE test")
        assert "dropped" in result[0]["status"]
        assert "test" not in conn.tables

    def test_drop_table_if_exists(self, conn):
        result = conn.execute("DROP TABLE IF EXISTS nonexistent")
        assert "does not exist" in result[0]["status"]

    def test_drop_table_error(self, conn):
        with pytest.raises(ValueError, match="does not exist"):
            conn.execute("DROP TABLE nonexistent")

    def test_alter_table_add_column(self, populated_conn):
        populated_conn.execute("ALTER TABLE users ADD COLUMN city VARCHAR(100)")
        desc = populated_conn.execute("DESCRIBE users")
        fields = [r["Field"] for r in desc]
        assert "city" in fields

    def test_alter_table_drop_column(self, populated_conn):
        populated_conn.execute("ALTER TABLE users DROP COLUMN email")
        desc = populated_conn.execute("DESCRIBE users")
        fields = [r["Field"] for r in desc]
        assert "email" not in fields

    def test_alter_table_modify_column(self, populated_conn):
        populated_conn.execute("ALTER TABLE users MODIFY COLUMN name TEXT")
        desc = populated_conn.execute("DESCRIBE users")
        for r in desc:
            if r["Field"] == "name":
                assert r["Type"] == "TEXT"

    def test_truncate_table(self, populated_conn):
        populated_conn.execute("TRUNCATE TABLE users")
        rows = populated_conn.execute("SELECT * FROM users")
        assert len(rows) == 0

    def test_rename_table(self, populated_conn):
        populated_conn.execute("RENAME TABLE users TO people")
        assert "people" in populated_conn.tables
        assert "users" not in populated_conn.tables
        rows = populated_conn.execute("SELECT * FROM people")
        assert len(rows) == 3


# ===========================
# DML Tests
# ===========================
class TestDML:
    def test_insert(self, conn):
        conn.execute("CREATE TABLE t (id INT, name TEXT)")
        conn.execute("INSERT INTO t (id, name) VALUES (1, 'test')")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1
        assert rows[0]["name"] == "test"

    def test_insert_multiple_rows(self, conn):
        conn.execute("CREATE TABLE t (id INT, name TEXT)")
        conn.execute("INSERT INTO t (id, name) VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 3

    def test_insert_auto_increment(self, populated_conn):
        populated_conn.execute("INSERT INTO users (name, email, age) VALUES ('Dave', 'dave@example.com', 40)")
        rows = populated_conn.execute("SELECT * FROM users WHERE name = 'Dave'")
        assert rows[0]["id"] == 4

    def test_insert_ignore(self, populated_conn):
        # Should not raise on duplicate primary key
        result = populated_conn.execute("INSERT IGNORE INTO users (id, name, email, age) VALUES (1, 'Dup', 'dup@example.com', 99)")
        assert "0 row(s) inserted" in result[0]["status"]

    def test_replace_into(self, conn):
        conn.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t (id, name) VALUES (1, 'old')")
        conn.execute("REPLACE INTO t (id, name) VALUES (1, 'new')")
        rows = conn.execute("SELECT * FROM t WHERE id = 1")
        assert rows[0]["name"] == "new"

    def test_update(self, populated_conn):
        populated_conn.execute("UPDATE users SET age = 31 WHERE name = 'Alice'")
        rows = populated_conn.execute("SELECT age FROM users WHERE name = 'Alice'")
        assert rows[0]["age"] == 31

    def test_update_multiple(self, populated_conn):
        populated_conn.execute("UPDATE users SET age = 99")
        rows = populated_conn.execute("SELECT * FROM users")
        assert all(r["age"] == 99 for r in rows)

    def test_delete(self, populated_conn):
        populated_conn.execute("DELETE FROM users WHERE name = 'Bob'")
        rows = populated_conn.execute("SELECT * FROM users")
        assert len(rows) == 2
        assert all(r["name"] != "Bob" for r in rows)

    def test_delete_all(self, populated_conn):
        populated_conn.execute("DELETE FROM users")
        rows = populated_conn.execute("SELECT * FROM users")
        assert len(rows) == 0


# ===========================
# SELECT Tests
# ===========================
class TestSelect:
    def test_select_all(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users")
        assert len(rows) == 3

    def test_select_columns(self, populated_conn):
        rows = populated_conn.execute("SELECT name, age FROM users")
        assert "name" in rows[0]
        assert "age" in rows[0]
        assert "email" not in rows[0]

    def test_select_where(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE age > 28")
        assert len(rows) == 2

    def test_select_where_and(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE age > 28 AND name = 'Alice'")
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_select_where_or(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE name = 'Alice' OR name = 'Bob'")
        assert len(rows) == 2

    def test_select_where_like(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE name LIKE 'A%'")
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_select_where_in(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE age IN (25, 35)")
        assert len(rows) == 2

    def test_select_where_between(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users WHERE age BETWEEN 26 AND 34")
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_select_where_is_null(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        conn.execute("INSERT INTO t (id, val) VALUES (2, 'x')")
        rows = conn.execute("SELECT * FROM t WHERE val IS NULL")
        assert len(rows) == 1
        assert rows[0]["id"] == 1

    def test_select_where_is_not_null(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        conn.execute("INSERT INTO t (id, val) VALUES (2, 'x')")
        rows = conn.execute("SELECT * FROM t WHERE val IS NOT NULL")
        assert len(rows) == 1
        assert rows[0]["id"] == 2

    def test_select_order_by_asc(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users ORDER BY age ASC")
        ages = [r["age"] for r in rows]
        assert ages == [25, 30, 35]

    def test_select_order_by_desc(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users ORDER BY age DESC")
        ages = [r["age"] for r in rows]
        assert ages == [35, 30, 25]

    def test_select_limit(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users LIMIT 2")
        assert len(rows) == 2

    def test_select_limit_offset(self, populated_conn):
        rows = populated_conn.execute("SELECT * FROM users ORDER BY id LIMIT 2 OFFSET 1")
        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"

    def test_select_distinct(self, conn):
        conn.execute("CREATE TABLE t (category TEXT)")
        conn.execute("INSERT INTO t VALUES ('A'), ('B'), ('A'), ('C'), ('B')")
        rows = conn.execute("SELECT DISTINCT category FROM t")
        assert len(rows) == 3

    def test_select_alias(self, populated_conn):
        rows = populated_conn.execute("SELECT name AS user_name FROM users")
        assert "user_name" in rows[0]

    def test_select_expression(self, conn):
        rows = conn.execute("SELECT 1 + 2 AS result")
        assert rows[0]["result"] == 3.0

    def test_select_no_from(self, conn):
        rows = conn.execute("SELECT NOW() AS current_time")
        assert "current_time" in rows[0]


# ===========================
# JOIN Tests
# ===========================
class TestJoins:
    def test_inner_join(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT users.name, orders.product FROM users "
            "INNER JOIN orders ON users.id = orders.user_id"
        )
        assert len(rows) == 4

    def test_left_join(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT users.name, orders.product FROM users "
            "LEFT JOIN orders ON users.id = orders.user_id"
        )
        assert len(rows) >= 3  # At least one row per user

    def test_cross_join(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT users.name, orders.product FROM users CROSS JOIN orders"
        )
        assert len(rows) == 12  # 3 users * 4 orders

    def test_join_with_alias(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT u.name, o.product FROM users u "
            "JOIN orders o ON u.id = o.user_id"
        )
        assert len(rows) == 4


# ===========================
# Aggregation Tests
# ===========================
class TestAggregations:
    def test_count(self, populated_conn):
        rows = populated_conn.execute("SELECT COUNT(*) AS cnt FROM users")
        assert rows[0]["cnt"] == 3

    def test_sum(self, populated_conn):
        rows = populated_conn.execute("SELECT SUM(age) AS total FROM users")
        assert rows[0]["total"] == 90.0

    def test_avg(self, populated_conn):
        rows = populated_conn.execute("SELECT AVG(age) AS avg_age FROM users")
        assert rows[0]["avg_age"] == 30.0

    def test_min_max(self, populated_conn):
        rows = populated_conn.execute("SELECT MIN(age) AS youngest, MAX(age) AS oldest FROM users")
        assert rows[0]["youngest"] == 25
        assert rows[0]["oldest"] == 35

    def test_group_by(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id"
        )
        assert len(rows) == 3
        for r in rows:
            if r["user_id"] == 1:
                assert r["order_count"] == 2

    def test_group_by_having(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT user_id, COUNT(*) AS cnt FROM orders GROUP BY user_id HAVING cnt > 1"
        )
        assert len(rows) == 1
        assert rows[0]["user_id"] == 1


# ===========================
# Transaction Tests
# ===========================
class TestTransactions:
    def test_commit(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("START TRANSACTION")
        conn.execute("INSERT INTO t (id, val) VALUES (1, 'test')")
        conn.execute("COMMIT")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1

    def test_rollback(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id, val) VALUES (1, 'original')")
        conn.execute("START TRANSACTION")
        conn.execute("INSERT INTO t (id, val) VALUES (2, 'rollback_me')")
        conn.execute("ROLLBACK")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1
        assert rows[0]["val"] == "original"

    def test_context_manager_commit(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        with conn.transaction():
            conn.execute("INSERT INTO t (id, val) VALUES (1, 'ctx')")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1

    def test_context_manager_rollback(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id, val) VALUES (1, 'keep')")
        try:
            with conn.transaction():
                conn.execute("INSERT INTO t (id, val) VALUES (2, 'discard')")
                raise ValueError("Intentional error")
        except ValueError:
            pass
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1


# ===========================
# Constraint Tests
# ===========================
class TestConstraints:
    def test_not_null(self, conn):
        conn.execute("CREATE TABLE t (id INT, name TEXT NOT NULL)")
        with pytest.raises(ValueError, match="cannot be NULL"):
            conn.execute("INSERT INTO t (id) VALUES (1)")

    def test_unique(self, conn):
        conn.execute("CREATE TABLE t (id INT, email TEXT UNIQUE)")
        conn.execute("INSERT INTO t (id, email) VALUES (1, 'a@b.com')")
        with pytest.raises(ValueError, match="Duplicate"):
            conn.execute("INSERT INTO t (id, email) VALUES (2, 'a@b.com')")

    def test_primary_key_unique(self, conn):
        conn.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t (id, name) VALUES (1, 'a')")
        with pytest.raises(ValueError, match="Duplicate"):
            conn.execute("INSERT INTO t (id, name) VALUES (1, 'b')")

    def test_default_value(self, conn):
        conn.execute("CREATE TABLE t (id INT, status TEXT DEFAULT 'active')")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        rows = conn.execute("SELECT * FROM t")
        assert rows[0]["status"] == "active"

    def test_auto_increment(self, conn):
        conn.execute("CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT, name TEXT)")
        conn.execute("INSERT INTO t (name) VALUES ('a')")
        conn.execute("INSERT INTO t (name) VALUES ('b')")
        rows = conn.execute("SELECT * FROM t ORDER BY id")
        assert rows[0]["id"] == 1
        assert rows[1]["id"] == 2


# ===========================
# Document Store Tests
# ===========================
class TestDocumentStore:
    def test_create_collection(self, conn):
        conn.create_collection("logs")
        assert "logs" in conn.list_collections()

    def test_insert_document(self, conn):
        conn.create_collection("logs")
        doc_id = conn.insert_document("logs", {"level": "info", "msg": "started"})
        assert doc_id is not None

    def test_find_documents(self, conn):
        conn.create_collection("logs")
        conn.insert_document("logs", {"level": "info", "msg": "started"})
        conn.insert_document("logs", {"level": "error", "msg": "failed"})
        conn.insert_document("logs", {"level": "info", "msg": "resumed"})
        results = conn.find_documents("logs", {"level": "info"})
        assert len(results) == 2

    def test_update_documents(self, conn):
        conn.create_collection("items")
        conn.insert_document("items", {"name": "widget", "count": 5})
        conn.update_documents("items", {"name": "widget"}, {"$inc": {"count": 3}})
        docs = conn.find_documents("items", {"name": "widget"})
        assert docs[0]["count"] == 8

    def test_delete_documents(self, conn):
        conn.create_collection("items")
        conn.insert_document("items", {"name": "a"})
        conn.insert_document("items", {"name": "b"})
        deleted = conn.delete_documents("items", {"name": "a"})
        assert deleted == 1
        assert conn.count_documents("items") == 1

    def test_document_query_operators(self, conn):
        conn.create_collection("data")
        conn.insert_document("data", {"val": 10})
        conn.insert_document("data", {"val": 20})
        conn.insert_document("data", {"val": 30})
        results = conn.find_documents("data", {"val": {"$gt": 15}})
        assert len(results) == 2

    def test_drop_collection(self, conn):
        conn.create_collection("temp")
        conn.drop_collection("temp")
        assert "temp" not in conn.list_collections()


# ===========================
# Import/Export Tests
# ===========================
class TestImportExport:
    def test_csv_roundtrip(self, populated_conn):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
        try:
            populated_conn.export_csv("users", csv_path)
            conn2 = kona.connect(":memory:")
            conn2.import_csv("imported_users", csv_path)
            rows = conn2.execute("SELECT * FROM imported_users")
            assert len(rows) == 3
            conn2.close()
        finally:
            os.unlink(csv_path)

    def test_json_roundtrip(self, populated_conn):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = f.name
        try:
            populated_conn.export_json("users", json_path)
            conn2 = kona.connect(":memory:")
            conn2.import_json("imported_users", json_path)
            rows = conn2.execute("SELECT * FROM imported_users")
            assert len(rows) == 3
            conn2.close()
        finally:
            os.unlink(json_path)


# ===========================
# Persistence Tests
# ===========================
class TestPersistence:
    def test_save_and_reload(self):
        with tempfile.NamedTemporaryFile(suffix='.kona', delete=False) as f:
            db_path = f.name
        try:
            conn1 = kona.connect(db_path)
            conn1.execute("CREATE TABLE items (id INT PRIMARY KEY, name TEXT)")
            conn1.execute("INSERT INTO items (id, name) VALUES (1, 'test')")
            conn1.close()

            conn2 = kona.connect(db_path)
            rows = conn2.execute("SELECT * FROM items")
            assert len(rows) == 1
            assert rows[0]["name"] == "test"
            conn2.close()
        finally:
            os.unlink(db_path)

    def test_memory_mode(self):
        conn = kona.connect(":memory:")
        conn.execute("CREATE TABLE t (id INT)")
        conn.execute("INSERT INTO t VALUES (1)")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1
        conn.close()


# ===========================
# Index Tests
# ===========================
class TestIndexes:
    def test_create_index(self, populated_conn):
        result = populated_conn.execute("CREATE INDEX idx_name ON users (name)")
        assert "created" in result[0]["status"]

    def test_create_unique_index(self, populated_conn):
        result = populated_conn.execute("CREATE UNIQUE INDEX idx_email ON users (email)")
        assert "created" in result[0]["status"]

    def test_drop_index(self, populated_conn):
        populated_conn.execute("CREATE INDEX idx_name ON users (name)")
        result = populated_conn.execute("DROP INDEX idx_name ON users")
        assert "dropped" in result[0]["status"]

    def test_show_indexes(self, populated_conn):
        populated_conn.execute("CREATE INDEX idx_age ON users (age)")
        rows = populated_conn.execute("SHOW INDEXES FROM users")
        idx_names = [r["Key_name"] for r in rows]
        assert "idx_age" in idx_names


# ===========================
# View Tests
# ===========================
class TestViews:
    def test_create_view(self, populated_conn):
        result = populated_conn.execute("CREATE VIEW adult_users AS SELECT * FROM users WHERE age >= 30")
        assert "created" in result[0]["status"]

    def test_select_from_view(self, populated_conn):
        populated_conn.execute("CREATE VIEW adult_users AS SELECT * FROM users WHERE age >= 30")
        rows = populated_conn.execute("SELECT * FROM adult_users")
        assert len(rows) == 2

    def test_drop_view(self, populated_conn):
        populated_conn.execute("CREATE VIEW v AS SELECT * FROM users")
        result = populated_conn.execute("DROP VIEW v")
        assert "dropped" in result[0]["status"]


# ===========================
# Utility SQL Tests
# ===========================
class TestUtilitySQL:
    def test_show_tables(self, populated_conn):
        rows = populated_conn.execute("SHOW TABLES")
        table_names = [r["table_name"] for r in rows]
        assert "users" in table_names
        assert "orders" in table_names

    def test_describe(self, populated_conn):
        rows = populated_conn.execute("DESCRIBE users")
        fields = [r["Field"] for r in rows]
        assert "id" in fields
        assert "name" in fields

    def test_show_columns(self, populated_conn):
        rows = populated_conn.execute("SHOW COLUMNS FROM users")
        fields = [r["Field"] for r in rows]
        assert "email" in fields

    def test_show_create_table(self, populated_conn):
        rows = populated_conn.execute("SHOW CREATE TABLE users")
        assert "CREATE TABLE" in rows[0]["Create Table"]

    def test_explain(self, populated_conn):
        rows = populated_conn.execute("EXPLAIN SELECT * FROM users WHERE id = 1")
        assert rows[0]["table"] == "users"
        assert rows[0]["rows"] == 3


# ===========================
# Function Tests
# ===========================
class TestFunctions:
    def test_upper(self, populated_conn):
        rows = populated_conn.execute("SELECT UPPER(name) AS uname FROM users WHERE name = 'Alice'")
        assert rows[0]["uname"] == "ALICE"

    def test_lower(self, populated_conn):
        rows = populated_conn.execute("SELECT LOWER(name) AS lname FROM users WHERE name = 'Alice'")
        assert rows[0]["lname"] == "alice"

    def test_length(self, populated_conn):
        rows = populated_conn.execute("SELECT LENGTH(name) AS len FROM users WHERE name = 'Alice'")
        assert rows[0]["len"] == 5

    def test_concat(self, populated_conn):
        rows = populated_conn.execute("SELECT CONCAT(name, ' - ', email) AS full FROM users WHERE name = 'Alice'")
        assert rows[0]["full"] == "Alice - alice@example.com"

    def test_coalesce(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        rows = conn.execute("SELECT COALESCE(val, 'default') AS result FROM t")
        assert rows[0]["result"] == "default"

    def test_ifnull(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        rows = conn.execute("SELECT IFNULL(val, 'none') AS result FROM t")
        assert rows[0]["result"] == "none"

    def test_now(self, conn):
        rows = conn.execute("SELECT NOW() AS ts")
        assert rows[0]["ts"] is not None

    def test_trim(self, conn):
        conn.execute("CREATE TABLE t (val TEXT)")
        conn.execute("INSERT INTO t VALUES ('  hello  ')")
        rows = conn.execute("SELECT TRIM(val) AS trimmed FROM t")
        assert rows[0]["trimmed"] == "hello"


# ===========================
# Edge Cases
# ===========================
class TestEdgeCases:
    def test_empty_table(self, conn):
        conn.execute("CREATE TABLE t (id INT)")
        rows = conn.execute("SELECT * FROM t")
        assert rows == []

    def test_null_handling(self, conn):
        conn.execute("CREATE TABLE t (id INT, val TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        rows = conn.execute("SELECT * FROM t")
        assert rows[0]["val"] is None

    def test_boolean_values(self, conn):
        conn.execute("CREATE TABLE t (id INT, active BOOLEAN)")
        conn.execute("INSERT INTO t VALUES (1, TRUE)")
        conn.execute("INSERT INTO t VALUES (2, FALSE)")
        rows = conn.execute("SELECT * FROM t WHERE active = TRUE")
        assert len(rows) == 1

    def test_multiple_statements(self, conn):
        conn.execute("CREATE TABLE t (id INT)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.execute("INSERT INTO t VALUES (2)")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 2

    def test_fetchone(self, populated_conn):
        row = populated_conn.fetchone("SELECT * FROM users ORDER BY id LIMIT 1")
        assert row is not None
        assert row["name"] == "Alice"

    def test_case_expression(self, populated_conn):
        rows = populated_conn.execute(
            "SELECT name, CASE WHEN age >= 30 THEN 'senior' ELSE 'junior' END AS category FROM users"
        )
        for r in rows:
            if r["name"] == "Bob":
                assert r["category"] == "junior"
            elif r["name"] == "Carol":
                assert r["category"] == "senior"


# ===========================
# AI Feature Tests (skipped without API key)
# ===========================
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
class TestAIFeatures:
    def test_ask(self, populated_conn):
        result = populated_conn.ask("How many users are there?")
        assert "sql" in result

    def test_optimize(self, populated_conn):
        result = populated_conn.optimize("SELECT * FROM users WHERE name = 'Alice'")
        assert "recommendations" in result

    def test_design_schema(self, conn):
        result = conn.design_schema("A blog with posts, comments, and tags")
        assert "sql" in result

    def test_detect_anomalies(self, populated_conn):
        result = populated_conn.detect_anomalies("users")
        assert "findings" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
