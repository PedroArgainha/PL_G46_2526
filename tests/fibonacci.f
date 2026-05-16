PROGRAM FIBONACCI
INTEGER N, I, A, B, TEMP
PRINT *, 'Quantos termos de Fibonacci?'
READ *, N
A = 0
B = 1
PRINT *, 'Sequencia de Fibonacci:'
DO 10 I = 1, N
    PRINT *, A
    TEMP = A + B
    A = B
    B = TEMP
10 CONTINUE
END
