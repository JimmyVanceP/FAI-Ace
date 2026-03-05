# handler.py - Versión para z-image turbo con soporte de carpeta LoRA
import runpod
import json
import requests
import time
import os
import subprocess
import base64
import urllib.parse

COMFYUI_URL = "http://127.0.0.1:8188"

# Modelos requeridos para el workflow z-image turbo
# NOTA: Las LoRAs NO son obligatorias - se cargan dinámicamente según el workflow
REQUIRED_MODELS = {
    "unet": "z_image_turbo_bf16.safetensors",
    "clip": "qwen_3_4b.safetensors",
    "vae": "ae.safetensors"
    # Las LoRAs se detectan dinámicamente según lo que pida el workflow
}


def log_system_info():
    """Loggear información completa del sistema"""
    print("=" * 60)
    print("DEBUG: Verificando sistema de archivos")
    print("=" * 60)

    print("\n--- Verificando /runpod-volume (Serverless) ---")
    if os.path.exists("/runpod-volume"):
        print("/runpod-volume EXISTE")
        result = subprocess.run(["ls", "-la", "/runpod-volume"], capture_output=True, text=True)
        print(result.stdout)

        if os.path.exists("/runpod-volume/models"):
            print("\nContenido de /runpod-volume/models:")
            result = subprocess.run(["ls", "-la", "/runpod-volume/models"], capture_output=True, text=True)
            print(result.stdout)

            # Verificar todas las carpetas de modelos incluyendo loras
            for subdir in ["checkpoints", "unet", "vae", "clip", "loras"]:
                path = f"/runpod-volume/models/{subdir}"
                if os.path.exists(path):
                    result = subprocess.run(["ls", "-la", path], capture_output=True, text=True)
                    print(f"\n{path}:\n{result.stdout}")
                else:
                    print(f"\n{path}: (carpeta vacía o no existe)")
    else:
        print("/runpod-volume NO EXISTE")

    print("\n--- Verificando /workspace (Pods) ---")
    if os.path.exists("/workspace"):
        print("/workspace EXISTE")
        if os.path.exists("/workspace/models/unet"):
            result = subprocess.run(["ls", "-la", "/workspace/models/unet"], capture_output=True, text=True)
            print(f"unet: {result.stdout}")

    print("\n--- Verificando extra_model_paths.yaml ---")
    config_path = "/comfyui/extra_model_paths.yaml"
    if os.path.exists(config_path):
        print(f"Archivo existe en: {config_path}")
        with open(config_path, "r") as f:
            print(f"Contenido:\n{f.read()}")
    else:
        print(f"NO EXISTE: {config_path}")

    print("=" * 60)


def check_models():
    """Verifica que los modelos base z-image estén disponibles"""
    base_paths = ["/runpod-volume/models", "/workspace/models", "/comfyui/models"]
    
    found_models = {}
    missing_models = []
    
    # Buscar UNET
    for base in base_paths:
        unet_path = f"{base}/unet/{REQUIRED_MODELS['unet']}"
        if os.path.exists(unet_path):
            found_models['unet'] = unet_path
            break
    else:
        missing_models.append(f"unet/{REQUIRED_MODELS['unet']}")
    
    # Buscar CLIP
    for base in base_paths:
        clip_path = f"{base}/clip/{REQUIRED_MODELS['clip']}"
        if os.path.exists(clip_path):
            found_models['clip'] = clip_path
            break
    else:
        missing_models.append(f"clip/{REQUIRED_MODELS['clip']}")
    
    # Buscar VAE
    for base in base_paths:
        vae_path = f"{base}/vae/{REQUIRED_MODELS['vae']}"
        if os.path.exists(vae_path):
            found_models['vae'] = vae_path
            break
    else:
        missing_models.append(f"vae/{REQUIRED_MODELS['vae']}")
    
    # Buscar LoRAs disponibles (solo para logging informativo)
    loras_found = []
    for base in base_paths:
        lora_path = f"{base}/loras"
        if os.path.exists(lora_path):
            try:
                loras = [f for f in os.listdir(lora_path) if f.endswith('.safetensors') or f.endswith('.ckpt')]
                if loras:
                    loras_found.extend([f"{base}/loras/{l}" for l in loras])
            except:
                pass
    
    if loras_found:
        found_models['loras_disponibles'] = loras_found
        print(f"LoRAs disponibles: {loras_found}")
    else:
        print("No se encontraron LoRAs (carpeta vacía o no configurada)")
    
    return found_models, missing_models


def wait_for_comfyui():
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if response.status_code == 200:
                print("ComfyUI listo")
                
                # Verificar modelos al inicio
                found, missing = check_models()
                if missing:
                    print(f"WARNING: Modelos faltantes: {missing}")
                else:
                    print(f"Todos los modelos base encontrados:")
                    for k, v in found.items():
                        if k != 'loras_disponibles':
                            print(f"  - {k}: {v}")
                
                log_system_info()
                return True
        except:
            print(f"Esperando ComfyUI... {i+1}/{max_retries}")
            time.sleep(2)
    return False


def download_image_from_comfyui(image_info):
    """
    Descarga la imagen desde el servidor local de ComfyUI
    y la devuelve como bytes + metadata.
    """
    filename = image_info.get("filename", "")
    subfolder = image_info.get("subfolder", "")
    file_type = image_info.get("type", "output")

    if not filename:
        return None, "No filename in image_info"

    params = {"filename": filename, "type": file_type}
    if subfolder:
        params["subfolder"] = subfolder

    view_url = f"{COMFYUI_URL}/view?{urllib.parse.urlencode(params)}"
    print(f"Descargando imagen desde ComfyUI: {view_url}")

    try:
        image_response = requests.get(view_url, timeout=120)

        if image_response.status_code != 200:
            return None, f"ComfyUI /view devolvió HTTP {image_response.status_code}"

        image_bytes = image_response.content
        file_size = len(image_bytes)
        print(f"Imagen descargada: {file_size} bytes ({file_size / 1024:.2f} KB)")

        if file_size < 1000:
            return None, f"Archivo de imagen sospechosamente pequeño: {file_size} bytes"

        return image_bytes, None

    except requests.exceptions.Timeout:
        return None, "Timeout descargando imagen de ComfyUI"
    except Exception as e:
        return None, f"Error descargando imagen: {str(e)}"


def find_save_image_node(outputs):
    """
    Encuentra el nodo SaveImage en los outputs.
    Busca en múltiples nodos posibles.
    """
    possible_nodes = ["9", "8", "10", "11", "12"]
    
    for node_id in possible_nodes:
        if node_id in outputs:
            node_output = outputs[node_id]
            if isinstance(node_output, dict) and "images" in node_output:
                image_list = node_output["images"]
                if image_list and len(image_list) > 0:
                    print(f"Imagen encontrada en nodo {node_id}")
                    return image_list[0]
    
    # Si no encontramos en los nodos conocidos, buscar en todos
    for node_id, node_output in outputs.items():
        if isinstance(node_output, dict) and "images" in node_output:
            image_list = node_output["images"]
            if image_list and len(image_list) > 0:
                print(f"Imagen encontrada en nodo {node_id} (búsqueda general)")
                return image_list[0]
    
    return None


def handler(job):
    job_input = job.get("input", {})

    if not job_input.get("workflow"):
        return {"error": "Missing workflow"}

    workflow = job_input["workflow"]
    
    # Verificar modelos base (UNET, CLIP, VAE)
    found_models, missing_models = check_models()
    
    if missing_models:
        error_msg = f"Modelos base no encontrados: {missing_models}"
        print(f"ERROR: {error_msg}")
        log_system_info()
        return {"error": error_msg}
    
    print(f"Modelos base verificados: {list(found_models.keys())}")
    print("Procesando workflow... (las LoRAs se cargarán según el workflow)")

    try:
        # Enviar workflow a ComfyUI
        response = requests.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow},
            timeout=30
        )

        if response.status_code != 200:
            return {"error": f"ComfyUI error: {response.text}"}

        prompt_data = response.json()
        prompt_id = prompt_data.get("prompt_id")

        if not prompt_id:
            return {"error": "No prompt_id received from ComfyUI"}

        print(f"Job iniciado en ComfyUI: {prompt_id}")

        # Polling del historial de ComfyUI
        max_wait = 600  # 10 minutos máximo
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                return {"error": f"Timeout después de {max_wait}s"}

            history_response = requests.get(
                f"{COMFYUI_URL}/history/{prompt_id}",
                timeout=10
            )

            if history_response.status_code == 200:
                history = history_response.json()

                if prompt_id in history:
                    job_data = history[prompt_id]

                    # Verificar si hubo error en ComfyUI
                    status_str = job_data.get("status", {}).get("status_str", "")
                    if status_str == "error":
                        return {
                            "error": "ComfyUI execution error",
                            "details": job_data.get("status", {})
                        }

                    outputs = job_data.get("outputs", {})
                    print(f"Outputs recibidos de ComfyUI: {json.dumps(outputs, default=str)[:500]}")

                    # Buscar imagen en cualquier nodo SaveImage
                    image_info = find_save_image_node(outputs)
                    
                    if image_info:
                        filename = image_info.get("filename", "")
                        print(f"Imagen encontrada: {json.dumps(image_info)}")

                        # Descargar el archivo localmente
                        image_bytes, error = download_image_from_comfyui(image_info)

                        if error:
                            return {
                                "error": f"Error descargando imagen: {error}",
                                "image_info": image_info
                            }

                        # Codificar en base64 para enviar en la respuesta
                        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                        print(f"Imagen codificada en base64: {len(image_b64)} caracteres")

                        return {
                            "status": "success",
                            "image_base64": image_b64,
                            "filename": filename,
                            "content_type": "image/png",
                            "file_size": len(image_bytes),
                            "prompt_id": prompt_id
                        }

                    # Si llegamos aquí, no encontramos imagen
                    if outputs:
                        return {
                            "error": "No se encontró imagen en ningún nodo SaveImage",
                            "available_outputs": list(outputs.keys()),
                            "outputs_preview": {k: str(v)[:200] for k, v in outputs.items()}
                        }

            time.sleep(2)

    except Exception as e:
        import traceback
        print(f"Exception en handler: {traceback.format_exc()}")
        return {"error": str(e)}


print("Iniciando worker z-image turbo...")
if not wait_for_comfyui():
    print("WARNING: ComfyUI no respondió a tiempo")

runpod.serverless.start({"handler": handler})
