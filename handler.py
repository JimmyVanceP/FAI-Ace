# handler.py
import runpod
import json
import requests
import time
import os
import subprocess

COMFYUI_URL = "http://127.0.0.1:8188"

def log_system_info():
    """Loggear información completa del sistema"""
    print("=" * 60)
    print("DEBUG: Verificando sistema de archivos")
    print("=" * 60)
    
    # Verificar /runpod-volume (Serverless)
    print("\n--- Verificando /runpod-volume (Serverless) ---")
    if os.path.exists("/runpod-volume"):
        print("/runpod-volume EXISTE")
        result = subprocess.run(["ls", "-la", "/runpod-volume"], capture_output=True, text=True)
        print(result.stdout)
        
        if os.path.exists("/runpod-volume/models"):
            print("\nContenido de /runpod-volume/models:")
            result = subprocess.run(["ls", "-la", "/runpod-volume/models"], capture_output=True, text=True)
            print(result.stdout)
            
            for subdir in ["checkpoints", "unet", "vae", "clip"]:
                path = f"/runpod-volume/models/{subdir}"
                if os.path.exists(path):
                    result = subprocess.run(["ls", "-la", path], capture_output=True, text=True)
                    print(f"\n{path}:\n{result.stdout}")
    else:
        print("/runpod-volume NO EXISTE")
    
    # Verificar /workspace (Pods)
    print("\n--- Verificando /workspace (Pods) ---")
    if os.path.exists("/workspace"):
        print("/workspace EXISTE")
        result = subprocess.run(["ls", "-la", "/workspace/models/checkpoints"], capture_output=True, text=True)
        print(f"checkpoints: {result.stdout}")
    
    # Verificar config de ComfyUI
    print("\n--- Verificando extra_model_paths.yaml ---")
    config_path = "/comfyui/extra_model_paths.yaml"
    if os.path.exists(config_path):
        print(f"Archivo existe en: {config_path}")
        with open(config_path, "r") as f:
            print(f"Contenido:\n{f.read()}")
    else:
        print(f"NO EXISTE: {config_path}")
    
    print("=" * 60)

def wait_for_comfyui():
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if response.status_code == 200:
                print("ComfyUI listo")
                log_system_info()
                return True
        except:
            print(f"Esperando ComfyUI... {i+1}/{max_retries}")
            time.sleep(2)
    return False

def handler(job):
    job_input = job.get("input", {})
    
    if not job_input.get("workflow"):
        return {"error": "Missing workflow"}
    
    workflow = job_input["workflow"]
    
    # Verificar todas las posibles ubicaciones del modelo
    possible_paths = [
        "/runpod-volume/models/checkpoints/ace_step_1.5_turbo_aio.safetensors",
        "/workspace/models/checkpoints/ace_step_1.5_turbo_aio.safetensors",
        "/comfyui/models/checkpoints/ace_step_1.5_turbo_aio.safetensors",
        "/runpod-volume/models/unet/ace_step_1.5_turbo_aio.safetensors",
        "/workspace/models/unet/ace_step_1.5_turbo_aio.safetensors"
    ]
    
    model_found = False
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Modelo encontrado en: {path}")
            model_found = True
            break
    
    if not model_found:
        print("ERROR: Modelo no encontrado en ninguna ubicación estándar")
        log_system_info()
        return {"error": "Modelo ace_step_1.5_turbo_aio.safetensors no encontrado"}
    
    try:
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
            return {"error": "No prompt_id"}
        
        print(f"Job iniciado: {prompt_id}")
        
        # Polling
        max_wait = 600
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                return {"error": "Timeout"}
            
            history_response = requests.get(
                f"{COMFYUI_URL}/history/{prompt_id}",
                timeout=10
            )
            
            if history_response.status_code == 200:
                history = history_response.json()
                
                if prompt_id in history:
                    job_data = history[prompt_id]
                    
                    if job_data.get("status", {}).get("status_str") == "error":
                        return {
                            "error": "ComfyUI error",
                            "details": job_data.get("status", {})
                        }
                    
                    outputs = job_data.get("outputs", {})
                    
                    # Extraer audio del nodo 8
                    if "8" in outputs:
                        node_output = outputs["8"]
                        if isinstance(node_output, dict) and "audio" in node_output:
                            audio_list = node_output["audio"]
                            if audio_list:
                                audio_info = audio_list[0]
                                filename = audio_info.get("filename")
                                if filename:
                                    url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
                                    return {
                                        "status": "success",
                                        "audio_url": url,
                                        "prompt_id": prompt_id
                                    }
                    
                    return {"error": "No audio in outputs", "outputs": outputs}
            
            time.sleep(2)
            
    except Exception as e:
        return {"error": str(e)}

print("Iniciando ComfyUI...")
if not wait_for_comfyui():
    print("WARNING: ComfyUI no respondió")

runpod.serverless.start({"handler": handler})
