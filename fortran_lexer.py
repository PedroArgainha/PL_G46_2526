# fortran_lexer.py
# Analisador léxico para um subconjunto de Fortran 77 (free-form)
# Usando PLY (ply.lex)

import ply.lex as lex
import logging
logging.getLogger('ply').setLevel(logging.ERROR)

# ─── Palavras reservadas ───────────────────────────────────────────────────────
reserved = {
    'PROGRAM':    'PROGRAM',
    'END':        'END',
    'INTEGER':    'INTEGER',
    'REAL':       'REAL',
    'LOGICAL':    'LOGICAL',
    'IF':         'IF',
    'THEN':       'THEN',
    'ELSE':       'ELSE',
    'ENDIF':      'ENDIF',
    'DO':         'DO',
    'CONTINUE':   'CONTINUE',
    'GOTO':       'GOTO',
    'READ':       'READ',
    'PRINT':      'PRINT',
    'STOP':       'STOP',
    'SUBROUTINE': 'SUBROUTINE',
    'FUNCTION':   'FUNCTION',
    'CALL':       'CALL',
    'RETURN':     'RETURN',
}

# ─── Lista de tokens ──────────────────────────────────────────────────────────
tokens = list(reserved.values()) + [
    # Literais
    'INTLIT',       # Literal inteiro: 42
    'REALLIT',      # Literal real: 3.14
    'STRLIT',       # Literal string: 'hello'

    # Valores lógicos
    'TRUE',         # .TRUE.
    'FALSE',        # .FALSE.

    # Operadores relacionais
    'EQ',           # .EQ.
    'NE',           # .NE.
    'LT',           # .LT.
    'GT',           # .GT.
    'LE',           # .LE.
    'GE',           # .GE.

    # Operadores lógicos
    'AND',          # .AND.
    'OR',           # .OR.
    'NOT',          # .NOT.

    # Operadores aritméticos
    'PLUS',         # +
    'MINUS',        # -
    'TIMES',        # *
    'DIVIDE',       # /

    # Delimitadores
    'LPAREN',       # (
    'RPAREN',       # )
    'COMMA',        # ,
    'EQUALS',       # =

    # Identificadores
    'ID',

    # Newline (separador de statements)
    'NEWLINE',
]

# ─── Tokens simples ───────────────────────────────────────────────────────────
t_PLUS    = r'\+'
t_MINUS   = r'-'
t_TIMES   = r'\*'
t_DIVIDE  = r'/'
t_LPAREN  = r'\('
t_RPAREN  = r'\)'
t_COMMA   = r','
t_EQUALS  = r'='

# ─── Tokens com ações ─────────────────────────────────────────────────────────

# Operadores relacionais Fortran (.EQ., .NE., etc.)
def t_EQ(t):
    r'\.EQ\.'
    return t

def t_NE(t):
    r'\.NE\.'
    return t

def t_LE(t):
    r'\.LE\.'
    return t

def t_GE(t):
    r'\.GE\.'
    return t

def t_LT(t):
    r'\.LT\.'
    return t

def t_GT(t):
    r'\.GT\.'
    return t

# Operadores lógicos
def t_AND(t):
    r'\.AND\.'
    return t

def t_OR(t):
    r'\.OR\.'
    return t

def t_NOT(t):
    r'\.NOT\.'
    return t

# Valores lógicos
def t_TRUE(t):
    r'\.TRUE\.'
    t.value = True
    return t

def t_FALSE(t):
    r'\.FALSE\.'
    t.value = False
    return t

# Literal real (deve vir antes do inteiro)
def t_REALLIT(t):
    r'\d+\.\d*|\.\d+'
    t.value = float(t.value)
    return t

# Literal inteiro
def t_INTLIT(t):
    r'\d+'
    t.value = int(t.value)
    return t

# Literal string (aspas simples do Fortran)
def t_STRLIT(t):
    r"'[^']*'"
    t.value = t.value[1:-1]  # Remover aspas
    return t

# Identificador ou keyword
def t_ID(t):
    r'[A-Za-z_][A-Za-z0-9_]*'
    # Verificar se é keyword (case insensitive no Fortran)
    upper = t.value.upper()
    if upper in reserved:
        t.type = reserved[upper]
        t.value = upper
    else:
        t.type = 'ID'
        t.value = upper  # Fortran é case insensitive
    return t

# Newline — significativo como separador de statements
def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

# Comentários inline com ! (em free-form Fortran)
def t_COMMENT(t):
    r'![^\n]*'
    pass  # Ignorar comentários inline

# Ignorar espaços e tabs
t_ignore = ' \t'

# Continuação de linha (& no final, como em free-form)
def t_CONTINUATION(t):
    r'&[ \t]*\n'
    t.lexer.lineno += 1
    pass  # Ignorar o & e o newline

# Erro léxico
def t_error(t):
    msg = f"Erro léxico na linha {t.lineno}: carácter inesperado '{t.value[0]}'"
    try:
        from fortran_parser import error_list
        error_list.append(msg)
    except ImportError:
        import sys
        print(msg, file=sys.stderr)
    t.lexer.skip(1)

# ─── Pré-processamento ────────────────────────────────────────────────────────
def preprocess(source):
    """Pré-processamento do código fonte. Em free-form, comentários são apenas com '!'
    (já tratados pelo lexer). Não removemos linhas com C/c/* pois podem ser código."""
    return source

# ─── Construir o lexer ────────────────────────────────────────────────────────
def build_lexer():
    """Constrói e retorna o lexer Fortran 77."""
    return lex.lex()

# ─── Teste standalone ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 fortran_lexer.py <ficheiro.f>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        data = f.read()
    
    lexer = build_lexer()
    lexer.input(data)
    
    for tok in lexer:
        print(tok)
