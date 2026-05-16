PROGRAM NESTED
INTEGER I, J
DO 10 I = 1, 3
    DO 20 J = 1, 3
        PRINT *, I, ' x ', J, ' = ', I * J
    20 CONTINUE
10 CONTINUE
END
