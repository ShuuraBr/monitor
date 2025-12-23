"""
╔════════════════════════════════════════════════════════════════════════════╗
║                     COMANDANTE NOC - VERSÃO 12.0                          ║
║              Sistema de Monitoramento em Tempo Real para TI                ║
║                                                                            ║
║  Desenvolvido para: Governança de Infraestrutura e Operações de Rede      ║
║  Versão: 12.0 (Profissional)                                              ║
║  Data: 2025                                                               ║
║  Linguagem: Python 3.8+                                                   ║
╚════════════════════════════════════════════════════════════════════════════╝

DESCRIÇÃO:
    Sistema de monitoramento em tempo real que coleta métricas de hardware,
    conectividade WAN e infraestrutura, com alertas automáticos via WhatsApp.

FUNCIONALIDADES PRINCIPAIS:
    ✓ Monitoramento de CPU, RAM, Disco e GPU em tempo real
    ✓ Testes de velocidade de internet (Speedtest)
    ✓ Ping em tempo real para múltiplos destinos
    ✓ Dashboard interativo via WebSocket
    ✓ Alertas críticos com notificação WhatsApp
    ✓ Histórico de eventos e incidentes
    ✓ Suporte para Windows, Linux e macOS

REQUISITOS:
    - Python 3.8 ou superior
    - FastAPI
    - psutil
    - requests
    - ping3 (opcional)
    - speedtest-cli (opcional)
    - GPUtil (opcional)
    - WMI (Windows apenas)

INSTALAÇÃO:
    pip install fastapi uvicorn psutil requests ping3 speedtest-cli GPUtil

EXECUÇÃO:
    python noc_commander_v12_melhorado.py
    Acesse: http://localhost:8000

HISTÓRICO DE VERSÕES:
    v12.0 - Refatoração completa com documentação profissional
    v11.0 - Versão anterior com funcionalidades básicas
"""

import asyncio
import random
import psutil
import os
import platform
import time
import socket
import threading
import logging
import requests
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, FileResponse

# ═══════════════════════════════════════════════════════════════════════════
# 1. CONFIGURAÇÃO DE LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] NOC-v12: %(message)s",
    handlers=[
        logging.FileHandler("noc_commander.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NOC-Commander-v12")

# ═══════════════════════════════════════════════════════════════════════════
# 2. ENUMS E TIPOS DE DADOS
# ═══════════════════════════════════════════════════════════════════════════

class StatusSistema(Enum):
    """Estados possíveis do sistema."""
    OK = "OK"
    AVISO = "AVISO"
    CRITICO = "CRÍTICO"
    DESCONHECIDO = "DESCONHECIDO"

class TipoAlerta(Enum):
    """Tipos de alertas do sistema."""
    CPU_CRITICA = "CPU_CRITICA"
    RAM_CRITICA = "RAM_CRITICA"
    DISCO_CRITICO = "DISCO_CRITICO"
    WAN_DESCONECTADA = "WAN_DESCONECTADA"
    LATENCIA_ALTA = "LATENCIA_ALTA"
    SERVIDOR_DOWN = "SERVIDOR_DOWN"

@dataclass
class EventoSistema:
    """Registro de evento do sistema."""
    timestamp: str
    tipo: str
    severidade: str
    mensagem: str
    componente: str
    valor: Optional[float] = None

@dataclass
class MetricasLocais:
    """Métricas do computador local."""
    cpu_percent: float
    ram_percent: float
    disco_percent: float
    rx_bytes_s: float
    tx_bytes_s: float
    temperatura_cpu: float

# ═══════════════════════════════════════════════════════════════════════════
# 3. IMPORTAÇÕES DEFENSIVAS
# ═══════════════════════════════════════════════════════════════════════════

try:
    from ping3 import ping
    PING3_DISPONIVEL = True
except ImportError:
    ping = None
    PING3_DISPONIVEL = False
    logger.warning("⚠️  ping3 não instalado. Instale com: pip install ping3")

try:
    import speedtest
    SPEEDTEST_DISPONIVEL = True
except ImportError:
    speedtest = None
    SPEEDTEST_DISPONIVEL = False
    logger.warning("⚠️  speedtest-cli não instalado. Instale com: pip install speedtest-cli")

try:
    import GPUtil
    GPUTIL_DISPONIVEL = True
except ImportError:
    GPUtil = None
    GPUTIL_DISPONIVEL = False
    logger.warning("⚠️  GPUtil não instalado. Instale com: pip install GPUtil")

try:
    import wmi
    WMI_INTERFACE = wmi.WMI() if os.name == "nt" else None
    WMI_DISPONIVEL = WMI_INTERFACE is not None
except Exception as e:
    WMI_INTERFACE = None
    WMI_DISPONIVEL = False
    logger.warning(f"⚠️  WMI não disponível: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 4. CONFIGURAÇÕES DO SISTEMA
# ═══════════════════════════════════════════════════════════════════════════

CONFIG = {
    # WhatsApp (CallMeBot)
    "WPP_PHONE": "556134623569",
    "WPP_KEY": "1240273",
    "WPP_HABILITADO": True,
    
    # Intervalos (segundos)
    "SPEEDTEST_INTERVALO": 300,  # A cada 5 minutos
    "COLETA_INTERVALO": 1,        # A cada 1 segundo
    "ALERT_COOLDOWN": 300,        # Mínimo 5 minutos entre alertas
    
    # Servidor
    "HOST": "0.0.0.0",
    "PORTA": 8000,
    
    # Histórico
    "MAX_EVENTOS": 1000,
    "MAX_ALERTAS": 500,
}

# Limites de alerta (thresholds)
LIMITES = {
    "cpu": 90,              # %
    "ram": 95,              # %
    "disco": 95,            # %
    "ping": 200,            # ms
    "temperatura_cpu": 80,  # °C
    "perda_pacotes": 10,    # %
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. ESTADO GLOBAL DO SISTEMA
# ═══════════════════════════════════════════════════════════════════════════

ESTADO = {
    # Velocidade de internet
    "velocidade": {
        "download": 0.0,
        "upload": 0.0,
        "ping": 0.0,
        "isp": "Aguardando...",
        "status": "Iniciando",
        "ultima_atualizacao": None,
    },
    
    # Status de testes
    "testando": False,
    "ultimo_alerta": 0,
    
    # Contadores de alertas
    "contadores_alertas": {
        "critico": 0,
        "aviso": 0,
        "info": 0,
    },
    
    # Histórico
    "eventos": [],
    "alertas": [],
    "uptime_inicio": time.time(),
    "wan_historico": [],
    
    # Métricas acumuladas
    "metricas_acumuladas": {
        "cpu_max": 0,
        "ram_max": 0,
        "disco_max": 0,
        "picos_cpu": 0,
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 6. FUNÇÕES UTILITÁRIAS
# ═══════════════════════════════════════════════════════════════════════════

def registrar_evento(tipo: str, severidade: str, mensagem: str, 
                    componente: str, valor: Optional[float] = None) -> None:
    """
    Registra um evento no histórico do sistema.
    
    Args:
        tipo: Tipo do evento (CPU, RAM, WAN, etc)
        severidade: CRÍTICO, AVISO, INFO
        mensagem: Descrição do evento
        componente: Componente afetado
        valor: Valor numérico associado (opcional)
    """
    evento = EventoSistema(
        timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        tipo=tipo,
        severidade=severidade,
        mensagem=mensagem,
        componente=componente,
        valor=valor
    )
    
    ESTADO["eventos"].append(asdict(evento))
    
    # Manter apenas os últimos N eventos
    if len(ESTADO["eventos"]) > CONFIG["MAX_EVENTOS"]:
        ESTADO["eventos"] = ESTADO["eventos"][-CONFIG["MAX_EVENTOS"]:]
    
    logger.info(f"[{severidade}] {componente}: {mensagem}")

def formatar_bytes(bytes_por_segundo: float) -> str:
    """
    Formata bytes/segundo em unidade legível.
    
    Args:
        bytes_por_segundo: Velocidade em bytes/s
        
    Returns:
        String formatada (ex: "1.5 MB/s")
    """
    unidades = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    indice = 0
    valor = float(bytes_por_segundo)
    
    while valor >= 1024 and indice < 4:
        valor /= 1024
        indice += 1
    
    return f"{valor:.1f} {unidades[indice]}/s"

def formatar_tempo_decorrido(segundos: int) -> str:
    """
    Formata segundos em formato HH:MM:SS.
    
    Args:
        segundos: Tempo em segundos
        
    Returns:
        String formatada (ex: "02:30:45")
    """
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{int(horas):02d}:{int(minutos):02d}:{int(segundos):02d}"

def obter_info_host() -> Dict:
    """
    Obtém informações do computador local.
    
    Returns:
        Dicionário com hostname, IP, SO e modelo de CPU
    """
    try:
        socket_temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_temp.settimeout(0.5)
        socket_temp.connect(("8.8.8.8", 80))
        ip = socket_temp.getsockname()[0]
        socket_temp.close()
    except Exception:
        ip = "127.0.0.1"
    
    return {
        "hostname": platform.node(),
        "ip": ip,
        "so": f"{platform.system()} {platform.release()}",
        "cpu_modelo": platform.processor() or "CPU Genérica",
        "arquitetura": platform.machine(),
    }

def obter_dados_gpu() -> Dict:
    """
    Obtém informações da GPU (Nvidia ou integrada).
    
    Returns:
        Dicionário com nome, carga e temperatura da GPU
    """
    dados = {
        "nome": "GPU Integrada/N/A",
        "carga": 0.0,
        "temperatura": 0.0,
        "disponivel": False
    }
    
    # Tentar obter dados de GPU Nvidia
    if GPUTIL_DISPONIVEL and GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                dados = {
                    "nome": gpu.name,
                    "carga": round(gpu.load * 100, 1),
                    "temperatura": int(gpu.temperature),
                    "disponivel": True
                }
                return dados
        except Exception as e:
            logger.debug(f"Erro ao obter dados GPU (Nvidia): {e}")
    
    # Fallback para WMI (Windows)
    if WMI_DISPONIVEL and WMI_INTERFACE:
        try:
            for controlador in WMI_INTERFACE.Win32_VideoController():
                dados["nome"] = controlador.Name
                dados["disponivel"] = True
                break
        except Exception as e:
            logger.debug(f"Erro ao obter dados GPU (WMI): {e}")
    
    return dados

def obter_velocidade_rede(ultima_io, ultimo_tempo: float) -> Tuple:
    """
    Calcula velocidade de rede em tempo real.
    
    Args:
        ultima_io: Último estado de I/O de rede
        ultimo_tempo: Último timestamp
        
    Returns:
        Tupla com (io_atual, tempo_atual, rx_bytes_s, tx_bytes_s)
    """
    io_atual = psutil.net_io_counters()
    tempo_atual = time.time()
    delta_tempo = tempo_atual - ultimo_tempo
    
    if delta_tempo <= 0:
        delta_tempo = 1
    
    rx = (io_atual.bytes_recv - ultima_io.bytes_recv) / delta_tempo
    tx = (io_atual.bytes_sent - ultima_io.bytes_sent) / delta_tempo
    
    return io_atual, tempo_atual, rx, tx

def ping_real(host: str, timeout: int = 2) -> float:
    """
    Executa ping real para um host.
    
    Args:
        host: Endereço IP ou domínio
        timeout: Timeout em segundos
        
    Returns:
        Latência em ms ou 9999 se falhar
    """
    if not PING3_DISPONIVEL or not ping:
        return 9999
    
    try:
        resultado = ping(host, timeout=timeout, unit='ms')
        if resultado is None:
            return 9999
        return round(resultado, 1)
    except Exception as e:
        logger.debug(f"Erro ao fazer ping em {host}: {e}")
        return 9999

# ═══════════════════════════════════════════════════════════════════════════
# 7. WORKER DE SPEEDTEST
# ═══════════════════════════════════════════════════════════════════════════

def worker_speedtest() -> None:
    """
    Worker que executa testes de velocidade periodicamente.
    Roda em thread separada e atualiza ESTADO["velocidade"].
    """
    logger.info("🚀 Worker de Speedtest iniciado")
    
    while True:
        try:
            ESTADO["testando"] = True
            ESTADO["velocidade"]["status"] = "Testando..."
            
            if SPEEDTEST_DISPONIVEL and speedtest:
                logger.info("⏱️  Iniciando teste de velocidade...")
                
                teste = speedtest.Speedtest()
                teste.get_best_server()
                
                # Obter informações do cliente
                info_cliente = teste.results.client
                isp = info_cliente.get("isp", "Desconhecido")
                
                # Executar testes
                velocidade_down = round(teste.download() / 1e6, 2)
                velocidade_up = round(teste.upload() / 1e6, 2)
                ping_resultado = round(teste.results.ping, 1)
                
                ESTADO["velocidade"] = {
                    "download": velocidade_down,
                    "upload": velocidade_up,
                    "ping": ping_resultado,
                    "isp": isp,
                    "status": "Online",
                    "ultima_atualizacao": datetime.now().strftime("%H:%M:%S")
                }
                
                logger.info(f"✅ Speedtest concluído: {velocidade_down} Mbps ⬇️  | "
                           f"{velocidade_up} Mbps ⬆️  | {ping_resultado}ms | ISP: {isp}")
                
                registrar_evento(
                    tipo="SPEEDTEST",
                    severidade="INFO",
                    mensagem=f"Teste concluído: {velocidade_down} Mbps",
                    componente="WAN",
                    valor=velocidade_down
                )
            else:
                ESTADO["velocidade"]["status"] = "Biblioteca não disponível"
                logger.warning("⚠️  Speedtest-cli não disponível")
        
        except Exception as e:
            logger.error(f"❌ Erro no Speedtest: {e}")
            ESTADO["velocidade"]["status"] = "Erro/Timeout"
            registrar_evento(
                tipo="SPEEDTEST_ERRO",
                severidade="AVISO",
                mensagem=f"Erro ao executar speedtest: {str(e)}",
                componente="WAN"
            )
        
        finally:
            ESTADO["testando"] = False
            time.sleep(CONFIG["SPEEDTEST_INTERVALO"])

async def enviar_whatsapp(mensagem: str) -> bool:
    """
    Envia alerta via WhatsApp usando CallMeBot.
    
    Args:
        mensagem: Texto do alerta
        
    Returns:
        True se enviado com sucesso, False caso contrário
    """
    if not CONFIG["WPP_HABILITADO"]:
        logger.debug("WhatsApp desabilitado")
        return False
    
    tempo_atual = time.time()
    tempo_desde_ultimo = tempo_atual - ESTADO["ultimo_alerta"]
    
    if tempo_desde_ultimo <= CONFIG["ALERT_COOLDOWN"]:
        logger.debug(f"Alerta em cooldown ({tempo_desde_ultimo:.0f}s)")
        return False
    
    ESTADO["ultimo_alerta"] = tempo_atual
    
    try:
        texto_alerta = f"🚨 NOC ALERTA: {mensagem}"
        url = (
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={CONFIG['WPP_PHONE']}"
            f"&text={urllib.parse.quote(texto_alerta)}"
            f"&apikey={CONFIG['WPP_KEY']}"
        )
        
        await asyncio.to_thread(requests.get, url, timeout=10)
        logger.info(f"📱 WhatsApp enviado: {mensagem}")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erro ao enviar WhatsApp: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════
# 8. COLETA DE DADOS DE CONECTIVIDADE
# ═══════════════════════════════════════════════════════════════════════════

def obter_dados_wan_reais() -> List[Dict]:
    """
    Obtém dados reais de conectividade WAN.
    
    Returns:
        Lista de dicionários com status de cada link WAN
    """
    alvos = [
        {"nome": "Google DNS", "ip": "8.8.8.8", "provedor": "Google"},
        {"nome": "Cloudflare DNS", "ip": "1.1.1.1", "provedor": "Cloudflare"},
        {"nome": "Gateway Local", "ip": "192.168.1.1", "provedor": "Router Local"},
    ]
    
    wan_lista = []
    
    for alvo in alvos:
        ms = ping_real(alvo["ip"])
        status = "UP" if ms != 9999 else "DOWN"
        perda = 0.0 if ms != 9999 else 100.0
        
        wan_lista.append({
            "nome": alvo["nome"],
            "provedor": alvo["provedor"],
            "tipo": "ICMP",
            "status": status,
            "latencia_ms": ms if ms != 9999 else 0,
            "perda_pacotes": perda,
            "jitter": 0.0,
            "banda_down": "--",
            "banda_up": "--",
        })
    
    return wan_lista

# ═══════════════════════════════════════════════════════════════════════════
# 9. SERVIDOR FASTAPI
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="NOC Commander v12",
    description="Sistema de Monitoramento em Tempo Real",
    version="12.0"
)

@app.on_event("startup")
def iniciar_sistema():
    """Inicializa workers ao iniciar o servidor."""
    logger.info("=" * 80)
    logger.info("🚀 NOC COMMANDER v12.0 - INICIANDO")
    logger.info("=" * 80)
    
    # Iniciar worker de speedtest
    thread_speedtest = threading.Thread(target=worker_speedtest, daemon=True)
    thread_speedtest.start()
    logger.info("✅ Worker de Speedtest iniciado")

@app.get("/")
async def index():
    """Retorna o dashboard HTML."""
    return HTMLResponse(CONTEUDO_HTML)

@app.get("/api/status")
async def obter_status():
    """Retorna status atual do sistema."""
    return {
        "sistema": "NOC Commander v12",
        "status": "Operacional",
        "timestamp": datetime.now().isoformat(),
        "eventos_totais": len(ESTADO["eventos"]),
        "alertas_totais": len(ESTADO["alertas"]),
    }

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket para streaming de dados em tempo real."""
    await ws.accept()
    logger.info("📡 Novo cliente WebSocket conectado")
    
    ultima_io = psutil.net_io_counters()
    ultimo_tempo = time.time()
    
    try:
        while True:
            # Coletar métricas locais
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            caminho_disco = "C:" if os.name == "nt" else "/"
            disco = psutil.disk_usage(caminho_disco)
            
            ultima_io, ultimo_tempo, rx, tx = obter_velocidade_rede(ultima_io, ultimo_tempo)
            gpu = obter_dados_gpu()
            
            # Coletar dados WAN
            wan = obter_dados_wan_reais()
            
            # Calcular uptime
            segundos_uptime = int(time.time() - ESTADO["uptime_inicio"])
            uptime_formatado = formatar_tempo_decorrido(segundos_uptime)
            
            # Lógica de alertas
            alerta_ativo = False
            mensagem_alerta = ""
            
            # Verificar limites
            if cpu >= LIMITES["cpu"]:
                alerta_ativo = True
                mensagem_alerta = f"CPU CRÍTICA: {cpu}%"
                ESTADO["contadores_alertas"]["critico"] += 1
            
            elif ram.percent >= LIMITES["ram"]:
                alerta_ativo = True
                mensagem_alerta = f"RAM CRÍTICA: {ram.percent}%"
                ESTADO["contadores_alertas"]["critico"] += 1
            
            # Verificar WAN
            links_down = sum(1 for w in wan if w["status"] == "DOWN")
            if links_down >= 2:
                alerta_ativo = True
                mensagem_alerta = f"WAN CRÍTICA: {links_down} links desconectados"
                ESTADO["contadores_alertas"]["critico"] += 1
            
            # Enviar alerta se necessário
            wpp_enviado = False
            if alerta_ativo:
                wpp_enviado = await enviar_whatsapp(mensagem_alerta)
                registrar_evento(
                    tipo="ALERTA",
                    severidade="CRÍTICO",
                    mensagem=mensagem_alerta,
                    componente="Sistema"
                )
            
            # Atualizar máximos
            ESTADO["metricas_acumuladas"]["cpu_max"] = max(
                ESTADO["metricas_acumuladas"]["cpu_max"], cpu
            )
            ESTADO["metricas_acumuladas"]["ram_max"] = max(
                ESTADO["metricas_acumuladas"]["ram_max"], ram.percent
            )
            
            # Preparar payload
            payload = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "local": {
                    "info": obter_info_host(),
                    "metricas": {
                        "cpu": round(cpu, 1),
                        "ram": round(ram.percent, 1),
                        "disco": round(disco.percent, 1),
                        "rx": formatar_bytes(rx),
                        "tx": formatar_bytes(tx),
                    },
                    "gpu": gpu,
                },
                "velocidade": ESTADO["velocidade"],
                "testando": ESTADO["testando"],
                "wan": wan,
                "uptime": uptime_formatado,
                "alerta": {
                    "ativo": alerta_ativo,
                    "mensagem": mensagem_alerta,
                    "whatsapp_enviado": wpp_enviado
                },
                "contadores": ESTADO["contadores_alertas"],
            }
            
            await ws.send_json(payload)
            await asyncio.sleep(CONFIG["COLETA_INTERVALO"])
    
    except Exception as e:
        logger.error(f"❌ Erro WebSocket: {e}")
    
    finally:
        logger.info("📡 Cliente WebSocket desconectado")

# ═══════════════════════════════════════════════════════════════════════════
# 10. CONTEÚDO HTML DO DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

CONTEUDO_HTML = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOC Commander v12 - Dashboard de Monitoramento</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #020617;
            --card: #0f172a;
            --border: #1e293b;
            --text: #f8fafc;
            --dim: #94a3b8;
            --blue: #38bdf8;
            --green: #4ade80;
            --warn: #facc15;
            --danger: #ef4444;
            --purple: #a855f7;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Inter', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            overflow: hidden;
            padding: 10px;
        }
        
        .container {
            display: grid;
            grid-template-columns: 350px 1fr 400px;
            grid-template-rows: 60px 1fr 180px;
            gap: 12px;
            height: 100%;
        }
        
        .header {
            grid-column: 1 / -1;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 900;
            color: var(--blue);
            letter-spacing: -0.5px;
        }
        
        .kpi-bar {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        .kpi-chip {
            background: var(--card);
            padding: 8px 16px;
            border-radius: 999px;
            border: 1px solid var(--border);
            display: flex;
            gap: 8px;
            align-items: center;
            font-size: 0.85rem;
        }
        
        .box {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 15px;
            display: flex;
            flex-direction: column;
        }
        
        .box-title {
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--dim);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(148,163,184,0.15);
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            font-size: 0.8rem;
            color: var(--dim);
        }
        
        .metric-value {
            font-family: 'JetBrains Mono';
            font-weight: 700;
            color: var(--text);
        }
        
        .progress-bar {
            background: rgba(15,23,42,0.9);
            height: 6px;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 4px;
        }
        
        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 700;
        }
        
        .status-ok {
            background: rgba(74,222,128,0.15);
            color: var(--green);
        }
        
        .status-warn {
            background: rgba(250,204,21,0.15);
            color: var(--warn);
        }
        
        .status-danger {
            background: rgba(239,68,68,0.15);
            color: var(--danger);
        }
        
        .col-left {
            grid-row: 2 / -1;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .col-center {
            grid-row: 2 / 3;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .col-right {
            grid-row: 2 / -1;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .footer {
            grid-column: 2 / 3;
            grid-row: 3 / 4;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
        }
        
        .alert-modal {
            position: fixed;
            inset: 0;
            background: rgba(15,23,42,0.96);
            z-index: 999;
            display: none;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            border: 3px solid var(--danger);
        }
        
        .alert-modal.active {
            display: flex;
        }
        
        .alert-title {
            font-size: 3rem;
            color: var(--danger);
            margin-bottom: 20px;
            font-weight: 900;
        }
        
        .alert-message {
            font-family: 'JetBrains Mono';
            font-size: 1.5rem;
            color: var(--text);
            margin-bottom: 30px;
        }
        
        .btn-acknowledge {
            padding: 12px 32px;
            font-weight: bold;
            cursor: pointer;
            border-radius: 999px;
            border: none;
            background: var(--danger);
            color: white;
            font-size: 1rem;
        }
    </style>
</head>
<body>
    <div class="alert-modal" id="alertModal">
        <div class="alert-title">⚠️ ALERTA CRÍTICO</div>
        <div class="alert-message" id="alertMessage">--</div>
        <button class="btn-acknowledge" onclick="fecharAlerta()">RECONHECER</button>
    </div>
    
    <div class="container">
        <div class="header">
            <div>
                <div class="logo">NOC Commander <span style="font-size:0.8rem; color:var(--dim); font-weight:400">v12</span></div>
                <div style="font-size:0.7rem; color:var(--dim)">Sistema de Monitoramento em Tempo Real</div>
            </div>
            <div class="kpi-bar">
                <div class="kpi-chip">
                    <span style="color:var(--dim)">CPU</span>
                    <span id="kpi-cpu" style="color:var(--blue); font-weight:700">--</span>
                </div>
                <div class="kpi-chip">
                    <span style="color:var(--dim)">RAM</span>
                    <span id="kpi-ram" style="color:var(--purple); font-weight:700">--</span>
                </div>
                <div class="kpi-chip">
                    <span style="color:var(--dim)">WAN</span>
                    <span id="kpi-wan" style="color:var(--green); font-weight:700">--</span>
                </div>
                <div class="kpi-chip">
                    <span style="color:var(--dim)">UPTIME</span>
                    <span id="kpi-uptime" style="color:var(--text); font-weight:700; font-family:'JetBrains Mono'">--:--:--</span>
                </div>
            </div>
        </div>
        
        <div class="col-left">
            <div class="box">
                <div class="box-title">Sistema Local</div>
                <div id="local-info" style="font-size:0.75rem; color:var(--dim); margin-bottom:10px">--</div>
                
                <div class="metric">
                    <span class="metric-label">CPU</span>
                    <span class="metric-value" id="local-cpu">0%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="bar-cpu" style="width:0%; background:var(--blue)"></div>
                </div>
                
                <div class="metric" style="margin-top:10px">
                    <span class="metric-label">RAM</span>
                    <span class="metric-value" id="local-ram">0%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="bar-ram" style="width:0%; background:var(--purple)"></div>
                </div>
                
                <div class="metric" style="margin-top:10px">
                    <span class="metric-label">DISCO</span>
                    <span class="metric-value" id="local-disk">0%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="bar-disk" style="width:0%; background:var(--warn)"></div>
                </div>
            </div>
        </div>
        
        <div class="col-center">
            <div class="box">
                <div class="box-title">Conectividade WAN</div>
                <div id="wan-list" style="font-size:0.8rem"></div>
            </div>
        </div>
        
        <div class="col-right">
            <div class="box">
                <div class="box-title">Velocidade de Internet</div>
                <div class="metric">
                    <span class="metric-label">Download</span>
                    <span class="metric-value" id="speed-down">-- Mbps</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Upload</span>
                    <span class="metric-value" id="speed-up">-- Mbps</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Ping</span>
                    <span class="metric-value" id="speed-ping">-- ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">ISP</span>
                    <span class="metric-value" id="speed-isp" style="font-size:0.75rem">Aguardando...</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="status-badge status-ok" id="speed-status">Online</span>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <div class="box">
                <div class="box-title">Alertas Críticos</div>
                <div style="font-size:2rem; font-weight:900; color:var(--danger)" id="alert-count">0</div>
            </div>
            <div class="box">
                <div class="box-title">Avisos</div>
                <div style="font-size:2rem; font-weight:900; color:var(--warn)" id="warn-count">0</div>
            </div>
            <div class="box">
                <div class="box-title">Eventos Registrados</div>
                <div style="font-size:2rem; font-weight:900; color:var(--text)" id="event-count">0</div>
            </div>
        </div>
    </div>
    
    <script>
        const ws = new WebSocket("ws://localhost:8000/ws");
        
        ws.onmessage = function(event) {
            const dados = JSON.parse(event.data);
            
            // Atualizar KPIs
            document.getElementById("kpi-cpu").textContent = dados.local.metricas.cpu + "%";
            document.getElementById("kpi-ram").textContent = dados.local.metricas.ram + "%";
            document.getElementById("kpi-uptime").textContent = dados.uptime;
            
            // Atualizar métricas locais
            document.getElementById("local-info").textContent = 
                dados.local.info.hostname + " (" + dados.local.info.ip + ")";
            document.getElementById("local-cpu").textContent = dados.local.metricas.cpu + "%";
            document.getElementById("bar-cpu").style.width = dados.local.metricas.cpu + "%";
            
            document.getElementById("local-ram").textContent = dados.local.metricas.ram + "%";
            document.getElementById("bar-ram").style.width = dados.local.metricas.ram + "%";
            
            document.getElementById("local-disk").textContent = dados.local.metricas.disco + "%";
            document.getElementById("bar-disk").style.width = dados.local.metricas.disco + "%";
            
            // Atualizar velocidade
            document.getElementById("speed-down").textContent = dados.velocidade.download + " Mbps";
            document.getElementById("speed-up").textContent = dados.velocidade.upload + " Mbps";
            document.getElementById("speed-ping").textContent = dados.velocidade.ping + " ms";
            document.getElementById("speed-isp").textContent = dados.velocidade.isp;
            document.getElementById("speed-status").textContent = dados.velocidade.status;
            
            // Atualizar WAN
            let wanHtml = "";
            for (let w of dados.wan) {
                let statusClass = w.status === "UP" ? "status-ok" : "status-danger";
                wanHtml += `
                    <div class="metric">
                        <span class="metric-label">${w.nome}</span>
                        <span class="status-badge ${statusClass}">${w.status} (${w.latencia_ms}ms)</span>
                    </div>
                `;
            }
            document.getElementById("wan-list").innerHTML = wanHtml;
            
            // Atualizar contadores
            document.getElementById("alert-count").textContent = dados.contadores.critico;
            document.getElementById("warn-count").textContent = dados.contadores.aviso;
            document.getElementById("event-count").textContent = dados.contadores.info;
            
            // Mostrar alerta se necessário
            if (dados.alerta.ativo) {
                document.getElementById("alertMessage").textContent = dados.alerta.mensagem;
                document.getElementById("alertModal").classList.add("active");
            }
        };
        
        function fecharAlerta() {
            document.getElementById("alertModal").classList.remove("active");
        }
    </script>
</body>
</html>
"""

# ═══════════════════════════════════════════════════════════════════════════
# 11. PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info("NOC COMMANDER v12.0 - INICIANDO SERVIDOR")
    logger.info("=" * 80)
    logger.info(f"🌐 Acesse: http://{CONFIG['HOST']}:{CONFIG['PORTA']}")
    logger.info("=" * 80)
    
    uvicorn.run(
        app,
        host=CONFIG["HOST"],
        port=CONFIG["PORTA"],
        log_level="info"
    )
