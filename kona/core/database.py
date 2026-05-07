"""
KonaDB Database Engine

Central engine managing tables, schemas, indexes, views, transactions,
and document collections.
"""

import copy
import re
import time
import uuid
from collections import defaultdict

from kona.query.parser import (
    parse_sql, ParseError, Select, Insert, Update, Delete,
    CreateTable, DropTable, AlterTable, TruncateTable, RenameTable,
    CreateIndex, DropIndex, CreateView, DropView,
    ShowTables, DescribeTable, ShowColumns, ShowCreateTable, ShowIndexes,
    ExplainQuery, StartTransaction, Commit, Rollback,
    BinaryOp, UnaryOp, Literal, ColumnRef, FunctionCall, WildCard,
    SubQuery, InList, BetweenExpr, IsNull, ExistsExpr, CaseExpr,
    CastExpr, AliasedExpr, OrderByItem, JoinClause, Placeholder,
)
from kona.storage.engine import StorageEngine
from kona.utils.logger import get_logger

logger = get_logger("kona.engine")


class KonaDB:
    """Core database engine for KonaDB."""

    def __init__(self, filepath=None, auto_save=True):
        self.storage = StorageEngine(filepath, auto_save)
        state = self.storage.load()
        self.tables = state["tables"]           # {name: [rows]}
        self.schemas = state["schemas"]         # {name: {col: {type,constraints}}}
        self.indexes = state["indexes"]         # {name: {idx_name: {cols, unique, data}}}
        self.views = state["views"]             # {name: sql_string}
        self.collections = state["collections"] # {name: [documents]}
        self.auto_increments = state["auto_increments"]  # {table: {col: val}}
        self.metadata = state["metadata"]
        self._transaction_stack = []
        self._in_transaction = False

    def _save(self):
        state = {
            "tables": self.tables,
            "schemas": self.schemas,
            "indexes": self.indexes,
            "views": self.views,
            "collections": self.collections,
            "auto_increments": self.auto_increments,
            "metadata": self.metadata,
        }
        self.storage.save_if_auto(state)

    def save(self):
        state = {
            "tables": self.tables,
            "schemas": self.schemas,
            "indexes": self.indexes,
            "views": self.views,
            "collections": self.collections,
            "auto_increments": self.auto_increments,
            "metadata": self.metadata,
        }
        self.storage.save(state)

    # === Transaction Management ===
    def start_transaction(self):
        snapshot = {
            "tables": copy.deepcopy(self.tables),
            "schemas": copy.deepcopy(self.schemas),
            "indexes": copy.deepcopy(self.indexes),
            "auto_increments": copy.deepcopy(self.auto_increments),
        }
        self._transaction_stack.append(snapshot)
        self._in_transaction = True

    def commit(self):
        if not self._transaction_stack:
            raise RuntimeError("No active transaction to commit")
        self._transaction_stack.pop()
        if not self._transaction_stack:
            self._in_transaction = False
        self._save()

    def rollback(self):
        if not self._transaction_stack:
            raise RuntimeError("No active transaction to rollback")
        snapshot = self._transaction_stack.pop()
        self.tables = snapshot["tables"]
        self.schemas = snapshot["schemas"]
        self.indexes = snapshot["indexes"]
        self.auto_increments = snapshot["auto_increments"]
        if not self._transaction_stack:
            self._in_transaction = False

    # === SQL Execution ===
    def execute(self, sql, params=None):
        try:
            ast = parse_sql(sql)
        except ParseError as e:
            raise ValueError(f"SQL Parse Error: {e}") from e
        if ast is None:
            return []
        return self._execute_ast(ast, params)

    def _execute_ast(self, ast, params=None):
        if isinstance(ast, CreateTable): return self._exec_create_table(ast)
        if isinstance(ast, DropTable): return self._exec_drop_table(ast)
        if isinstance(ast, AlterTable): return self._exec_alter_table(ast)
        if isinstance(ast, TruncateTable): return self._exec_truncate(ast)
        if isinstance(ast, RenameTable): return self._exec_rename(ast)
        if isinstance(ast, Insert): return self._exec_insert(ast, params)
        if isinstance(ast, Select): return self._exec_select(ast, params)
        if isinstance(ast, Update): return self._exec_update(ast, params)
        if isinstance(ast, Delete): return self._exec_delete(ast, params)
        if isinstance(ast, CreateIndex): return self._exec_create_index(ast)
        if isinstance(ast, DropIndex): return self._exec_drop_index(ast)
        if isinstance(ast, CreateView): return self._exec_create_view(ast)
        if isinstance(ast, DropView): return self._exec_drop_view(ast)
        if isinstance(ast, ShowTables): return self._exec_show_tables()
        if isinstance(ast, DescribeTable): return self._exec_describe(ast)
        if isinstance(ast, ShowColumns): return self._exec_show_columns(ast)
        if isinstance(ast, ShowCreateTable): return self._exec_show_create_table(ast)
        if isinstance(ast, ShowIndexes): return self._exec_show_indexes(ast)
        if isinstance(ast, ExplainQuery): return self._exec_explain(ast, params)
        if isinstance(ast, StartTransaction): self.start_transaction(); return [{"status": "Transaction started"}]
        if isinstance(ast, Commit): self.commit(); return [{"status": "Transaction committed"}]
        if isinstance(ast, Rollback): self.rollback(); return [{"status": "Transaction rolled back"}]
        raise ValueError(f"Unknown AST node: {type(ast).__name__}")

    # === DDL Execution ===
    def _exec_create_table(self, ast):
        name = ast.name.lower()
        if name in self.tables:
            if ast.if_not_exists:
                return [{"status": f"Table '{name}' already exists"}]
            raise ValueError(f"Table '{name}' already exists")
        schema = {}
        pk_cols = []
        for col in ast.columns:
            col_info = {"type": col.data_type, "constraints": []}
            for c in col.constraints:
                if isinstance(c, tuple):
                    col_info["constraints"].append(c)
                    if c[0] == 'DEFAULT':
                        col_info["default"] = self._eval_expr(c[1], {})
                else:
                    col_info["constraints"].append(c)
                    if c == 'PRIMARY KEY':
                        pk_cols.append(col.name.lower())
                    if c == 'AUTO_INCREMENT':
                        if name not in self.auto_increments:
                            self.auto_increments[name] = {}
                        self.auto_increments[name][col.name.lower()] = 0
            schema[col.name.lower()] = col_info
        for constraint in ast.constraints:
            if constraint[0] == 'PRIMARY KEY':
                pk_cols.extend([c.lower() for c in constraint[1]])
        self.schemas[name] = schema
        self.tables[name] = []
        if name not in self.indexes:
            self.indexes[name] = {}
        if pk_cols:
            self.indexes[name]["_pk"] = {"columns": pk_cols, "unique": True, "data": {}}
        self._save()
        return [{"status": f"Table '{name}' created"}]

    def _exec_drop_table(self, ast):
        name = ast.name.lower()
        if name not in self.tables:
            if ast.if_exists:
                return [{"status": f"Table '{name}' does not exist"}]
            raise ValueError(f"Table '{name}' does not exist")
        del self.tables[name]
        del self.schemas[name]
        self.indexes.pop(name, None)
        self.auto_increments.pop(name, None)
        self._save()
        return [{"status": f"Table '{name}' dropped"}]

    def _exec_alter_table(self, ast):
        name = ast.name.lower()
        if name not in self.tables:
            raise ValueError(f"Table '{name}' does not exist")
        schema = self.schemas[name]
        for action in ast.actions:
            if action[0] == 'ADD':
                col = action[1]
                cn = col.name.lower()
                col_info = {"type": col.data_type, "constraints": []}
                default_val = None
                for c in col.constraints:
                    if isinstance(c, tuple):
                        col_info["constraints"].append(c)
                        if c[0] == 'DEFAULT':
                            default_val = self._eval_expr(c[1], {})
                    else:
                        col_info["constraints"].append(c)
                schema[cn] = col_info
                for row in self.tables[name]:
                    row[cn] = default_val
            elif action[0] == 'DROP':
                cn = action[1].lower()
                if cn in schema:
                    del schema[cn]
                for row in self.tables[name]:
                    row.pop(cn, None)
            elif action[0] == 'MODIFY':
                col = action[1]
                cn = col.name.lower()
                col_info = {"type": col.data_type, "constraints": []}
                for c in col.constraints:
                    if isinstance(c, tuple):
                        col_info["constraints"].append(c)
                    else:
                        col_info["constraints"].append(c)
                schema[cn] = col_info
            elif action[0] == 'RENAME_TABLE':
                new_name = action[1].lower()
                self.tables[new_name] = self.tables.pop(name)
                self.schemas[new_name] = self.schemas.pop(name)
                if name in self.indexes:
                    self.indexes[new_name] = self.indexes.pop(name)
                if name in self.auto_increments:
                    self.auto_increments[new_name] = self.auto_increments.pop(name)
                name = new_name
            elif action[0] == 'RENAME_COLUMN':
                old_cn = action[1].lower()
                new_cn = action[2].lower()
                if old_cn in schema:
                    schema[new_cn] = schema.pop(old_cn)
                for row in self.tables[name]:
                    if old_cn in row:
                        row[new_cn] = row.pop(old_cn)
        self._save()
        return [{"status": f"Table '{name}' altered"}]

    def _exec_truncate(self, ast):
        name = ast.name.lower()
        if name not in self.tables:
            raise ValueError(f"Table '{name}' does not exist")
        self.tables[name] = []
        if name in self.auto_increments:
            for col in self.auto_increments[name]:
                self.auto_increments[name][col] = 0
        if name in self.indexes:
            for idx in self.indexes[name]:
                self.indexes[name][idx]["data"] = {}
        self._save()
        return [{"status": f"Table '{name}' truncated"}]

    def _exec_rename(self, ast):
        old = ast.old_name.lower()
        new = ast.new_name.lower()
        if old not in self.tables:
            raise ValueError(f"Table '{old}' does not exist")
        self.tables[new] = self.tables.pop(old)
        self.schemas[new] = self.schemas.pop(old)
        if old in self.indexes:
            self.indexes[new] = self.indexes.pop(old)
        if old in self.auto_increments:
            self.auto_increments[new] = self.auto_increments.pop(old)
        self._save()
        return [{"status": f"Table '{old}' renamed to '{new}'"}]

    # === DML: INSERT ===
    def _exec_insert(self, ast, params=None):
        table = ast.table.lower()
        if table not in self.tables:
            if table in self.views:
                raise ValueError("Cannot INSERT into a view")
            raise ValueError(f"Table '{table}' does not exist")
        schema = self.schemas[table]
        columns = [c.lower() for c in ast.columns] if ast.columns else list(schema.keys())
        inserted = 0
        for value_row in ast.values:
            row = {}
            for i, col in enumerate(columns):
                if i < len(value_row):
                    row[col] = self._eval_expr(value_row[i], {}, params=params)
                else:
                    row[col] = None
            # Handle auto_increment
            if table in self.auto_increments:
                for ac_col, ac_val in self.auto_increments[table].items():
                    if ac_col not in row or row[ac_col] is None:
                        ac_val += 1
                        self.auto_increments[table][ac_col] = ac_val
                        row[ac_col] = ac_val
                    else:
                        if isinstance(row[ac_col], (int, float)) and row[ac_col] > ac_val:
                            self.auto_increments[table][ac_col] = int(row[ac_col])
            # Handle defaults
            for col_name, col_info in schema.items():
                if col_name not in row:
                    if "default" in col_info:
                        row[col_name] = col_info["default"]
                    else:
                        row[col_name] = None
            # Validate constraints
            try:
                self._validate_constraints(table, row, schema, is_replace=ast.replace)
            except ValueError:
                if ast.ignore:
                    continue
                raise
            # Handle REPLACE: delete existing row with same PK
            if ast.replace:
                self._replace_existing(table, row, schema)
            self.tables[table].append(row)
            self._update_indexes(table, row)
            inserted += 1
        self._save()
        return [{"status": f"{inserted} row(s) inserted"}]

    def _replace_existing(self, table, new_row, schema):
        pk_cols = self._get_pk_columns(table)
        if not pk_cols:
            return
        to_remove = []
        for i, existing in enumerate(self.tables[table]):
            if all(existing.get(c) == new_row.get(c) for c in pk_cols):
                to_remove.append(i)
        for i in reversed(to_remove):
            self.tables[table].pop(i)

    def _get_pk_columns(self, table):
        pk_cols = []
        if table in self.indexes and "_pk" in self.indexes[table]:
            pk_cols = self.indexes[table]["_pk"]["columns"]
        if not pk_cols:
            schema = self.schemas.get(table, {})
            for col_name, col_info in schema.items():
                if 'PRIMARY KEY' in col_info.get("constraints", []):
                    pk_cols.append(col_name)
        return pk_cols

    def _validate_constraints(self, table, row, schema, is_replace=False):
        pk_cols = self._get_pk_columns(table)
        for col_name, col_info in schema.items():
            constraints = col_info.get("constraints", [])
            val = row.get(col_name)
            if 'NOT NULL' in constraints and val is None and 'AUTO_INCREMENT' not in constraints:
                raise ValueError(f"Column '{col_name}' cannot be NULL")
            if 'PRIMARY KEY' in constraints and val is None and 'AUTO_INCREMENT' not in constraints:
                raise ValueError(f"Primary key '{col_name}' cannot be NULL")
        # Check unique/PK constraints
        for col_name, col_info in schema.items():
            constraints = col_info.get("constraints", [])
            val = row.get(col_name)
            if ('UNIQUE' in constraints or 'PRIMARY KEY' in constraints) and val is not None:
                for existing in self.tables[table]:
                    if existing.get(col_name) == val:
                        if is_replace and col_name in pk_cols:
                            continue
                        raise ValueError(f"Duplicate value '{val}' for unique column '{col_name}'")
        # Check foreign key constraints
        for col_name, col_info in schema.items():
            for c in col_info.get("constraints", []):
                if isinstance(c, tuple) and c[0] == 'REFERENCES':
                    ref_table = c[1].lower()
                    ref_col = c[2].lower()
                    val = row.get(col_name)
                    if val is not None and ref_table in self.tables:
                        found = any(r.get(ref_col) == val for r in self.tables[ref_table])
                        if not found:
                            raise ValueError(f"Foreign key constraint failed: {col_name} -> {ref_table}.{ref_col}")
        # Check CHECK constraints
        for col_name, col_info in schema.items():
            for c in col_info.get("constraints", []):
                if isinstance(c, tuple) and c[0] == 'CHECK':
                    result = self._eval_expr(c[1], row)
                    if not result:
                        raise ValueError(f"CHECK constraint failed for column '{col_name}'")

    def _update_indexes(self, table, row):
        if table not in self.indexes:
            return
        for idx_name, idx_info in self.indexes[table].items():
            cols = idx_info["columns"]
            key = tuple(str(row.get(c)) for c in cols)
            key_str = "|".join(key)
            if key_str not in idx_info["data"]:
                idx_info["data"][key_str] = []
            idx_info["data"][key_str].append(len(self.tables[table]) - 1)

    # === DML: SELECT ===
    def _exec_select(self, ast, params=None):
        if ast.from_table is None:
            # SELECT without FROM (e.g., SELECT 1+1, SELECT NOW())
            row = {}
            result_row = {}
            for col_expr in ast.columns:
                if isinstance(col_expr, AliasedExpr):
                    result_row[col_expr.alias] = self._eval_expr(col_expr.expr, row, params=params)
                else:
                    result_row[str(self._expr_name(col_expr))] = self._eval_expr(col_expr, row, params=params)
            return [result_row]

        table_name = ast.from_table.lower()
        # Check if it's a view
        if table_name in self.views and table_name not in self.tables:
            view_ast = parse_sql(self.views[table_name])
            return self._exec_select(view_ast, params)

        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")

        rows = [dict(r) for r in self.tables[table_name]]
        table_alias = ast.table_alias or table_name

        # Prefix rows with table alias for join disambiguation
        def prefix_row(row, alias):
            prefixed = {}
            for k, v in row.items():
                prefixed[k] = v
                prefixed[f"{alias}.{k}"] = v
            return prefixed

        rows = [prefix_row(r, table_alias) for r in rows]

        # Process JOINs
        for join in ast.joins:
            join_table = join.table.lower()
            if join_table in self.views and join_table not in self.tables:
                join_rows_raw = self._exec_select(parse_sql(self.views[join_table]), params)
            elif join_table not in self.tables:
                raise ValueError(f"Table '{join_table}' does not exist")
            else:
                join_rows_raw = [dict(r) for r in self.tables[join_table]]

            j_alias = join.alias or join_table
            join_rows = [prefix_row(r, j_alias) for r in join_rows_raw]

            if join.join_type == 'CROSS':
                new_rows = []
                for lr in rows:
                    for rr in join_rows:
                        merged = {**lr, **rr}
                        new_rows.append(merged)
                rows = new_rows
            elif join.join_type in ('INNER', 'LEFT', 'RIGHT'):
                new_rows = []
                if join.join_type == 'RIGHT':
                    rows, join_rows = join_rows, rows
                for lr in rows:
                    matched = False
                    for rr in join_rows:
                        merged = {**lr, **rr}
                        if join.on_condition is None or self._eval_expr(join.on_condition, merged, params=params):
                            new_rows.append(merged)
                            matched = True
                    if not matched and join.join_type in ('LEFT', 'RIGHT'):
                        null_row = {k: None for k in (join_rows[0] if join_rows else {})}
                        new_rows.append({**lr, **null_row})
                rows = new_rows

        # WHERE
        if ast.where:
            rows = [r for r in rows if self._eval_expr(ast.where, r, params=params)]

        # Detect if query has aggregate functions without GROUP BY
        has_agg = self._has_aggregate(ast.columns)

        # GROUP BY
        if ast.group_by:
            groups = defaultdict(list)
            for r in rows:
                key = tuple(self._eval_expr(g, r, params=params) for g in ast.group_by)
                groups[key].append(r)
            rows = []
            for key, group_rows in groups.items():
                result_row = dict(group_rows[0])
                result_row["__group__"] = group_rows
                rows.append(result_row)
            # Pre-compute SELECT column values for HAVING alias access
            if ast.having:
                for r in rows:
                    for col_expr in ast.columns:
                        if isinstance(col_expr, AliasedExpr):
                            r[col_expr.alias] = self._eval_expr(col_expr.expr, r, params=params)
                rows = [r for r in rows if self._eval_expr(ast.having, r, params=params)]
        elif has_agg and rows:
            # Implicit single group for aggregate without GROUP BY
            combined = dict(rows[0])
            combined["__group__"] = rows
            rows = [combined]

        # SELECT columns
        result = []
        for r in rows:
            out = {}
            for col_expr in ast.columns:
                if isinstance(col_expr, WildCard):
                    if col_expr.table:
                        prefix = col_expr.table + "."
                        for k, v in r.items():
                            if k.startswith(prefix):
                                out[k.split(".", 1)[1]] = v
                            elif "." not in k:
                                out[k] = v
                    else:
                        for k, v in r.items():
                            if "." not in k:
                                out[k] = v
                elif isinstance(col_expr, AliasedExpr):
                    out[col_expr.alias] = self._eval_expr(col_expr.expr, r, params=params)
                else:
                    name = self._expr_name(col_expr)
                    out[name] = self._eval_expr(col_expr, r, params=params)
            result.append(out)

        # DISTINCT
        if ast.distinct:
            seen = set()
            unique = []
            for r in result:
                key = tuple(sorted(r.items()))
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
            result = unique

        # ORDER BY
        if ast.order_by:
            def sort_key(row):
                keys = []
                for item in ast.order_by:
                    val = self._eval_expr(item.expr, row, params=params)
                    if val is None:
                        keys.append((0, "", ""))
                    elif isinstance(val, (int, float)):
                        keys.append((1, val if item.direction == 'ASC' else -val, ""))
                    else:
                        keys.append((1, 0, str(val)))
                return keys
            try:
                # For string DESC, we need a different approach
                all_numeric = all(
                    all(isinstance(self._eval_expr(item.expr, r, params=params), (int, float, type(None)))
                        for r in result)
                    for item in ast.order_by
                )
                if all_numeric:
                    result.sort(key=sort_key)
                else:
                    # Use reverse for non-numeric types
                    reverse = ast.order_by[0].direction == 'DESC'
                    result.sort(key=lambda r: [
                        (0 if self._eval_expr(item.expr, r, params=params) is None else 1,
                         self._eval_expr(item.expr, r, params=params) or "")
                        for item in ast.order_by
                    ], reverse=reverse)
            except TypeError:
                pass

        # OFFSET
        if ast.offset:
            result = result[ast.offset:]

        # LIMIT
        if ast.limit is not None:
            result = result[:ast.limit]

        # Remove __group__ from results
        for r in result:
            r.pop("__group__", None)

        return result

    # === DML: UPDATE & DELETE ===
    def _exec_update(self, ast, params=None):
        table = ast.table.lower()
        if table not in self.tables:
            raise ValueError(f"Table '{table}' does not exist")
        updated = 0
        for row in self.tables[table]:
            if ast.where is None or self._eval_expr(ast.where, row, params=params):
                for col, val_expr in ast.assignments:
                    row[col.lower()] = self._eval_expr(val_expr, row, params=params)
                updated += 1
        self._save()
        return [{"status": f"{updated} row(s) updated"}]

    def _exec_delete(self, ast, params=None):
        table = ast.table.lower()
        if table not in self.tables:
            raise ValueError(f"Table '{table}' does not exist")
        if ast.where is None:
            deleted = len(self.tables[table])
            self.tables[table] = []
        else:
            original = self.tables[table]
            keep = [r for r in original if not self._eval_expr(ast.where, r, params=params)]
            deleted = len(original) - len(keep)
            self.tables[table] = keep
        self._save()
        return [{"status": f"{deleted} row(s) deleted"}]

    # === Index, View, Utility ===
    def _exec_create_index(self, ast):
        table = ast.table.lower()
        if table not in self.tables:
            raise ValueError(f"Table '{table}' does not exist")
        if table not in self.indexes:
            self.indexes[table] = {}
        idx_name = ast.name.lower()
        cols = [c.lower() for c in ast.columns]
        data = {}
        for i, row in enumerate(self.tables[table]):
            key = "|".join(str(row.get(c)) for c in cols)
            if key not in data:
                data[key] = []
            data[key].append(i)
        self.indexes[table][idx_name] = {"columns": cols, "unique": ast.unique, "data": data}
        self._save()
        return [{"status": f"Index '{idx_name}' created on '{table}'"}]

    def _exec_drop_index(self, ast):
        idx_name = ast.name.lower()
        table = ast.table.lower() if ast.table else None
        if table and table in self.indexes:
            self.indexes[table].pop(idx_name, None)
        else:
            for t in self.indexes:
                if idx_name in self.indexes[t]:
                    del self.indexes[t][idx_name]
                    break
        self._save()
        return [{"status": f"Index '{idx_name}' dropped"}]

    def _exec_create_view(self, ast):
        name = ast.name.lower()
        # Store the SQL representation by reconstructing it
        # We store a simplified version - re-parse on use
        self.views[name] = self._ast_to_sql(ast.select_stmt)
        self._save()
        return [{"status": f"View '{name}' created"}]

    def _ast_to_sql(self, select):
        """Simple AST-to-SQL for view storage."""
        parts = ["SELECT"]
        if select.distinct:
            parts.append("DISTINCT")
        col_strs = []
        for c in select.columns:
            if isinstance(c, WildCard):
                col_strs.append("*")
            elif isinstance(c, AliasedExpr):
                col_strs.append(f"{self._expr_to_sql(c.expr)} AS {c.alias}")
            else:
                col_strs.append(self._expr_to_sql(c))
        parts.append(", ".join(col_strs))
        if select.from_table:
            parts.append(f"FROM {select.from_table}")
        if select.where:
            parts.append(f"WHERE {self._expr_to_sql(select.where)}")
        if select.group_by:
            parts.append("GROUP BY " + ", ".join(self._expr_to_sql(g) for g in select.group_by))
        if select.having:
            parts.append(f"HAVING {self._expr_to_sql(select.having)}")
        if select.order_by:
            ob = []
            for item in select.order_by:
                ob.append(f"{self._expr_to_sql(item.expr)} {item.direction}")
            parts.append("ORDER BY " + ", ".join(ob))
        if select.limit is not None:
            parts.append(f"LIMIT {select.limit}")
        if select.offset:
            parts.append(f"OFFSET {select.offset}")
        return " ".join(parts)

    def _expr_to_sql(self, expr):
        if isinstance(expr, Literal):
            if expr.value is None: return "NULL"
            if isinstance(expr.value, str): return f"'{expr.value}'"
            if isinstance(expr.value, bool): return "TRUE" if expr.value else "FALSE"
            return str(expr.value)
        if isinstance(expr, ColumnRef):
            if expr.table: return f"{expr.table}.{expr.name}"
            return expr.name
        if isinstance(expr, BinaryOp):
            return f"({self._expr_to_sql(expr.left)} {expr.op} {self._expr_to_sql(expr.right)})"
        if isinstance(expr, UnaryOp):
            return f"({expr.op} {self._expr_to_sql(expr.operand)})"
        if isinstance(expr, FunctionCall):
            args = ", ".join(self._expr_to_sql(a) for a in expr.args)
            return f"{expr.name}({args})"
        if isinstance(expr, WildCard):
            return "*"
        return str(expr)

    def _exec_drop_view(self, ast):
        name = ast.name.lower()
        if name not in self.views:
            if ast.if_exists: return [{"status": f"View '{name}' does not exist"}]
            raise ValueError(f"View '{name}' does not exist")
        del self.views[name]
        self._save()
        return [{"status": f"View '{name}' dropped"}]

    def _exec_show_tables(self):
        tables = [{"table_name": t} for t in sorted(self.tables.keys())]
        views = [{"table_name": f"{v} (view)"} for v in sorted(self.views.keys())]
        return tables + views

    def _exec_describe(self, ast):
        name = ast.name.lower()
        if name not in self.schemas:
            raise ValueError(f"Table '{name}' does not exist")
        result = []
        for col_name, col_info in self.schemas[name].items():
            constraints = col_info.get("constraints", [])
            c_strs = []
            for c in constraints:
                if isinstance(c, tuple): c_strs.append(str(c[0]))
                else: c_strs.append(c)
            result.append({
                "Field": col_name, "Type": col_info["type"],
                "Null": "NO" if "NOT NULL" in constraints or "PRIMARY KEY" in constraints else "YES",
                "Key": "PRI" if "PRIMARY KEY" in constraints else ("UNI" if "UNIQUE" in constraints else ""),
                "Default": col_info.get("default", "NULL"),
                "Extra": "auto_increment" if "AUTO_INCREMENT" in constraints else "",
            })
        return result

    def _exec_show_columns(self, ast):
        return self._exec_describe(DescribeTable(ast.table))

    def _exec_show_create_table(self, ast):
        name = ast.table.lower()
        if name not in self.schemas:
            raise ValueError(f"Table '{name}' does not exist")
        lines = [f"CREATE TABLE `{name}` ("]
        col_lines = []
        for col_name, col_info in self.schemas[name].items():
            parts = [f"  `{col_name}` {col_info['type']}"]
            for c in col_info.get("constraints", []):
                if isinstance(c, tuple):
                    if c[0] == 'DEFAULT': parts.append(f"DEFAULT {c[1]}")
                    elif c[0] == 'REFERENCES': parts.append(f"REFERENCES {c[1]}({c[2]})")
                else:
                    parts.append(c)
            col_lines.append(" ".join(parts))
        lines.append(",\n".join(col_lines))
        lines.append(")")
        return [{"Table": name, "Create Table": "\n".join(lines)}]

    def _exec_show_indexes(self, ast):
        table = ast.table.lower()
        result = []
        if table in self.indexes:
            for idx_name, idx_info in self.indexes[table].items():
                for i, col in enumerate(idx_info["columns"]):
                    result.append({
                        "Table": table, "Key_name": idx_name,
                        "Column_name": col, "Seq_in_index": i + 1,
                        "Non_unique": 0 if idx_info["unique"] else 1,
                    })
        return result

    def _exec_explain(self, ast, params=None):
        inner = ast.query
        info = {"id": 1, "select_type": "SIMPLE", "type": "ALL", "possible_keys": None, "rows": 0}
        if isinstance(inner, Select) and inner.from_table:
            table = inner.from_table.lower()
            info["table"] = table
            info["rows"] = len(self.tables.get(table, []))
            if table in self.indexes:
                info["possible_keys"] = ", ".join(self.indexes[table].keys())
        return [info]

    # === Expression Evaluator ===
    def _eval_expr(self, expr, row, params=None):
        if expr is None:
            return None
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Placeholder):
            if params and expr.index < len(params):
                return params[expr.index]
            return None
        if isinstance(expr, ColumnRef):
            name = expr.name.lower() if isinstance(expr.name, str) else expr.name
            if expr.table:
                key = f"{expr.table}.{name}"
                if key in row:
                    return row[key]
            if name in row:
                return row[name]
            # Try case-insensitive
            for k, v in row.items():
                if k.lower() == name:
                    return v
            return None
        if isinstance(expr, BinaryOp):
            left = self._eval_expr(expr.left, row, params)
            right = self._eval_expr(expr.right, row, params)
            return self._eval_binary_op(expr.op, left, right)
        if isinstance(expr, UnaryOp):
            val = self._eval_expr(expr.operand, row, params)
            if expr.op == 'NOT':
                return not val
            if expr.op == '-':
                return -val if val is not None else None
            return val
        if isinstance(expr, FunctionCall):
            return self._eval_function(expr, row, params)
        if isinstance(expr, IsNull):
            val = self._eval_expr(expr.expr, row, params)
            result = val is None
            return not result if expr.negated else result
        if isinstance(expr, InList):
            val = self._eval_expr(expr.expr, row, params)
            values = [self._eval_expr(v, row, params) for v in expr.values]
            result = val in values
            return not result if expr.negated else result
        if isinstance(expr, BetweenExpr):
            val = self._eval_expr(expr.expr, row, params)
            low = self._eval_expr(expr.low, row, params)
            high = self._eval_expr(expr.high, row, params)
            result = low <= val <= high if val is not None else False
            return not result if expr.negated else result
        if isinstance(expr, ExistsExpr):
            if isinstance(expr.subquery, SubQuery):
                results = self._exec_select(expr.subquery.query, params)
                return len(results) > 0
            return False
        if isinstance(expr, SubQuery):
            results = self._exec_select(expr.query, params)
            if results and len(results) == 1:
                vals = list(results[0].values())
                return vals[0] if vals else None
            return [list(r.values())[0] for r in results] if results else []
        if isinstance(expr, CaseExpr):
            if expr.operand:
                op_val = self._eval_expr(expr.operand, row, params)
                for cond, result in expr.when_clauses:
                    if self._eval_expr(cond, row, params) == op_val:
                        return self._eval_expr(result, row, params)
            else:
                for cond, result in expr.when_clauses:
                    if self._eval_expr(cond, row, params):
                        return self._eval_expr(result, row, params)
            if expr.else_clause:
                return self._eval_expr(expr.else_clause, row, params)
            return None
        if isinstance(expr, CastExpr):
            val = self._eval_expr(expr.expr, row, params)
            return self._cast_value(val, expr.target_type)
        if isinstance(expr, WildCard):
            return None
        if isinstance(expr, AliasedExpr):
            return self._eval_expr(expr.expr, row, params)
        return None

    def _eval_binary_op(self, op, left, right):
        if op == 'AND': return bool(left) and bool(right)
        if op == 'OR': return bool(left) or bool(right)
        if left is None or right is None:
            if op == '=': return left is None and right is None
            if op in ('!=', '<>'): return not (left is None and right is None)
            return None
        if op == '=': return left == right
        if op in ('!=', '<>'): return left != right
        if op == '<':
            try: return left < right
            except: return str(left) < str(right)
        if op == '>':
            try: return left > right
            except: return str(left) > str(right)
        if op == '<=':
            try: return left <= right
            except: return str(left) <= str(right)
        if op == '>=':
            try: return left >= right
            except: return str(left) >= str(right)
        if op == 'LIKE':
            pattern = str(right).replace('%', '.*').replace('_', '.')
            return bool(re.match(f"^{pattern}$", str(left), re.IGNORECASE))
        try:
            l, r = float(left), float(right)
            if op == '+': return l + r
            if op == '-': return l - r
            if op == '*': return l * r
            if op == '/': return l / r if r != 0 else None
            if op == '%': return l % r if r != 0 else None
        except (ValueError, TypeError):
            if op == '+' and isinstance(left, str): return str(left) + str(right)
        return None

    def _eval_function(self, expr, row, params=None):
        name = expr.name.upper()
        args = expr.args
        group = row.get("__group__", [row])

        # Aggregate functions
        if name == 'COUNT':
            if args and isinstance(args[0], WildCard):
                return len(group)
            if args:
                vals = [self._eval_expr(args[0], r, params) for r in group]
                if expr.distinct:
                    return len(set(v for v in vals if v is not None))
                return sum(1 for v in vals if v is not None)
            return len(group)
        if name == 'SUM':
            vals = [self._eval_expr(args[0], r, params) for r in group]
            nums = [v for v in vals if v is not None]
            return sum(float(v) for v in nums) if nums else 0
        if name == 'AVG':
            vals = [self._eval_expr(args[0], r, params) for r in group]
            nums = [float(v) for v in vals if v is not None]
            return sum(nums) / len(nums) if nums else None
        if name == 'MIN':
            vals = [self._eval_expr(args[0], r, params) for r in group]
            nums = [v for v in vals if v is not None]
            return min(nums) if nums else None
        if name == 'MAX':
            vals = [self._eval_expr(args[0], r, params) for r in group]
            nums = [v for v in vals if v is not None]
            return max(nums) if nums else None

        # Scalar functions - evaluate on single row
        evaluated = [self._eval_expr(a, row, params) for a in args]
        if name == 'UPPER': return str(evaluated[0]).upper() if evaluated[0] is not None else None
        if name == 'LOWER': return str(evaluated[0]).lower() if evaluated[0] is not None else None
        if name == 'LENGTH': return len(str(evaluated[0])) if evaluated[0] is not None else None
        if name == 'TRIM': return str(evaluated[0]).strip() if evaluated[0] is not None else None
        if name == 'CONCAT': return ''.join(str(v) for v in evaluated if v is not None)
        if name == 'SUBSTRING':
            s = str(evaluated[0]) if evaluated[0] else ''
            start = int(evaluated[1]) - 1 if len(evaluated) > 1 else 0
            length = int(evaluated[2]) if len(evaluated) > 2 else len(s)
            return s[start:start + length]
        if name == 'NOW':
            from datetime import datetime
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if name == 'COALESCE':
            for v in evaluated:
                if v is not None: return v
            return None
        if name == 'IF':
            return evaluated[1] if evaluated[0] else (evaluated[2] if len(evaluated) > 2 else None)
        if name == 'IFNULL':
            return evaluated[0] if evaluated[0] is not None else (evaluated[1] if len(evaluated) > 1 else None)
        if name == 'CAST':
            return self._cast_value(evaluated[0], str(evaluated[1]) if len(evaluated) > 1 else 'TEXT')
        if name == 'ABS': return abs(float(evaluated[0])) if evaluated[0] is not None else None
        if name == 'ROUND':
            if evaluated[0] is None: return None
            decimals = int(evaluated[1]) if len(evaluated) > 1 else 0
            return round(float(evaluated[0]), decimals)
        if name == 'REPLACE':
            if len(evaluated) >= 3 and evaluated[0] is not None:
                return str(evaluated[0]).replace(str(evaluated[1]), str(evaluated[2]))
            return evaluated[0]
        return None

    def _cast_value(self, val, target_type):
        if val is None: return None
        t = target_type.upper().split('(')[0]
        try:
            if t in ('INT', 'INTEGER', 'SIGNED'): return int(float(val))
            if t in ('FLOAT', 'DOUBLE', 'DECIMAL', 'REAL'): return float(val)
            if t in ('CHAR', 'VARCHAR', 'TEXT'): return str(val)
            if t in ('BOOLEAN', 'BOOL'): return bool(val)
        except (ValueError, TypeError):
            return None
        return val

    AGGREGATE_FUNCS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}

    def _has_aggregate(self, columns):
        """Check if any column expression contains an aggregate function."""
        for col in columns:
            if self._is_aggregate_expr(col):
                return True
        return False

    def _is_aggregate_expr(self, expr):
        if isinstance(expr, FunctionCall) and expr.name.upper() in self.AGGREGATE_FUNCS:
            return True
        if isinstance(expr, AliasedExpr):
            return self._is_aggregate_expr(expr.expr)
        if isinstance(expr, BinaryOp):
            return self._is_aggregate_expr(expr.left) or self._is_aggregate_expr(expr.right)
        return False

    def _expr_name(self, expr):
        if isinstance(expr, ColumnRef):
            return expr.name
        if isinstance(expr, FunctionCall):
            args = ", ".join(self._expr_name(a) for a in expr.args)
            return f"{expr.name}({args})"
        if isinstance(expr, Literal):
            return str(expr.value)
        if isinstance(expr, WildCard):
            return "*"
        if isinstance(expr, BinaryOp):
            return f"{self._expr_name(expr.left)} {expr.op} {self._expr_name(expr.right)}"
        return "expr"

    # === Document Store (MongoDB-style) ===
    def create_collection(self, name):
        name = name.lower()
        if name in self.collections:
            raise ValueError(f"Collection '{name}' already exists")
        self.collections[name] = []
        self._save()

    def drop_collection(self, name):
        name = name.lower()
        if name in self.collections:
            del self.collections[name]
            self._save()

    def insert_document(self, collection, doc):
        collection = collection.lower()
        if collection not in self.collections:
            raise ValueError(f"Collection '{collection}' does not exist")
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        self.collections[collection].append(doc)
        self._save()
        return doc["_id"]

    def insert_many_documents(self, collection, docs):
        ids = []
        for doc in docs:
            ids.append(self.insert_document(collection, doc))
        return ids

    def find_documents(self, collection, query=None, projection=None, sort=None, limit=None, skip=None):
        collection = collection.lower()
        if collection not in self.collections:
            raise ValueError(f"Collection '{collection}' does not exist")
        results = self.collections[collection]
        if query:
            results = [d for d in results if self._match_document(d, query)]
        if sort:
            for key, direction in reversed(sort):
                results = sorted(results, key=lambda d: (d.get(key) is None, d.get(key, "")),
                                reverse=(direction == -1))
        if skip:
            results = results[skip:]
        if limit:
            results = results[:limit]
        if projection:
            projected = []
            for doc in results:
                p = {}
                for key, include in projection.items():
                    if include and key in doc:
                        p[key] = doc[key]
                if not any(v for v in projection.values()):
                    p = {k: v for k, v in doc.items() if k not in projection or not projection[k]}
                projected.append(p)
            return projected
        return [dict(d) for d in results]

    def update_documents(self, collection, query, update, multi=False):
        collection = collection.lower()
        if collection not in self.collections:
            raise ValueError(f"Collection '{collection}' does not exist")
        updated = 0
        for doc in self.collections[collection]:
            if self._match_document(doc, query):
                for key, value in update.items():
                    if key == "$set":
                        doc.update(value)
                    elif key == "$unset":
                        for k in value:
                            doc.pop(k, None)
                    elif key == "$inc":
                        for k, v in value.items():
                            doc[k] = doc.get(k, 0) + v
                    elif key == "$push":
                        for k, v in value.items():
                            if k not in doc: doc[k] = []
                            doc[k].append(v)
                    else:
                        doc[key] = value
                updated += 1
                if not multi:
                    break
        self._save()
        return updated

    def delete_documents(self, collection, query, multi=True):
        collection = collection.lower()
        if collection not in self.collections:
            raise ValueError(f"Collection '{collection}' does not exist")
        original = len(self.collections[collection])
        if multi:
            self.collections[collection] = [
                d for d in self.collections[collection] if not self._match_document(d, query)
            ]
        else:
            for i, d in enumerate(self.collections[collection]):
                if self._match_document(d, query):
                    self.collections[collection].pop(i)
                    break
        deleted = original - len(self.collections[collection])
        self._save()
        return deleted

    def _match_document(self, doc, query):
        for key, value in query.items():
            if key == "$and":
                return all(self._match_document(doc, q) for q in value)
            if key == "$or":
                return any(self._match_document(doc, q) for q in value)
            if key == "$not":
                return not self._match_document(doc, value)
            doc_val = doc.get(key)
            if isinstance(value, dict):
                for op, op_val in value.items():
                    if op == "$eq" and doc_val != op_val: return False
                    if op == "$ne" and doc_val == op_val: return False
                    if op == "$gt" and (doc_val is None or doc_val <= op_val): return False
                    if op == "$gte" and (doc_val is None or doc_val < op_val): return False
                    if op == "$lt" and (doc_val is None or doc_val >= op_val): return False
                    if op == "$lte" and (doc_val is None or doc_val > op_val): return False
                    if op == "$in" and doc_val not in op_val: return False
                    if op == "$nin" and doc_val in op_val: return False
                    if op == "$exists" and (key in doc) != op_val: return False
                    if op == "$regex" and not re.search(op_val, str(doc_val or "")): return False
            elif doc_val != value:
                return False
        return True

    def list_collections(self):
        return list(self.collections.keys())

    def count_documents(self, collection, query=None):
        collection = collection.lower()
        if collection not in self.collections:
            raise ValueError(f"Collection '{collection}' does not exist")
        if query:
            return sum(1 for d in self.collections[collection] if self._match_document(d, query))
        return len(self.collections[collection])
