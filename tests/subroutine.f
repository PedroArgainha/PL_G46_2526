PROGRAM TESTSUB
INTEGER A, B, C
PRINT *, 'Introduza dois numeros:'
READ *, A
READ *, B
CALL IMPRIME(A, B)
C = A + B
PRINT *, 'Soma: ', C
END

SUBROUTINE IMPRIME(X, Y)
INTEGER X, Y
PRINT *, 'Valor 1: ', X
PRINT *, 'Valor 2: ', Y
RETURN
END
