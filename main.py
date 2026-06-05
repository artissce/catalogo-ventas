import os
import json
import requests
from fastapi import FastAPI, Request
from google import genai
from dotenv import load_dotenv
from github_tools import crear_archivo_en_github

# Cargar las llaves
load_dotenv()

# Inicializar servicios
app = FastAPI(title="Agente Catálogo Bot")
cliente_ia = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def responder_en_telegram(chat_id: int, texto: str):
    """Envía un mensaje de vuelta al chat de Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto})

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    """Este es el endpoint que Telegram va a golpear cada vez que alguien escriba"""
    datos = await request.json()
    
    # Validamos que el JSON de Telegram traiga un mensaje de texto
    if "message" in datos and "text" in datos["message"]:
        chat_id = datos["message"]["chat"]["id"]
        mensaje_usuario = datos["message"]["text"]
        
        # Le avisamos a tu prima que la IA está trabajando
        responder_en_telegram(chat_id, "🧠 Analizando tu producto...")
        
        # --- EL CEREBRO ---
        prompt = f"""
        Eres el asistente de un catálogo de ventas. 
        Extrae la información y devuelve ESTRICTAMENTE este JSON, sin texto extra:
        {{
          "nombre": "producto",
          "precio": 0.0,
          "stock": 0,
          "descripcion_corta": "frase con emojis"
        }}
        Mensaje: "{mensaje_usuario}"
        """
        
        try:
            respuesta = cliente_ia.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            # --- NUEVA LÓGICA DE LIMPIEZA ---
            texto_ia = respuesta.text.strip()
            
            # Le quitamos las etiquetas de Markdown si la IA se las puso
            if texto_ia.startswith("```json"):
                texto_ia = texto_ia.replace("```json", "").replace("```", "").strip()
            elif texto_ia.startswith("```"):
                texto_ia = texto_ia.replace("```", "").strip()
                
            datos_producto = json.loads(texto_ia)
            # --------------------------------
            
            contenido_github = json.dumps({"productos": [datos_producto]}, indent=2)
            
            # --- LAS MANOS ---
            resultado_git = crear_archivo_en_github(
                ruta_archivo="datos/productos.json",
                contenido=contenido_github,
                mensaje_commit=f"feat: agregar {datos_producto['nombre']}"
            )
            
            # Confirmación de éxito
            responder_en_telegram(chat_id, f"✅ ¡Listo! {resultado_git}\n📦 Producto registrado: {datos_producto['nombre']}")
            
        except Exception as e:
            responder_en_telegram(chat_id, f"❌ Ocurrió un error en el sistema: {e}")

    # Siempre hay que devolver un 200 OK rápido para que Telegram no reintente mandar el mensaje
    return {"status": "ok"}