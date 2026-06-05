import os
import json
import time
import requests
from fastapi import FastAPI, Request
from google import genai
from dotenv import load_dotenv
from github_tools import agregar_producto_json, subir_imagen_a_github

load_dotenv()

app = FastAPI(title="Agente Catálogo Bot")
cliente_ia = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def responder_en_telegram(chat_id: int, texto: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto})

def descargar_foto_telegram(file_id: str):
    """Pide a Telegram el archivo real y descarga sus bytes"""
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
        
        # 1. Detectar si hay texto o el "caption" de una foto
        texto_usuario = mensaje.get("text", "")
        if "caption" in mensaje:
            texto_usuario = mensaje["caption"]
            
        if not texto_usuario:
            responder_en_telegram(chat_id, "🤔 Me mandaste algo sin texto. Escribe el nombre y precio del producto.")
            return {"status": "ok"}
            
        responder_en_telegram(chat_id, "🧠 Analizando producto...")
        
        # 2. EL CEREBRO CON EDGE CASES
        prompt = f"""
        Eres un validador de datos para un catálogo. Analiza el siguiente texto de un usuario.
        Si falta el precio o el nombre del producto, marca error.
        Devuelve ESTRICTAMENTE este JSON:
        {{
          "status": "ok" o "error",
          "mensaje_error": "Mensaje amistoso avisando qué falta (vacío si todo está ok)",
          "producto": {{
            "nombre": "nombre",
            "precio": 0.0,
            "stock": 1,
            "descripcion_corta": "desc"
          }}
        }}
        Texto: "{texto_usuario}"
        """
        
        try:
            respuesta = cliente_ia.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            # Limpieza de Markdown
            texto_ia = respuesta.text.strip()
            if texto_ia.startswith("```json"):
                texto_ia = texto_ia.replace("```json", "").replace("```", "").strip()
            elif texto_ia.startswith("```"):
                texto_ia = texto_ia.replace("```", "").strip()
                
            datos_ia = json.loads(texto_ia)
            
            # Validar Edge Cases (Falta precio o nombre)
            if datos_ia["status"] == "error":
                responder_en_telegram(chat_id, f"⚠️ ¡Ojo! {datos_ia['mensaje_error']}")
                return {"status": "ok"}
                
            producto_final = datos_ia["producto"]
            
            # 3. MANEJO DE IMÁGENES
            if "photo" in mensaje:
                responder_en_telegram(chat_id, "📸 Procesando imagen...")
                # Telegram manda varios tamaños, agarramos el último (el más grande)
                foto_id = mensaje["photo"][-1]["file_id"]
                bytes_imagen = descargar_foto_telegram(foto_id)
                
                if bytes_imagen:
                    # Generamos un nombre único con el timestamp
                    nombre_archivo = f"img_{int(time.time())}.jpg"
                    url_imagen = subir_imagen_a_github(nombre_archivo, bytes_imagen)
                    if url_imagen:
                        producto_final["imagen_url"] = url_imagen

            # 4. LAS MANOS
            exito = agregar_producto_json(producto_final)
            if exito:
                responder_en_telegram(chat_id, f"✅ ¡Producto '{producto_final['nombre']}' agregado con éxito y sin sobreescribir nada!")
            else:
                responder_en_telegram(chat_id, "❌ No pude guardar en GitHub. Revisa los logs.")
                
        except Exception as e:
            responder_en_telegram(chat_id, f"❌ Ocurrió un error en el sistema: {e}")

    return {"status": "ok"}