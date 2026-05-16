# compiler.py
# Ponto de entrada do compilador Fortran 77 → EWVM
# Processamento de Linguagens 2025-26

import sys
from fortran_parser import compile_fortran

def main():
    if len(sys.argv) < 2:
        print("Compilador Fortran 77 → EWVM")
        print(f"Uso: python3 {sys.argv[0]} <ficheiro.f> [ficheiro_saida.vm]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Ler ficheiro fonte
    try:
        with open(input_file, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Erro: ficheiro '{input_file}' não encontrado")
        sys.exit(1)
    
    # Compilar
    try:
        ewvm_code = compile_fortran(source)
    except Exception as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    
    # Output
    if output_file:
        with open(output_file, 'w') as f:
            f.write(ewvm_code + '\n')
        print(f"Código EWVM escrito em '{output_file}'")
    else:
        print(ewvm_code)

if __name__ == '__main__':
    main()
