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

# Copiar el handler
COPY handler.py /handler.py

# Crear directorio para outputs
RUN mkdir -p /comfyui/output

# Crear script de inicio (CORREGIDO)
RUN printf '#!/bin/bash\n\
echo "Iniciando ComfyUI v0.12.3..."\n\
cd /comfyui && python main.py --listen 0.0.0.0 --port 8188 --preview-method auto &\n\
echo "Esperando a que ComfyUI esté listo..."\n\
sleep 15\n\
echo "Iniciando RunPod handler..."\n\
python /handler.py\n' > /start.sh && chmod +x /start.sh

# Exponer puertos
EXPOSE 8188

# Comando de inicio
CMD ["/bin/bash", "/start.sh"]
