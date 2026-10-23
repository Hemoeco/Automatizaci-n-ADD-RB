import ast
import json

dict_raw = GetVar("dictMovimientos")
cuenta_actual = str(GetVar("cuentaActualFor")).strip()
mapa_cuentas_raw = GetVar("mapaCuentas")

if isinstance(dict_raw, str):
    dict_movimientos = ast.literal_eval(dict_raw)
else:
    dict_movimientos = dict_raw or {}

datos_cuenta = dict_movimientos.get(cuenta_actual) or {}
saldo_inicial = datos_cuenta.get("saldo_inicial")
lista_movimientos = datos_cuenta.get("movimientos")

nombre_pestana = datos_cuenta.get("pestana_destino")
moneda_cuenta = datos_cuenta.get("moneda")

SetVar("saldoCuentaActual", saldo_inicial)
SetVar("movimientosCuentaActual", lista_movimientos)
SetVar("tieneMovimientos", len(lista_movimientos) > 0)
SetVar("pestanaDestino", nombre_pestana)
SetVar("monedaActual", moneda_cuenta)