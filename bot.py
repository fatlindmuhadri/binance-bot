import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode

# --- KONFIGURIMI I LLOGARISË ---
API_KEY = "vCVPFQecFIZVIin8MlfQENB4RtQ3LvJOEwswEBAeGcUuJx6CHu5AayJvqbvfD3dd"
API_SECRET = "5xSVmS1XGuMIoH0GxB3DUMgcYF49TEoscb6lBeEN1nlyB4ISCAVgwUcInPXeOOkl"
TELEGRAM_TOKEN = "8921013869:AAGPdghtjE8KCJWXX_CaGEthMcYODCeAFDc"
CHAT_ID = "5458100041"

BASE_URL = "https://testnet.binancefuture.com"  # Për Testnet/Demo (ndryshoje në live nëse kalon real)

trades_executed_today = 0
active_symbols = set()

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Gabim në dërgimin e Telegram: {e}")

def binance_request(method, endpoint, params=None):
    if params is None:
        params = {}
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

def get_exchange_info():
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    response = requests.get(url).json()
    symbols_data = []
    
    for s in response.get('symbols', []):
        # Filtrojmë vetëm monedhat që mbarojnë me USDT (përjashtojmë USDC, BUSD, etj.)
        if s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL' and s['quoteAsset'] == 'USDT':
            symbol = s['symbol']
            max_lev = 20
            for bracket in s.get('brackets', []):
                if 'initialLeverage' in bracket:
                    max_lev = max(max_lev, bracket['initialLeverage'])
            symbols_data.append({"symbol": symbol, "max_leverage": max_lev})
            
    return symbols_data

def set_cross_and_leverage(symbol, leverage):
    try:
        binance_request('POST', "/fapi/v1/marginType", {"symbol": symbol, "marginType": "CROSSED"})
    except Exception:
        pass
        
    try:
        binance_request('POST', "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
    except Exception:
        pass

def get_klines(symbol, interval, limit=50):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception:
        return []

def get_account_balance():
    account_info = binance_request('GET', "/fapi/v2/account")
    for asset in account_info.get('assets', []):
        if asset['asset'] == 'USDT':
            return float(asset['availableBalance'])
    return 0.0

def place_binance_order(symbol, side, quantity):
    endpoint = "/fapi/v1/order"
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity
    }
    return binance_request('POST', endpoint, params)

def place_tp_sl_automatic_orders(symbol, side, quantity, tp1, tp2, tp3, tp4, sl):
    close_side = "SELL" if side == "BUY" else "BUY"
    part_qty = round(quantity / 4, 3)
    if part_qty <= 0:
        part_qty = quantity

    tps = [tp1, tp2, tp3, tp4]
    
    for tp_price in tps:
        params = {
            "symbol": symbol,
            "side": close_side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": part_qty,
            "price": round(tp_price, 4),
            "reduceOnly": "true"
        }
        binance_request('POST', "/fapi/v1/order", params)

    sl_params = {
        "symbol": symbol,
        "side": close_side,
        "type": "STOP_MARKET",
        "stopPrice": round(sl, 4),
        "quantity": quantity,
        "reduceOnly": "true"
    }
    binance_request('POST', "/fapi/v1/order", sl_params)

def analyze_high_probability_setup(symbol):
    candles_4h = get_klines(symbol, "4h", 10)
    candles_1h = get_klines(symbol, "1h", 10)
    candles_15m = get_klines(symbol, "15m", 15)
    
    if len(candles_4h) < 5 or len(candles_1h) < 5 or len(candles_15m) < 5:
        return None

    close_4h_latest = float(candles_4h[-1][4])
    close_4h_past = float(candles_4h[-4][4])
    trend_4h = "BULLISH" if close_4h_latest > close_4h_past else "BEARISH"

    price_now = float(candles_15m[-1][4])
    price_prev = float(candles_15m[-3][4])
    change_pct = abs((price_now - price_prev) / price_prev) * 100

    if change_pct < 1.2:
        return None

    if trend_4h == "BULLISH" and price_now > price_prev:
        return "LONG"
    elif trend_4h == "BEARISH" and price_now < price_prev:
        return "SHORT"
        
    return None

def scan_and_execute_trades():
    global trades_executed_today, active_symbols
    
    if trades_executed_today >= 10:
        print("U arrit limiti prej 10 tregtimesh për sot.")
        return

    print(f"Duke kërkuar sinjale USDT (Tregtia {trades_executed_today + 1}/10)...")
    coins = get_exchange_info()
    
    for coin in coins:
        if trades_executed_today >= 10:
            break
            
        symbol = coin["symbol"]
        if symbol in active_symbols:
            continue
            
        chosen_lev = coin["max_leverage"]
        setup = analyze_high_probability_setup(symbol)
        
        if setup:
            klines_15m = get_klines(symbol, "15m", 10)
            if not klines_15m:
                continue
                
            entry_price = float(klines_15m[-1][4])
            set_cross_and_leverage(symbol, chosen_lev)
            
            available_balance = get_account_balance()
            position_usdt = available_balance * 0.05 * chosen_lev
            quantity = round(position_usdt / entry_price, 3)
            
            if quantity <= 0:
                continue

            target_pct_1 = 0.75 / chosen_lev
            target_pct_2 = 1.50 / chosen_lev
            target_pct_3 = 2.25 / chosen_lev
            target_pct_4 = 3.00 / chosen_lev
            sl_pct = 1.50 / chosen_lev  

            if setup == "LONG":
                side = "BUY"
                display_side = "LONG (buy)"
                tp1 = entry_price * (1 + target_pct_1)
                tp2 = entry_price * (1 + target_pct_2)
                tp3 = entry_price * (1 + target_pct_3)
                tp4 = entry_price * (1 + target_pct_4)
                sl = entry_price * (1 - sl_pct)
            else:
                side = "SELL"
                display_side = "SHORT (sell)"
                tp1 = entry_price * (1 - target_pct_1)
                tp2 = entry_price * (1 - target_pct_2)
                tp3 = entry_price * (1 - target_pct_3)
                tp4 = entry_price * (1 - target_pct_4)
                sl = entry_price * (1 + sl_pct)

            order_response = place_binance_order(symbol, side, quantity)
            
            if 'orderId' in order_response:
                trades_executed_today += 1
                active_symbols.add(symbol)
                
                place_tp_sl_automatic_orders(symbol, side, quantity, tp1, tp2, tp3, tp4, sl)
                
                signal_message = (
                    f"🚨 **USDT FUTURES SIGNAL ({trades_executed_today}/10)** 🚨\n"
                    f"🟢 **{symbol} {display_side}**\n"
                    f"⚙️ Margin: **Cross, {chosen_lev}X**\n"
                    f"📍 ENTRY: `{entry_price:.4f}`\n\n"
                    f"🎯 **TARGETS:**\n"
                    f"1. `{tp1:.4f}`\n2. `{tp2:.4f}`\n3. `{tp3:.4f}`\n4. `{tp4:.4f}`\n\n"
                    f"❌ **STOPLOSS:** `{sl:.4f}`"
                )
                send_telegram_message(signal_message)
                print(f"Pozicioni u hap për {symbol} ( USDT )")
                
                time.sleep(10)

if __name__ == "__main__":
    send_telegram_message("🤖 Boti u nis! Duke tregtuar vetëm çiftet USDT me Cross dhe Levë Maksimale.")
    
    while True:
        scan_and_execute_trades()
        time.sleep(600)
