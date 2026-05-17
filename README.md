# Compilador Fortran 77 → EWVM

Compilador para um subconjunto de **Fortran 77** (free-form), implementado em Python 3 com [PLY](https://www.dabeaz.com/ply/).  
Gera código para a máquina virtual **EWVM** ([ewvm.epl.di.uminho.pt](https://ewvm.epl.di.uminho.pt/)).

**Unidade Curricular:** Processamento de Linguagens — 2025/2026  
**Universidade do Minho** — Licenciatura em Engenharia Informática

## Autores

| Nome | Número |
|------|--------|
| Filipe Viana | a104361 |
| Pedro Argainha | a104351 |
| João Nuno | a104084 |

## Estrutura do Repositório

```
├── compiler.py           # Ponto de entrada do compilador
├── fortran_lexer.py      # Analisador léxico (ply.lex)
├── fortran_parser.py     # Analisador sintático + geração de código (ply.yacc)
├── Relatorio.pdf         # Relatório técnico
├── tests/                # Programas de teste (.f) e código VM gerado (.vm)
│   ├── hello.f / .vm
│   ├── fatorial.f / .vm
│   ├── primo.f / .vm
│   ├── somaarr.f / .vm
│   ├── conversor.f / .vm
│   ├── subroutine.f / .vm
│   ├── fibonacci.f / .vm
│   ├── tabuada.f / .vm
│   ├── logica.f / .vm
│   └── maxmin.f / .vm
```

## Pré-requisitos

- Python 3.x
- Biblioteca PLY: `pip install ply`

## Utilização

```bash
# Compilar um programa Fortran
python3 compiler.py tests/hello.f

# Guardar o output num ficheiro .vm
python3 compiler.py tests/fatorial.f > tests/fatorial.vm
```

O código EWVM gerado pode ser colado na [EWVM](https://ewvm.epl.di.uminho.pt/) para execução.

## Funcionalidades

### Obrigatórias
- Análise léxica com `ply.lex` (keywords, operadores, literais)
- Análise sintática com `ply.yacc` (gramática LALR(1))
- Análise semântica (tabela de símbolos, verificação de tipos)
- Declaração de variáveis (`INTEGER`, `REAL`, `LOGICAL`) e arrays
- Expressões aritméticas, lógicas e relacionais
- Controlo de fluxo: `IF-THEN-ELSE`, `DO` loops com labels, `GOTO`
- Input/Output: `READ`, `PRINT`

### Valorização
- Subprogramas: `FUNCTION` e `SUBROUTINE`
- Chamada de subprogramas: `CALL` com argumentos
- Funções intrínsecas: `MOD`, `ABS`, `MAX`, `MIN`
