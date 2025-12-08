import asyncio
import random
import psutil
import os
import subprocess
import platform
import time
import requests
import urllib.parse
import socket
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

# --- 1. CONFIGURAÇÃO WHATSAPP ---
WPP_PHONE = "556134623569"  
WPP_API_KEY = "1240273"       
ALERT_COOLDOWN = 300 
last_alert_time = 0

async def enviar_zap_background(mensagem):
    global last_alert_time
    agora = time.time()
    if (agora - last_alert_time) > ALERT_COOLDOWN:
        last_alert_time = agora 
        try:
            url = f"https://api.callmebot.com/whatsapp.php?phone={WPP_PHONE}&text={urllib.parse.quote('🚨 ' + mensagem)}&apikey={WPP_API_KEY}"
            await asyncio.to_thread(requests.get, url, timeout=5)
            return True
        except: return False
    return False

# --- 2. DETALHES DE HARDWARE AVANÇADOS ---

def get_gpu_details():
    """
    Busca: Carga(%), Memória Usada(MB), Memória Total(MB), Temperatura(C)
    """
    # Dados padrão se falhar
    dados = {"load": 0, "mem_used": 0, "mem_total": 0, "temp": 0}
    
    try:
        # Comando Mágico: Pede tudo de uma vez separado por vírgula
        cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        # Exemplo de saída: "45, 2048, 8192, 65"
        partes = output.split(',')
        
        if len(partes) == 4:
            dados["load"] = float(partes[0])
            dados["mem_used"] = float(partes[1])
            dados["mem_total"] = float(partes[2])
            dados["temp"] = float(partes[3])
    except:
        pass
    return dados

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"

def get_net_name():
    try:
        cmd = "powershell \"Get-NetConnectionProfile | Select-Object -ExpandProperty Name\""
        out = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore').strip()
        if out: return out.split('\n')[0].strip()
    except: pass
    return "Desconhecido"

# Adiciona caminhos
paths = [r"C:\Program Files\NVIDIA Corporation\NVSMI", r"C:\Windows\System32"]
for p in paths:
    if os.path.exists(p): os.environ["PATH"] += os.pathsep + p

# Pega nomes estáticos uma vez só
def get_gpu_name_static():
    try:
        cmd = "powershell \"Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name\""
        return subprocess.check_output(cmd, shell=True).decode().strip().split('\r\n')[0]
    except: return "GPU Genérica"

GPU_NAME_REAL = get_gpu_name_static()
CPU_NAME_REAL = platform.processor()

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>NOC - Pro Dashboard</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background-color: #0b0c10; color: #c5c6c7; padding: 20px; text-align: center; }
            h1 { color: #66fcf1; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 30px; border-bottom: 2px solid #45a29e; display: inline-block; padding-bottom: 10px;}

            #wpp-alert {
                background: #00e676; color: #000; font-weight: bold; padding: 15px; border-radius: 8px;
                position: fixed; top: 20px; right: 20px; z-index: 9999; display: none;
                animation: slideIn 0.3s;
            }
            @keyframes slideIn { from {transform: translateX(100%);} to {transform: translateX(0);} }

            .dashboard {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                max-width: 1600px;
                margin: 0 auto;
            }

            .card {
                background: #1f2833; padding: 20px; border-radius: 10px; border-left: 5px solid #45a29e;
                text-align: left; box-shadow: 0 5px 15px rgba(0,0,0,0.3); position: relative;
            }

            .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
            .card-title { font-size: 1.1rem; color: #66fcf1; font-weight: 700; text-transform: uppercase; }
            .card-subtitle { font-size: 0.8rem; color: #888; text-align: right; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

            .main-row { display: flex; align-items: baseline; gap: 10px; margin-bottom: 15px; }
            .big-value { font-size: 3.5rem; font-weight: bold; color: #fff; line-height: 1; }
            .unit { font-size: 1.2rem; color: #45a29e; }

            /* Grid de Detalhes (A mágica acontece aqui) */
            .details-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                background: #0b0c10;
                padding: 10px;
                border-radius: 6px;
                font-size: 0.85rem;
            }
            .detail-item { display: flex; flex-direction: column; }
            .d-label { color: #888; font-size: 0.75rem; text-transform: uppercase; }
            .d-val { color: #fff; font-weight: 600; }

            .progress-track { background: #0b0c10; height: 8px; border-radius: 4px; width: 100%; margin-top: 15px; overflow: hidden; }
            .progress-fill { height: 100%; width: 0%; background: #45a29e; transition: width 0.3s; }

            /* Cores Específicas */
            .crit-border { border-left-color: #ff3333 !important; }
            .crit-text { color: #ff3333 !important; }
            .crit-fill { background: #ff3333 !important; }

            button { background: #1f2833; color: #66fcf1; border: 1px solid #45a29e; padding: 10px 25px; cursor: pointer; border-radius: 4px; font-weight: bold; transition: 0.3s; }
            button:hover { background: #45a29e; color: #000; }
        </style>
    </head>
    <body>
        <div id="wpp-alert">🚀 ALERTA ENVIADO!</div>
        <h1>NOC - Monitoramento Pro</h1>
        <br>
        <button onclick="enableAudio()">🔊 Habilitar Som</button>
        <br><br>

        <div class="dashboard">
            <div class="card" id="card-ping">
                <div class="card-header">
                    <span class="card-title">Rede</span>
                    <span class="card-subtitle" id="net-name">...</span>
                </div>
                <div class="main-row">
                    <span class="big-value" id="val-ping">0</span><span class="unit">ms</span>
                </div>
                <div class="details-grid">
                    <div class="detail-item"><span class="d-label">IP Local</span><span class="d-val" id="net-ip">...</span></div>
                    <div class="detail-item"><span class="d-label">Status</span><span class="d-val" id="net-status">OK</span></div>
                </div>
                <div class="progress-track"><div class="progress-fill" id="bar-ping"></div></div>
            </div>

            <div class="card" id="card-cpu">
                <div class="card-header">
                    <span class="card-title">CPU</span>
                    <span class="card-subtitle" id="cpu-name">...</span>
                </div>
                <div class="main-row">
                    <span class="big-value" id="val-cpu">0</span><span class="unit">%</span>
                </div>
                <div class="details-grid">
                    <div class="detail-item"><span class="d-label">Frequência</span><span class="d-val" id="cpu-freq">... GHz</span></div>
                    <div class="detail-item"><span class="d-label">Threads/Núcleos</span><span class="d-val" id="cpu-cores">...</span></div>
                </div>
                <div class="progress-track"><div class="progress-fill" id="bar-cpu"></div></div>
            </div>

            <div class="card" id="card-ram">
                <div class="card-header">
                    <span class="card-title">RAM</span>
                    <span class="card-subtitle">Memória Física</span>
                </div>
                <div class="main-row">
                    <span class="big-value" id="val-ram">0</span><span class="unit">%</span>
                </div>
                <div class="details-grid">
                    <div class="detail-item"><span class="d-label">Em Uso</span><span class="d-val" id="ram-used">... GB</span></div>
                    <div class="detail-item"><span class="d-label">Total</span><span class="d-val" id="ram-total">... GB</span></div>
                </div>
                <div class="progress-track"><div class="progress-fill" id="bar-ram"></div></div>
            </div>

            <div class="card" id="card-gpu">
                <div class="card-header">
                    <span class="card-title">GPU</span>
                    <span class="card-subtitle" id="gpu-name">...</span>
                </div>
                <div class="main-row">
                    <span class="big-value" id="val-gpu">0</span><span class="unit">%</span>
                </div>
                <div class="details-grid">
                    <div class="detail-item"><span class="d-label">Temperatura</span><span class="d-val" id="gpu-temp">-- °C</span></div>
                    <div class="detail-item"><span class="d-label">VRAM (Memória)</span><span class="d-val" id="gpu-mem">-- / -- MB</span></div>
                </div>
                <div class="progress-track"><div class="progress-fill" id="bar-gpu"></div></div>
            </div>
        </div>

        <script>
            var ws = new WebSocket("ws://" + window.location.host + "/ws");
            var audio = new Audio('alerta_latencia_alta.mp3');
            var soundOn = false;
            function enableAudio() { soundOn = true; audio.play().then(()=>audio.pause()); document.querySelector('button').style.display='none'; }

            ws.onmessage = function(event) {
                var data = JSON.parse(event.data);

                // --- REDE ---
                document.getElementById('val-ping').innerText = data.ping_val;
                document.getElementById('net-name').innerText = data.net_name;
                document.getElementById('net-ip').innerText = data.net_ip;
                updateBar('ping', data.ping_val, 100);
                
                if(data.ping_val > 100) {
                    document.getElementById('net-status').innerText = "LATÊNCIA ALTA";
                    document.getElementById('net-status').style.color = "#ff3333";
                    if(soundOn) audio.play().catch(e=>{});
                } else {
                    document.getElementById('net-status').innerText = "Estável";
                    document.getElementById('net-status').style.color = "#fff";
                }

                // --- CPU ---
                document.getElementById('val-cpu').innerText = data.cpu_load;
                document.getElementById('cpu-name').innerText = data.cpu_name;
                document.getElementById('cpu-freq').innerText = data.cpu_freq + " GHz";
                document.getElementById('cpu-cores').innerText = data.cpu_threads;
                updateBar('cpu', data.cpu_load, 85);

                // --- RAM ---
                document.getElementById('val-ram').innerText = data.ram_percent;
                document.getElementById('ram-used').innerText = data.ram_used + " GB";
                document.getElementById('ram-total').innerText = data.ram_total + " GB";
                updateBar('ram', data.ram_percent, 90);

                // --- GPU ---
                document.getElementById('val-gpu').innerText = data.gpu_load;
                document.getElementById('gpu-name').innerText = data.gpu_name;
                document.getElementById('gpu-temp').innerText = data.gpu_temp + " °C";
                document.getElementById('gpu-mem').innerText = data.gpu_mem;
                updateBar('gpu', data.gpu_load, 85);

                // --- WPP ---
                if(data.wpp_sent) {
                    var box = document.getElementById('wpp-alert');
                    box.style.display = 'block';
                    setTimeout(() => box.style.display = 'none', 3000);
                }
            };

            function updateBar(id, val, limit) {
                var bar = document.getElementById('bar-'+id);
                var card = document.getElementById('card-'+id);
                
                var pct = id==='ping' ? (val/200)*100 : val;
                if(pct>100) pct=100;
                bar.style.width = pct + "%";

                if(val >= limit) {
                    card.classList.add('crit-border');
                    bar.classList.add('crit-fill');
                } else {
                    card.classList.remove('crit-border');
                    bar.classList.remove('crit-fill');
                }
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get(): return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Dados estáticos (CPU Name)
    cpu_threads = psutil.cpu_count()
    
    try:
        while True:
            # 1. Rede
            net_name = get_net_name()
            net_ip = get_local_ip()
            ping = random.randint(10, 120)

            # 2. CPU
            cpu_load = psutil.cpu_percent(interval=None)
            cpu_freq = round(psutil.cpu_freq().current / 1000, 2) # Converte MHz para GHz

            # 3. RAM
            mem = psutil.virtual_memory()
            ram_used = round(mem.used / (1024**3), 1)
            ram_total = round(mem.total / (1024**3), 1)

            # 4. GPU (Detalhada via NVIDIA)
            gpu_data = get_gpu_details()
            
            # Formata memória da GPU (ex: 4096 / 8192 MB)
            gpu_mem_str = f"{int(gpu_data['mem_used'])} / {int(gpu_data['mem_total'])} MB"

            # 5. Zap
            wpp_enviado = False
            if ping > 100:
                msg = f"Latência ({ping}ms) em {net_name} ({net_ip})"
                asyncio.create_task(enviar_zap_background(msg))
                if (time.time() - last_alert_time) < 1: wpp_enviado = True

            payload = {
                "net_name": net_name, "net_ip": net_ip, "ping_val": ping,
                "cpu_name": CPU_NAME_REAL, "cpu_load": cpu_load, "cpu_freq": cpu_freq, "cpu_threads": cpu_threads,
                "ram_percent": mem.percent, "ram_used": ram_used, "ram_total": ram_total,
                "gpu_name": GPU_NAME_REAL, "gpu_load": gpu_data['load'], "gpu_temp": gpu_data['temp'], "gpu_mem": gpu_mem_str,
                "wpp_sent": wpp_enviado
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(0.5)

    except Exception as e:
        print(f"Erro Loop: {e}")