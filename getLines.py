import os
import glob
import ast
import json
import re

# ==================================== PASO 1 - Definiciones ====================================
def safe_int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, (list, tuple)):
            for item in value:
                numero = safe_int(item, None)
                if numero is not None:
                    return numero
            return default
        texto = str(value).strip()
        try:
            evaluado = ast.literal_eval(texto)
            if evaluado != value:
                return safe_int(evaluado, default)
        except:
            pass
        texto = texto.strip("[]'\" ").replace(" ", "")
        return int(texto) if texto.isdigit() else default
    except:
        return default

def leer_archivo_texto(ruta):
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(ruta, "r", encoding=encoding) as archivo:
                return archivo.read()
        except UnicodeDecodeError:
            continue
    with open(ruta, "r", errors="ignore") as archivo:
        return archivo.read()

def formateo(lista_movimientos, mapa_cuentas):
    for mov in lista_movimientos:
        registro = mov["line22"]
        cuenta = mov.get("cuenta_banorte")
        
        config_cuenta = mapa_cuentas.get(cuenta, {})
        moneda = config_cuenta.get("moneda", "MXN")
        
        mov["moneda"] 				= moneda
        mov["pestana_destino"] 		= config_cuenta.get("pestana", "")
        mov["CodigoRegistro"]		= registro[0:2]
        mov["libre"]				= registro[2:6]
        mov["claveOficinaOrigen"]	= registro[6:10]
        mov["fechaOperacion"]     	= registro[10:16]
        mov["fechaValor"]         	= registro[16:22]
        mov["conceptoPropio"]     	= registro[22:27]
        mov["claveDebeoHaber"]    	= registro[27:28]
        mov["Importe"]            	= registro[28:42]
        
        try:
            mov["ImporteFloat"] 	= float(registro[28:40] + "." + registro[40:42])
        except Exception:
            mov["ImporteFloat"] 	= 0.0
            
        mov["noDocumento"]        	= registro[42:52]
        mov["referencia"]         	= registro[52:82].strip()
        mov["noMOVIMIENTO"]       	= registro[82:95].strip()
        
        linea23_raw = mov.get("line23", "")
        mov["descripcion"]        = linea23_raw.replace("2301", " ").strip()
        
        if mov["claveDebeoHaber"] == "1":
            mov["tipo"] = "Retiro"
        elif mov["claveDebeoHaber"] == "2":
            mov["tipo"] = "Deposito"

        if moneda == "USD":
            tc_match = re.search(r'TC:\s*([\d\.]+)', linea23_raw)
            mov["TC"] = float(tc_match.group(1)) if tc_match else ""            
            importe_match = re.search(r'IMPORTE OP:\s*([\d\,\.]+)', linea23_raw)
            mov["ImportePesos"] = importe_match.group(1).replace(',', '') if importe_match else ""
          

def preparar_movimiento(obj, cuenta, fuente, ruta):
    obj["cuenta_banorte"] = cuenta
    obj["fuente"] = fuente
    obj["archivo_fuente"] = os.path.basename(ruta)
    return obj

def parsear_archivo(ruta, fuente, cuentas_permitidas, dict_saldos, mapa_cuentas):
    contenido = leer_archivo_texto(ruta)
    mensaje = contenido.replace("/", "-").replace("\x00", "").split("\n")
    movimientos = []
    obj_temporal = {"line22": "", "line23": ""}
    cuenta_valida = False
    cuenta = None
    i = 0
    
    while i < len(mensaje):
        linea = mensaje[i]
        if linea[:2] == "11":
            if obj_temporal["line22"] != "" and cuenta_valida:
                movimientos.append(preparar_movimiento(obj_temporal, cuenta, fuente, ruta))
                obj_temporal = {"line22": "", "line23": ""}
                
            cuenta_actual = linea[25:35].strip()
            if cuenta_actual in cuentas_permitidas:
                cuenta = cuenta_actual
                cuenta_valida = True
                if fuente == "RES":
                    saldo_texto = linea[48:62].strip()
                    if saldo_texto.isdigit():
                        dict_saldos[cuenta] = "=" + str(int(saldo_texto) / 100.0)
            else:
                cuenta = None
                cuenta_valida = False

        elif linea[:2] == "22":
            if not cuenta_valida:
                i += 1
                continue
            if obj_temporal["line22"] != "":
                movimientos.append(preparar_movimiento(obj_temporal, cuenta, fuente, ruta))
            obj_temporal = {"line22": linea, "line23": ""}

        elif linea[:2] == "23":
            if not cuenta_valida:
                i += 1
                continue
            obj_temporal["line23"] += linea
            
        i += 1

    if obj_temporal["line22"] != "" and cuenta_valida:
        movimientos.append(preparar_movimiento(obj_temporal, cuenta, fuente, ruta))
        
    formateo(movimientos, mapa_cuentas)
    return movimientos

def obtener_sufijo_res(nombre):
    base = os.path.basename(nombre).upper()
    if not base.endswith(".RES"):
        return None
    sufijo = base[-8:-4]
    return sufijo if sufijo.isdigit() else None

def buscar_txt_relacionados(base_dir, ruta_res):
    sufijo = obtener_sufijo_res(ruta_res)
    if not sufijo:
        return []
    patrones = [
        os.path.join(base_dir, "*_" + str(sufijo) + ".TXT"),
        os.path.join(base_dir, "*" + str(sufijo) + ".TXT")
    ]
    candidatos = []
    for patron in patrones:
        candidatos.extend(glob.glob(patron))
    candidatos = [ruta for ruta in candidatos if os.path.isfile(ruta)]
    
    if not candidatos:
        return []
    elegido = max(candidatos, key=os.path.getmtime)
    return [elegido]

def fail_fast(mensaje_error):
    raise ValueError("[Business Exception]: " + str(mensaje_error))

# Puente de compatibilidad
for _nombre in [
    "os", "glob", "ast", "json", "re",
    "safe_int", "leer_archivo_texto", "formateo",
    "preparar_movimiento", "parsear_archivo", 
    "obtener_sufijo_res", "buscar_txt_relacionados", "fail_fast"
]:
    try:
        globals()[_nombre] = locals()[_nombre]
    except Exception:
        pass

# ==================================== PASO 2 - Inicialización ====================================
mapa_str = GetVar("mapaCuentas")
try:
    mapa_bruto = json.loads(mapa_str)
    mapa_cuentas = {str(k).strip(): v for k, v in mapa_bruto.items()}
except Exception:
    mapa_cuentas = {}

cuentas_permitidas = list(mapa_cuentas.keys())
saldos_iniciales = {}

# ==================================== PASO 3 - Lectura y Rutas ====================================
base_dir = str(GetVar("pathRes") or "").strip().strip('"')
if base_dir and not base_dir.endswith(("/", "\\")):
    base_dir += os.sep

nombre_res = str(GetVar("newFile") or "").strip().strip('"').strip("'")
if not nombre_res:
    fail_fast("La variable 'newFile' está vacía.")

ruta_res = os.path.join(base_dir, nombre_res)
if not os.path.isfile(ruta_res):
    fail_fast("No existe el archivo .RES en la ruta indicada: " + str(ruta_res))

# ==================================== PASO 4 - Extracción ====================================
movimientos_res = parsear_archivo(ruta_res, "RES", cuentas_permitidas, saldos_iniciales, mapa_cuentas)
archivos_txt = buscar_txt_relacionados(base_dir, ruta_res)
movimientos_txt = []

for ruta_txt in archivos_txt:
    aux_movs = parsear_archivo(ruta_txt, "TXT", cuentas_permitidas, saldos_iniciales, mapa_cuentas)
    movimientos_txt.extend(aux_movs)

# ==================================== PASO 5 - Deduplicación y Agrupación ====================================
# ==================================== PASO 5 - Deduplicación y Agrupación ====================================
unicos = {}
for movimiento in movimientos_res + movimientos_txt:
    numero = safe_int(movimiento.get("noMOVIMIENTO"), 0)
    cuenta = str(movimiento.get("cuenta_banorte", "")).strip()
    if numero <= 0:
        continue
    clave = cuenta + "_" + str(numero)
    if clave not in unicos:
        unicos[clave] = movimiento

movimientos_finales = list(unicos.values())
movimientos_finales.sort(key=lambda x: safe_int(x.get("noMOVIMIENTO"), 0))

agrupados = {}
# Generar estructura base con saldos iniciales
for cta, saldo in saldos_iniciales.items():
    cta_limpia = str(cta).strip()
    # Buscamos en el mapa ignorando espacios extra
    config_cuenta = mapa_cuentas.get(cta_limpia) or mapa_cuentas.get(cta_limpia + " ", {})
    
    agrupados[cta_limpia] = {
        "saldo_inicial": saldo,
        "moneda": config_cuenta.get("moneda", "MXN"),
        "pestana_destino": config_cuenta.get("pestana", cta_limpia),
        "movimientos": []
    }

# Llenar movimientos
for mov in movimientos_finales:
    cta_limpia = str(mov.get("cuenta_banorte", "")).strip()
    if cta_limpia not in agrupados:
        config_cuenta = mapa_cuentas.get(cta_limpia) or mapa_cuentas.get(cta_limpia + " ", {})
        agrupados[cta_limpia] = {
            "saldo_inicial": "=0.0", 
            "moneda": config_cuenta.get("moneda", "MXN"),
            "pestana_destino": config_cuenta.get("pestana", cta_limpia),
            "movimientos": []
        }
    agrupados[cta_limpia]["movimientos"].append(mov)
    
# ==================================== PASO 6 - Salida ====================================
SetVar("movimientosAgrupados", json.dumps(agrupados))

# Aseguramos que el IF de Rocketbot reciba un String literal
if len(agrupados) > 0:
    SetVar("hayMovimientosGlobal", "True")
else:
    SetVar("hayMovimientosGlobal", "False")
    
try:
    with open("dataHemoeco_V2.json", "w", encoding="utf-8") as archivo:
        json.dump(agrupados, archivo, indent=4, ensure_ascii=False)
except Exception as e:
    print("Advertencia: No se pudo guardar el JSON de respaldo.", e)