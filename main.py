import os
import time
import random
from datetime import datetime, timedelta
from threading import Thread
from binance.client import Client
from zoneinfo import ZoneInfo

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

def pegar_saldo_moeda(moeda):
    try:
        info = client.get_asset_balance(asset=moeda)
        return float(info['free'])
    except Exception as e:
        print(f"Erro ao pegar saldo {moeda}: {e}")
        return 0

def mostrar_saldo():
    saldo_usdt = pegar_saldo_moeda('USDT')
    saldo_btc = pegar_saldo_moeda('BTC')
    saldo_eth = pegar_saldo_moeda('ETH')
    print(f"[{datetime.now()}] Saldo Atual - USDT: {saldo_usdt:.4f}, BTC: {saldo_btc:.6f}, ETH: {saldo_eth:.6f}")

def ciclo():
    while True:
        # Sua lógica de análise e operações aqui
        print("Rodando análise e operações...")

        time.sleep(60)  # exemplo: 1 minuto entre operações

def log_saldo_periodico():
    while True:
        mostrar_saldo()
        time.sleep(3600)  # a cada 1 hora

if __name__ == '__main__':
    Thread(target=log_saldo_periodico, daemon=True).start()
    Thread(target=ciclo, daemon=True).start()

    while True:
        time.sleep(1)
