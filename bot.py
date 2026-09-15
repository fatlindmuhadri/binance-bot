import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime
from dotenv import load_dotenv

# Ngarko variablat e mjedisit nga skedari .env
load_dotenv()

# --- KONFIGURIMI I LLOGARISË ---
API_KEY = "vCVPFQecFIZVIin8MlfQENB4RtQ3LvJOEwswEBAeGcUuJx6CHu5AayJvqbvfD3dd"
API_SECRET = "5xSVmS1XGuMIoH0GxB3DUMgcYF49TEoscb6lBeEN1nlyB4ISCAVgwUcInPXeOOkl"
TELEGRAM_TOKEN = "8921013869:AAGPdghtjE8KCJWXX_CaGEthMcYODCeAFDc"
CHAT_ID = "5458100041"

BASE_URL = "https://testnet.binancefuture.com"  # Për Testnet/Demo (ndryshoje në live nëse kalon real)

# --- PAUSE PËR LAJMET (True = Tregton, False = Ndalon 2 orë para lajmit) ---
# Mund ta ndryshosh direkt këtu ose në Railway Variables duke shtuar fushën MARKET_ACTIVE
MARKET_ACTIVE = True 

CUSTOM_LEVERAGE_MAP = {
    "AAVEUSDT": 75, "ADAUSDT": 75, "ALGOUSDT": 50, "ANKRUSDT": 50, "APEUSDT": 50,
    "APTUSDT": 50, "ARBUSDT": 75, "ATOMUSDT": 75, "AVAXUSDT": 75, "AXSUSDT": 50,
    "BATUSDT": 50, "BNBUSDT": 100, "BOMEUSDT": 50, "BONKUSDT": 50, "BTCUSDT": 125,
    "CAKEUSDT": 50, "CELOUSDT": 50, "CHZUSDT": 50, "COMPUSDT": 50, "CRVUSDT": 50,
    "DASHUSDT": 50, "DOGEUSDT": 75, "DOTUSDT": 75, "EGLDUSDT": 50, "ENJUSDT": 50,
    "ENSUSDT": 50, "EOSUSDT": 50, "ETCUSDT": 75, "ETHUSDT": 125, "FETUSDT": 75,
    "FILUSDT": 75, "FLOKIUSDT": 50, "FLOWUSDT": 50, "FTMUSDT": 75, "FXSUSDT": 50,
    "GALAUSDT": 50, "GMTUSDT": 50, "GMXUSDT": 50, "GRTUSDT": 75, "HBARUSDT": 50,
    "ICPUSDT": 75, "IMXUSDT": 75, "INJUSDT": 75, "IOSTUSDT": 50, "IOTAUSDT": 50,
    "JASMYUSDT": 50, "JUPUSDT": 50, "KAVAUSDT": 50, "KSMUSDT": 50, "LDOUSDT": 75,
    "LINKUSDT": 75, "LTCUSDT": 75, "MANAUSDT": 50, "MASKUSDT": 50, "MATICUSDT": 75,
    "NEARUSDT": 75, "NEOUSDT": 50, "NOTUSDT": 50, "OGNUSDT": 50, "OMUSDT": 50,
    "ONDOUSDT": 50, "OPUSDT": 75, "PENDLEUSDT": 50, "PEPEUSDT": 75, "PERPUSDT": 50,
    "POLUSDT": 75, "POLYXUSDT": 50, "PYTHUSDT": 50, "QTUMUSDT": 50, "RAYUSDT": 50,
    "RENDERUSDT": 75, "RUNEUSDT": 75, "RVNUSDT": 50, "SANDUSDT": 50, "SEIUSDT": 75,
    "SHIBUSDT": 75, "SKLUSDT": 50, "SNXUSDT": 50, "SOLUSDT": 125, "SSVUSDT": 50,
    "STEEMUSDT": 50, "STXUSDT": 75, "SUIUSDT": 75, "SUSHIUSDT": 50, "THETAUSDT": 50,
    "TIAUSDT": 75, "TNSRUSDT": 50, "TRUMPUSDT": 50, "TRXUSDT": 75, "TURBOUSDT": 50,
    "UNIUSDT": 75, "WLDUSDT": 75, "WOOUSDT": 50, "XLMUSDT": 75, "XRPUSDT": 75,
    "XTZUSDT": 50, "ZECUSDT": 50, "ZENUSDT": 50, "ZROUSDT": 50
}

trades_executed_today = 0
active_symbols = set()
current_day = datetime.now().day

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Gabim në dërgimin e Telegram: {e}")

def binance_request(method, endpoint, params=None):
    if params is None: params = {}
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature
    url = BASE_URL + endpoint
    headers = {"X-MBX-APIKEY": API_KEY}
    if method == 'GET':
        response = requests.get(url, headers=headers, params=params)
    elif method == 'POST':
        response = requests.post(url, headers=headers, params=params)
    return response.json()

def set_cross_and_leverage(symbol, leverage):
    try:
        binance_request('POST', "/fapi/v1/marginType", {"symbol": symbol, "marginType": "CROSSED"})
    except Exception: pass
    try:
        binance_request('POST', "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
    except Exception: pass

def get_klines(symbol, interval, limit=50):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        return requests.get(url, params=params).json()
    except Exception:
        return []

def get_account_balance():
    account_info = binance_request('GET', "/fapi/v2/account")
    for asset in account_info.get('assets', []):
        if asset['asset'] == 'USDT':
            return float(asset['availableBalance'])
    return 0.0

def place_binance_order(symbol, side, quantity):
    return binance_request('POST', "/fapi/v1/order", {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

def place_algo_order(symbol, side, algo_type, trigger_price, quantity):
    endpoint = "/fapi/v1/algoOrder"
    if trigger_price < 5: quantity = round(quantity, 0)
    else: quantity = round(quantity, 2)
    if quantity <= 0: quantity = 1.0
    params = {
        "symbol": symbol, "side": side, "type": algo_type,
        "triggerPrice": round(trigger_price, 4), "quantity": quantity, "reduceOnly": "true"
    }
    return binance_request('POST', endpoint, params)

def is_market_safe_from_news():
    # Kontrollon nëse ke dhënë urdhër për bllokim manual për shkak të lajmeve FOMC/CPI
    env_status = os.environ.get("MARKET_ACTIVE", "True")
    if env_status == "False" or not MARKET_ACTIVE:
        return False
    return True

def analyze_smc_fvg_setup(symbol):
    candles = get_klines(symbol, "15m", 30)
    if len(candles) < 10: return None

    try:
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]

        bullish_fvg = lows[-1] > highs[-3] and closes[-2] > closes[-3]
        bearish_fvg = highs[-1] < lows[-3] and closes[-2] < closes[-3]

        recent_high = max(highs[-15:-3])
        recent_low = min(lows[-15:-3])
        
        market_structure = None
        if closes[-1] > recent_high: market_structure = "BULLISH_BOS"
        elif closes[-1] < recent_low: market_structure = "BEARISH_BOS"

        if bullish_fvg and market_structure == "BULLISH_BOS":
            return {"side": "LONG", "high": recent_high, "low": recent_low}
        elif bearish_fvg and market_structure == "BEARISH_BOS":
            return {"side": "SHORT", "high": recent_high, "low": recent_low}
            
    except Exception:
        return None
    return None

def scan_and_execute_trades():
    global trades_executed_today, active_symbols, current_day
    
    # MBROJTJA: Nëse jemi në kohë lajmesh, boti pezullon skanimin totalisht
    if not is_market_safe_from_news():
        print("⚠️ SKANIMI I PEZULLUAR: Tregu është i bllokuar për shkak të lajmeve të rëndësishme (FOMC/CPI).")
        return

    now_day = datetime.now().day
    if now_day != current_day:
        current_day = now_day
        trades_executed_today = 0
        active_symbols.clear()

    if trades_executed_today >= 10: return

    print(f"Duke skanuar tregun për struktura SMC (Tregtia {trades_executed_today + 1}/10)...")

    for symbol, max_lev in CUSTOM_LEVERAGE_MAP.items():
        if trades_executed_today >= 10: break
        if symbol in active_symbols: continue

        smc_data = analyze_smc_fvg_setup(symbol)
        
        if smc_data:
            klines_15m = get_klines(symbol, "15m", 5)
            if not klines_15m: continue
            
            entry_price = float(klines_15m[-1][4])
            set_cross_and_leverage(symbol, max_lev)
            
            swing_high = smc_data["high"]
            swing_low = smc_data["low"]
            price_range = swing_high - swing_low
            
            if price_range <= 0: continue

            available_balance = get_account_balance()
            initial_margin_usdt = available_balance * 0.02
            position_usdt = initial_margin_usdt * max_lev
            quantity = round(position_usdt / entry_price, 3)
            if quantity <= 0: return

            target_quantity = quantity / 4
            side = "BUY" if smc_data["side"] == "LONG" else "SELL"
            algo_side = "SELL" if smc_data["side"] == "LONG" else "BUY"
            display_side = "LONG (buy)" if smc_data["side"] == "LONG" else "SHORT (sell)"

            if smc_data["side"] == "LONG":
                sl_price = swing_low - (price_range * 0.1)
                tp1 = entry_price + (price_range * 0.236)
                tp2 = entry_price + (price_range * 0.382)
                tp3 = entry_price + (price_range * 0.500)
                tp4 = entry_price + (price_range * 0.618)
            else:
                sl_price = swing_high + (price_range * 0.1)
                tp1 = entry_price - (price_range * 0.236)
                tp2 = entry_price - (price_range * 0.382)
                tp3 = entry_price - (price_range * 0.500)
                tp4 = entry_price - (price_range * 0.618)

            order_response = place_binance_order(symbol, side, quantity)
            if 'orderId' in order_response:
                active_symbols.add(symbol)
                trades_executed_today += 1
                
                place_algo_order(symbol, algo_side, "STOP_MARKET", sl_price, quantity)
                place_algo_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp1, target_quantity)
                place_algo_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp2, target_quantity)
                place_algo_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp3, target_quantity)
                place_algo_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp4, target_quantity)
                
                signal_message = (
                    f"PREMIUM SIGNAL\n"
                    f"🟢{symbol} {display_side}\n"
                    f"Margin: Cross, {max_lev}X\n"
                    f"ENTRY: <{entry_price:.5f}>\n"
                    f"-----------\n"
                    f"🎯TARGETS:\n"
                    f"1. [{tp1:.5f}] 2. [{tp2:.5f}]\n"
                    f"3. [{tp3:.5f}] 4. [{tp4:.5f}]\n"
                    f"-----------\n"
                    f"❌STOPLOSS: [{sl_price:.5f}]"
                )
                send_telegram_message(signal_message)
                time.sleep(5)

            
if __name__ == "__main__":
    send_telegram_message("🤖 Boti aktiv.")
    while True:
        try:
            scan_and_execute_trades()
        except Exception as e:
            print(f"Gabim kritik në ciklin kryesor: {e}")
        time.sleep(10)
