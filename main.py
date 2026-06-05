import os
import json
import time
import csv
import io
import requests
from fastapi import FastAPI, Request
from google import genai
from dotenv import load_dotenv
from github_tools import agregar_producto_json, subir_imagen_a_github, obtener_productos_json, reemplazar_productos_json

load_dotenv()

app = FastAPI(title="Agente Catálogo Bot")
cliente_ia = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def responder_en_telegram(chat_id: int, texto: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto})

def enviar_documento_telegram(chat_id: int, nombre_archivo: str, contenido_bytes: bytes):
    """Envía un archivo binario/texto directamente al chat"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    archivos = {'document': (nombre_archivo, contenido_bytes)}
    requests.post(url, data={'chat_id': chat_id}, files=archivos)

def descargar_foto_telegram(file_id: str):
    url_get = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    res = requests.get(url_get).json()
    if res.get("ok"):
        file_path = res["result"]["file_path"]
        url_descarga = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        return requests.get(url_descarga).content
    return None

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    datos = await request.json()
    
    if "message" in datos:
        mensaje = datos["message"]
        chat_id = mensaje["chat"]["id"]
        
        texto_usuario = mensaje.get("text", "")
        if "caption" in mensaje:
            texto_usuario = mensaje["caption"]
            
        if not texto_usuario:
            responder_en_telegram(chat_id, "🤔 Necesito texto para entender qué quieres hacer.")
            return {"status": "ok"}
            
        responder_en_telegram(chat_id, "🧠 Analizando tu petición...")
        
        prompt = f"""
        Eres el enrutador principal de un catálogo de ventas. Analiza el texto del usuario.
        
        Intenciones posibles:
        - AGREGAR: Quiere meter un producto nuevo. Obligatorio: nombre y precio.
        - BUSCAR: Quiere saber si hay un producto.
        - BORRAR: Quiere eliminar un producto del catálogo.
        - EDITAR: Quiere cambiar el precio, stock o nombre de un producto que ya existe.
        - EXPORTAR: Pide descargar un reporte, excel, csv o lista completa.

        Devuelve ESTRICTAMENTE este JSON:
        {{
          "intencion": "AGREGAR|BUSCAR|BORRAR|EDITAR|EXPORTAR|DESCONOCIDO",
          "status": "ok o error",
          "mensaje_error": "Mensaje si falta precio al agregar, o si la intención es dudosa",
          "termino_busqueda": "Palabra clave principal para buscar, borrar o editar (vacío si no aplica)",
          "producto": {{
            "nombre": "nombre a agregar o el nuevo nombre al editar",
            "precio": 0.0,
            "stock": 1,
            "descripcion_corta": "desc"
          }}
        }}
        Texto: "{texto_usuario}"
        """
        
        try:
            respuesta = cliente_ia.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            texto_ia = respuesta.text.strip()
            if texto_ia.startswith("```json"): texto_ia = texto_ia.replace("json", "").replace("```", "").strip()
            elif texto_ia.startswith("```"): texto_ia = texto_ia.replace("", "").strip()
                
            datos_ia = json.loads(texto_ia)
            
            if datos_ia.get("status") == "error":
                responder_en_telegram(chat_id, f"⚠️ ¡Ojo! {datos_ia.get('mensaje_error')}")
                return {"status": "ok"}
                
            intencion = datos_ia.get("intencion", "DESCONOCIDO")
            termino = datos_ia.get("termino_busqueda", "").lower()
            productos_actuales = obtener_productos_json()
            
            # --- RUTAS DEL CRUD ---
            
            if intencion == "EXPORTAR":
                responder_en_telegram(chat_id, "📊 Generando archivo Excel/CSV...")
                # Crear CSV en memoria
                output = io.StringIO()
                if productos_actuales:
                    campos = ["nombre", "precio", "stock", "descripcion_corta", "imagen_url"]
                    escritor = csv.DictWriter(output, fieldnames=campos, extrasaction='ignore')
                    escritor.writeheader()
                    for p in productos_actuales:
                        escritor.writerow(p)
                else:
                    output.write("El catalogo esta vacio")
                
                # Enviar a Telegram
                enviar_documento_telegram(chat_id, "catalogo.csv", output.getvalue().encode('utf-8'))
                
            elif intencion == "BUSCAR":
                resultados = [p for p in productos_actuales if termino in p.get("nombre", "").lower() or termino in p.get("descripcion_corta", "").lower()]
                if resultados:
                    respuesta_txt = f"📦 Encontré:\n"
                    for p in resultados:
                        respuesta_txt += f"▫️ {p['nombre']} - ${p['precio']} (Stock: {p.get('stock',0)})\n"
                    responder_en_telegram(chat_id, respuesta_txt)
                else:
                    responder_en_telegram(chat_id, f"🤷‍♀️ No encontré nada relacionado con '{termino}'.")
                    
            elif intencion == "BORRAR":
                productos_filtrados = [p for p in productos_actuales if termino not in p.get("nombre", "").lower()]
                if len(productos_filtrados) < len(productos_actuales):
                    exito = reemplazar_productos_json(productos_filtrados, f"fix: borrar {termino}")
                    if exito: responder_en_telegram(chat_id, f"🗑️ Se eliminó '{termino}' del catálogo.")
                    else: responder_en_telegram(chat_id, "❌ Error al borrar en GitHub.")
                else:
                    responder_en_telegram(chat_id, f"No encontré ningún producto que coincida con '{termino}' para borrar.")

            elif intencion == "EDITAR":
                editado = False
                for p in productos_actuales:
                    if termino in p.get("nombre", "").lower():
                        # Actualizamos solo si la IA detectó cambios
                        nuevo_prod = datos_ia.get("producto", {})
                        if nuevo_prod.get("precio", 0) > 0: p["precio"] = nuevo_prod["precio"]
                        if nuevo_prod.get("stock") is not None: p["stock"] = nuevo_prod["stock"]
                        if nuevo_prod.get("descripcion_corta"): p["descripcion_corta"] = nuevo_prod["descripcion_corta"]
                        editado = True
                        break # Solo editamos el primero que coincida
                
                if editado:
                    exito = reemplazar_productos_json(productos_actuales, f"fix: actualizar {termino}")
                    if exito: responder_en_telegram(chat_id, f"✏️ ¡Se actualizó '{termino}' correctamente!")
                    else: responder_en_telegram(chat_id, "❌ Error al actualizar en GitHub.")
                else:
                    responder_en_telegram(chat_id, f"No encontré '{termino}' para editarlo.")
                    
            elif intencion == "AGREGAR":
                producto_final = datos_ia.get("producto", {})
                if "photo" in mensaje:
                    responder_en_telegram(chat_id, "📸 Procesando imagen...")
                    foto_id = mensaje["photo"][-1]["file_id"]
                    bytes_imagen = descargar_foto_telegram(foto_id)
                    if bytes_imagen:
                        url_imagen = subir_imagen_a_github(f"img_{int(time.time())}.jpg", bytes_imagen)
                        if url_imagen: producto_final["imagen_url"] = url_imagen

                exito = agregar_producto_json(producto_final)
                if exito: responder_en_telegram(chat_id, f"✅ ¡'{producto_final.get('nombre')}' agregado!")
                else: responder_en_telegram(chat_id, "❌ Error al guardar en GitHub.")
            
            else:
                responder_en_telegram(chat_id, "🤔 No entendí. Puedes Agregar, Buscar, Editar, Borrar o Exportar.")
                
        except Exception as e:
            responder_en_telegram(chat_id, f"❌ Ocurrió un error: {e}")

    return {"status": "ok"}