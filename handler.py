import runpod
import json
import subprocess
import os

def handler(event):
    # Aquí va la lógica para procesar workflows de ComfyUI
    # Puedes adaptar el código del worker oficial
    pass

runpod.serverless.start({"handler": handler})
