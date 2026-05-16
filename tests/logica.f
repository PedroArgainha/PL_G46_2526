PROGRAM LOGICA
INTEGER X
LOGICAL POSITIVO, PAR, AMBOS
PRINT *, 'Introduza um numero:'
READ *, X
POSITIVO = X .GT. 0
PAR = MOD(X, 2) .EQ. 0
AMBOS = POSITIVO .AND. PAR
IF (AMBOS) THEN
    PRINT *, X, ' e positivo e par'
ELSE
    IF (POSITIVO) THEN
        PRINT *, X, ' e positivo mas impar'
    ELSE
        IF (PAR) THEN
            PRINT *, X, ' e negativo e par'
        ELSE
            PRINT *, X, ' e negativo e impar'
        ENDIF
    ENDIF
ENDIF
END
