"""SQL Tokenizer for KonaDB."""
import re

# Token types
TT = type('TT', (), {
    'KEYWORD': 'KEYWORD', 'IDENT': 'IDENT', 'NUMBER': 'NUMBER',
    'STRING': 'STRING', 'OP': 'OP', 'COMMA': 'COMMA', 'DOT': 'DOT',
    'LPAREN': 'LPAREN', 'RPAREN': 'RPAREN', 'SEMICOLON': 'SEMICOLON',
    'STAR': 'STAR', 'EOF': 'EOF', 'PLACEHOLDER': 'PLACEHOLDER',
})

KEYWORDS = {
    'SELECT','FROM','WHERE','INSERT','INTO','VALUES','UPDATE','SET',
    'DELETE','CREATE','DROP','ALTER','TABLE','INDEX','VIEW','AS',
    'AND','OR','NOT','IN','BETWEEN','LIKE','IS','NULL','TRUE','FALSE',
    'JOIN','INNER','LEFT','RIGHT','CROSS','ON','ORDER','BY','ASC','DESC',
    'LIMIT','OFFSET','GROUP','HAVING','DISTINCT','ALL','EXISTS',
    'PRIMARY','KEY','FOREIGN','REFERENCES','UNIQUE','CHECK','DEFAULT',
    'AUTO_INCREMENT','NOT','NULL','INT','INTEGER','VARCHAR','TEXT',
    'FLOAT','DOUBLE','DECIMAL','BOOLEAN','BOOL','DATE','DATETIME',
    'TIMESTAMP','BLOB','JSON','ADD','MODIFY','COLUMN','RENAME','TO',
    'TRUNCATE','SHOW','TABLES','DESCRIBE','DESC','COLUMNS','INDEXES',
    'EXPLAIN','START','TRANSACTION','BEGIN','COMMIT','ROLLBACK',
    'IF','IFNULL','COALESCE','CAST','COUNT','SUM','AVG','MIN','MAX',
    'UPPER','LOWER','LENGTH','CONCAT','SUBSTRING','TRIM','NOW',
    'REPLACE','IGNORE','CASE','WHEN','THEN','ELSE','END',
    'CONSTRAINT','CASCADE','RESTRICT','ACTION','NO','FULL','OUTER',
    'USING','NATURAL','UNION','EXCEPT','INTERSECT','WITH','RECURSIVE',
    'TEMPORARY','TEMP','EXISTS','LIKE','REGEXP','MOD','DIV',
    'YEAR','MONTH','DAY','HOUR','MINUTE','SECOND',
}


class Token:
    __slots__ = ('type', 'value', 'pos')
    def __init__(self, type, value, pos=0):
        self.type = type
        self.value = value
        self.pos = pos
    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


def tokenize(sql):
    """Tokenize a SQL string into a list of Token objects."""
    tokens = []
    i = 0
    s = sql.strip()
    n = len(s)

    while i < n:
        # Skip whitespace
        if s[i].isspace():
            i += 1
            continue

        # Skip comments
        if s[i:i+2] == '--':
            while i < n and s[i] != '\n':
                i += 1
            continue
        if s[i:i+2] == '/*':
            end = s.find('*/', i + 2)
            i = end + 2 if end != -1 else n
            continue

        # Numbers
        if s[i].isdigit() or (s[i] == '.' and i + 1 < n and s[i+1].isdigit()):
            j = i
            has_dot = False
            while j < n and (s[j].isdigit() or (s[j] == '.' and not has_dot)):
                if s[j] == '.':
                    has_dot = True
                j += 1
            tokens.append(Token(TT.NUMBER, s[i:j], i))
            i = j
            continue

        # Strings (single or double quoted)
        if s[i] in ("'", '"'):
            quote = s[i]
            j = i + 1
            val = []
            while j < n:
                if s[j] == '\\' and j + 1 < n:
                    val.append(s[j+1])
                    j += 2
                elif s[j] == quote:
                    if j + 1 < n and s[j+1] == quote:
                        val.append(quote)
                        j += 2
                    else:
                        j += 1
                        break
                else:
                    val.append(s[j])
                    j += 1
            tokens.append(Token(TT.STRING, ''.join(val), i))
            i = j
            continue

        # Backtick-quoted identifiers
        if s[i] == '`':
            j = i + 1
            while j < n and s[j] != '`':
                j += 1
            tokens.append(Token(TT.IDENT, s[i+1:j], i))
            i = j + 1
            continue

        # Placeholder ?
        if s[i] == '?':
            tokens.append(Token(TT.PLACEHOLDER, '?', i))
            i += 1
            continue

        # Two-char operators
        if i + 1 < n and s[i:i+2] in ('!=', '<>', '<=', '>=', ':='):
            tokens.append(Token(TT.OP, s[i:i+2], i))
            i += 2
            continue

        # Single-char tokens
        ch = s[i]
        if ch == '(':
            tokens.append(Token(TT.LPAREN, '(', i))
        elif ch == ')':
            tokens.append(Token(TT.RPAREN, ')', i))
        elif ch == ',':
            tokens.append(Token(TT.COMMA, ',', i))
        elif ch == '.':
            tokens.append(Token(TT.DOT, '.', i))
        elif ch == ';':
            tokens.append(Token(TT.SEMICOLON, ';', i))
        elif ch == '*':
            tokens.append(Token(TT.STAR, '*', i))
        elif ch in '+-/%=<>!&|^~':
            tokens.append(Token(TT.OP, ch, i))
        else:
            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                j = i
                while j < n and (s[j].isalnum() or s[j] == '_'):
                    j += 1
                word = s[i:j]
                if word.upper() in KEYWORDS:
                    tokens.append(Token(TT.KEYWORD, word.upper(), i))
                else:
                    tokens.append(Token(TT.IDENT, word, i))
                i = j
                continue
            else:
                i += 1
                continue
        i += 1

    tokens.append(Token(TT.EOF, '', i))
    return tokens
