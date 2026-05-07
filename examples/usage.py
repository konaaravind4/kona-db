"""
KonaDB — Comprehensive Usage Examples

Demonstrates SQL operations, document store, transactions,
import/export, persistence, and AI features.
"""

import os
import sys
import tempfile

# Add parent directory to path for development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kona


def main():
    print("=" * 60)
    print("  KonaDB — Comprehensive Usage Examples")
    print("=" * 60)

    # ─── 1. Connect to in-memory database ───
    print("\n▶ 1. Connecting to in-memory database...")
    conn = kona.connect(":memory:")
    print(f"  Connected! Version: {kona.__version__}")

    # ─── 2. Create Tables ───
    print("\n▶ 2. Creating tables with constraints...")
    conn.execute("""
        CREATE TABLE users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE,
            age INT DEFAULT 0,
            active BOOLEAN DEFAULT TRUE
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            product VARCHAR(200) NOT NULL,
            amount FLOAT NOT NULL,
            status VARCHAR(50) DEFAULT 'pending'
        )
    """)
    conn.execute("""
        CREATE TABLE categories (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT
        )
    """)
    print("  ✓ Created tables: users, orders, categories")

    # ─── 3. Insert Data ───
    print("\n▶ 3. Inserting data...")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Alice Johnson', 'alice@example.com', 30)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Bob Smith', 'bob@example.com', 25)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Carol White', 'carol@example.com', 35)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Dave Brown', 'dave@example.com', 28)")
    conn.execute("INSERT INTO users (name, email, age, active) VALUES ('Eve Davis', 'eve@example.com', 42, FALSE)")

    # Multiple rows in one INSERT
    conn.execute("""
        INSERT INTO orders (user_id, product, amount, status) VALUES
        (1, 'Laptop', 999.99, 'completed'),
        (1, 'Mouse', 29.99, 'completed'),
        (2, 'Keyboard', 79.99, 'pending'),
        (3, 'Monitor', 399.99, 'completed'),
        (3, 'Webcam', 69.99, 'shipped'),
        (4, 'Headphones', 149.99, 'pending'),
        (5, 'Desk Lamp', 39.99, 'completed')
    """)

    conn.execute("INSERT INTO categories (name, description) VALUES ('Electronics', 'Electronic devices and accessories')")
    conn.execute("INSERT INTO categories (name, description) VALUES ('Accessories', 'Computer accessories')")
    print("  ✓ Inserted 5 users, 7 orders, 2 categories")

    # ─── 4. SELECT Queries ───
    print("\n▶ 4. SELECT queries...")

    # Basic SELECT
    rows = conn.execute("SELECT * FROM users")
    print(f"  All users ({len(rows)} rows):")
    for r in rows:
        print(f"    {r['id']}. {r['name']} (age: {r['age']}, email: {r['email']})")

    # WHERE with conditions
    rows = conn.execute("SELECT name, age FROM users WHERE age >= 30 AND active = TRUE")
    print(f"\n  Active users age >= 30: {[r['name'] for r in rows]}")

    # LIKE
    rows = conn.execute("SELECT name FROM users WHERE email LIKE '%@example.com'")
    print(f"  Users with @example.com: {[r['name'] for r in rows]}")

    # IN
    rows = conn.execute("SELECT name FROM users WHERE age IN (25, 30, 42)")
    print(f"  Users aged 25, 30, or 42: {[r['name'] for r in rows]}")

    # BETWEEN
    rows = conn.execute("SELECT name, age FROM users WHERE age BETWEEN 26 AND 36")
    print(f"  Users aged 26-36: {[r['name'] for r in rows]}")

    # ORDER BY
    rows = conn.execute("SELECT name, age FROM users ORDER BY age DESC")
    print(f"  Users by age (desc): {[(r['name'], r['age']) for r in rows]}")

    # LIMIT / OFFSET
    rows = conn.execute("SELECT name FROM users ORDER BY id LIMIT 3 OFFSET 1")
    print(f"  Users (skip 1, take 3): {[r['name'] for r in rows]}")

    # DISTINCT
    rows = conn.execute("SELECT DISTINCT status FROM orders")
    print(f"  Unique order statuses: {[r['status'] for r in rows]}")

    # ─── 5. Aggregations ───
    print("\n▶ 5. Aggregations...")
    rows = conn.execute("SELECT COUNT(*) AS total_users FROM users")
    print(f"  Total users: {rows[0]['total_users']}")

    rows = conn.execute("SELECT AVG(age) AS avg_age, MIN(age) AS youngest, MAX(age) AS oldest FROM users")
    print(f"  Age stats: avg={rows[0]['avg_age']}, min={rows[0]['youngest']}, max={rows[0]['oldest']}")

    rows = conn.execute("SELECT SUM(amount) AS total_revenue FROM orders WHERE status = 'completed'")
    print(f"  Total revenue (completed): ${rows[0]['total_revenue']:.2f}")

    # GROUP BY
    rows = conn.execute("""
        SELECT user_id, COUNT(*) AS order_count, SUM(amount) AS total_spent
        FROM orders GROUP BY user_id
    """)
    print("  Orders by user:")
    for r in rows:
        print(f"    User {r['user_id']}: {r['order_count']} orders, ${r['total_spent']:.2f}")

    # GROUP BY with HAVING
    rows = conn.execute("""
        SELECT user_id, COUNT(*) AS cnt FROM orders
        GROUP BY user_id HAVING cnt >= 2
    """)
    print(f"  Users with 2+ orders: {[r['user_id'] for r in rows]}")

    # ─── 6. JOINs ───
    print("\n▶ 6. JOIN queries...")
    rows = conn.execute("""
        SELECT users.name, orders.product, orders.amount
        FROM users
        INNER JOIN orders ON users.id = orders.user_id
        ORDER BY orders.amount DESC
    """)
    print("  User orders (by amount DESC):")
    for r in rows:
        print(f"    {r['name']}: {r['product']} (${r['amount']})")

    # LEFT JOIN
    rows = conn.execute("""
        SELECT users.name, COUNT(orders.id) AS order_count
        FROM users
        LEFT JOIN orders ON users.id = orders.user_id
        GROUP BY users.name
    """)
    print("  Orders per user (LEFT JOIN):")
    for r in rows:
        print(f"    {r['name']}: {r['order_count']} orders")

    # ─── 7. Functions ───
    print("\n▶ 7. SQL Functions...")
    rows = conn.execute("SELECT UPPER(name) AS upper_name, LENGTH(name) AS name_len FROM users LIMIT 3")
    for r in rows:
        print(f"  {r['upper_name']} (length: {r['name_len']})")

    rows = conn.execute("SELECT CONCAT(name, ' <', email, '>') AS contact FROM users LIMIT 2")
    for r in rows:
        print(f"  {r['contact']}")

    rows = conn.execute("SELECT COALESCE(NULL, NULL, 'fallback') AS result")
    print(f"  COALESCE(NULL, NULL, 'fallback') = {rows[0]['result']}")

    rows = conn.execute("SELECT NOW() AS current_time")
    print(f"  NOW() = {rows[0]['current_time']}")

    # CASE expression
    rows = conn.execute("""
        SELECT name,
               CASE WHEN age >= 35 THEN 'senior'
                    WHEN age >= 28 THEN 'mid'
                    ELSE 'junior' END AS tier
        FROM users
    """)
    print("  User tiers:")
    for r in rows:
        print(f"    {r['name']}: {r['tier']}")

    # ─── 8. Transactions ───
    print("\n▶ 8. Transactions...")

    # Successful transaction
    with conn.transaction():
        conn.execute("UPDATE users SET age = 31 WHERE name = 'Alice Johnson'")
        conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (1, 'Tablet', 599.99)")
    rows = conn.execute("SELECT age FROM users WHERE name = 'Alice Johnson'")
    print(f"  After commit: Alice's age = {rows[0]['age']}")

    # Rolled-back transaction
    rows_before = conn.execute("SELECT COUNT(*) AS cnt FROM orders")
    try:
        with conn.transaction():
            conn.execute("INSERT INTO orders (user_id, product, amount) VALUES (99, 'Ghost', 0.01)")
            raise ValueError("Simulated error!")
    except ValueError:
        pass
    rows_after = conn.execute("SELECT COUNT(*) AS cnt FROM orders")
    print(f"  After rollback: orders count unchanged ({rows_before[0]['cnt']} → {rows_after[0]['cnt']})")

    # ─── 9. UPDATE & DELETE ───
    print("\n▶ 9. UPDATE & DELETE...")
    conn.execute("UPDATE users SET active = FALSE WHERE age < 28")
    conn.execute("DELETE FROM orders WHERE status = 'pending'")
    rows = conn.execute("SELECT COUNT(*) AS cnt FROM orders")
    print(f"  After deleting pending orders: {rows[0]['cnt']} orders remain")

    # ─── 10. DDL Operations ───
    print("\n▶ 10. DDL operations...")

    # ALTER TABLE
    conn.execute("ALTER TABLE users ADD COLUMN city VARCHAR(100) DEFAULT 'Unknown'")
    print("  ✓ Added 'city' column to users")

    # RENAME TABLE
    conn.execute("RENAME TABLE categories TO product_categories")
    print("  ✓ Renamed categories → product_categories")

    # CREATE INDEX
    conn.execute("CREATE INDEX idx_user_age ON users (age)")
    conn.execute("CREATE UNIQUE INDEX idx_user_email ON users (email)")
    print("  ✓ Created indexes on users")

    # Views
    conn.execute("CREATE VIEW active_users AS SELECT * FROM users WHERE active = TRUE")
    rows = conn.execute("SELECT name FROM active_users")
    print(f"  Active users (via view): {[r['name'] for r in rows]}")

    # Utility commands
    print("\n  SHOW TABLES:")
    for r in conn.execute("SHOW TABLES"):
        print(f"    - {r['table_name']}")

    print("\n  DESCRIBE users:")
    for r in conn.execute("DESCRIBE users"):
        print(f"    {r['Field']:15} {r['Type']:15} {r['Key']:5} {r['Extra']}")

    # ─── 11. Document Store ───
    print("\n▶ 11. Document Store (MongoDB-style)...")

    conn.create_collection("logs")
    conn.insert_document("logs", {"level": "info", "service": "api", "msg": "Server started", "ts": "2024-01-01T00:00:00"})
    conn.insert_document("logs", {"level": "error", "service": "api", "msg": "Connection timeout", "ts": "2024-01-01T00:05:00"})
    conn.insert_document("logs", {"level": "info", "service": "worker", "msg": "Job completed", "ts": "2024-01-01T00:10:00"})
    conn.insert_document("logs", {"level": "warn", "service": "api", "msg": "High latency", "ts": "2024-01-01T00:15:00"})
    print(f"  Inserted 4 log documents")

    # Query documents
    errors = conn.find_documents("logs", {"level": "error"})
    print(f"  Error logs: {len(errors)}")

    api_logs = conn.find_documents("logs", {"service": "api"})
    print(f"  API logs: {len(api_logs)}")

    # MongoDB-style operators
    recent = conn.find_documents("logs", {"level": {"$in": ["error", "warn"]}})
    print(f"  Error/Warn logs: {len(recent)}")

    # Update documents
    conn.update_documents("logs", {"level": "warn"}, {"$set": {"level": "warning"}}, multi=True)
    print("  ✓ Updated 'warn' → 'warning'")

    # Count
    count = conn.count_documents("logs")
    print(f"  Total documents: {count}")

    print(f"  Collections: {conn.list_collections()}")

    # ─── 12. Import/Export ───
    print("\n▶ 12. Import/Export...")
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
        csv_path = f.name
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
        json_path = f.name

    conn.export_csv("users", csv_path)
    print(f"  ✓ Exported users to CSV ({csv_path})")

    conn.export_json("orders", json_path)
    print(f"  ✓ Exported orders to JSON ({json_path})")

    # Re-import into new tables
    conn2 = kona.connect(":memory:")
    count = conn2.import_csv("imported_users", csv_path)
    print(f"  ✓ Imported {count} rows from CSV")

    count = conn2.import_json("imported_orders", json_path)
    print(f"  ✓ Imported {count} rows from JSON")
    conn2.close()

    os.unlink(csv_path)
    os.unlink(json_path)

    # ─── 13. Persistence ───
    print("\n▶ 13. Persistence (.kona file)...")
    with tempfile.NamedTemporaryFile(suffix='.kona', delete=False) as f:
        db_path = f.name

    # Save
    db1 = kona.connect(db_path)
    db1.execute("CREATE TABLE persist_test (id INT PRIMARY KEY, val TEXT)")
    db1.execute("INSERT INTO persist_test VALUES (1, 'persisted!')")
    db1.close()
    print(f"  ✓ Saved to {db_path}")

    # Reload
    db2 = kona.connect(db_path)
    rows = db2.execute("SELECT * FROM persist_test")
    print(f"  ✓ Reloaded: {rows}")
    db2.close()
    os.unlink(db_path)

    # ─── 14. AI Features (if API key available) ───
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\n▶ 14. AI Features (Claude claude-opus-4-6)...")

        result = conn.ask("How many active users are there?")
        print(f"  Ask: SQL = {result.get('sql')}")
        print(f"       Results = {result.get('results')}")

        result = conn.optimize("SELECT * FROM users WHERE age > 30")
        print(f"  Optimize: {result['recommendations'][:200]}...")

        result = conn.design_schema("An e-commerce system with products, customers, and reviews")
        print(f"  Schema design:\n{result['sql'][:300]}...")

        result = conn.detect_anomalies("users")
        print(f"  Anomalies: {result['findings'][:200]}...")
    else:
        print("\n▶ 14. AI Features — SKIPPED (set ANTHROPIC_API_KEY to enable)")

    # Cleanup
    conn.close()

    print("\n" + "=" * 60)
    print("  ✅ All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
