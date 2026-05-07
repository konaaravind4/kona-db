"""SQL Parser for KonaDB - recursive descent parser."""
from kona.query.tokenizer import tokenize, TT, Token

class ParseError(Exception):
    pass

class ASTNode:
    pass

class CreateTable(ASTNode):
    def __init__(s, name, columns, constraints=None, if_not_exists=False, temporary=False):
        s.name=name; s.columns=columns; s.constraints=constraints or []; s.if_not_exists=if_not_exists; s.temporary=temporary

class ColumnDef(ASTNode):
    def __init__(s, name, data_type, constraints=None):
        s.name=name; s.data_type=data_type; s.constraints=constraints or []

class DropTable(ASTNode):
    def __init__(s, name, if_exists=False):
        s.name=name; s.if_exists=if_exists

class AlterTable(ASTNode):
    def __init__(s, name, actions=None):
        s.name=name; s.actions=actions or []

class TruncateTable(ASTNode):
    def __init__(s, name):
        s.name=name

class RenameTable(ASTNode):
    def __init__(s, old_name, new_name):
        s.old_name=old_name; s.new_name=new_name

class Insert(ASTNode):
    def __init__(s, table, columns, values, ignore=False, replace=False):
        s.table=table; s.columns=columns; s.values=values; s.ignore=ignore; s.replace=replace

class Select(ASTNode):
    def __init__(s, columns=None, from_table=None, joins=None, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, distinct=False, aliases=None, table_alias=None):
        s.columns=columns or []; s.from_table=from_table; s.joins=joins or []; s.where=where; s.group_by=group_by; s.having=having; s.order_by=order_by; s.limit=limit; s.offset=offset; s.distinct=distinct; s.aliases=aliases or {}; s.table_alias=table_alias

class Update(ASTNode):
    def __init__(s, table, assignments, where=None):
        s.table=table; s.assignments=assignments; s.where=where

class Delete(ASTNode):
    def __init__(s, table, where=None):
        s.table=table; s.where=where

class CreateIndex(ASTNode):
    def __init__(s, name, table, columns, unique=False):
        s.name=name; s.table=table; s.columns=columns; s.unique=unique

class DropIndex(ASTNode):
    def __init__(s, name, table=None):
        s.name=name; s.table=table

class CreateView(ASTNode):
    def __init__(s, name, select_stmt, or_replace=False):
        s.name=name; s.select_stmt=select_stmt; s.or_replace=or_replace

class DropView(ASTNode):
    def __init__(s, name, if_exists=False):
        s.name=name; s.if_exists=if_exists

class ShowTables(ASTNode):
    pass

class DescribeTable(ASTNode):
    def __init__(s, name):
        s.name=name

class ShowColumns(ASTNode):
    def __init__(s, table):
        s.table=table

class ShowCreateTable(ASTNode):
    def __init__(s, table):
        s.table=table

class ShowIndexes(ASTNode):
    def __init__(s, table):
        s.table=table

class ExplainQuery(ASTNode):
    def __init__(s, query):
        s.query=query

class StartTransaction(ASTNode):
    pass

class Commit(ASTNode):
    pass

class Rollback(ASTNode):
    pass

class JoinClause(ASTNode):
    def __init__(s, join_type, table, alias, on_condition):
        s.join_type=join_type; s.table=table; s.alias=alias; s.on_condition=on_condition

class BinaryOp(ASTNode):
    def __init__(s, op, left, right):
        s.op=op; s.left=left; s.right=right

class UnaryOp(ASTNode):
    def __init__(s, op, operand):
        s.op=op; s.operand=operand

class Literal(ASTNode):
    def __init__(s, value):
        s.value=value

class ColumnRef(ASTNode):
    def __init__(s, name, table=None):
        s.name=name; s.table=table

class FunctionCall(ASTNode):
    def __init__(s, name, args, distinct=False):
        s.name=name; s.args=args; s.distinct=distinct

class SubQuery(ASTNode):
    def __init__(s, query):
        s.query=query

class InList(ASTNode):
    def __init__(s, expr, values, negated=False):
        s.expr=expr; s.values=values; s.negated=negated

class BetweenExpr(ASTNode):
    def __init__(s, expr, low, high, negated=False):
        s.expr=expr; s.low=low; s.high=high; s.negated=negated

class IsNull(ASTNode):
    def __init__(s, expr, negated=False):
        s.expr=expr; s.negated=negated

class ExistsExpr(ASTNode):
    def __init__(s, subquery):
        s.subquery=subquery

class CaseExpr(ASTNode):
    def __init__(s, operand, when_clauses, else_clause):
        s.operand=operand; s.when_clauses=when_clauses; s.else_clause=else_clause

class CastExpr(ASTNode):
    def __init__(s, expr, target_type):
        s.expr=expr; s.target_type=target_type

class WildCard(ASTNode):
    def __init__(s, table=None):
        s.table=table

class OrderByItem(ASTNode):
    def __init__(s, expr, direction="ASC"):
        s.expr=expr; s.direction=direction

class AliasedExpr(ASTNode):
    def __init__(s, expr, alias):
        s.expr=expr; s.alias=alias

class Placeholder(ASTNode):
    def __init__(s, index):
        s.index=index


class Parser:
    """Recursive descent SQL parser."""
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.placeholder_idx = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TT.EOF, '')

    def advance(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, ttype, value=None):
        t = self.peek()
        if t.type != ttype or (value and t.value != value):
            raise ParseError(f"Expected {ttype}:{value} got {t.type}:{t.value} at pos {t.pos}")
        return self.advance()

    def expect_keyword(self, kw):
        return self.expect(TT.KEYWORD, kw)

    def match_keyword(self, *kws):
        t = self.peek()
        if t.type == TT.KEYWORD and t.value in kws:
            return self.advance()
        return None

    def match(self, ttype, value=None):
        t = self.peek()
        if t.type == ttype and (value is None or t.value == value):
            return self.advance()
        return None

    def at_keyword(self, *kws):
        t = self.peek()
        return t.type == TT.KEYWORD and t.value in kws

    def at_end(self):
        t = self.peek()
        return t.type in (TT.EOF, TT.SEMICOLON)

    def parse_ident(self):
        t = self.peek()
        if t.type == TT.IDENT:
            return self.advance().value
        if t.type == TT.KEYWORD:
            return self.advance().value.lower()
        raise ParseError(f"Expected identifier, got {t.type}:{t.value}")

    def parse(self):
        self.match(TT.SEMICOLON)
        if self.at_end():
            return None
        stmt = self._parse_statement()
        self.match(TT.SEMICOLON)
        return stmt

    def _parse_statement(self):
        t = self.peek()
        if t.type == TT.KEYWORD:
            k = t.value
            if k == 'SELECT': return self._parse_select()
            if k == 'INSERT': return self._parse_insert()
            if k == 'REPLACE': return self._parse_replace()
            if k == 'UPDATE': return self._parse_update()
            if k == 'DELETE': return self._parse_delete()
            if k == 'CREATE': return self._parse_create()
            if k == 'DROP': return self._parse_drop()
            if k == 'ALTER': return self._parse_alter()
            if k == 'TRUNCATE': return self._parse_truncate()
            if k == 'RENAME': return self._parse_rename()
            if k == 'SHOW': return self._parse_show()
            if k in ('DESCRIBE', 'DESC'): return self._parse_describe()
            if k == 'EXPLAIN': return self._parse_explain()
            if k == 'START': return self._parse_start_transaction()
            if k == 'BEGIN': self.advance(); return StartTransaction()
            if k == 'COMMIT': self.advance(); return Commit()
            if k == 'ROLLBACK': self.advance(); return Rollback()
        raise ParseError(f"Unexpected token: {t.value}")

    def _parse_select(self):
        self.expect_keyword('SELECT')
        distinct = bool(self.match_keyword('DISTINCT'))
        cols = self._parse_select_columns()
        from_table = None; table_alias = None; joins = []; where = None
        group_by = None; having = None; order_by = None; limit = None; offset = None
        if self.match_keyword('FROM'):
            from_table = self.parse_ident()
            if not self.at_end() and not self.at_keyword('WHERE','JOIN','INNER','LEFT','RIGHT','CROSS','GROUP','ORDER','LIMIT','HAVING','ON'):
                t = self.peek()
                if t.type == TT.IDENT or (t.type == TT.KEYWORD and t.value not in ('WHERE','JOIN','INNER','LEFT','RIGHT','CROSS','GROUP','ORDER','LIMIT','HAVING','ON','OFFSET')):
                    table_alias = self.parse_ident()
            if self.match_keyword('AS'):
                table_alias = self.parse_ident()
            joins = self._parse_joins()
        if self.match_keyword('WHERE'):
            where = self._parse_expr()
        if self.match_keyword('GROUP'):
            self.expect_keyword('BY')
            group_by = [self._parse_expr()]
            while self.match(TT.COMMA):
                group_by.append(self._parse_expr())
        if self.match_keyword('HAVING'):
            having = self._parse_expr()
        if self.match_keyword('ORDER'):
            self.expect_keyword('BY')
            order_by = self._parse_order_by_list()
        if self.match_keyword('LIMIT'):
            limit = int(self.expect(TT.NUMBER).value)
        if self.match_keyword('OFFSET'):
            offset = int(self.expect(TT.NUMBER).value)
        return Select(columns=cols, from_table=from_table, joins=joins, where=where,
                       group_by=group_by, having=having, order_by=order_by,
                       limit=limit, offset=offset, distinct=distinct, table_alias=table_alias)

    def _parse_select_columns(self):
        if self.peek().type == TT.STAR:
            self.advance()
            return [WildCard()]
        cols = [self._parse_aliased_expr()]
        while self.match(TT.COMMA):
            cols.append(self._parse_aliased_expr())
        return cols

    def _parse_aliased_expr(self):
        expr = self._parse_expr()
        alias = None
        if self.match_keyword('AS'):
            alias = self.parse_ident()
        elif not self.at_end() and self.peek().type == TT.IDENT and not self.at_keyword('FROM','WHERE','JOIN','INNER','LEFT','RIGHT','CROSS','GROUP','ORDER','LIMIT','HAVING','ON','OFFSET'):
            alias = self.parse_ident()
        if alias:
            return AliasedExpr(expr, alias)
        return expr

    def _parse_order_by_list(self):
        items = [self._parse_order_by_item()]
        while self.match(TT.COMMA):
            items.append(self._parse_order_by_item())
        return items

    def _parse_order_by_item(self):
        expr = self._parse_expr()
        direction = 'ASC'
        if self.match_keyword('ASC'):
            direction = 'ASC'
        elif self.match_keyword('DESC'):
            direction = 'DESC'
        return OrderByItem(expr, direction)

    def _parse_joins(self):
        joins = []
        while True:
            jt = None
            if self.match_keyword('INNER'): jt = 'INNER'
            elif self.match_keyword('LEFT'): jt = 'LEFT'; self.match_keyword('OUTER')
            elif self.match_keyword('RIGHT'): jt = 'RIGHT'; self.match_keyword('OUTER')
            elif self.match_keyword('CROSS'): jt = 'CROSS'
            if jt is None and self.at_keyword('JOIN'):
                jt = 'INNER'
            if jt is None:
                break
            self.expect_keyword('JOIN')
            table = self.parse_ident()
            alias = None
            if self.match_keyword('AS'):
                alias = self.parse_ident()
            elif not self.at_keyword('ON','WHERE','GROUP','ORDER','LIMIT','HAVING') and not self.at_end() and self.peek().type == TT.IDENT:
                alias = self.parse_ident()
            on_cond = None
            if self.match_keyword('ON'):
                on_cond = self._parse_expr()
            joins.append(JoinClause(jt, table, alias, on_cond))
        return joins

    def _parse_insert(self):
        self.expect_keyword('INSERT')
        ignore = bool(self.match_keyword('IGNORE'))
        self.expect_keyword('INTO')
        table = self.parse_ident()
        columns = None
        if self.match(TT.LPAREN):
            columns = [self.parse_ident()]
            while self.match(TT.COMMA):
                columns.append(self.parse_ident())
            self.expect(TT.RPAREN)
        self.expect_keyword('VALUES')
        values = self._parse_values_list()
        return Insert(table, columns, values, ignore=ignore)

    def _parse_replace(self):
        self.expect_keyword('REPLACE')
        self.expect_keyword('INTO')
        table = self.parse_ident()
        columns = None
        if self.match(TT.LPAREN):
            columns = [self.parse_ident()]
            while self.match(TT.COMMA):
                columns.append(self.parse_ident())
            self.expect(TT.RPAREN)
        self.expect_keyword('VALUES')
        values = self._parse_values_list()
        return Insert(table, columns, values, replace=True)

    def _parse_values_list(self):
        all_values = [self._parse_value_row()]
        while self.match(TT.COMMA):
            all_values.append(self._parse_value_row())
        return all_values

    def _parse_value_row(self):
        self.expect(TT.LPAREN)
        vals = [self._parse_expr()]
        while self.match(TT.COMMA):
            vals.append(self._parse_expr())
        self.expect(TT.RPAREN)
        return vals

    def _parse_update(self):
        self.expect_keyword('UPDATE')
        table = self.parse_ident()
        self.expect_keyword('SET')
        assignments = self._parse_assignments()
        where = None
        if self.match_keyword('WHERE'):
            where = self._parse_expr()
        return Update(table, assignments, where)

    def _parse_assignments(self):
        assigns = [self._parse_assignment()]
        while self.match(TT.COMMA):
            assigns.append(self._parse_assignment())
        return assigns

    def _parse_assignment(self):
        col = self.parse_ident()
        self.expect(TT.OP, '=')
        val = self._parse_expr()
        return (col, val)

    def _parse_delete(self):
        self.expect_keyword('DELETE')
        self.expect_keyword('FROM')
        table = self.parse_ident()
        where = None
        if self.match_keyword('WHERE'):
            where = self._parse_expr()
        return Delete(table, where)

    def _parse_create(self):
        self.expect_keyword('CREATE')
        if self.match_keyword('UNIQUE'):
            return self._parse_create_index(unique=True)
        if self.at_keyword('INDEX'):
            return self._parse_create_index(unique=False)
        if self.at_keyword('VIEW'):
            return self._parse_create_view()
        if self.match_keyword('OR'):
            self.expect_keyword('REPLACE')
            return self._parse_create_view(or_replace=True)
        temporary = bool(self.match_keyword('TEMPORARY', 'TEMP'))
        self.expect_keyword('TABLE')
        if_not_exists = False
        if self.match_keyword('IF'):
            self.expect_keyword('NOT')
            self.expect_keyword('EXISTS')
            if_not_exists = True
        name = self.parse_ident()
        self.expect(TT.LPAREN)
        columns, constraints = self._parse_column_defs()
        self.expect(TT.RPAREN)
        return CreateTable(name, columns, constraints, if_not_exists, temporary)

    def _parse_column_defs(self):
        columns = []; constraints = []
        while True:
            if self.at_keyword('PRIMARY','UNIQUE','FOREIGN','CHECK','CONSTRAINT','INDEX','KEY'):
                constraints.append(self._parse_table_constraint())
            else:
                columns.append(self._parse_column_def())
            if not self.match(TT.COMMA):
                break
        return columns, constraints

    def _parse_column_def(self):
        name = self.parse_ident()
        data_type = self._parse_data_type()
        col_constraints = []
        while True:
            if self.match_keyword('PRIMARY'):
                self.expect_keyword('KEY')
                col_constraints.append('PRIMARY KEY')
            elif self.match_keyword('NOT'):
                self.expect_keyword('NULL')
                col_constraints.append('NOT NULL')
            elif self.at_keyword('NULL') and not self.at_keyword('NOT'):
                self.advance()
                col_constraints.append('NULL')
            elif self.match_keyword('UNIQUE'):
                col_constraints.append('UNIQUE')
            elif self.match_keyword('AUTO_INCREMENT'):
                col_constraints.append('AUTO_INCREMENT')
            elif self.match_keyword('DEFAULT'):
                val = self._parse_expr()
                col_constraints.append(('DEFAULT', val))
            elif self.match_keyword('CHECK'):
                self.expect(TT.LPAREN)
                expr = self._parse_expr()
                self.expect(TT.RPAREN)
                col_constraints.append(('CHECK', expr))
            elif self.match_keyword('REFERENCES'):
                ref_table = self.parse_ident()
                self.expect(TT.LPAREN)
                ref_col = self.parse_ident()
                self.expect(TT.RPAREN)
                col_constraints.append(('REFERENCES', ref_table, ref_col))
            else:
                break
        return ColumnDef(name, data_type, col_constraints)

    def _parse_data_type(self):
        t = self.peek()
        if t.type == TT.KEYWORD:
            type_name = self.advance().value
        elif t.type == TT.IDENT:
            type_name = self.advance().value.upper()
        else:
            raise ParseError(f"Expected data type, got {t.value}")
        if type_name in ('UNSIGNED','SIGNED','ZEROFILL'):
            next_t = self.peek()
            if next_t.type in (TT.KEYWORD, TT.IDENT):
                type_name = self.advance().value.upper() + ' ' + type_name
        length = None
        if self.match(TT.LPAREN):
            length = self.expect(TT.NUMBER).value
            if self.match(TT.COMMA):
                length += ',' + self.expect(TT.NUMBER).value
            self.expect(TT.RPAREN)
        if length:
            return f"{type_name}({length})"
        return type_name

    def _parse_table_constraint(self):
        name = None
        if self.match_keyword('CONSTRAINT'):
            name = self.parse_ident()
        if self.match_keyword('PRIMARY'):
            self.expect_keyword('KEY')
            self.expect(TT.LPAREN)
            cols = [self.parse_ident()]
            while self.match(TT.COMMA): cols.append(self.parse_ident())
            self.expect(TT.RPAREN)
            return ('PRIMARY KEY', cols, name)
        if self.match_keyword('UNIQUE'):
            self.match_keyword('KEY','INDEX')
            idx_name = None
            if self.peek().type == TT.IDENT:
                idx_name = self.parse_ident()
            self.expect(TT.LPAREN)
            cols = [self.parse_ident()]
            while self.match(TT.COMMA): cols.append(self.parse_ident())
            self.expect(TT.RPAREN)
            return ('UNIQUE', cols, name or idx_name)
        if self.match_keyword('FOREIGN'):
            self.expect_keyword('KEY')
            self.expect(TT.LPAREN)
            cols = [self.parse_ident()]
            while self.match(TT.COMMA): cols.append(self.parse_ident())
            self.expect(TT.RPAREN)
            self.expect_keyword('REFERENCES')
            ref_table = self.parse_ident()
            self.expect(TT.LPAREN)
            ref_cols = [self.parse_ident()]
            while self.match(TT.COMMA): ref_cols.append(self.parse_ident())
            self.expect(TT.RPAREN)
            on_delete = None; on_update = None
            while self.match_keyword('ON'):
                if self.match_keyword('DELETE'):
                    on_delete = self._parse_ref_action()
                elif self.match_keyword('UPDATE'):
                    on_update = self._parse_ref_action()
            return ('FOREIGN KEY', cols, ref_table, ref_cols, on_delete, on_update, name)
        if self.match_keyword('CHECK'):
            self.expect(TT.LPAREN)
            expr = self._parse_expr()
            self.expect(TT.RPAREN)
            return ('CHECK', expr, name)
        if self.match_keyword('INDEX','KEY'):
            idx_name = None
            if self.peek().type == TT.IDENT:
                idx_name = self.parse_ident()
            self.expect(TT.LPAREN)
            cols = [self.parse_ident()]
            while self.match(TT.COMMA): cols.append(self.parse_ident())
            self.expect(TT.RPAREN)
            return ('INDEX', cols, idx_name)
        raise ParseError(f"Unknown constraint at {self.peek().value}")

    def _parse_ref_action(self):
        if self.match_keyword('CASCADE'): return 'CASCADE'
        if self.match_keyword('RESTRICT'): return 'RESTRICT'
        if self.match_keyword('SET'):
            if self.match_keyword('NULL'): return 'SET NULL'
            self.expect_keyword('DEFAULT'); return 'SET DEFAULT'
        if self.match_keyword('NO'):
            self.expect_keyword('ACTION'); return 'NO ACTION'
        return 'RESTRICT'

    def _parse_create_index(self, unique=False):
        self.expect_keyword('INDEX')
        name = self.parse_ident()
        self.expect_keyword('ON')
        table = self.parse_ident()
        self.expect(TT.LPAREN)
        cols = [self.parse_ident()]
        while self.match(TT.COMMA): cols.append(self.parse_ident())
        self.expect(TT.RPAREN)
        return CreateIndex(name, table, cols, unique)

    def _parse_create_view(self, or_replace=False):
        self.expect_keyword('VIEW')
        name = self.parse_ident()
        self.expect_keyword('AS')
        select = self._parse_select()
        return CreateView(name, select, or_replace)

    def _parse_drop(self):
        self.expect_keyword('DROP')
        if self.match_keyword('TABLE'):
            if_exists = False
            if self.match_keyword('IF'):
                self.expect_keyword('EXISTS')
                if_exists = True
            name = self.parse_ident()
            return DropTable(name, if_exists)
        if self.match_keyword('INDEX'):
            name = self.parse_ident()
            table = None
            if self.match_keyword('ON'):
                table = self.parse_ident()
            return DropIndex(name, table)
        if self.match_keyword('VIEW'):
            if_exists = False
            if self.match_keyword('IF'):
                self.expect_keyword('EXISTS')
                if_exists = True
            name = self.parse_ident()
            return DropView(name, if_exists)
        raise ParseError(f"Expected TABLE/INDEX/VIEW after DROP")

    def _parse_alter(self):
        self.expect_keyword('ALTER')
        self.expect_keyword('TABLE')
        name = self.parse_ident()
        actions = []
        while True:
            if self.match_keyword('ADD'):
                self.match_keyword('COLUMN')
                col = self._parse_column_def()
                actions.append(('ADD', col))
            elif self.match_keyword('DROP'):
                self.match_keyword('COLUMN')
                col_name = self.parse_ident()
                actions.append(('DROP', col_name))
            elif self.match_keyword('MODIFY'):
                self.match_keyword('COLUMN')
                col = self._parse_column_def()
                actions.append(('MODIFY', col))
            elif self.match_keyword('RENAME'):
                if self.match_keyword('TO'):
                    new_name = self.parse_ident()
                    actions.append(('RENAME_TABLE', new_name))
                else:
                    self.expect_keyword('COLUMN')
                    old = self.parse_ident()
                    self.expect_keyword('TO')
                    new = self.parse_ident()
                    actions.append(('RENAME_COLUMN', old, new))
            else:
                break
            if not self.match(TT.COMMA):
                break
        return AlterTable(name, actions)

    def _parse_truncate(self):
        self.expect_keyword('TRUNCATE')
        self.match_keyword('TABLE')
        return TruncateTable(self.parse_ident())

    def _parse_rename(self):
        self.expect_keyword('RENAME')
        self.expect_keyword('TABLE')
        old = self.parse_ident()
        self.expect_keyword('TO')
        new = self.parse_ident()
        return RenameTable(old, new)

    def _parse_show(self):
        self.expect_keyword('SHOW')
        if self.match_keyword('TABLES'):
            return ShowTables()
        if self.match_keyword('COLUMNS'):
            self.expect_keyword('FROM')
            return ShowColumns(self.parse_ident())
        if self.match_keyword('CREATE'):
            self.expect_keyword('TABLE')
            return ShowCreateTable(self.parse_ident())
        if self.match_keyword('INDEXES','INDEX'):
            self.expect_keyword('FROM')
            return ShowIndexes(self.parse_ident())
        raise ParseError("Expected TABLES/COLUMNS/CREATE/INDEXES after SHOW")

    def _parse_describe(self):
        self.advance()  # DESCRIBE or DESC
        return DescribeTable(self.parse_ident())

    def _parse_explain(self):
        self.expect_keyword('EXPLAIN')
        query = self._parse_statement()
        return ExplainQuery(query)

    def _parse_start_transaction(self):
        self.expect_keyword('START')
        self.expect_keyword('TRANSACTION')
        return StartTransaction()

    def _parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self.match_keyword('OR'):
            right = self._parse_and()
            left = BinaryOp('OR', left, right)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self.match_keyword('AND'):
            right = self._parse_not()
            left = BinaryOp('AND', left, right)
        return left

    def _parse_not(self):
        if self.match_keyword('NOT'):
            return UnaryOp('NOT', self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self):
        left = self._parse_addition()
        if self.match_keyword('IS'):
            negated = bool(self.match_keyword('NOT'))
            self.expect_keyword('NULL')
            return IsNull(left, negated)
        negated = bool(self.match_keyword('NOT'))
        if self.match_keyword('IN'):
            self.expect(TT.LPAREN)
            if self.at_keyword('SELECT'):
                sq = self._parse_select()
                self.expect(TT.RPAREN)
                return InList(left, [SubQuery(sq)], negated)
            vals = [self._parse_expr()]
            while self.match(TT.COMMA):
                vals.append(self._parse_expr())
            self.expect(TT.RPAREN)
            return InList(left, vals, negated)
        if self.match_keyword('BETWEEN'):
            low = self._parse_addition()
            self.expect_keyword('AND')
            high = self._parse_addition()
            return BetweenExpr(left, low, high, negated)
        if self.match_keyword('LIKE'):
            pattern = self._parse_addition()
            node = BinaryOp('LIKE', left, pattern)
            if negated:
                return UnaryOp('NOT', node)
            return node
        if negated:
            self.pos -= 1  # put NOT back
        t = self.peek()
        if t.type == TT.OP and t.value in ('=','!=','<>','<','>','<=','>='):
            op = self.advance().value
            if op == '<>': op = '!='
            right = self._parse_addition()
            return BinaryOp(op, left, right)
        return left

    def _parse_addition(self):
        left = self._parse_multiplication()
        while self.peek().type == TT.OP and self.peek().value in ('+','-'):
            op = self.advance().value
            right = self._parse_multiplication()
            left = BinaryOp(op, left, right)
        return left

    def _parse_multiplication(self):
        left = self._parse_unary()
        while (self.peek().type == TT.STAR) or (self.peek().type == TT.OP and self.peek().value in ('/','%')):
            if self.peek().type == TT.STAR:
                self.advance()
                op = '*'
            else:
                op = self.advance().value
            right = self._parse_unary()
            left = BinaryOp(op, left, right)
        return left

    def _parse_unary(self):
        if self.peek().type == TT.OP and self.peek().value == '-':
            self.advance()
            return UnaryOp('-', self._parse_primary())
        if self.match_keyword('EXISTS'):
            self.expect(TT.LPAREN)
            sq = self._parse_select()
            self.expect(TT.RPAREN)
            return ExistsExpr(SubQuery(sq))
        return self._parse_primary()

    def _parse_primary(self):
        t = self.peek()
        # Parenthesized expression or subquery
        if t.type == TT.LPAREN:
            self.advance()
            if self.at_keyword('SELECT'):
                sq = self._parse_select()
                self.expect(TT.RPAREN)
                return SubQuery(sq)
            expr = self._parse_expr()
            self.expect(TT.RPAREN)
            return expr
        # NULL
        if t.type == TT.KEYWORD and t.value == 'NULL':
            self.advance()
            return Literal(None)
        # TRUE/FALSE
        if t.type == TT.KEYWORD and t.value == 'TRUE':
            self.advance()
            return Literal(True)
        if t.type == TT.KEYWORD and t.value == 'FALSE':
            self.advance()
            return Literal(False)
        # Numbers
        if t.type == TT.NUMBER:
            self.advance()
            val = float(t.value) if '.' in t.value else int(t.value)
            return Literal(val)
        # Strings
        if t.type == TT.STRING:
            self.advance()
            return Literal(t.value)
        # Placeholder
        if t.type == TT.PLACEHOLDER:
            self.advance()
            idx = self.placeholder_idx
            self.placeholder_idx += 1
            return Placeholder(idx)
        # CASE expression
        if t.type == TT.KEYWORD and t.value == 'CASE':
            return self._parse_case()
        # CAST expression
        if t.type == TT.KEYWORD and t.value == 'CAST':
            return self._parse_cast()
        # Functions and identifiers
        if t.type in (TT.KEYWORD, TT.IDENT):
            name = self.advance().value
            # Function call
            if self.peek().type == TT.LPAREN:
                return self._parse_function_call(name)
            # Dotted column ref (table.column)
            if self.match(TT.DOT):
                if self.peek().type == TT.STAR:
                    self.advance()
                    return WildCard(table=name.lower() if name == name.upper() else name)
                col = self.parse_ident()
                return ColumnRef(col, table=name.lower() if name == name.upper() else name)
            n = name.lower() if name == name.upper() and name not in ('COUNT','SUM','AVG','MIN','MAX') else name
            return ColumnRef(n)
        # Star
        if t.type == TT.STAR:
            self.advance()
            return WildCard()
        raise ParseError(f"Unexpected token in expression: {t.type}:{t.value}")

    def _parse_function_call(self, name):
        name_upper = name.upper()
        self.expect(TT.LPAREN)
        if self.match(TT.RPAREN):
            return FunctionCall(name_upper, [])
        distinct = bool(self.match_keyword('DISTINCT'))
        if self.peek().type == TT.STAR:
            self.advance()
            self.expect(TT.RPAREN)
            return FunctionCall(name_upper, [WildCard()], distinct)
        args = [self._parse_expr()]
        while self.match(TT.COMMA):
            args.append(self._parse_expr())
        self.expect(TT.RPAREN)
        return FunctionCall(name_upper, args, distinct)

    def _parse_case(self):
        self.expect_keyword('CASE')
        operand = None
        if not self.at_keyword('WHEN'):
            operand = self._parse_expr()
        whens = []
        while self.match_keyword('WHEN'):
            cond = self._parse_expr()
            self.expect_keyword('THEN')
            result = self._parse_expr()
            whens.append((cond, result))
        else_clause = None
        if self.match_keyword('ELSE'):
            else_clause = self._parse_expr()
        self.expect_keyword('END')
        return CaseExpr(operand, whens, else_clause)

    def _parse_cast(self):
        self.expect_keyword('CAST')
        self.expect(TT.LPAREN)
        expr = self._parse_expr()
        self.expect_keyword('AS')
        target = self._parse_data_type()
        self.expect(TT.RPAREN)
        return CastExpr(expr, target)


def parse_sql(sql):
    """Parse a SQL string and return an AST node."""
    tokens = tokenize(sql)
    parser = Parser(tokens)
    return parser.parse()
