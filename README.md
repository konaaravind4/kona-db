# KonaDB 🔥

**A MySQL-compatible database engine for Python with AI-powered features.**

KonaDB is a lightweight, zero-dependency database engine that supports full MySQL SQL syntax, MongoDB-style document collections, ACID transactions, file-based persistence, and AI features powered by Claude.

[![CI](https://github.com/yourusername/kona-db/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/kona-db/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Full MySQL SQL** | CREATE, INSERT, SELECT, UPDATE, DELETE, JOINs, GROUP BY, subqueries, and more |
| **Document Store** | MongoDB-style JSON collections with query operators |
| **ACID Transactions** | Snapshot isolation with context manager support |
| **File Persistence** | `.kona` files (gzip-compressed JSON) with atomic writes |
| **AI Features** | Natural language queries, query optimization, schema design, anomaly detection |
| **Interactive CLI** | `kona mydb.kona` — full-featured REPL with tabular output |
| **Zero Dependencies** | Core engine has no external dependencies |
| **Import/Export** | CSV and JSON import/export |

---

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Python API

```python
import kona

# Connect to in-memory or file-based database
conn = kona.connect(":memory:")       # in-memory
conn = kona.connect("mydb.kona")     # persistent file

# Create tables
conn.execute("""
    CREATE TABLE users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(255) UNIQUE,
        age INT DEFAULT 0
    )
""")

# Insert data
conn.execute("INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@example.com', 30)")
conn.execute("INSERT INTO users (name, email, age) VALUES ('Bob', 'bob@example.com', 25)")

# Query data
rows = conn.execute("SELECT * FROM users WHERE age > 20 ORDER BY name")
print(rows)
# [{'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'age': 30},
#  {'id': 2, 'name': 'Bob', 'email': 'bob@example.com', 'age': 25}]

# Aggregations
rows = conn.execute("SELECT COUNT(*) AS total, AVG(age) AS avg_age FROM users")

conn.close()
```

### CLI Shell

```bash
kona mydb.kona
# or
python -m kona mydb.kona
```

```
╔═══════════════════════════════════════╗
║         KonaDB Shell v1.0.0          ║
║   MySQL-compatible Database Engine    ║
╚═══════════════════════════════════════╝

kona> CREATE TABLE items (id INT PRIMARY KEY, name TEXT);
Table 'items' created.

kona> INSERT INTO items VALUES (1, 'Widget'), (2, 'Gadget');
2 row(s) inserted.

kona> SELECT * FROM items;
+----+--------+
| id | name   |
+----+--------+
|  1 | Widget |
|  2 | Gadget |
+----+--------+
2 row(s) in set
```

---

## 📖 SQL Reference

### DDL (Data Definition Language)

```sql
-- Tables
CREATE TABLE table_name (col1 TYPE, col2 TYPE, ...);
CREATE TABLE IF NOT EXISTS table_name (...);
DROP TABLE table_name;
DROP TABLE IF EXISTS table_name;
ALTER TABLE table_name ADD COLUMN col TYPE;
ALTER TABLE table_name DROP COLUMN col;
ALTER TABLE table_name MODIFY COLUMN col NEW_TYPE;
TRUNCATE TABLE table_name;
RENAME TABLE old_name TO new_name;

-- Indexes
CREATE INDEX idx_name ON table_name (col1, col2);
CREATE UNIQUE INDEX idx_name ON table_name (col);
DROP INDEX idx_name ON table_name;

-- Views
CREATE VIEW view_name AS SELECT ...;
DROP VIEW view_name;
```

### Data Types

`INT`, `INTEGER`, `VARCHAR(N)`, `TEXT`, `FLOAT`, `DOUBLE`, `DECIMAL(M,N)`, `BOOLEAN`, `BOOL`, `DATE`, `DATETIME`, `TIMESTAMP`, `BLOB`, `JSON`

### Constraints

`PRIMARY KEY`, `AUTO_INCREMENT`, `NOT NULL`, `UNIQUE`, `DEFAULT value`, `FOREIGN KEY ... REFERENCES`, `CHECK (expr)`

### DML (Data Manipulation Language)

```sql
-- Insert
INSERT INTO table (col1, col2) VALUES (val1, val2);
INSERT INTO table (col1) VALUES (v1), (v2), (v3);
INSERT IGNORE INTO table ...;
REPLACE INTO table ...;

-- Select
SELECT * FROM table;
SELECT col1, col2 FROM table WHERE condition;
SELECT DISTINCT col FROM table;
SELECT col, COUNT(*) FROM table GROUP BY col HAVING COUNT(*) > 1;
SELECT * FROM table ORDER BY col DESC LIMIT 10 OFFSET 5;
SELECT a.col, b.col FROM a INNER JOIN b ON a.id = b.a_id;
SELECT a.col FROM a LEFT JOIN b ON a.id = b.a_id;

-- Update / Delete
UPDATE table SET col = value WHERE condition;
DELETE FROM table WHERE condition;
```

### Functions

| Function | Description |
|----------|-------------|
| `COUNT(*)`, `COUNT(col)` | Count rows |
| `SUM(col)`, `AVG(col)` | Sum / average |
| `MIN(col)`, `MAX(col)` | Min / max |
| `UPPER(str)`, `LOWER(str)` | Case conversion |
| `LENGTH(str)` | String length |
| `CONCAT(a, b, ...)` | Concatenation |
| `SUBSTRING(str, pos, len)` | Substring |
| `TRIM(str)` | Trim whitespace |
| `COALESCE(a, b, ...)` | First non-NULL |
| `IF(cond, true_val, false_val)` | Conditional |
| `IFNULL(val, default)` | NULL replacement |
| `NOW()` | Current timestamp |
| `CAST(expr AS TYPE)` | Type casting |

### Utility Commands

```sql
SHOW TABLES;
DESCRIBE table_name;
SHOW COLUMNS FROM table_name;
SHOW CREATE TABLE table_name;
SHOW INDEXES FROM table_name;
EXPLAIN SELECT ...;
```

### Transactions

```sql
START TRANSACTION;
-- ... operations ...
COMMIT;
-- or
ROLLBACK;
```

Python context manager:

```python
with conn.transaction():
    conn.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
    conn.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
# Auto-commits on success, auto-rolls back on exception
```

---

## 📦 Document Store

MongoDB-style schemaless document collections alongside relational tables.

```python
# Create collection
conn.create_collection("logs")

# Insert documents
conn.insert_document("logs", {"level": "info", "msg": "started"})
conn.insert_document("logs", {"level": "error", "msg": "connection failed"})

# Query with MongoDB operators
docs = conn.find_documents("logs", {"level": "error"})
docs = conn.find_documents("logs", {"level": {"$in": ["error", "warn"]}})
docs = conn.find_documents("logs", {"count": {"$gt": 5}})

# Update with operators
conn.update_documents("logs", {"level": "error"}, {"$set": {"resolved": True}}, multi=True)
conn.update_documents("logs", {"level": "info"}, {"$inc": {"count": 1}})

# Delete
conn.delete_documents("logs", {"level": "debug"})

# Count
count = conn.count_documents("logs", {"level": "error"})
```

### Query Operators

`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`, `$regex`, `$and`, `$or`, `$not`

### Update Operators

`$set`, `$unset`, `$inc`, `$push`

---

## 🤖 AI Features

Powered by Claude claude-opus-4-6. Set `ANTHROPIC_API_KEY` environment variable to enable.

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Natural Language → SQL

```python
result = conn.ask("What are the top 5 customers by total order value?")
print(result["sql"])      # Generated SQL query
print(result["results"])  # Query results
```

### Query Optimization

```python
result = conn.optimize("SELECT * FROM orders WHERE status = 'pending'")
print(result["recommendations"])  # Index suggestions, rewrite tips
```

### Schema Design

```python
result = conn.design_schema("An e-commerce platform with products, customers, orders, and reviews")
print(result["sql"])  # Generated CREATE TABLE statements
```

### Anomaly Detection

```python
result = conn.detect_anomalies("users")
print(result["findings"])  # Data quality issues and suggestions
```

### CLI AI Commands

```
kona> .ai ask How many users signed up last month?
kona> .ai optimize SELECT * FROM orders WHERE amount > 100
kona> .ai design A blog system with posts, comments, and tags
kona> .ai anomalies users
```

---

## 📁 Import/Export

```python
# CSV
conn.export_csv("users", "users.csv")
conn.import_csv("new_users", "users.csv")

# JSON
conn.export_json("users", "users.json")
conn.import_json("new_users", "users.json")

# JSON to document collection
conn.import_json("logs", "logs.json", as_collection=True)
conn.export_json("logs", "logs_export.json", from_collection=True)
```

---

## 🏗️ Architecture

```
kona/
├── __init__.py          # Public connect() API
├── __main__.py          # python -m kona entry point
├── cli.py               # Interactive shell
├── core/
│   ├── database.py      # KonaDB engine (tables, indexes, transactions)
│   └── connection.py    # KonaConnection user interface
├── query/
│   ├── tokenizer.py     # SQL tokenizer
│   └── parser.py        # Recursive descent SQL parser
├── ai/
│   └── optimizer.py     # Claude AI features
├── storage/
│   └── engine.py        # .kona file persistence
└── utils/
    └── logger.py        # Logging utility
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/test_kona.py -v

# Run specific test group
python -m pytest tests/test_kona.py::TestSelect -v
python -m pytest tests/test_kona.py::TestTransactions -v
```

Test coverage: DDL, DML, aggregations, JOINs, transactions, constraints, document store, import/export, persistence, utility SQL, functions, and edge cases.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
