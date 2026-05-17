# fortran_parser.py
# Parser + geração de código EWVM para Fortran 77
# Usa ply.yacc e gera código diretamente nas regras

import ply.yacc as yacc
from fortran_lexer import tokens, build_lexer, preprocess

# ─── Tabela de símbolos ───────────────────────────────────────────────────────
class SymbolTable:
    def __init__(self):
        self.globals = {}       # nome -> {type, index, is_array, size}
        self.locals = {}        # nome -> {type, index}
        self.functions = {}     # nome -> {type, params}
        self.subroutines = {}   # nome -> {params}
        self.global_index = 0
        self.local_index = 0
        self.label_counter = 0
        self.in_subprogram = False
        self.current_func = None

    def declare_global(self, name, vtype, is_array=False, size=0):
        if name in self.globals:
            return
        #     raise Exception(f"Variável '{name}' já declarada")
        if is_array:
            info = {'type': vtype, 'index': self.global_index, 'is_array': True, 'size': size}
            self.global_index += size
        else:
            info = {'type': vtype, 'index': self.global_index, 'is_array': False, 'size': 1}
            self.global_index += 1
        self.globals[name] = info
        return info

    def declare_local(self, name, vtype):
        if name in self.locals:
            raise Exception(f"Variável local '{name}' já declarada")
        info = {'type': vtype, 'index': self.local_index}
        self.local_index += 1
        self.locals[name] = info
        return info

    def lookup(self, name):
        if self.in_subprogram and name in self.locals:
            return self.locals[name], 'local'
        if name in self.globals:
            return self.globals[name], 'global'
        return None, None

    def new_label(self):
        self.label_counter += 1
        return f"L{self.label_counter}"

    def reset_locals(self):
        self.locals = {}
        self.local_index = 0

# Instância global da tabela de símbolos
symtab = SymbolTable()
# Labels do Fortran (número -> label EWVM)
fortran_labels = {}
# Código de subprogramas (acumulado separadamente)
subprogram_code = []
# Tipo de declaração corrente
current_decl_type = None
# Lista de erros semânticos
error_list = []

def report_error(msg, lineno=None):
    """Regista um erro semântico."""
    if lineno:
        error_list.append(f"Erro semântico na linha {lineno}: {msg}")
    else:
        error_list.append(f"Erro semântico: {msg}")

def get_fortran_label(num):
    """Obtém ou cria label EWVM para label numérico Fortran."""
    if num not in fortran_labels:
        fortran_labels[num] = symtab.new_label()
    return fortran_labels[num]

# ─── Precedência de operadores ────────────────────────────────────────────────
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'EQ', 'NE', 'LT', 'GT', 'LE', 'GE'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS'),
)

# ─── Regras gramaticais ──────────────────────────────────────────────────────

# Programa principal
def p_program(p):
    '''program : PROGRAM ID NEWLINE declarations statements END NEWLINE optional_subprograms'''
    n_globals = symtab.global_index
    alloc = [f"PUSHN {n_globals}"] if n_globals > 0 else []
    code = ["START"] + alloc + p[5] + ["STOP"]
    if p[8]:
        code += p[8]
    p[0] = code

def p_program_no_end_nl(p):
    '''program : PROGRAM ID NEWLINE declarations statements END optional_subprograms'''
    n_globals = symtab.global_index
    alloc = [f"PUSHN {n_globals}"] if n_globals > 0 else []
    code = ["START"] + alloc + p[5] + ["STOP"]
    if p[7]:
        code += p[7]
    p[0] = code

# Subprogramas opcionais após END
def p_optional_subprograms(p):
    '''optional_subprograms : newline_padding subprogram_list
                            | subprogram_list
                            | empty'''
    if len(p) == 3:
        p[0] = p[2] if p[2] else []
    else:
        p[0] = p[1] if p[1] else []

def p_newline_padding(p):
    '''newline_padding : newline_padding NEWLINE
                       | NEWLINE'''
    pass

def p_subprogram_list(p):
    '''subprogram_list : subprogram_list newline_padding subprogram
                       | subprogram_list subprogram
                       | subprogram'''
    if len(p) == 4:
        p[0] = p[1] + p[3]
    elif len(p) == 3:
        p[0] = p[1] + p[2]
    else:
        p[0] = p[1]

# FUNCTION
def p_subprogram_function(p):
    '''subprogram : func_header NEWLINE declarations statements RETURN NEWLINE END NEWLINE
                  | func_header NEWLINE declarations statements RETURN NEWLINE END'''
    header = p[1]  # (fname, params)
    fname = header[0]
    params = header[1]
    symtab.in_subprogram = False
    n_locals = symtab.local_index
    code = [f"{fname}:"]
    if n_locals > 0:
        code += [f"PUSHN {n_locals}"]
    code += p[4]  # statements
    # Epilogue: guardar resultado num global dedicado e limpar locals
    n_params = len(params)
    ret_info = symtab.locals.get(fname)
    # Alocar global para valor de retorno se ainda não existir
    ret_global_name = f'__ret_{fname}'
    if ret_global_name not in symtab.globals:
        symtab.declare_global(ret_global_name, 'INTEGER')
    ret_global = symtab.globals[ret_global_name]
    if ret_info:
        code += [f"PUSHL {ret_info['index']}"]
        code += [f"STOREG {ret_global['index']}"]
    # Limpar locals (POP até SP = FP, seguro na EWVM)
    if n_locals > 0:
        code += [f"POP {n_locals}"]
    code += ["RETURN"]
    symtab.functions[fname] = {'type': 'INTEGER', 'params': params, 'n_locals': n_locals}
    symtab.reset_locals()
    p[0] = code

# Cabeçalho da função — ativa scope local e regista parâmetros
def p_func_header(p):
    '''func_header : INTEGER FUNCTION ID LPAREN param_list RPAREN'''
    fname = p[3]
    params = p[5]
    symtab.in_subprogram = True
    symtab.current_func = fname
    symtab.reset_locals()
    for i, param in enumerate(params):
        symtab.locals[param] = {'type': 'INTEGER', 'index': -(len(params) - i)}
    symtab.declare_local(fname, 'INTEGER')
    p[0] = (fname, params)

# SUBROUTINE
def p_subprogram_subroutine(p):
    '''subprogram : sub_header NEWLINE declarations statements RETURN NEWLINE END NEWLINE
                  | sub_header NEWLINE declarations statements RETURN NEWLINE END
                  | sub_header NEWLINE declarations statements END NEWLINE
                  | sub_header NEWLINE declarations statements END'''
    header = p[1]  # (sname, params)
    sname = header[0]
    params = header[1]
    symtab.in_subprogram = False
    n_locals = symtab.local_index
    code = [f"{sname}:"]
    if n_locals > 0:
        code += [f"PUSHN {n_locals}"]
    code += p[4]  # statements
    # Limpar locals
    if n_locals > 0:
        code += [f"POP {n_locals}"]
    code += ["RETURN"]
    symtab.subroutines[sname] = {'params': params, 'n_locals': n_locals}
    symtab.reset_locals()
    p[0] = code

# Cabeçalho da subroutine
def p_sub_header(p):
    '''sub_header : SUBROUTINE ID LPAREN param_list RPAREN
                  | SUBROUTINE ID'''
    sname = p[2]
    params = p[4] if len(p) == 6 else []
    symtab.in_subprogram = True
    symtab.current_func = sname
    symtab.reset_locals()
    for i, param in enumerate(params):
        symtab.locals[param] = {'type': 'INTEGER', 'index': -(len(params) - i)}
    p[0] = (sname, params)

# Lista de parâmetros
def p_param_list(p):
    '''param_list : param_list COMMA ID
                  | ID'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_param_list_empty(p):
    '''param_list : empty'''
    p[0] = []

# ─── Declarações ──────────────────────────────────────────────────────────────

def p_declarations(p):
    '''declarations : declarations declaration NEWLINE
                    | empty'''
    if len(p) == 4:
        p[0] = p[1]  # Declarações não geram código
    else:
        p[0] = []

def p_declaration(p):
    '''declaration : type_spec var_decl_list'''
    pass

def p_type_spec(p):
    '''type_spec : INTEGER
                 | REAL
                 | LOGICAL'''
    global current_decl_type
    current_decl_type = p[1]

def p_var_decl_list(p):
    '''var_decl_list : var_decl_list COMMA var_decl
                     | var_decl'''
    pass

def p_var_decl_simple(p):
    '''var_decl : ID'''
    if symtab.in_subprogram:
        # Não re-declarar parâmetros que já são locais
        if p[1] not in symtab.locals:
            symtab.declare_local(p[1], current_decl_type)
        else:
            # Apenas atualizar o tipo
            symtab.locals[p[1]]['type'] = current_decl_type
    else:
        symtab.declare_global(p[1], current_decl_type)

def p_var_decl_array(p):
    '''var_decl : ID LPAREN INTLIT RPAREN'''
    if symtab.in_subprogram:
        raise Exception("Arrays locais não suportados")
    symtab.declare_global(p[1], current_decl_type, is_array=True, size=p[3])

# ─── Statements ───────────────────────────────────────────────────────────────

def p_statements(p):
    '''statements : statements statement NEWLINE
                  | statements labeled_statement NEWLINE
                  | statements NEWLINE
                  | empty'''
    if len(p) == 4:
        p[0] = p[1] + p[2]
    elif len(p) == 3:
        p[0] = p[1]  # blank line, keep existing statements
    else:
        p[0] = []

def p_labeled_statement(p):
    '''labeled_statement : INTLIT statement'''
    label_num = p[1]
    stmt = p[2]
    # Verificar se este label é o fim de um DO loop
    loop_info = getattr(p.parser, 'loop_info', {}).get(label_num)
    if loop_info:
        info = loop_info['info']
        scope = loop_info['scope']
        loop_label = loop_info['loop_label']
        end_label = loop_info['end_label']
        step_code = loop_info.get('step_code', ["PUSHI 1"])
        # Executar o statement (geralmente CONTINUE -> NOP)
        code = stmt
        # Incrementar variável e voltar ao teste
        if scope == 'global':
            code += [f"PUSHG {info['index']}"]
        else:
            code += [f"PUSHL {info['index']}"]
        code += step_code + ["ADD"]
        if scope == 'global':
            code += [f"STOREG {info['index']}"]
        else:
            code += [f"STOREL {info['index']}"]
        code += [f"JUMP {loop_label}", f"{end_label}:"]
        p[0] = code
    else:
        label = get_fortran_label(label_num)
        p[0] = [f"{label}:"] + stmt

# Atribuição
def p_statement_assign(p):
    '''statement : ID EQUALS expression'''
    info, scope = symtab.lookup(p[1])
    if info is None:
        # Auto-declarar como INTEGER (Fortran implicit typing)
        info = symtab.declare_global(p[1], 'INTEGER')
        scope = 'global'
    if scope == 'global':
        p[0] = p[3] + [f"STOREG {info['index']}"]
    else:
        p[0] = p[3] + [f"STOREL {info['index']}"]

# Atribuição a elemento de array
def p_statement_assign_array(p):
    '''statement : ID LPAREN expression RPAREN EQUALS expression'''
    info, scope = symtab.lookup(p[1])
    if info is None or not info.get('is_array'):
        report_error(f"'{p[1]}' não é um array declarado", p.lineno(1))
    # Calcular endereço: base + (index - 1)
    # PUSHGP + PUSHI base_offset + PADD -> endereço base
    # Depois expression do índice - 1 -> PADD
    # Depois STORE 0
    idx_code = p[3]  # Código para calcular o índice
    val_code = p[6]  # Código para calcular o valor
    code = ["PUSHGP", f"PUSHI {info['index']}", "PADD"]
    code += idx_code + ["PUSHI 1", "SUB"]  # Fortran arrays são 1-based
    code += val_code
    code += ["STOREN"]
    p[0] = code

# IF-THEN-ELSE
def p_statement_if(p):
    '''statement : IF LPAREN expression RPAREN THEN NEWLINE statements ENDIF'''
    else_label = symtab.new_label()
    code = p[3] + [f"JZ {else_label}"] + p[7] + [f"{else_label}:"]
    p[0] = code

def p_statement_if_else(p):
    '''statement : IF LPAREN expression RPAREN THEN NEWLINE statements ELSE NEWLINE statements ENDIF'''
    else_label = symtab.new_label()
    end_label = symtab.new_label()
    code = p[3] + [f"JZ {else_label}"] + p[7] + [f"JUMP {end_label}"]
    code += [f"{else_label}:"] + p[10] + [f"{end_label}:"]
    p[0] = code


# DO loop
def p_statement_do(p):
    '''statement : DO INTLIT ID EQUALS expression COMMA expression'''
    var_name = p[3]
    label_num = p[2]
    info, scope = symtab.lookup(var_name)
    if info is None:
        info = symtab.declare_global(var_name, 'INTEGER')
        scope = 'global'
    
    loop_label = symtab.new_label()
    end_label = get_fortran_label(label_num)  # O CONTINUE com este label marca o fim
    
    # Inicializar variável de controlo
    if scope == 'global':
        init_code = p[5] + [f"STOREG {info['index']}"]
        loop_code = [f"{loop_label}:"]
        # Testar condição: var <= end
        loop_code += [f"PUSHG {info['index']}"] + p[7] + ["SUP", f"NOT", f"JZ {end_label}"]
    else:
        init_code = p[5] + [f"STOREL {info['index']}"]
        loop_code = [f"{loop_label}:"]
        loop_code += [f"PUSHL {info['index']}"] + p[7] + ["SUP", "NOT", f"JZ {end_label}"]

    # Guardar info do loop para o CONTINUE
    fortran_labels[label_num] = end_label  # Já criado
    
    # Precisamos guardar info extra para o CONTINUE gerar o incremento
    if not hasattr(p.parser, 'loop_info'):
        p.parser.loop_info = {}
    p.parser.loop_info[label_num] = {
        'var': var_name, 'info': info, 'scope': scope,
        'loop_label': loop_label, 'end_label': end_label
    }
    
    p[0] = init_code + loop_code

# DO loop com step
def p_statement_do_step(p):
    '''statement : DO INTLIT ID EQUALS expression COMMA expression COMMA expression'''
    var_name = p[3]
    label_num = p[2]
    info, scope = symtab.lookup(var_name)
    if info is None:
        info = symtab.declare_global(var_name, 'INTEGER')
        scope = 'global'
    
    loop_label = symtab.new_label()
    end_label = get_fortran_label(label_num)
    
    if scope == 'global':
        init_code = p[5] + [f"STOREG {info['index']}"]
        loop_code = [f"{loop_label}:"]
        loop_code += [f"PUSHG {info['index']}"] + p[7] + ["SUP", "NOT", f"JZ {end_label}"]
    else:
        init_code = p[5] + [f"STOREL {info['index']}"]
        loop_code = [f"{loop_label}:"]
        loop_code += [f"PUSHL {info['index']}"] + p[7] + ["SUP", "NOT", f"JZ {end_label}"]
    
    fortran_labels[label_num] = end_label
    
    if not hasattr(p.parser, 'loop_info'):
        p.parser.loop_info = {}
    p.parser.loop_info[label_num] = {
        'var': var_name, 'info': info, 'scope': scope,
        'loop_label': loop_label, 'end_label': end_label,
        'step_code': p[9]
    }
    
    p[0] = init_code + loop_code

# CONTINUE (fim de loop DO)
def p_statement_continue(p):
    '''statement : CONTINUE'''
    p[0] = ["NOP"]

# GOTO
def p_statement_goto(p):
    '''statement : GOTO INTLIT'''
    label = get_fortran_label(p[2])
    p[0] = [f"JUMP {label}"]

# STOP
def p_statement_stop(p):
    '''statement : STOP'''
    p[0] = ["STOP"]

# CALL (subroutine) com argumentos
def p_statement_call_args(p):
    '''statement : CALL ID LPAREN arg_list RPAREN'''
    sname = p[2]
    args = p[4]
    code = []
    for arg_code in args:
        code += arg_code
    code += [f"PUSHA {sname}", "CALL"]
    n_args = len(args)
    if n_args > 0:
        code += [f"POP {n_args}"]
    p[0] = code

# CALL (subroutine) sem argumentos
def p_statement_call_noargs(p):
    '''statement : CALL ID'''
    p[0] = [f"PUSHA {p[2]}", "CALL"]

def p_arg_list(p):
    '''arg_list : arg_list COMMA expression
               | expression'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]


# PRINT
def p_statement_print(p):
    '''statement : PRINT TIMES COMMA print_list'''
    p[0] = p[4] + ["WRITELN"]

def p_print_list(p):
    '''print_list : print_list COMMA print_item
                  | print_item'''
    if len(p) == 4:
        p[0] = p[1] + p[3]
    else:
        p[0] = p[1]

def p_print_item_expr(p):
    '''print_item : expression'''
    # Determinar tipo e usar WRITEI ou WRITEF
    p[0] = p[1] + ["WRITEI"]

def p_print_item_string(p):
    '''print_item : STRLIT'''
    escaped = p[1].replace('"', '\\"')
    p[0] = [f'PUSHS "{escaped}"', "WRITES"]

# READ
def p_statement_read(p):
    '''statement : READ TIMES COMMA read_list'''
    p[0] = p[4]

def p_read_list(p):
    '''read_list : read_list COMMA read_item
                 | read_item'''
    if len(p) == 4:
        p[0] = p[1] + p[3]
    else:
        p[0] = p[1]

def p_read_item(p):
    '''read_item : ID'''
    info, scope = symtab.lookup(p[1])
    if info is None:
        info = symtab.declare_global(p[1], 'INTEGER')
        scope = 'global'
    code = ["READ", "ATOI"]
    if scope == 'global':
        code += [f"STOREG {info['index']}"]
    else:
        code += [f"STOREL {info['index']}"]
    p[0] = code

def p_read_item_array(p):
    '''read_item : ID LPAREN expression RPAREN'''
    info, scope = symtab.lookup(p[1])
    if info is None or not info.get('is_array'):
        report_error(f"'{p[1]}' não é um array declarado", p.lineno(1))
    code = ["PUSHGP", f"PUSHI {info['index']}", "PADD"]
    code += p[3] + ["PUSHI 1", "SUB"]
    code += ["READ", "ATOI", "STOREN"]
    p[0] = code



# ─── Expressões ───────────────────────────────────────────────────────────────

# Aritméticas
def p_expression_binop(p):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression'''
    ops = {'+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV'}
    p[0] = p[1] + p[3] + [ops[p[2]]]

# Relacionais
def p_expression_relop(p):
    '''expression : expression EQ expression
                  | expression NE expression
                  | expression LT expression
                  | expression GT expression
                  | expression LE expression
                  | expression GE expression'''
    op_map = {
        '.EQ.': 'EQUAL', '.NE.': None, '.LT.': 'INF',
        '.GT.': 'SUP', '.LE.': 'INFEQ', '.GE.': 'SUPEQ'
    }
    op = p[2]
    if op == '.NE.':
        p[0] = p[1] + p[3] + ["EQUAL", "NOT"]
    else:
        p[0] = p[1] + p[3] + [op_map[op]]

# Lógicas
def p_expression_and(p):
    '''expression : expression AND expression'''
    p[0] = p[1] + p[3] + ["AND"]

def p_expression_or(p):
    '''expression : expression OR expression'''
    p[0] = p[1] + p[3] + ["OR"]

def p_expression_not(p):
    '''expression : NOT expression'''
    p[0] = p[2] + ["NOT"]

# Negação unária
def p_expression_uminus(p):
    '''expression : MINUS expression %prec UMINUS'''
    p[0] = ["PUSHI 0"] + p[2] + ["SUB"]

# Parêntesis
def p_expression_group(p):
    '''expression : LPAREN expression RPAREN'''
    p[0] = p[2]

# Literal inteiro
def p_expression_intlit(p):
    '''expression : INTLIT'''
    p[0] = [f"PUSHI {p[1]}"]

# Literal real
def p_expression_reallit(p):
    '''expression : REALLIT'''
    p[0] = [f"PUSHF {p[1]}"]

# Literal lógico
def p_expression_true(p):
    '''expression : TRUE'''
    p[0] = ["PUSHI 1"]

def p_expression_false(p):
    '''expression : FALSE'''
    p[0] = ["PUSHI 0"]

# Variável
def p_expression_id(p):
    '''expression : ID'''
    info, scope = symtab.lookup(p[1])
    if info is None:
        # Pode ser uma chamada de função sem parêntesis — tentar auto-declarar
        info = symtab.declare_global(p[1], 'INTEGER')
        scope = 'global'
    if scope == 'global':
        p[0] = [f"PUSHG {info['index']}"]
    else:
        p[0] = [f"PUSHL {info['index']}"]

# Acesso a array
def p_expression_array(p):
    '''expression : ID LPAREN expression RPAREN'''
    info, scope = symtab.lookup(p[1])
    if info and info.get('is_array'):
        # Acesso a array: base + (index - 1)
        code = ["PUSHGP", f"PUSHI {info['index']}", "PADD"]
        code += p[3] + ["PUSHI 1", "SUB"]
        code += ["LOADN"]
        p[0] = code
    elif p[1] == 'ABS':
        # ABS(x): se x < 0 então -x senão x
        lbl_pos = symtab.new_label()
        lbl_end = symtab.new_label()
        p[0] = p[3] + ["DUP 1", "PUSHI 0", "SUPEQ", f"JZ {lbl_pos}", f"JUMP {lbl_end}", f"{lbl_pos}:", "PUSHI -1", "MUL", f"{lbl_end}:"]
    else:
        # Chamada de função com 1 argumento
        fname = p[1]
        args_code = p[3]
        ret_global_name = f'__ret_{fname}'
        if ret_global_name not in symtab.globals:
            symtab.declare_global(ret_global_name, 'INTEGER')
        ret_idx = symtab.globals[ret_global_name]['index']
        code = args_code
        code += [f"PUSHA {fname}", "CALL"]
        code += ["POP 1"]
        code += [f"PUSHG {ret_idx}"]
        p[0] = code

# Funções intrínsecas e chamadas com 2 argumentos
def p_expression_two_args(p):
    '''expression : ID LPAREN expression COMMA expression RPAREN'''
    name = p[1]
    if name == 'MOD':
        p[0] = p[3] + p[5] + ["MOD"]
    elif name == 'MAX':
        # MAX(a,b): compara, depois re-avalia o maior
        lbl_b = symtab.new_label()
        lbl_end = symtab.new_label()
        code = p[3] + p[5]              # [a, b]
        code += ["SUP"]                 # a > b ? (consome ambos)
        code += [f"JZ {lbl_b}"]         # se não, b é maior
        code += p[3]                    # re-push a (o maior)
        code += [f"JUMP {lbl_end}"]
        code += [f"{lbl_b}:"]
        code += p[5]                    # re-push b (o maior)
        code += [f"{lbl_end}:"]
        p[0] = code
    elif name == 'MIN':
        # MIN(a,b): compara, depois re-avalia o menor
        lbl_b = symtab.new_label()
        lbl_end = symtab.new_label()
        code = p[3] + p[5]              # [a, b]
        code += ["INF"]                 # a < b ? (consome ambos)
        code += [f"JZ {lbl_b}"]         # se não, b é menor
        code += p[3]                    # re-push a (o menor)
        code += [f"JUMP {lbl_end}"]
        code += [f"{lbl_b}:"]
        code += p[5]                    # re-push b (o menor)
        code += [f"{lbl_end}:"]
        p[0] = code
    else:
        # Chamada de função com 2 argumentos
        fname = name
        n_args = 2
        ret_global_name = f'__ret_{fname}'
        if ret_global_name not in symtab.globals:
            symtab.declare_global(ret_global_name, 'INTEGER')
        ret_idx = symtab.globals[ret_global_name]['index']
        code = p[3] + p[5]
        code += [f"PUSHA {fname}", "CALL"]
        code += [f"POP {n_args}"]
        code += [f"PUSHG {ret_idx}"]
        p[0] = code

# Empty
def p_empty(p):
    '''empty :'''
    p[0] = None

# Erro sintático
def p_error(p):
    if p:
        msg = f"Erro sintático na linha {p.lineno}: token inesperado '{p.value}' (tipo {p.type})"
    else:
        msg = "Erro sintático: fim de ficheiro inesperado"
    error_list.append(msg)

# ─── Construir o parser ──────────────────────────────────────────────────────
def build_parser():
    """Constrói e retorna o parser Fortran 77."""
    import logging
    log = logging.getLogger('ply')
    log.setLevel(logging.ERROR)
    parser = yacc.yacc(debug=False, write_tables=False, errorlog=log)
    parser.loop_info = {}
    return parser

def compile_fortran(source):
    """Compila código Fortran 77 para instruções EWVM."""
    global symtab, fortran_labels, current_decl_type, error_list
    symtab = SymbolTable()
    fortran_labels = {}
    current_decl_type = None
    error_list = []
    
    lexer = build_lexer()
    parser = build_parser()
    
    # Pré-processar (remover comentários de linha)
    source = preprocess(source)
    
    # Garantir newline no final
    if not source.endswith('\n'):
        source += '\n'
    
    result = parser.parse(source, lexer=lexer)
    
    # Relatório de erros
    if error_list:
        import sys
        print("\n=== RELATÓRIO DE ERROS ===", file=sys.stderr)
        for i, err in enumerate(error_list, 1):
            print(f"  {i}. {err}", file=sys.stderr)
        print(f"\nTotal: {len(error_list)} erro(s) encontrado(s)", file=sys.stderr)
        raise Exception(f"Compilação falhou com {len(error_list)} erro(s)")
    
    if result is None:
        raise Exception("Falha na compilação")
    
    return '\n'.join(result)

# ─── Teste standalone ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 fortran_parser.py <ficheiro.f>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        source = f.read()
    
    try:
        code = compile_fortran(source)
        print(code)
    except Exception as e:
        print(f"Erro: {e}")
        sys.exit(1)
