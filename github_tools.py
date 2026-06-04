import os
from dotenv import load_dotenv
from github import Github, Auth
from github.GithubException import GithubException

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "artissce/catalogo-ventas"

def crear_archivo_en_github(ruta_archivo: str, contenido: str, mensaje_commit: str) -> str:
    """
    Crea o actualiza un archivo en el repositorio de GitHub de forma segura.
    """
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(REPO_NAME)
        
        try:
            # 1. Intentamos leer el archivo para ver si ya existe
            archivo_existente = repo.get_contents(ruta_archivo, ref="main")
            
            # 2. Si no explotó, significa que existe. Lo actualizamos usando su SHA.
            repo.update_file(
                path=ruta_archivo,
                message=mensaje_commit,
                content=contenido,
                sha=archivo_existente.sha,
                branch="main"
            )
            return f"Éxito: Archivo '{ruta_archivo}' actualizado correctamente."
            
        except GithubException as e:
            # 3. Si da error 404, significa que el archivo es nuevo. Lo creamos.
            if e.status == 404:
                repo.create_file(
                    path=ruta_archivo,
                    message=mensaje_commit,
                    content=contenido,
                    branch="main"
                )
                return f"Éxito: Archivo '{ruta_archivo}' creado por primera vez."
            else:
                # Si es otro tipo de error, lo lanzamos
                raise e
                
    except GithubException as e:
        return f"Error de GitHub: {e.data.get('message', str(e))}"
        
# --- ZONA DE PRUEBAS ---
if __name__ == "__main__":
    # Vamos a simular que el agente decidió crear la base de datos vacía
    json_inicial = '{\n  "productos": []\n}'
    
    resultado = crear_archivo_en_github(
        ruta_archivo="datos/productos.json",
        contenido=json_inicial,
        mensaje_commit="chore: inicializar base de datos de productos"
    )
    
    print(resultado)