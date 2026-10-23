import ast
import json

def safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default

def formatear_fecha(texto_fecha):
    texto_str = str(texto_fecha or "").strip()
    if len(texto_str) < 6: return ""
    try:
        dia = int(texto_str[4:6])
        mes = int(texto_str[2:4])
        anio = int(texto_str[0:2])
        if mes < 1 or mes > 12 or dia < 1 or dia > 31: return ""
        return f"{dia:02d}/{mes:02d}/20{anio:02d}"
    except:
        return ""

def limpiar_texto(texto):
    return " ".join(str(texto or "").split())
  
def formatear_parrafo(texto, limite_palabras=10):
    texto_seguro = str(texto or "").replace('"', '""')
    palabras = texto_seguro.split()    
    lineas = [" ".join(palabras[i:i+limite_palabras]) for i in range(0, len(palabras), limite_palabras)]    
    cuerpo = '" & CHAR(10) & "'.join(lineas)
    return f'="{cuerpo}"'

fila_inicial = safe_int(GetVar("filasActualesPestana"), 0)
movs_nuevos_raw = GetVar("movimientosCuentaActual")
historial_raw = GetVar("movsRegistradosCuentaActual")
moneda_actual = str(GetVar("monedaActual") or "MXN").strip()

if isinstance(movs_nuevos_raw, str):
    try:
        movs_nuevos = ast.literal_eval(movs_nuevos_raw)
    except Exception:
        try:
            movs_nuevos = json.loads(movs_nuevos_raw)
        except Exception:
            movs_nuevos = []
else:
    movs_nuevos = movs_nuevos_raw if isinstance(movs_nuevos_raw, list) else []

if isinstance(historial_raw, str):
    try:
        historial = ast.literal_eval(historial_raw)
    except Exception:
        historial = []
else:
    historial = historial_raw if isinstance(historial_raw, list) else []

# 1. Parsear el historial de forma segura
historial_ids = set()
for fila in historial:
    if isinstance(fila, list) and len(fila) > 11:
        historial_ids.add(str(fila[11]).strip()) # Extraemos el ID de la Columna L
    elif isinstance(fila, list) and len(fila) == 1:
        # Respaldo por si Rocketbot llega a leer 1 sola columna accidentalmente
        historial_ids.add(str(fila[0]).strip())
    elif isinstance(fila, str):
         historial_ids.add(fila.strip())
        
ventana = safe_int(GetVar("filasRevisionMovimientos"), 0)

# 2. Filtrar y Deduplicar
ultimo_registrado = 0
for hid in historial_ids:
    val = safe_int(hid, 0)
    if val > ultimo_registrado:
        ultimo_registrado = val

movs_a_procesar = []
for mov in movs_nuevos:
    if isinstance(mov, dict):
        mov_id_str = str(mov.get("noMOVIMIENTO", "")).strip()
        numero = safe_int(mov_id_str, 0)
        fuente = mov.get("fuente", "RES")
        
        if not mov_id_str or mov_id_str in historial_ids:
            continue
            
        if fuente == "RES":
            if numero <= ultimo_registrado:
                continue
        elif fuente == "TXT":
            minimo = max(0, ultimo_registrado - ventana)
            if numero <= ultimo_registrado and numero < minimo:
                continue
                
        movs_a_procesar.append(mov)
        
# Obtener el saldo inicial del .RES
saldo_inicial_bruto = str(GetVar("saldoCuentaActual") or "0").replace("=", "").strip()
if not saldo_inicial_bruto: 
    saldo_inicial_bruto = "0"

# Identificar la última fecha registrada en Google Sheets para saber si es registro inicial y usar saldo inicial
fecha_ultima_fila = ""
if len(historial) > 0:
    ultima_fila = historial[-1]
    if isinstance(ultima_fila, list) and len(ultima_fila) > 2:
        fecha_ultima_fila = str(ultima_fila[2]).strip()

# 3. Generar Matriz Formateada
matriz_salida = []
fila_actual = fila_inicial
saldo_inyectado = False

for mov in movs_a_procesar:
    fila_actual += 1
    es_deposito = mov.get("tipo") == "Deposito"
    
    fecha_op = formatear_fecha(mov.get("fechaOperacion"))
    fecha_val = formatear_fecha(mov.get("fechaValor"))

    importe = float(mov.get("ImporteFloat", 0.0))
    deposito_val = importe if es_deposito else ""
    retiro_val = "" if es_deposito else importe
    
    cuenta_mov = mov.get("cuenta_banorte", "")
    
    mov_id_str = str(mov.get("noMOVIMIENTO", "")).strip()
    
    # Regla para Cuentas Alpha C (Nuevas)
    if cuenta_mov in ["0243171130", "0227890927"]:
        valor_ref = limpiar_texto(mov.get("conceptoPropio", ""))
        valor_descripcion = limpiar_texto(mov.get("referencia", ""))
    else:
        valor_ref = 0
        valor_descripcion = limpiar_texto(mov.get("conceptoPropio", ""))
        
    fecha_ultima_fila = fecha_op
    
    texto_bruto = limpiar_texto(mov.get('referencia', '')) + " " + limpiar_texto(mov.get('descripcion', ''))    
    desc_completa = formatear_parrafo(texto_bruto, 10)
    
    if moneda_actual == "MXN":
        fila = [
            "" if es_deposito else "",                                                   	# A - ID
            "Administración",                                                               # B - Sucursal
            fecha_op,                                                                       # C - Fecha Op.
            fecha_val,                                                                      # D - Fecha Valor
            valor_ref,                                                                      # E - Ref
            valor_descripcion,                                                              # F - Descripción
            "", #Antes: "NI" if es_deposito else mov.get("claveDebeoHaber", "1"),           # G - Cod. Transacción
            limpiar_texto(mov.get("claveOficinaOrigen", "")),                               # H - Suc (Bco)
            deposito_val,                                                                   # I - Depósito
            retiro_val,                                                                     # J - Retiro
            f'=K{fila_actual-1}+I{fila_actual}-J{fila_actual}',							# K - Saldo Copiado Portal (Es el saldo inicial si es el primer move del día)
            mov_id_str,                                                                     # L - Mov Portal (Folio)
            desc_completa,                                                                  # M - Descripción Detallada
            f'=K{fila_actual-1}+I{fila_actual}-J{fila_actual}',							# N - Saldo 
            f'=N{fila_actual}-K{fila_actual}',                                              # O - Circulando
            f'=N{fila_actual}', 															# P - Saldo Real
            "Administración",                                                               # Q - Sucursal
            ""                                                                              # R - Observaciones
        ]
        
    else:
        importe_pesos = mov.get("ImportePesos", "")
        tc_aplicado = mov.get("TC", "")
        
        dep_pesos_val = importe_pesos if es_deposito and importe_pesos != "" else ""
        ret_pesos_val = importe_pesos if not es_deposito and importe_pesos != "" else ""
        
        fila = [
            "" if es_deposito else "",                                                      # A - ID
            "Administración",                                                               # B - Sucursal
            fecha_op,                                                                       # C - Fecha Op.
            fecha_val,                                                                      # D - Fecha Valor
            valor_ref,                                                                      # E - Ref
            valor_descripcion,                                                              # F - Descripción
            "", #Antes: "NI" if es_deposito else mov.get("claveDebeoHaber", "1"),           # G - Cod. Transacción
            limpiar_texto(mov.get("claveOficinaOrigen", "")),                               # H - Suc (Bco)
            deposito_val,                                                                   # I - Depósito (USD)
            retiro_val,                                                                     # J - Retiro (USD)
            f'=K{fila_actual-1}+I{fila_actual}-J{fila_actual}',	 							# K - Saldo Copiado Portal
            mov_id_str,                                                                     # L - Mov Portal (Folio)
            desc_completa,                                                                  # M - Descripción Detallada
            f'=K{fila_actual-1}+I{fila_actual}-J{fila_actual}',								# N - Saldo (Es el saldo inicial si es el primer move del día)
            f'=N{fila_actual}-K{fila_actual}',                                              # O - Circulando
            f'=N{fila_actual}', 															# P - Saldo Real
            "Administración",                                                               # Q - Sucursal
            "",                                                                             # R - Observaciones
            f'=K{fila_actual}-P{fila_actual}',                                              # S - -
            "",                                                                             # T - Vacía
            f'=I{fila_actual}*W{fila_actual}',#Antes: dep_pesos_val,                        # U - Dep. Pesos
            f'=J{fila_actual}*W{fila_actual}',#Antes: ret_pesos_val,                        # V - Ret. Pesos
            f'=W{fila_actual-1}', #Antes: tc_aplicado,                                      # W - TC
            f'=K{fila_actual}*W{fila_actual}'                                               # X - Total Eg MN
        ]
        
    matriz_salida.append(fila)

SetVar("matrizEscribir", matriz_salida)
SetVar("cantidadEscribir", len(matriz_salida))