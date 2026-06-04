import requests

def enviar_mensaje_telegram(mensaje: str) -> str:
    """
    Envía un mensaje de texto a tu chat de Telegram.
    Usa esta herramienta cuando necesites notificar al usuario sobre un evento, 
    un resumen del día, o simplemente para mantener la racha de comunicación.
    
    Args:
        mensaje (str): El texto exacto que quieres enviar.
        
    Returns:
        str: Un mensaje de éxito o el detalle del error.
    """
    token = "TU_TOKEN_DE_BOTFATHER"
    chat_id = "AAHKg1XX6tvViR8CtY8o51DDLvKzOjjZU-4"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    respuesta = requests.post(url, json={"chat_id": chat_id, "text": mensaje})
    
    if respuesta.status_code == 200:
        return "Mensaje enviado exitosamente."
    return f"Error al enviar: {respuesta.text}"

def buscar_noticias_tech() -> str:
    """
    Busca los titulares de tecnología más importantes del día.
    Usa esta herramienta para tener contexto antes de redactar un mensaje.
    """
    # Aquí iría un request a una API de noticias o un scraping básico
    return "1. Nuevo modelo de IA lanzado. 2. Vulnerabilidad en Kubernetes parcheada."