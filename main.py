import os
import time
import threading
from datetime import datetime
from binance.client import Client
import pandas as pd
import numpy as np
import ta
from flask import Flask

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

client = Client(API_KEY, API_SECRET)

app = Flask(__name__)

# Função para obter candles e gerar dataframe
def get_klines(symbol, interval='1h', limit=100):
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        print(f"Erro ao obter candles para {symbol}: {e}")
        return None

# Função que aplica indicadores e gera sinal de compra/venda
def gerar_sinal(df):
    try:
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        df['macd'] = ta.trend.MACD(df['close']).macd()
        df['macd_signal'] = ta.trend.MACD(df['close']).macd_signal()
        df['macd_diff'] = df['macd'] - df['macd_signal']

        rsi = df['rsi'].iloc[-1]
        macd_diff = df['macd_diff'].iloc[-1]

        # Condições simples (exemplo profissional: rsi < 30 e macd_diff positivo -> compra)
        if rsi < 30 and macd_diff > 0:
            return 'BUY'
        elif rsi > 70 and macd_diff < 0:
            return 'SELL'
        else:
            return 'HOLD'
    except Exception as e:
        print(f"Erro ao gerar sinal: {e}")
        return 'HOLD'

# Função para pegar saldo de USDT para operar
def pegar_saldo_usdt():
    try:
        saldo = client.get_asset_balance(asset='USDT')
        return float(saldo['free']) if saldo else 0
    except Exception as e:
        print(f"Erro ao pegar saldo USDT: {e}")
        return 0

# Função para comprar
def comprar(symbol, quantidade):
    try:
        order = client.create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantidade
        )
        print(f"Compra executada: {order}")
        return True
    except Exception as e:
        print(f"Erro na compra {symbol}: {e}")
        return False

# Função para vender
def vender(symbol, quantidade):
    try:
        order = client.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantidade
        )
        print(f"Venda executada: {order}")
        return True
    except Exception as e:
        print(f"Erro na venda {symbol}: {e}")
        return False

# Função principal de análise e trading
def analisar_e_operar():
    while True:
        try:
            saldo_usdt = pegar_saldo_usdt()
            print(f"[{datetime.now()}] Saldo USDT disponível: {saldo_usdt:.2f}")

            # Pega todos os pares com USDT
            info = client.get_exchange_info()
            pares_usdt = [s['symbol'] for s in info['symbols'] if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and 'UPDOWN' not in s['symbol']]

            # Lista para armazenar sinais
            sinais_validos = []

            for simbolo in pares_usdt:
                df = get_klines(simbolo)
                if df is None or df.empty:
                    continue

                sinal = gerar_sinal(df)
                if sinal != 'HOLD':
                    sinais_validos.append((simbolo, sinal))

                if len(sinais_validos) >= 10:  # máximo 10 moedas para diversificar
                    break

            if not sinais_validos:
                print("Nenhum sinal forte detectado. Aguardando próximo ciclo.")
                time.sleep(300)  # Espera 5 minutos
                continue

            # Dividir saldo entre os ativos para compra (para venda deve pegar saldo da moeda)
            saldo_por_ativo = saldo_usdt / len(sinais_validos)

            for simbolo, sinal in sinais_validos:
                if sinal == 'BUY':
                    # Calcular quantidade para comprar
                    ticker_info = client.get_symbol_info(simbolo)
                    step_size = None
                    for filt in ticker_info['filters']:
                        if filt['filterType'] == 'LOT_SIZE':
                            step_size = float(filt['stepSize'])
                            break
                    preco_atual = float(client.get_symbol_ticker(symbol=simbolo)['price'])
                    qtd = saldo_por_ativo / preco_atual
                    # Ajustar quantidade para o step_size
                    if step_size:
                        qtd = (qtd // step_size) * step_size
                    if qtd > 0:
                        comprar(simbolo, round(qtd, 6))
                elif sinal == 'SELL':
                    # Verificar saldo da moeda base
                    moeda_base = simbolo.replace('USDT', '')
                    try:
                        saldo_moeda = float(client.get_asset_balance(moeda_base)['free'])
                    except:
                        saldo_moeda = 0
                    if saldo_moeda > 0:
                        vender(simbolo, round(saldo_moeda, 6))

            print("Ciclo concluído. Esperando próximo...")
            time.sleep(300)  # esperar 5 minutos para o próximo ciclo

        except Exception as e:
            print(f"Erro geral no ciclo: {e}")
            time.sleep(60)

@app.route('/')
def home():
    return "🤖 Bot de Trading Binance rodando!", 200

if __name__ == '__main__':
    threading.Thread(target=analisar_e_operar, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
