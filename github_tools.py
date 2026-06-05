import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "artissce"  # Tu usuario
REPO_NAME = "catalogo-ventas" # Tu repo

def obtener_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def agregar_producto_json(nuevo_producto):
    """Descarga el JSON actual, le hace append y lo vuelve a subir"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/datos/productos.json"
    headers = obtener_headers()
    
    # 1. Leer el archivo actual para obtener el SHA y los datos viejos
    response = requests.get(url, headers=headers)
    sha = None
    productos = []
    
    if response.status_code == 200:
        data = response.json()
        sha = data['sha']
        contenido_decodificado = base64.b64decode(data['content']).decode('utf-8')
        try:
            productos = json.loads(contenido_decodificado).get("productos", [])
        except json.JSONDecodeError:
            productos = []
            
    # 2. Agregamos el nuevo producto a la lista que ya existía
    productos.append(nuevo_producto)
    nuevo_contenido = json.dumps({"productos": productos}, indent=2)
    
    # 3. Subimos la actualización con el SHA para no sobreescribir
    payload = {
        "message": f"feat: agregar {nuevo_producto.get('nombre', 'producto')}",
        "content": base64.b64encode(nuevo_contenido.encode('utf-8')).decode('utf-8'),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    res = requests.put(url, headers=headers, json=payload)
    return res.status_code in [200, 201]

def subir_imagen_a_github(nombre_archivo, bytes_imagen):
    """Sube una imagen y devuelve su URL pública cruda"""
    ruta = f"datos/imagenes/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ruta}"
    
    payload = {
        "message": f"assets: subir imagen {nombre_archivo}",
        "content": base64.b64encode(bytes_imagen).decode('utf-8'),
        "branch": "main"
    }
    
    response = requests.put(url, headers=obtener_headers(), json=payload)
    if response.status_code in [200, 201]:
        # Si se subió bien, devolvemos la URL pública para verla
        return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{ruta}"
    return None

def obtener_productos_json():
    """Descarga el JSON actual y lo devuelve como una lista de diccionarios de Python"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/datos/productos.json"
    headers = obtener_headers()
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        contenido_decodificado = base64.b64decode(data['content']).decode('utf-8')
        try:
            return json.loads(contenido_decodificado).get("productos", [])
        except json.JSONDecodeError:
            return []
    return []

def reemplazar_productos_json(nueva_lista, mensaje_commit):
    """Sobrescribe el JSON con una lista nueva (útil para Editar y Borrar)"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/datos/productos.json"
    headers = obtener_headers()
    
    # 1. Obtener el SHA actual
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json().get('sha')
        
    # 2. Preparar el nuevo contenido
    nuevo_contenido = json.dumps({"productos": nueva_lista}, indent=2)
    payload = {
        "message": mensaje_commit,
        "content": base64.b64encode(nuevo_contenido.encode('utf-8')).decode('utf-8'),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    # 3. Hacer el PUT
    res = requests.put(url, headers=headers, json=payload)
    return res.status_code in [200, 201]