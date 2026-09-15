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

# --- LISTA E COIN-EVE DHE LEVA MAX ---
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

def analyze_high_probability_setup(symbol):
    candles_4h = get_klines(symbol, "4h", 10)
    candles_15m = get_klines(symbol, "15m", 15)
    
    if len(candles_4h) < 5 or len(candles_15m) < 5:
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

    print(f"Duke skanuar listën e pastër (Tregtia {trades_executed_today + 1}/10)...")
    
    for symbol, max_lev in CUSTOM_LEVERAGE_MAP.items():
        if trades_executed_today >= 10:
            break
            
        if symbol in active_symbols:
            continue
            
        setup = analyze_high_probability_setup(symbol)
        
        if setup:
            klines_15m = get_klines(symbol, "15m", 10)
            if not klines_15m:
                continue
                
            entry_price = float(klines_15m[-1][4])
            set_cross_and_leverage(symbol, max_lev)
            
            # --- INITIAL MARGIN: Fiks 2% i bilancit të disponueshëm (si në foto) ---
            available_balance = get_account_balance()
            initial_margin_usdt = available_balance * 0.02  # 2% e bilancit
            
            # Vlera totale e pozicionit (Notional Size) = Initial Margin * Leva Max e Coin-it
            position_usdt = initial_margin_usdt * max_lev
            quantity = round(position_usdt / entry_price, 3)
            
            if quantity <= 0:
                continue

            side = "BUY" if setup == "LONG" else "SELL"
            display_side = "LONG (buy)" if setup == "LONG" else "SHORT (sell)"

            order_response = place_binance_order(symbol, side, quantity)
            
            if 'orderId' in order_response:
                trades_executed_today += 1
                active_symbols.add(symbol)
                
                signal_message = (
                    f"🚀 **MARKET SIGNAL ({trades_executed_today}/10)** 🚀\n"
                    f"🟢 **{symbol} {display_side}**\n"
                    f"⚙️ Margin Mode: **Cross, {max_lev}X**\n"
                    f"💰 Initial Margin: **~{initial_margin_usdt:.2f} USDT** (2% e Balancës)\n"
                    f"📍 ENTRY PRICE: `{entry_price:.4f}`"
                )
                send_telegram_message(signal_message)
                print(f"U hap pozicioni Market për {symbol} në Cross me Levë {max_lev}x")
                
                time.sleep(10)

if __name__ == "__main__":
    send_telegram_message("🤖 Boti u përditësua! Tani punon në Market, Cross, me Levë Max dhe 2% Initial Margin.")
    
    while True:
        scan_and_execute_trades()
        time.sleep(600)
