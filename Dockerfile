# Dockerfile
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Variables de entorno
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clonar ComfyUI versión 0.12.3 oficial (Comfy-Org)
WORKDIR /comfyui
RUN git clone https://github.com/Comfy-Org/ComfyUI.git . && \
    git checkout v0.12.3

# Instalar dependencias de Python para ComfyUI
RUN pip install --no-cache-dir -r requirements.txt

# Instalar RunPod SDK
RUN pip install --no-cache-dir runpod

# ============================================
# CONFIGURACIÓN PARA NETWORK VOLUME (Opción 1)
# ============================================
# Crear el archivo de configuración para que ComfyUI busque modelos en /workspace
RUN echo "comfyui:" > /comfyui/extra_model_paths.yaml && \
    echo "  base_path: /workspace" >> /comfyui/extra_model_paths.yaml && \
    echo "  checkpoints: models/checkpoints/" >> /comfyui/extra_model_paths.yaml && \
    echo "  clip: models/clip/" >> /comfyui/extra_model_paths.yaml && \
    echo "  clip_vision: models/clip_vision/" >> /comfyui/extra_model_paths.yaml && \
    echo "  configs: models/configs/" >> /comfyui/extra_model_paths.yaml && \
    echo "  controlnet: models/controlnet/" >> /comfyui/extra_model_paths.yaml && \
    echo "  diffusion_models: models/diffusion_models/" >> /comfyui/extra_model_paths.yaml && \
    echo "  embeddings: models/embeddings/" >> /comfyui/extra_model_paths.yaml && \
    echo "  loras: models/loras/" >> /comfyui/extra_model_paths.yaml && \
    echo "  upscale_models: models/upscale_models/" >> /comfyui/extra_model_paths.yaml && \
    echo "  vae: models/vae/" >> /comfyui/extra_model_paths.yaml && \
    echo "  unet: models/unet/" >> /comfyui/extra_model_paths.yaml && \
    echo "  gligen: models/gligen/" >> /comfyui/extra_model_paths.yaml && \
    echo "  hypernetworks: models/hypernetworks/" >> /comfyui/extra_model_paths.yaml && \
    echo "  style_models: models/style_models/" >> /comfyui/extra_model_paths.yaml && \
    echo "  t2i_adapter: models/t2i_adapter/" >> /comfyui/extra_model_paths.yaml

# ============================================
# SOLUCIÓN ALTERNATIVA: Descargar modelo directamente (Opción 2)
# Descomenta las siguientes líneas si el Network Volume no funciona
# ============================================
# RUN mkdir -p /comfyui/models/checkpoints && \
#     wget -O /comfyui/models/checkpoints/ace_step_1.5_turbo_aio.safetensors \
#     "https://huggingface.co/ace-step/ace-step-1.5-turbo/resolve/main/ace_step_1.5_turbo_aio.safetensors" || \
#     echo "No se pudo descargar el modelo - se asume que está en el volumen"

# ============================================
# CREAR ESTRUCTURA EN /workspace (por si el volumen no tiene estas carpetas)
# ============================================
RUN mkdir -p /workspace/models/checkpoints && \
    mkdir -p /workspace/models/unet && \
    mkdir -p /workspace/models/vae && \
    mkdir -p /workspace/models/clip && \
    mkdir -p /workspace/output

# Copiar el handler
COPY handler.py /handler.py

# Crear script de inicio con debugging completo
RUN printf '#!/bin/bash\n\
echo "========================================"\n\
echo "INICIANDO WORKER ACE-STEP"\n\
echo "========================================"\n\
echo "Fecha: $(date)"\n\
echo "Hostname: $(hostname)"\n\
echo "Esperando 5 segundos por si el volumen tarda en montar..."\n\
sleep 5\n\
echo "Verificando estructura de directorios..."\n\
echo "--- Contenido de /workspace ---"\n\
ls -la /workspace 2>/dev/null || echo "/workspace no existe"\n\
echo "--- Contenido de /workspace/models ---"\n\
ls -la /workspace/models 2>/dev/null || echo "/workspace/models no existe"\n\
echo "--- Contenido de /workspace/models/checkpoints ---"\n\
ls -la /workspace/models/checkpoints 2>/dev/null || echo "/workspace/models/checkpoints no existe"\n\
echo "--- Contenido de /comfyui/models/checkpoints ---"\n\
ls -la /comfyui/models/checkpoints 2>/dev/null || echo "/comfyui/models/checkpoints no existe"\n\
echo "--- Verificando archivo de configuración ---"\n\
cat /comfyui/extra_model_paths.yaml 2>/dev/null || echo "extra_model_paths.yaml no existe"\n\
echo "========================================"\n\
echo "Iniciando ComfyUI v0.12.3..."\n\
cd /comfyui && python main.py --listen 0.0.0.0 --port 8188 --preview-method auto &\n\
echo "Esperando a que ComfyUI esté listo (15s)..."\n\
sleep 15\n\
echo "Iniciando RunPod handler con debugging..."\n\
python /handler.py\n' > /start.sh && chmod +x /start.sh

# Exponer puertos
EXPOSE 8188

# Comando de inicio
CMD ["/bin/bash", "/start.sh"]
