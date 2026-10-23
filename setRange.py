import ast

SetVar("movsRegistradosCuentaActual", [])

pestana = GetVar("pestanaDestino").strip()
filas_actuales = int(GetVar("filasActualesPestana"))
ventana = int(GetVar("filasRevisionMovimientos"))

if filas_actuales < 2:
    filas_actuales = 222

inicio = max(2, filas_actuales - ventana + 1)

rango_lectura = pestana + "!L" + str(inicio) + ":L" + str(filas_actuales)
SetVar("rangoLecturaActual", rango_lectura)
