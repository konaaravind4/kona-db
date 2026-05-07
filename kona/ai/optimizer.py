"""
KonaDB AI Optimizer

AI-powered features using Claude claude-opus-4-6 via the Anthropic Messages API.
Provides natural language querying, query optimization, schema design,
and data anomaly detection.
"""

import json
import os
import urllib.request
import urllib.error

from kona.utils.logger import get_logger

logger = get_logger("kona.ai")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-opus-4-6"
ANTHROPIC_VERSION = "2023-06-01"


class KonaAI:
    """AI features for KonaDB powered by Claude."""

    def __init__(self, db):
        self.db = db
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

    def _check_api_key(self):
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "AI features require a valid Anthropic API key. "
                "Set it with: export ANTHROPIC_API_KEY='your-key-here'"
            )

    def _get_schema_context(self):
        """Build a schema description for the AI context."""
        parts = []
        for table_name, schema in self.db.schemas.items():
            cols = []
            for col_name, col_info in schema.items():
                constraints = []
                for c in col_info.get("constraints", []):
                    if isinstance(c, tuple):
                        constraints.append(str(c[0]))
                    else:
                        constraints.append(c)
                cols.append(f"  {col_name} {col_info['type']} {' '.join(constraints)}".strip())
            row_count = len(self.db.tables.get(table_name, []))
            parts.append(f"TABLE {table_name} ({row_count} rows):\n" + "\n".join(cols))

        for coll_name in self.db.collections:
            doc_count = len(self.db.collections[coll_name])
            sample = self.db.collections[coll_name][:2] if self.db.collections[coll_name] else []
            parts.append(f"COLLECTION {coll_name} ({doc_count} documents):\n  Sample: {json.dumps(sample, default=str)[:500]}")

        if self.db.indexes:
            idx_parts = []
            for table, idxs in self.db.indexes.items():
                for idx_name, idx_info in idxs.items():
                    idx_parts.append(f"  INDEX {idx_name} ON {table}({', '.join(idx_info['columns'])})"
                                     + (" UNIQUE" if idx_info["unique"] else ""))
            if idx_parts:
                parts.append("INDEXES:\n" + "\n".join(idx_parts))

        return "\n\n".join(parts) if parts else "Database is empty."

    def _call_claude(self, system_prompt, user_message, max_tokens=2048):
        """Make a request to the Anthropic Messages API."""
        self._check_api_key()

        payload = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("content", [])
                text_parts = [c["text"] for c in content if c.get("type") == "text"]
                return "\n".join(text_parts)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            logger.error("Claude API error %d: %s", e.code, error_body)
            raise RuntimeError(f"Claude API error ({e.code}): {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to Claude API: {e.reason}") from e

    def ask(self, question):
        """
        Ask a natural language question about the database.

        Translates the question to SQL, executes it, and returns
        both the SQL and results in a readable format.
        """
        schema = self._get_schema_context()
        system = (
            "You are a SQL expert. Given the database schema below, translate the user's "
            "natural language question into a MySQL-compatible SQL query. Return ONLY the SQL "
            "query, no explanations. Use only tables and columns that exist in the schema.\n\n"
            f"DATABASE SCHEMA:\n{schema}"
        )

        sql = self._call_claude(system, question).strip()
        # Clean up markdown code blocks if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1]) if len(lines) > 2 else lines[0]
        sql = sql.strip("`").strip()

        try:
            results = self.db.execute(sql)
            return {
                "question": question,
                "sql": sql,
                "results": results,
                "row_count": len(results),
            }
        except Exception as e:
            return {
                "question": question,
                "sql": sql,
                "error": str(e),
            }

    def optimize(self, sql):
        """
        Analyze a SQL query and provide optimization recommendations.

        Returns suggestions for indexes, query rewrites, and performance tips.
        """
        schema = self._get_schema_context()
        system = (
            "You are a database optimization expert. Analyze the SQL query below and provide:\n"
            "1. Performance assessment\n"
            "2. Suggested indexes (as CREATE INDEX statements)\n"
            "3. Query rewrite suggestions if applicable\n"
            "4. General optimization tips\n\n"
            f"DATABASE SCHEMA:\n{schema}"
        )

        response = self._call_claude(system, f"Optimize this query:\n{sql}")
        return {
            "original_query": sql,
            "recommendations": response,
        }

    def design_schema(self, description):
        """
        Generate CREATE TABLE statements from a plain English description.

        Returns executable SQL statements for the described schema.
        """
        system = (
            "You are a database architect. Generate MySQL-compatible CREATE TABLE statements "
            "based on the user's description. Include appropriate:\n"
            "- Data types (INT, VARCHAR, TEXT, FLOAT, BOOLEAN, DATE, DATETIME, etc.)\n"
            "- Primary keys with AUTO_INCREMENT\n"
            "- Foreign key relationships\n"
            "- NOT NULL constraints where appropriate\n"
            "- Indexes for commonly queried columns\n"
            "- DEFAULT values where sensible\n\n"
            "Return ONLY the SQL statements, each ending with a semicolon."
        )

        response = self._call_claude(system, description)
        # Clean markdown
        if "```" in response:
            lines = response.split("\n")
            sql_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block or not line.strip().startswith("```"):
                    sql_lines.append(line)
            response = "\n".join(sql_lines)

        return {
            "description": description,
            "sql": response.strip(),
        }

    def detect_anomalies(self, table):
        """
        Detect data quality issues and anomalies in a table.

        Samples data and uses AI to identify potential problems.
        """
        table = table.lower()
        if table not in self.db.tables:
            raise ValueError(f"Table '{table}' does not exist")

        schema = self._get_schema_context()
        rows = self.db.tables[table]
        sample = rows[:50]
        sample_json = json.dumps(sample, default=str, indent=2)[:3000]

        system = (
            "You are a data quality expert. Analyze the sample data below and identify:\n"
            "1. Missing or NULL values in important fields\n"
            "2. Inconsistent data formats\n"
            "3. Outliers or suspicious values\n"
            "4. Duplicate or near-duplicate records\n"
            "5. Data type mismatches\n"
            "6. Referential integrity issues\n\n"
            "Provide specific examples and actionable recommendations.\n\n"
            f"DATABASE SCHEMA:\n{schema}"
        )

        response = self._call_claude(
            system,
            f"Analyze this data from table '{table}':\n{sample_json}"
        )

        return {
            "table": table,
            "rows_analyzed": len(sample),
            "total_rows": len(rows),
            "findings": response,
        }
