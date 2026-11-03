from __future__ import annotations

import csv
import calendar
import hashlib
import hmac
import io
import json
import math
import os
import re
import secrets
import subprocess
import sys
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from html import escape, unescape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OPTIONS_TRACKER_DATA", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "trades.db"
BOOTSTRAP_PATH = BASE_DIR / "bootstrap_trades.json"
STATIC_DIR = BASE_DIR / "static"
PORTFOLIO_CONFIG_PATH = DATA_DIR / "portfolio_config.json"


def local_secret(name: str, filename: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    path = DATA_DIR / (filename or f".{name.lower()}")
    try:
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except OSError:
        return ""


def local_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


PORTFOLIO_CONFIG = local_json(PORTFOLIO_CONFIG_PATH)


HOST = os.environ.get("OPTIONS_TRACKER_HOST", "127.0.0.1")
PORT = int(os.environ.get("OPTIONS_TRACKER_PORT", "8000"))
AI_MODEL = os.environ.get("OPTIONS_TRACKER_AI_MODEL", "gpt-5")
RELOAD = os.environ.get("OPTIONS_TRACKER_RELOAD", "1").lower() not in {"0", "false", "no", "off"}
RELOAD_INTERVAL = float(os.environ.get("OPTIONS_TRACKER_RELOAD_INTERVAL", "1"))
RELOAD_ID = str(time.time_ns())
AUTO_REFRESH_PRICES = os.environ.get("OPTIONS_TRACKER_AUTO_REFRESH_PRICES", "1").lower() not in {"0", "false", "no", "off"}
PRICE_REFRESH_TIME = os.environ.get("OPTIONS_TRACKER_PRICE_REFRESH_TIME", "00:00")
AUTO_REFRESH_PORTFOLIO = os.environ.get("OPTIONS_TRACKER_AUTO_REFRESH_PORTFOLIO", "1").lower() not in {"0", "false", "no", "off"}
PORTFOLIO_REFRESH_TIME = os.environ.get("OPTIONS_TRACKER_PORTFOLIO_REFRESH_TIME", PRICE_REFRESH_TIME)
PORTFOLIO_REFRESH_USER_ID = int(os.environ.get("OPTIONS_TRACKER_PORTFOLIO_REFRESH_USER_ID", "1"))
PORTFOLIO_DEPOSIT_BASIS = float(os.environ.get(
    "OPTIONS_TRACKER_PORTFOLIO_DEPOSIT_BASIS",
    PORTFOLIO_CONFIG.get("deposit_basis", 0),
))
PORTFOLIO_MANUAL_EQUITY_POINTS = tuple(
    (str(item.get("date") or ""), float(item.get("value") or 0))
    for item in PORTFOLIO_CONFIG.get("manual_equity_points", [])
    if item.get("date") and item.get("value") is not None
)
JIN10_FLASH_URL = os.environ.get("OPTIONS_TRACKER_JIN10_FLASH_URL", "https://flash-api.jin10.com/get_flash_list")
JIN10_APP_ID = local_secret("OPTIONS_TRACKER_JIN10_APP_ID", ".jin10_app_id")
JIN10_REFRESH_SECONDS = int(os.environ.get("OPTIONS_TRACKER_JIN10_REFRESH_SECONDS", "30"))
JIN10_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_JIN10_CACHE_SECONDS", "20"))
JIN10_KEEP_ITEMS = int(os.environ.get("OPTIONS_TRACKER_JIN10_KEEP_ITEMS", "10"))
JIN10_FETCH_LIMIT = int(os.environ.get("OPTIONS_TRACKER_JIN10_FETCH_LIMIT", str(max(120, JIN10_KEEP_ITEMS * 12))))
JIN10_FETCH_PAGES = int(os.environ.get("OPTIONS_TRACKER_JIN10_FETCH_PAGES", "4"))
JIN10_SOURCE_TIMEZONE = os.environ.get("OPTIONS_TRACKER_JIN10_SOURCE_TIMEZONE", "Asia/Shanghai")
LOCAL_TIMEZONE = os.environ.get("OPTIONS_TRACKER_LOCAL_TIMEZONE", "America/Los_Angeles")
LOCAL_TIME_LABEL = os.environ.get("OPTIONS_TRACKER_LOCAL_TIME_LABEL", "PT")
JIN10_CACHE_PATH = DATA_DIR / "jin10_red_flashes.json"
JIN10_CACHE = {"at": 0.0, "items": [], "error": None}
JIN10_CACHE_LOCK = threading.Lock()
GREEDYFEAR_URL = os.environ.get("OPTIONS_TRACKER_GREEDYFEAR_URL", "https://greedyfear.com/")
GREEDYFEAR_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_GREEDYFEAR_CACHE_SECONDS", "300"))
GREEDYFEAR_CACHE = {"at": 0.0, "cards": [], "error": None}
GREEDYFEAR_CACHE_LOCK = threading.Lock()
MARKET_TAPE_REFRESH_SECONDS = int(os.environ.get("OPTIONS_TRACKER_MARKET_TAPE_REFRESH_SECONDS", "30"))
MARKET_QUOTE_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_MARKET_QUOTE_CACHE_SECONDS", "25"))
MARKET_QUOTE_CACHE = {}
MARKET_QUOTE_CACHE_LOCK = threading.Lock()
BENCHMARK_RETURN_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_BENCHMARK_RETURN_CACHE_SECONDS", str(60 * 60)))
BENCHMARK_RETURN_CACHE = {}
BENCHMARK_RETURN_CACHE_LOCK = threading.Lock()
FINNHUB_API_KEY = local_secret("FINNHUB_API_KEY", ".finnhub_api_key")
PLAID_CLIENT_ID = local_secret("PLAID_CLIENT_ID", ".plaid_client_id")
PLAID_SECRET = local_secret("PLAID_SECRET", ".plaid_secret")
PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox").strip().lower()
PLAID_BASE_URL = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}.get(PLAID_ENV, "https://sandbox.plaid.com")
ROBINHOOD_SNAPSHOT_PATH = DATA_DIR / "robinhood_snapshot.json"
FIDELITY_TAXABLE_LEDGER_PATH = DATA_DIR / str(PORTFOLIO_CONFIG.get("taxable_ledger_file", "external_taxable_ledger.json"))
FIDELITY_401K_LEDGER_PATH = DATA_DIR / str(PORTFOLIO_CONFIG.get("retirement_ledger_file", "external_retirement_ledger.json"))
SYMBOL_INTEL_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_SYMBOL_INTEL_CACHE_SECONDS", str(6 * 60 * 60)))
SYMBOL_INTEL_CACHE = {}
SYMBOL_INTEL_CACHE_LOCK = threading.Lock()
EARNINGS_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_EARNINGS_CACHE_SECONDS", str(6 * 60 * 60)))
EARNINGS_MIN_MARKET_CAP = float(os.environ.get("OPTIONS_TRACKER_EARNINGS_MIN_MARKET_CAP", "1000000000"))
EARNINGS_SYMBOL_FALLBACKS = tuple(
    symbol.strip().upper()
    for symbol in os.environ.get(
        "OPTIONS_TRACKER_EARNINGS_SYMBOLS",
        "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,DELL,HPE,PANW,MDB,AVGO,CRM,ORCL,ADBE,NFLX,COST,HD,WMT,TGT",
    ).split(",")
    if symbol.strip()
)
EARNINGS_SYMBOL_LOOKUP_LIMIT = int(os.environ.get("OPTIONS_TRACKER_EARNINGS_SYMBOL_LOOKUP_LIMIT", "36"))
EARNINGS_CACHE = {}
EARNINGS_PROFILE_CACHE = {}
EARNINGS_CACHE_LOCK = threading.Lock()
ECONOMIC_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_ECONOMIC_CACHE_SECONDS", str(15 * 60)))
ECONOMIC_EVENT_TERMS = (
    "cpi", "ppi", "fomc", "nonfarm", "non-farm", "payroll", "unemployment",
    "gdp", "fed interest rate", "federal funds", "jobless claims", "pce",
    "retail sales", "ism", "jolts",
)
ECONOMIC_CACHE = {}
ECONOMIC_CACHE_LOCK = threading.Lock()
HEATMAP_REFRESH_SECONDS = int(os.environ.get("OPTIONS_TRACKER_HEATMAP_REFRESH_SECONDS", "30"))
SUPPORT_RESISTANCE_CACHE_SECONDS = int(os.environ.get("OPTIONS_TRACKER_SUPPORT_RESISTANCE_CACHE_SECONDS", str(15 * 60)))
SUPPORT_RESISTANCE_CACHE = {}
SUPPORT_RESISTANCE_CACHE_LOCK = threading.Lock()
MARKET_TAPE_BASE_SYMBOLS = (
    ("SPY", "SPY"),
    ("QQQ", "QQQ"),
    ("IWM", "IWM"),
    ("BTCUSD", "BTC-USD"),
    ("SPX", "^GSPC"),
    ("Nasdaq Index", "^IXIC"),
    ("Crude Oil", "CL=F"),
    ("AAPL", "AAPL"),
    ("MSFT", "MSFT"),
    ("NVDA", "NVDA"),
    ("AMZN", "AMZN"),
    ("GOOGL", "GOOGL"),
    ("META", "META"),
    ("TSLA", "TSLA"),
)
PRIVATE_MARKET_SYMBOLS = {
    symbol.strip().upper()
    for symbol in os.environ.get("OPTIONS_TRACKER_PRIVATE_SYMBOLS", "").split(",")
    if symbol.strip()
}
WATCHED_EXTENSIONS = {".py", ".css", ".js", ".html", ".json"}
IGNORED_WATCH_DIRS = {".git", ".pytest_cache", "__pycache__", "data"}
USD_CNY_RATE = float(os.environ.get("OPTIONS_TRACKER_USD_CNY_RATE", "7.20"))
RMB_SYMBOL = "\u00a5"
DISPLAY_CURRENCY = "usd"
CURRENCY_CONTEXT = threading.local()
USER_CONTEXT = threading.local()

STRATEGIES = ("Sell Put", "Covered Call", "Put Credit Spread", "Call Credit Spread", "Iron Condor")
BROKER_SOURCES = ("Robinhood", "Webull", "Moomoo", "Fidelity", "IRA", "External")
BROKER_SHORT_LABELS = {
    "Robinhood": "RH",
    "Webull": "WB",
    "Moomoo": "MM",
    "Fidelity": "FD",
    "IRA": "IRA",
    "External": "EX",
    "Unknown": "Unknown",
}
TRADE_BOOK_FILTERS = (
    ("seller", "Option Seller"),
    ("buyer", "Option Buyer"),
    ("day", "Day Trades"),
    ("stock", "Stock Trades"),
)
SYMBOL_STRATEGY_FILTERS = (
    "Option Seller",
    "Option Buyer",
    "Day Trade",
    "Stock",
    "Sell Put",
    "Covered Call",
    "Put Credit Spread",
    "Call Credit Spread",
    "Iron Condor",
    "Option Buyer Call",
    "Option Buyer Put",
    "Option Buyer Combo",
    "Option Buyer Buy combo",
    "Option Buyer Call Debit Spread",
    "Option Buyer Put Debit Spread",
    "Day Trade Call",
    "Day Trade Put",
    "Stock Sell",
)
STATUSES = ("Open", "Closed", "Expired", "Assigned", "Rolled")
SECTORS = (
    "Technology", "Communication Services", "Consumer Discretionary", "Consumer Staples",
    "Financials", "Healthcare", "Industrials", "Energy", "Utilities", "Materials",
    "Real Estate", "ETF / Index / Commodity", "Other / Unknown"
)
TICKER_SECTOR_MAP = {
    "AAOI": "Technology",
    "AAOX": "ETF / Index / Commodity",
    "AAPL": "Technology",
    "ABBV": "Healthcare",
    "ABNB": "Consumer Discretionary",
    "ADBE": "Technology",
    "AEVA": "Technology",
    "AES": "Utilities",
    "AFRM": "Financials",
    "AGEN": "Healthcare",
    "AGBA": "Communication Services",
    "AGRI": "Consumer Staples",
    "AI": "Technology",
    "AIXI": "Technology",
    "AKBA": "Healthcare",
    "AKAM": "Technology",
    "ALAB": "Technology",
    "ALB": "Materials",
    "ALLO": "Healthcare",
    "ALLR": "Healthcare",
    "ALM": "Industrials",
    "AMA": "Communication Services",
    "AMC": "Communication Services",
    "AMDL": "ETF / Index / Commodity",
    "AMD": "Technology",
    "AMAT": "Technology",
    "AMBA": "Technology",
    "AMKR": "Technology",
    "AMZN": "Consumer Discretionary",
    "AMSC": "Industrials",
    "AMTM": "Industrials",
    "AMZU": "ETF / Index / Commodity",
    "ANET": "Technology",
    "APP": "Technology",
    "APVO": "Healthcare",
    "APRE": "Healthcare",
    "ARKK": "ETF / Index / Commodity",
    "AREB": "Consumer Discretionary",
    "ARM": "Technology",
    "ARMG": "ETF / Index / Commodity",
    "ASML": "Technology",
    "ASST": "Communication Services",
    "ASTS": "Communication Services",
    "ATNF": "Healthcare",
    "AUR": "Technology",
    "AVGX": "ETF / Index / Commodity",
    "AVL": "Materials",
    "AVGO": "Technology",
    "AWX": "Industrials",
    "AXTI": "Technology",
    "BA": "Industrials",
    "BABA": "Consumer Discretionary",
    "BAC": "Financials",
    "BB": "Technology",
    "BBAI": "Technology",
    "BCHT": "Healthcare",
    "BDGE": "Financials",
    "BE": "Industrials",
    "BFLY": "Healthcare",
    "BITX": "ETF / Index / Commodity",
    "BJDX": "Healthcare",
    "BMR": "Technology",
    "BNED": "Consumer Discretionary",
    "BOX": "Technology",
    "BPTH": "Healthcare",
    "BRKB": "Financials",
    "BRSHF": "Consumer Staples",
    "BSX": "Healthcare",
    "BSFC": "Consumer Staples",
    "BTBD": "Consumer Discretionary",
    "BTDR": "Financials",
    "BULL": "ETF / Index / Commodity",
    "BYND": "Consumer Staples",
    "C": "Financials",
    "CCL": "Consumer Discretionary",
    "CBRS": "Financials",
    "CCJ": "Energy",
    "CDNS": "Technology",
    "CFLT": "Technology",
    "CHWY": "Consumer Discretionary",
    "CIFR": "Technology",
    "CISS": "Industrials",
    "CL": "Consumer Staples",
    "CLF": "Materials",
    "CLSK": "Financials",
    "CMG": "Consumer Discretionary",
    "CNDG": "ETF / Index / Commodity",
    "COHR": "Technology",
    "COHX": "Healthcare",
    "COIN": "Financials",
    "CONL": "ETF / Index / Commodity",
    "CRCL": "Financials",
    "CRCG": "Financials",
    "CRDO": "Technology",
    "CRM": "Technology",
    "CRML": "Materials",
    "CRSP": "Healthcare",
    "CRWV": "Technology",
    "CSCO": "Technology",
    "CVX": "Energy",
    "CVNA": "Consumer Discretionary",
    "CVS": "Healthcare",
    "CYCC": "Healthcare",
    "DAL": "Industrials",
    "DARE": "Healthcare",
    "DASH": "Consumer Discretionary",
    "DDOG": "Technology",
    "DELL": "Technology",
    "DFNS": "ETF / Index / Commodity",
    "DG": "Consumer Staples",
    "DGXX": "ETF / Index / Commodity",
    "DIS": "Communication Services",
    "DJT": "Communication Services",
    "DKNG": "Consumer Discretionary",
    "DOCN": "Technology",
    "DOCU": "Technology",
    "DRAM": "ETF / Index / Commodity",
    "DXCM": "Healthcare",
    "DXF": "Financials",
    "DXFFY": "Financials",
    "EBAY": "Consumer Discretionary",
    "EDUC": "Consumer Discretionary",
    "ENPH": "Technology",
    "EOSE": "Industrials",
    "ERIC": "Technology",
    "ETHA": "ETF / Index / Commodity",
    "EVLV": "Technology",
    "EXPE": "Consumer Discretionary",
    "F": "Consumer Discretionary",
    "FBL": "ETF / Index / Commodity",
    "FCX": "Materials",
    "FFIE": "Consumer Discretionary",
    "FIG": "Financials",
    "FGL": "Financials",
    "FIGR": "Financials",
    "FLNC": "Industrials",
    "FLY": "Technology",
    "FLYT": "ETF / Index / Commodity",
    "FPS": "ETF / Index / Commodity",
    "FRGT": "Industrials",
    "FRSH": "Technology",
    "FROG": "Technology",
    "FSLR": "Technology",
    "FSLY": "Technology",
    "FSRNQ": "Consumer Discretionary",
    "FTNT": "Technology",
    "FUBO": "Communication Services",
    "FXI": "ETF / Index / Commodity",
    "GDX": "ETF / Index / Commodity",
    "GCT": "Consumer Discretionary",
    "GEVX": "Healthcare",
    "GFS": "Technology",
    "GH": "Healthcare",
    "GILD": "Healthcare",
    "GKOS": "Healthcare",
    "GLD": "ETF / Index / Commodity",
    "GLW": "Technology",
    "GM": "Consumer Discretionary",
    "GME": "Consumer Discretionary",
    "GOLD": "Materials",
    "GOOG": "Communication Services",
    "GOOGL": "Communication Services",
    "GPN": "Financials",
    "GPS": "Consumer Discretionary",
    "GRAB": "Consumer Discretionary",
    "GRRR": "Technology",
    "GSIT": "Technology",
    "GURE": "Materials",
    "GWAV": "Materials",
    "HD": "Consumer Discretionary",
    "HGAS": "Energy",
    "HIMX": "Technology",
    "HIMS": "Healthcare",
    "HIVE": "Financials",
    "HKIT": "Technology",
    "HOLO": "Technology",
    "HON": "Industrials",
    "HOOD": "Financials",
    "HPE": "Technology",
    "HTCR": "Healthcare",
    "HTZ": "Industrials",
    "IAU": "ETF / Index / Commodity",
    "IBIT": "ETF / Index / Commodity",
    "IBIO": "Healthcare",
    "IBM": "Technology",
    "ICHR": "Technology",
    "IGV": "ETF / Index / Commodity",
    "IMNM": "Healthcare",
    "INDO": "Energy",
    "INFQ": "ETF / Index / Commodity",
    "INM": "Healthcare",
    "INTC": "Technology",
    "INTS": "Healthcare",
    "IONQ": "Technology",
    "IOT": "Technology",
    "IOTR": "ETF / Index / Commodity",
    "IREN": "Technology",
    "ISPC": "Healthcare",
    "IWM": "ETF / Index / Commodity",
    "JCI": "Industrials",
    "JD": "Consumer Discretionary",
    "JPM": "Financials",
    "KEEL": "Industrials",
    "KIDZ": "ETF / Index / Commodity",
    "KLAC": "Technology",
    "KMX": "Consumer Discretionary",
    "KO": "Consumer Staples",
    "KRE": "ETF / Index / Commodity",
    "KTOS": "Industrials",
    "KWEB": "ETF / Index / Commodity",
    "KZIA": "Healthcare",
    "LABX": "ETF / Index / Commodity",
    "LAC": "Materials",
    "LAES": "Technology",
    "LAZRQ": "Consumer Discretionary",
    "LCID": "Consumer Discretionary",
    "LEN": "Consumer Discretionary",
    "LGHL": "Financials",
    "LIDR": "Consumer Discretionary",
    "LITE": "Technology",
    "LITX": "ETF / Index / Commodity",
    "LMND": "Financials",
    "LRCX": "Technology",
    "LUNR": "Industrials",
    "LULU": "Consumer Discretionary",
    "LUV": "Industrials",
    "LVS": "Consumer Discretionary",
    "LYFT": "Industrials",
    "MA": "Financials",
    "MARA": "Financials",
    "MAXN": "Technology",
    "MCD": "Consumer Discretionary",
    "MDT": "Healthcare",
    "META": "Communication Services",
    "METU": "ETF / Index / Commodity",
    "MNDY": "Technology",
    "MOD": "Consumer Discretionary",
    "MP": "Materials",
    "MRK": "Healthcare",
    "MRNA": "Healthcare",
    "MRVL": "Technology",
    "MSFT": "Technology",
    "MSTR": "Technology",
    "MSTZ": "ETF / Index / Commodity",
    "MTCH": "Communication Services",
    "MU": "Technology",
    "MUU": "ETF / Index / Commodity",
    "NASA": "ETF / Index / Commodity",
    "NBIL": "ETF / Index / Commodity",
    "NCNA": "Healthcare",
    "NBIS": "Technology",
    "NEBX": "Financials",
    "NEM": "Materials",
    "NET": "Technology",
    "NFLX": "Communication Services",
    "NKE": "Consumer Discretionary",
    "NITO": "Industrials",
    "NNOX": "Healthcare",
    "NNE": "Utilities",
    "NOK": "Technology",
    "NOVA": "Energy",
    "NOW": "Technology",
    "NOWL": "ETF / Index / Commodity",
    "NTNX": "Technology",
    "NU": "Financials",
    "NUAI": "ETF / Index / Commodity",
    "NVDA": "Technology",
    "NVDL": "ETF / Index / Commodity",
    "NVDY": "ETF / Index / Commodity",
    "NVTS": "Technology",
    "NVO": "Healthcare",
    "NXT": "Technology",
    "OCEA": "Healthcare",
    "OKLO": "Utilities",
    "OKLL": "ETF / Index / Commodity",
    "OKTA": "Technology",
    "OLED": "Technology",
    "OMEX": "Industrials",
    "ON": "Technology",
    "ONCO": "Healthcare",
    "ONON": "Consumer Discretionary",
    "ONDS": "Technology",
    "ORCL": "Technology",
    "OSRH": "Healthcare",
    "OSCR": "Healthcare",
    "OUST": "Technology",
    "OXY": "Energy",
    "P": "Communication Services",
    "PALI": "Healthcare",
    "PANW": "Technology",
    "PATH": "Technology",
    "PCT": "Materials",
    "PDD": "Consumer Discretionary",
    "PDYN": "Technology",
    "PENN": "Consumer Discretionary",
    "PEP": "Consumer Staples",
    "PEW": "ETF / Index / Commodity",
    "PFE": "Healthcare",
    "PFSA": "Healthcare",
    "PGR": "Financials",
    "PINS": "Communication Services",
    "PL": "Industrials",
    "PLTR": "Technology",
    "PLSE": "Healthcare",
    "PLTU": "ETF / Index / Commodity",
    "PLTZ": "ETF / Index / Commodity",
    "PLUG": "Industrials",
    "POET": "Technology",
    "PRME": "Healthcare",
    "PRST": "Technology",
    "PSIG": "Industrials",
    "PTPI": "Healthcare",
    "PTRN": "ETF / Index / Commodity",
    "QQQ": "ETF / Index / Commodity",
    "QCOM": "Technology",
    "QRVO": "Technology",
    "QS": "Consumer Discretionary",
    "RANI": "Healthcare",
    "RAYA": "Industrials",
    "RBLX": "Communication Services",
    "RBRK": "Technology",
    "RCAT": "Technology",
    "RCM": "Healthcare",
    "RDW": "Industrials",
    "REVB": "Healthcare",
    "RELI": "Financials",
    "RGTI": "Technology",
    "RH": "Consumer Discretionary",
    "RIOT": "Financials",
    "RIVN": "Consumer Discretionary",
    "RKLB": "Industrials",
    "RR": "Technology",
    "RTX": "Industrials",
    "RXRX": "Healthcare",
    "RXT": "Technology",
    "S": "Technology",
    "SBUX": "Consumer Discretionary",
    "SCHW": "Financials",
    "SCO": "ETF / Index / Commodity",
    "SE": "Consumer Discretionary",
    "SELX": "Healthcare",
    "SG": "Consumer Discretionary",
    "SHPH": "Healthcare",
    "SHOP": "Technology",
    "SIRI": "Communication Services",
    "SKHY": "Industrials",
    "SKK": "Industrials",
    "SLDP": "Consumer Discretionary",
    "SLV": "ETF / Index / Commodity",
    "SMH": "ETF / Index / Commodity",
    "SMCI": "Technology",
    "SMCX": "ETF / Index / Commodity",
    "SMR": "Utilities",
    "SNAP": "Communication Services",
    "SNDK": "Technology",
    "SNOW": "Technology",
    "SNPS": "Technology",
    "SNXX": "ETF / Index / Commodity",
    "SOFI": "Financials",
    "SOXL": "ETF / Index / Commodity",
    "SPOT": "Communication Services",
    "SPCX": "Industrials",
    "SPX": "ETF / Index / Commodity",
    "SPXW": "ETF / Index / Commodity",
    "SPY": "ETF / Index / Commodity",
    "SQ": "Financials",
    "SRPT": "Healthcare",
    "SPCE": "Industrials",
    "SPCH": "Communication Services",
    "SSYS": "Technology",
    "STM": "Technology",
    "STFS": "Consumer Discretionary",
    "SWKS": "Technology",
    "SYM": "Industrials",
    "TGT": "Consumer Staples",
    "TLT": "ETF / Index / Commodity",
    "TMDX": "Healthcare",
    "TSM": "Technology",
    "TDOC": "Healthcare",
    "TE": "Technology",
    "TEAM": "Technology",
    "TELO": "Healthcare",
    "TEM": "Healthcare",
    "TMC": "Materials",
    "TME": "Communication Services",
    "TMF": "ETF / Index / Commodity",
    "TMO": "Healthcare",
    "TNA": "ETF / Index / Commodity",
    "TOON": "Communication Services",
    "TOST": "Technology",
    "TRON": "Technology",
    "TSLA": "Consumer Discretionary",
    "TSLL": "ETF / Index / Commodity",
    "TSMX": "ETF / Index / Commodity",
    "TTD": "Technology",
    "TTWO": "Communication Services",
    "TURB": "Energy",
    "U": "Technology",
    "UAL": "Industrials",
    "UBER": "Industrials",
    "UCAR": "Consumer Discretionary",
    "UNH": "Healthcare",
    "UPS": "Industrials",
    "UPST": "Financials",
    "USAR": "Materials",
    "USEG": "Energy",
    "USO": "ETF / Index / Commodity",
    "UUUU": "Energy",
    "VALE": "Materials",
    "VERB": "Technology",
    "VERI": "Technology",
    "VIAV": "Technology",
    "VIVK": "Industrials",
    "VIVO": "Healthcare",
    "VKTX": "Healthcare",
    "VNRX": "Healthcare",
    "VOYG": "Industrials",
    "VRT": "Industrials",
    "VSCO": "Consumer Discretionary",
    "VST": "Utilities",
    "VTAK": "Healthcare",
    "VZ": "Communication Services",
    "WAL": "Financials",
    "WDC": "Technology",
    "WFC": "Financials",
    "WINT": "Healthcare",
    "WLDS": "Technology",
    "WMT": "Consumer Staples",
    "WNW": "Consumer Discretionary",
    "WOLF": "Technology",
    "WULF": "Financials",
    "XBI": "ETF / Index / Commodity",
    "XLF": "ETF / Index / Commodity",
    "XOM": "Energy",
    "XPEV": "Consumer Discretionary",
    "XYZ": "Financials",
    "YINN": "ETF / Index / Commodity",
    "YMM": "Industrials",
    "YOU": "Technology",
    "ZCMD": "Healthcare",
    "ZETA": "Technology",
    "ZI": "Technology",
    "ZS": "Technology",
    "ZVSA": "Healthcare",
}


def sector_for_ticker(ticker: str, fallback: str = "Other / Unknown") -> str:
    symbol = (ticker or "").strip().upper()
    return TICKER_SECTOR_MAP.get(symbol, fallback)


def resolved_sector(ticker: str, sector: str | None = None) -> str:
    current = (sector or "").strip()
    if current and current != "Other / Unknown":
        return current
    return sector_for_ticker(ticker)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def auth_secret() -> str:
    secret_path = DATA_DIR / ".auth_secret"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(32)
    secret_path.write_text(secret, encoding="utf-8")
    return secret


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def check_password(password: str, stored: str | None) -> bool:
    if stored is None:
        return password == ""
    try:
        algorithm, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()
    return hmac.compare_digest(candidate, digest)


def signed_user_cookie(user_id: int) -> str:
    payload = str(user_id)
    signature = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_user_cookie(value: str | None) -> int | None:
    if not value or "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    expected = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return int(payload)
    except ValueError:
        return None


def current_user_id() -> int:
    return getattr(USER_CONTEXT, "id", 1) or 1


def current_user():
    with closing(db()) as connection:
        return connection.execute("SELECT * FROM users WHERE id=?", (current_user_id(),)).fetchone()


def user_by_id(user_id: int):
    with closing(db()) as connection:
        return connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def user_by_name(username: str):
    with closing(db()) as connection:
        return connection.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()


def all_user_ids() -> list[int]:
    with closing(db()) as connection:
        return [row["id"] for row in connection.execute("SELECT id FROM users ORDER BY id").fetchall()]


def all_users():
    with closing(db()) as connection:
        return connection.execute("SELECT id, username, display_name FROM users ORDER BY id").fetchall()


def brokerage_account():
    with closing(db()) as connection:
        return connection.execute(
            "SELECT * FROM brokerage_accounts WHERE user_id=? AND provider='Robinhood' ORDER BY id DESC LIMIT 1",
            (current_user_id(),),
        ).fetchone()


def brokerage_accounts():
    with closing(db()) as connection:
        return connection.execute(
            """
            SELECT * FROM brokerage_accounts
            WHERE user_id=? AND provider='Robinhood'
            ORDER BY
                CASE WHEN account_type='individual' THEN 0 WHEN account_type='ira_roth' THEN 1 ELSE 2 END,
                id
            """,
            (current_user_id(),),
        ).fetchall()


def save_brokerage_account(form: dict) -> None:
    last4 = re.sub(r"\D", "", form.get("account_last4", ""))[-4:]
    data = {
        "user_id": current_user_id(),
        "provider": "Robinhood",
        "nickname": form.get("nickname", "").strip() or "Robinhood",
        "account_last4": last4,
        "account_type": form.get("account_type", "").strip() or None,
        "trading_type": form.get("trading_type", "").strip() or None,
        "portfolio_value": number(form.get("portfolio_value")),
        "buying_power": number(form.get("buying_power")),
        "stocks_value": number(form.get("stocks_value")),
        "options_value": number(form.get("options_value")),
        "cash_value": number(form.get("cash_value")),
        "last_sync_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": form.get("notes", "").strip() or None,
    }
    existing = None
    if last4:
        with closing(db()) as connection:
            existing = connection.execute(
                "SELECT * FROM brokerage_accounts WHERE user_id=? AND provider='Robinhood' AND account_last4=? ORDER BY id DESC LIMIT 1",
                (current_user_id(), last4),
            ).fetchone()
    if existing is None and not last4:
        existing = brokerage_account()
    fields = tuple(key for key in data if key != "user_id")
    with closing(db()) as connection:
        if existing:
            connection.execute(
                f"UPDATE brokerage_accounts SET {', '.join(field + '=?' for field in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                [data[field] for field in fields] + [existing["id"], current_user_id()],
            )
        else:
            insert_fields = tuple(data.keys())
            connection.execute(
                f"INSERT INTO brokerage_accounts ({','.join(insert_fields)}) VALUES ({','.join('?' for _ in insert_fields)})",
                [data[field] for field in insert_fields],
            )
        connection.commit()


def import_robinhood_snapshot(snapshot: dict) -> tuple[int, int]:
    source_synced_at = snapshot.get("synced_at")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_synced_at = str(source_synced_at or now)[:19]
    accounts = snapshot.get("accounts") or []
    equity_positions = snapshot.get("equity_positions") or []
    user_id = current_user_id()
    synced_accounts = 0
    synced_holdings = 0

    with closing(db()) as connection:
        live_equity_tickers = {
            str(position.get("ticker") or position.get("symbol") or "").strip().upper()
            for position in equity_positions
            if (number(position.get("shares", position.get("quantity"))) or 0) > 0
        }
        open_stock_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM stock_trades WHERE user_id=? AND COALESCE(status, 'Closed')='Open' ORDER BY id",
            (user_id,),
        ).fetchall()]
        def synced_position_key(row):
            ticker = str(row.get("ticker") or "").strip().upper()
            match = re.search(r"account \*{4}(\d{4})", str(row.get("notes") or ""))
            return ticker, match.group(1) if match else ""

        synced_open_by_key = {
            synced_position_key(row): row
            for row in open_stock_rows
            if str(row.get("notes") or "").startswith("Synced from Robinhood")
        }
        manual_open_tickers = {
            str(row.get("ticker") or "").strip().upper()
            for row in open_stock_rows
            if not str(row.get("notes") or "").startswith("Synced from Robinhood")
        }
        legacy_synced_holdings = {
            str(row["ticker"] or "").strip().upper(): dict(row)
            for row in connection.execute(
                "SELECT * FROM stock_holdings WHERE user_id=? AND notes LIKE 'Synced from Robinhood%'",
                (user_id,),
            ).fetchall()
        }
        connection.execute(
            "DELETE FROM stock_holdings WHERE user_id=? AND notes LIKE 'Synced from Robinhood%'",
            (user_id,),
        )
        live_equity_keys = {
            (
                str(position.get("ticker") or position.get("symbol") or "").strip().upper(),
                re.sub(r"\D", "", str(position.get("account_last4") or ""))[-4:],
            )
            for position in equity_positions
            if (number(position.get("shares", position.get("quantity"))) or 0) > 0
        }
        for key, row in synced_open_by_key.items():
            if key not in live_equity_keys:
                connection.execute(
                    "DELETE FROM stock_trades WHERE id=? AND user_id=?",
                    (row["id"], user_id),
                )

        for account in accounts:
            raw_last4 = account.get("account_last4") or account.get("account_number") or ""
            last4 = re.sub(r"\D", "", str(raw_last4))[-4:]
            if not last4:
                continue
            data = {
                "user_id": user_id,
                "provider": "Robinhood",
                "nickname": account.get("nickname") or account.get("name") or "Robinhood",
                "account_last4": last4,
                "account_type": account.get("account_type") or account.get("brokerage_account_type"),
                "trading_type": account.get("trading_type") or account.get("type"),
                "portfolio_value": number(account.get("portfolio_value"), 0),
                "buying_power": number(account.get("buying_power"), 0),
                "stocks_value": number(account.get("stocks_value"), 0),
                "options_value": number(account.get("options_value"), 0),
                "cash_value": number(account.get("cash_value"), 0),
                "last_sync_at": snapshot_synced_at,
                "notes": account.get("notes") or f"Synced from Robinhood MCP snapshot{f' generated {source_synced_at}' if source_synced_at else ''}.",
            }
            existing = connection.execute(
                "SELECT id FROM brokerage_accounts WHERE user_id=? AND provider='Robinhood' AND account_last4=? ORDER BY id DESC LIMIT 1",
                (user_id, last4),
            ).fetchone()
            fields = tuple(key for key in data if key != "user_id")
            if existing:
                connection.execute(
                    f"UPDATE brokerage_accounts SET {', '.join(field + '=?' for field in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                    [data[field] for field in fields] + [existing["id"], user_id],
                )
            else:
                insert_fields = tuple(data.keys())
                connection.execute(
                    f"INSERT INTO brokerage_accounts ({','.join(insert_fields)}) VALUES ({','.join('?' for _ in insert_fields)})",
                    [data[field] for field in insert_fields],
                )
            synced_accounts += 1

        for position in equity_positions:
            ticker = str(position.get("ticker") or position.get("symbol") or "").strip().upper()
            shares = number(position.get("shares", position.get("quantity")))
            if not ticker or shares is None or shares <= 0:
                continue
            current_price = number(position.get("current_price"))
            if ticker in manual_open_tickers:
                if current_price is not None:
                    connection.execute(
                        """
                        UPDATE stock_trades
                        SET current_price=?, as_of=?, updated_at=CURRENT_TIMESTAMP
                        WHERE user_id=? AND UPPER(ticker)=?
                          AND COALESCE(status, 'Closed')='Open'
                          AND COALESCE(notes, '') NOT LIKE 'Synced from Robinhood%'
                        """,
                        (current_price, snapshot_synced_at[:10], user_id, ticker),
                    )
                connection.execute(
                    "DELETE FROM stock_holdings WHERE user_id=? AND UPPER(ticker)=?",
                    (user_id, ticker),
                )
                synced_rows = [row for key, row in synced_open_by_key.items() if key[0] == ticker]
                for synced in synced_rows:
                    connection.execute(
                        "DELETE FROM stock_trades WHERE id=? AND user_id=?",
                        (synced["id"], user_id),
                    )
                synced_holdings += 1
                continue
            avg_cost = number(position.get("avg_cost", position.get("average_buy_price")))
            account_last4 = re.sub(r"\D", "", str(position.get("account_last4") or ""))[-4:]
            notes = "Synced from Robinhood"
            if account_last4:
                notes += f" account ****{account_last4}"
            existing = synced_open_by_key.get((ticker, account_last4))
            legacy = legacy_synced_holdings.get(ticker, {})
            if current_price is None:
                current_price = number(existing.get("current_price")) if existing else number(legacy.get("current_price"))
            as_of = snapshot_synced_at[:10]
            if existing:
                connection.execute(
                    """
                    UPDATE stock_trades
                    SET shares=?, price=?, buy_price=?, current_price=?, as_of=?, broker_source='Robinhood', notes=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=? AND user_id=?
                    """,
                    (shares, avg_cost, avg_cost, current_price, as_of, notes, existing["id"], user_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO stock_trades (
                        user_id, trade_date, ticker, side, status, shares, price, buy_price,
                        sell_price, current_price, as_of, fees, realized_pnl, broker_source, notes
                    ) VALUES (?, ?, ?, 'Buy', 'Open', ?, ?, ?, NULL, ?, ?, 0, 0, 'Robinhood', ?)
                    """,
                    (user_id, as_of, ticker, shares, avg_cost, avg_cost, current_price, as_of, notes),
                )
            connection.execute(
                "DELETE FROM stock_holdings WHERE user_id=? AND UPPER(ticker)=?",
                (user_id, ticker),
            )
            synced_holdings += 1

        total = sum(number(account.get("portfolio_value"), 0) for account in accounts)
        if total:
            connection.execute(
                "INSERT INTO portfolio_snapshots (user_id, total_value, snapshot_at) VALUES (?, ?, ?)",
                (user_id, total, now),
            )
        connection.commit()
    return synced_accounts, synced_holdings


def plaid_configured() -> bool:
    return bool(PLAID_CLIENT_ID and PLAID_SECRET)


def plaid_request(endpoint: str, payload: dict) -> tuple[dict | None, str | None]:
    if not plaid_configured():
        return None, "Plaid is not configured. Add PLAID_CLIENT_ID and PLAID_SECRET first."
    body = dict(payload)
    body.setdefault("client_id", PLAID_CLIENT_ID)
    body.setdefault("secret", PLAID_SECRET)
    request = urllib.request.Request(
        f"{PLAID_BASE_URL}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            return None, parsed.get("error_message") or parsed.get("display_message") or detail
        except json.JSONDecodeError:
            return None, f"Plaid HTTP {exc.code}: {detail[:240]}"
    except Exception as exc:
        return None, str(exc)


def plaid_items():
    with closing(db()) as connection:
        return connection.execute(
            "SELECT * FROM plaid_items WHERE user_id=? ORDER BY institution_name, id",
            (current_user_id(),),
        ).fetchall()


def external_accounts():
    with closing(db()) as connection:
        return connection.execute(
            "SELECT * FROM external_accounts WHERE user_id=? ORDER BY category, institution_name, name",
            (current_user_id(),),
        ).fetchall()


def portfolio_snapshots(limit: int = 24):
    with closing(db()) as connection:
        rows = connection.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id=? ORDER BY snapshot_at DESC LIMIT ?",
            (current_user_id(), limit),
        ).fetchall()
    return list(reversed(rows))


def portfolio_cash_flows():
    with closing(db()) as connection:
        return connection.execute(
            "SELECT * FROM portfolio_cash_flows WHERE user_id=? ORDER BY flow_date, id",
            (current_user_id(),),
        ).fetchall()


def save_portfolio_deposit(flow_date: str, amount: float, account: str = "", notes: str = "") -> None:
    with closing(db()) as connection:
        connection.execute(
            """
            INSERT INTO portfolio_cash_flows (user_id, flow_date, amount, flow_type, account, notes)
            VALUES (?, ?, ?, 'deposit', ?, ?)
            """,
            (current_user_id(), flow_date, amount, account.strip(), notes.strip()),
        )
        connection.commit()


def save_portfolio_snapshot(total_value: float) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(db()) as connection:
        connection.execute(
            "INSERT INTO portfolio_snapshots (user_id, total_value, snapshot_at) VALUES (?, ?, ?)",
            (current_user_id(), total_value, now),
        )
        connection.commit()


def current_portfolio_total() -> float:
    return sum(number(account["portfolio_value"], 0) for account in brokerage_accounts())


def refresh_portfolio_snapshot(import_robinhood: bool = True, sync_plaid: bool = True) -> dict:
    synced_robinhood_accounts = 0
    synced_robinhood_holdings = 0
    synced_plaid_accounts = 0
    errors = []
    if import_robinhood and ROBINHOOD_SNAPSHOT_PATH.exists():
        try:
            status = robinhood_snapshot_status()
            if status.get("needs_import"):
                snapshot = json.loads(ROBINHOOD_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                synced_robinhood_accounts, synced_robinhood_holdings = import_robinhood_snapshot(snapshot)
        except Exception as exc:
            errors.append(f"Robinhood snapshot import failed: {exc}")
    if sync_plaid:
        try:
            synced_plaid_accounts, plaid_errors = sync_plaid_accounts()
            errors.extend(plaid_errors)
        except Exception as exc:
            errors.append(f"Plaid sync failed: {exc}")
    total = current_portfolio_total()
    if total:
        save_portfolio_snapshot(total)
    return {
        "total": total,
        "synced_robinhood_accounts": synced_robinhood_accounts,
        "synced_robinhood_holdings": synced_robinhood_holdings,
        "synced_plaid_accounts": synced_plaid_accounts,
        "errors": errors,
    }


def robinhood_snapshot_status() -> dict:
    db_accounts = [dict(account) for account in brokerage_accounts()]
    db_total = sum(number(account.get("portfolio_value"), 0) for account in db_accounts)
    db_last_sync = max((str(account.get("last_sync_at") or "") for account in db_accounts), default="")
    payload = {
        "exists": False,
        "marker": "",
        "snapshot_synced_at": "",
        "snapshot_total": None,
        "db_total": db_total,
        "db_last_sync": db_last_sync,
        "needs_import": False,
    }
    if not ROBINHOOD_SNAPSHOT_PATH.exists():
        return payload
    try:
        raw = json.loads(ROBINHOOD_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        snapshot_total = sum(number(account.get("portfolio_value"), 0) for account in raw.get("accounts") or [])
        stat = ROBINHOOD_SNAPSHOT_PATH.stat()
        synced_at = str(raw.get("synced_at") or "")
        file_synced_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        snapshot_is_newer = bool(
            not synced_at and file_synced_at and (not db_last_sync or file_synced_at > db_last_sync)
        )
        source_is_newer = bool(synced_at and (not db_last_sync or synced_at[:19] > db_last_sync))
        payload.update(
            exists=True,
            marker=f"{synced_at}:{int(stat.st_mtime)}",
            snapshot_synced_at=synced_at,
            snapshot_total=snapshot_total,
            file_synced_at=file_synced_at,
            needs_import=abs(snapshot_total - db_total) >= 0.005 or snapshot_is_newer or source_is_newer,
        )
    except Exception as exc:
        payload.update(error=str(exc))
    return payload


def robinhood_option_underlyings() -> list[dict]:
    if not ROBINHOOD_SNAPSHOT_PATH.exists():
        return []
    try:
        raw = json.loads(ROBINHOOD_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    underlyings = []
    for item in raw.get("option_underlyings") or []:
        ticker = str(item.get("ticker") or item.get("symbol") or "").strip().upper()
        market_value = number(item.get("market_value"))
        if ticker and market_value is not None and not math.isclose(market_value, 0):
            underlyings.append({"ticker": ticker, "market_value": market_value})
    return sorted(underlyings, key=lambda item: abs(item["market_value"]), reverse=True)


def robinhood_equity_tickers() -> set[str] | None:
    if not ROBINHOOD_SNAPSHOT_PATH.exists():
        return None
    try:
        raw = json.loads(ROBINHOOD_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        str(position.get("ticker") or position.get("symbol") or "").strip().upper()
        for position in raw.get("equity_positions") or []
        if (number(position.get("shares", position.get("quantity"))) or 0) > 0
    }


def upsert_external_account(account: dict) -> None:
    fields = (
        "user_id", "source", "institution_name", "name", "mask", "account_type",
        "account_subtype", "category", "current_balance", "available_balance",
        "currency", "plaid_account_id", "notes",
    )
    values = [account.get(field) for field in fields]
    with closing(db()) as connection:
        existing = connection.execute(
            """
            SELECT id FROM external_accounts
            WHERE user_id=? AND source=? AND plaid_account_id=?
            """,
            (account.get("user_id"), account.get("source"), account.get("plaid_account_id")),
        ).fetchone()
        if existing:
            update_fields = [field for field in fields if field != "user_id"]
            connection.execute(
                f"UPDATE external_accounts SET {', '.join(field + '=?' for field in update_fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [account.get(field) for field in update_fields] + [existing["id"]],
            )
        else:
            connection.execute(
                f"INSERT INTO external_accounts ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                values,
            )
        connection.commit()


def save_external_account(form: dict) -> None:
    name = form.get("name", "").strip() or "Manual account"
    institution = form.get("institution_name", "").strip() or "Manual"
    mask = re.sub(r"\D", "", form.get("mask", ""))[-4:]
    account_type = form.get("account_type", "").strip() or "manual"
    subtype = form.get("account_subtype", "").strip() or account_type
    category = form.get("category", "").strip() or categorize_external_account(account_type, subtype)
    if category not in {"banking", "crypto", "investments", "retirement"}:
        category = "banking"
    upsert_external_account({
        "user_id": current_user_id(),
        "source": "Manual",
        "institution_name": institution,
        "name": name,
        "mask": mask,
        "account_type": account_type,
        "account_subtype": subtype,
        "category": category,
        "current_balance": number(form.get("current_balance")),
        "available_balance": number(form.get("available_balance")),
        "currency": form.get("currency", "").strip() or "USD",
        "plaid_account_id": f"manual:{current_user_id()}:{institution.lower()}:{name.lower()}:{mask}",
        "notes": form.get("notes", "").strip() or None,
    })


def categorize_external_account(account_type: str, subtype: str) -> str:
    raw = f"{account_type} {subtype}".lower()
    if any(term in raw for term in ("ira", "401", "403", "457", "retirement", "roth", "pension")):
        return "retirement"
    if any(term in raw for term in ("investment", "brokerage", "stock", "mutual fund")):
        return "investments"
    if "crypto" in raw:
        return "crypto"
    return "banking"


def create_plaid_link_token() -> tuple[dict | None, str | None]:
    payload = {
        "client_name": "dandan.com Portfolio",
        "country_codes": ["US"],
        "language": "en",
        "products": ["transactions", "investments"],
        "user": {"client_user_id": str(current_user_id())},
    }
    return plaid_request("/link/token/create", payload)


def exchange_plaid_public_token(public_token: str, institution_name: str = "") -> tuple[str, str | None]:
    payload, error = plaid_request("/item/public_token/exchange", {"public_token": public_token})
    if error:
        return "", error
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(db()) as connection:
        connection.execute(
            """
            INSERT INTO plaid_items (user_id, item_id, access_token, institution_name, products, last_sync_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                current_user_id(),
                payload.get("item_id"),
                payload.get("access_token"),
                institution_name or "Plaid account",
                "transactions,investments",
                now,
            ),
        )
        connection.commit()
    return "Plaid account connected.", None


def sync_plaid_accounts() -> tuple[int, list[str]]:
    synced = 0
    errors = []
    for item in plaid_items():
        access_token = item["access_token"]
        balances, error = plaid_request("/accounts/balance/get", {"access_token": access_token})
        if error:
            errors.append(f"{item['institution_name']}: {error}")
            continue
        investment_values = {}
        holdings_payload, holdings_error = plaid_request("/investments/holdings/get", {"access_token": access_token})
        if holdings_payload:
            for holding in holdings_payload.get("holdings", []):
                account_id = holding.get("account_id")
                quantity = number(holding.get("quantity"), 0) or 0
                price = number(holding.get("institution_price"), 0) or 0
                investment_values[account_id] = investment_values.get(account_id, 0) + quantity * price
        elif holdings_error and "not authorized" not in holdings_error.lower():
            errors.append(f"{item['institution_name']} holdings: {holdings_error}")
        institution = item["institution_name"] or "Plaid account"
        for account in balances.get("accounts", []):
            balances_data = account.get("balances") or {}
            current_balance = number(balances_data.get("current"), 0) or 0
            plaid_account_id = account.get("account_id") or ""
            if plaid_account_id in investment_values and investment_values[plaid_account_id]:
                current_balance = investment_values[plaid_account_id]
            account_type = account.get("type") or ""
            subtype = account.get("subtype") or ""
            upsert_external_account({
                "user_id": current_user_id(),
                "source": "Plaid",
                "institution_name": institution,
                "name": account.get("name") or account.get("official_name") or "Account",
                "mask": account.get("mask") or "",
                "account_type": account_type,
                "account_subtype": subtype,
                "category": categorize_external_account(account_type, subtype),
                "current_balance": current_balance,
                "available_balance": number(balances_data.get("available")),
                "currency": balances_data.get("iso_currency_code") or "USD",
                "plaid_account_id": plaid_account_id,
                "notes": account.get("official_name") or "",
            })
            synced += 1
        with closing(db()) as connection:
            connection.execute("UPDATE plaid_items SET last_sync_at=CURRENT_TIMESTAMP WHERE id=?", (item["id"],))
            connection.commit()
    return synced, errors


def fetch_benchmark_series(symbol: str, start_date: date | None, end_date: date | None) -> list[tuple[date, float]]:
    ticker = (symbol or "").strip().upper()
    if not ticker or not start_date or not end_date:
        return []
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    cache_key = (ticker, start_date.isoformat(), end_date.isoformat())
    now = time.time()
    with BENCHMARK_RETURN_CACHE_LOCK:
        cached = BENCHMARK_RETURN_CACHE.get(cache_key)
        if cached and now - cached.get("at", 0) < BENCHMARK_RETURN_CACHE_SECONDS:
            return list(cached.get("series") or [])
    period1 = int(datetime.combine(start_date - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end_date + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}"
        f"?period1={period1}&period2={period2}&interval=1d"
    )
    result = []
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "options-seller-tracker/1.0"})
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = payload.get("chart", {}).get("result") or []
        if rows:
            row = rows[0]
            timestamps = row.get("timestamp") or []
            closes = row.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            dated_closes = []
            for timestamp, close_value in zip(timestamps, closes):
                if close_value in {None, 0}:
                    continue
                close_date = datetime.fromtimestamp(timestamp, timezone.utc).date()
                if start_date <= close_date <= end_date:
                    dated_closes.append((close_date, float(close_value)))
            result = dated_closes
    except Exception:
        result = []
    with BENCHMARK_RETURN_CACHE_LOCK:
        BENCHMARK_RETURN_CACHE[cache_key] = {"at": now, "series": list(result)}
    return result


def benchmark_series_return(series: list[tuple[date, float]]) -> float | None:
    if len(series) < 2 or not series[0][1]:
        return None
    return (series[-1][1] - series[0][1]) / series[0][1]


def fidelity_taxable_ledger() -> dict:
    if not FIDELITY_TAXABLE_LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(FIDELITY_TAXABLE_LEDGER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def fidelity_taxable_series(start_date: date, end_date: date) -> list[dict]:
    ledger = fidelity_taxable_ledger()
    events = []
    for raw_event in ledger.get("events") or []:
        event_date = parse_date(str(raw_event.get("date") or ""))
        if event_date:
            events.append((event_date, raw_event))
    events.sort(key=lambda item: item[0])
    if not events or start_date > end_date:
        return []

    fallback_prices = sorted((
        (parsed, number(raw_price, 0) or 0)
        for raw_date, raw_price in (ledger.get("fallback_prices") or [])
        if (parsed := parse_date(str(raw_date or "")))
    ), key=lambda item: item[0])
    market_prices = {
        price_date: price
        for price_date, price in fetch_benchmark_series("HPE", start_date - timedelta(days=10), end_date)
    }

    def fallback_price(target_date: date) -> float:
        if not fallback_prices:
            return 0.0
        if target_date <= fallback_prices[0][0]:
            return fallback_prices[0][1]
        for (left_date, left_price), (right_date, right_price) in zip(fallback_prices, fallback_prices[1:]):
            if left_date <= target_date <= right_date:
                days = max((right_date - left_date).days, 1)
                progress = (target_date - left_date).days / days
                return left_price + (right_price - left_price) * progress
        return fallback_prices[-1][1]

    events_by_date = {}
    for event_date, event in events:
        events_by_date.setdefault(event_date, []).append(event)
    shares = 0.0
    cash = 0.0
    last_market_price = None
    points = []
    current_day = min(events[0][0], start_date)
    while current_day <= end_date:
        price_override = None
        account_value_override = None
        cash_flow = 0.0
        for event in events_by_date.get(current_day, []):
            if event.get("shares_set") is not None:
                shares = number(event.get("shares_set"), shares) or 0
            else:
                shares += number(event.get("shares_delta"), 0) or 0
            cash += number(event.get("cash_delta"), 0) or 0
            cash_flow += number(event.get("cash_flow"), 0) or 0
            if event.get("cash_after") is not None:
                cash = number(event.get("cash_after"), cash) or 0
            if event.get("price") is not None:
                price_override = number(event.get("price"), 0) or 0
            if event.get("account_value") is not None:
                account_value_override = number(event.get("account_value"), 0) or 0
        if current_day in market_prices:
            last_market_price = market_prices[current_day]
        price = price_override if price_override is not None else (last_market_price or fallback_price(current_day))
        value = account_value_override if account_value_override is not None else shares * price + cash
        if current_day >= start_date:
            points.append({
                "date": current_day,
                "value": value,
                "cash_flow": cash_flow,
                "shares": shares,
                "cash": cash,
                "price": price,
            })
        current_day += timedelta(days=1)
    return points


def fidelity_401k_ledger() -> dict:
    if not FIDELITY_401K_LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(FIDELITY_401K_LEDGER_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def fidelity_401k_series(start_date: date, end_date: date) -> list[dict]:
    ledger = fidelity_401k_ledger()
    events = []
    for raw_event in ledger.get("events") or []:
        event_date = parse_date(str(raw_event.get("date") or ""))
        if event_date:
            events.append((event_date, raw_event))
    events.sort(key=lambda item: item[0])
    if not events or start_date > end_date:
        return []

    checkpoint_date = parse_date(str(ledger.get("as_of") or ""))
    current_funds = {str(fund.get("symbol") or ""): fund for fund in ledger.get("funds") or []}
    price_anchors: dict[str, list[tuple[date, float]]] = {}
    for event_date, event in events:
        quantity = number(event.get("quantity"), 0) or 0
        amount = number(event.get("amount"), 0) or 0
        if quantity and amount:
            price_anchors.setdefault(str(event.get("symbol") or ""), []).append((event_date, abs(amount / quantity)))
    if checkpoint_date:
        for symbol, fund in current_funds.items():
            shares = number(fund.get("shares"), 0) or 0
            current_value = number(fund.get("current_value"), 0) or 0
            if shares and current_value:
                price_anchors.setdefault(symbol, []).append((checkpoint_date, current_value / shares))
    for anchors in price_anchors.values():
        anchors.sort(key=lambda item: item[0])

    def price_at(symbol: str, target_date: date) -> float:
        anchors = price_anchors.get(symbol) or []
        if not anchors:
            return 0.0
        if target_date <= anchors[0][0]:
            return anchors[0][1]
        for (left_date, left_price), (right_date, right_price) in zip(anchors, anchors[1:]):
            if left_date <= target_date <= right_date:
                days = max((right_date - left_date).days, 1)
                progress = (target_date - left_date).days / days
                return left_price + (right_price - left_price) * progress
        return anchors[-1][1]

    events_by_date: dict[date, list[dict]] = {}
    for event_date, event in events:
        events_by_date.setdefault(event_date, []).append(event)
    shares_by_symbol: dict[str, float] = {}
    points = []
    current_day = min(events[0][0], start_date)
    while current_day <= end_date:
        cash_flow = 0.0
        basis_flow = 0.0
        for event in events_by_date.get(current_day, []):
            symbol = str(event.get("symbol") or "")
            shares_by_symbol[symbol] = shares_by_symbol.get(symbol, 0.0) + (number(event.get("quantity"), 0) or 0)
            basis_flow += number(event.get("amount"), 0) or 0
            if str(event.get("action") or "") == "Contributions":
                cash_flow += number(event.get("amount"), 0) or 0
        if checkpoint_date and current_day == checkpoint_date:
            for symbol, fund in current_funds.items():
                shares_by_symbol[symbol] = number(fund.get("shares"), 0) or 0
        fund_values = {
            symbol: shares * price_at(symbol, current_day)
            for symbol, shares in shares_by_symbol.items()
            if shares
        }
        value = sum(fund_values.values())
        if checkpoint_date and current_day == checkpoint_date:
            value = number(ledger.get("current_value"), value) or value
        if current_day >= start_date:
            points.append({
                "date": current_day,
                "value": value,
                "cash_flow": cash_flow,
                "basis_flow": basis_flow,
                "fund_values": fund_values,
            })
        current_day += timedelta(days=1)
    return points


def add_fidelity_taxable_to_portfolio_points(points: list[dict]) -> list[dict]:
    dated_points = [
        (parse_date(str(point.get("date") or "")), point)
        for point in points
        if parse_date(str(point.get("date") or ""))
    ]
    if not dated_points:
        return points
    series = fidelity_taxable_series(dated_points[0][0], dated_points[-1][0])
    if not series:
        return points
    value_by_date = {item["date"]: item["value"] for item in series}
    flow_by_date = {item["date"]: item["cash_flow"] for item in series if item.get("cash_flow")}
    previous_date = None
    for point_date, point in dated_points:
        old_value = number(point.get("value"), 0) or 0
        old_adjustment = (number(point.get("adjusted_value"), old_value) or old_value) - old_value
        point["value"] = old_value + (value_by_date.get(point_date, 0) or 0)
        interval_flow = sum(
            amount for flow_date, amount in flow_by_date.items()
            if (previous_date is None or flow_date > previous_date) and flow_date <= point_date
        )
        point["cash_flow"] = (number(point.get("cash_flow"), 0) or 0) + interval_flow
        future_fidelity_flows = sum(amount for flow_date, amount in flow_by_date.items() if flow_date > point_date)
        point["adjusted_value"] = point["value"] + old_adjustment + future_fidelity_flows
        previous_date = point_date
    return points


def add_fidelity_401k_to_portfolio_points(points: list[dict]) -> list[dict]:
    dated_points = [
        (parse_date(str(point.get("date") or "")), point)
        for point in points
        if parse_date(str(point.get("date") or ""))
    ]
    if not dated_points:
        return points
    series = fidelity_401k_series(dated_points[0][0], dated_points[-1][0])
    if not series:
        return points
    value_by_date = {item["date"]: item["value"] for item in series}
    flow_by_date = {item["date"]: item["cash_flow"] for item in series if item.get("cash_flow")}
    previous_date = None
    for point_date, point in dated_points:
        old_value = number(point.get("value"), 0) or 0
        old_adjustment = (number(point.get("adjusted_value"), old_value) or old_value) - old_value
        point["value"] = old_value + (value_by_date.get(point_date, 0) or 0)
        interval_flow = sum(
            amount for flow_date, amount in flow_by_date.items()
            if (previous_date is None or flow_date > previous_date) and flow_date <= point_date
        )
        point["cash_flow"] = (number(point.get("cash_flow"), 0) or 0) + interval_flow
        future_flows = sum(amount for flow_date, amount in flow_by_date.items() if flow_date > point_date)
        point["adjusted_value"] = point["value"] + old_adjustment + future_flows
        previous_date = point_date
    return points


def is_retirement_account(account: dict) -> bool:
    description = " ".join(str(account.get(field) or "") for field in (
        "account_type", "account_subtype", "category", "name", "nickname",
    )).lower()
    return any(marker in description for marker in ("ira", "401k", "401(k)", "retirement", "roth"))


def primary_brokerage_account(accounts: list[dict]) -> dict | None:
    return next((account for account in accounts if not is_retirement_account(account)), None)


def external_taxable_account(accounts: list[dict]) -> dict | None:
    return next((account for account in accounts if not is_retirement_account(account)), None)


def external_retirement_account(accounts: list[dict]) -> dict | None:
    return next((account for account in accounts if is_retirement_account(account)), None)


def account_display_label(account: dict | None, fallback: str) -> str:
    if not account:
        return fallback
    name = (
        account.get("nickname") or account.get("name") or account.get("institution_name")
        or account.get("provider") or fallback
    )
    mask = account.get("account_last4") or account.get("mask") or ""
    return f"{name} ****{mask}" if mask else str(name)


def portfolio_account_estimates(points_data: list, accounts: list[dict], external_accounts_data: list[dict]) -> list[dict]:
    total_points = sorted((
        (
            parsed,
            number(item.get("value"), 0) or 0,
        )
        for item in points_data
        if isinstance(item, dict) and (parsed := parse_date(str(item.get("date") or "")))
    ), key=lambda item: item[0])
    if not total_points:
        return []

    robinhood = primary_brokerage_account(accounts)
    fidelity = external_taxable_account(external_accounts_data)
    fidelity_401k = external_retirement_account(external_accounts_data)
    ira = next((
        account for account in accounts
        if "ira" in f'{account.get("account_type") or ""} {account.get("nickname") or ""}'.lower()
    ), None)
    ira_current_value = number(ira.get("portfolio_value"), 0) if ira else 0

    start_date, end_date = total_points[0][0], total_points[-1][0]
    fidelity_series = fidelity_taxable_series(start_date, end_date) if fidelity else []
    fidelity_values = [(item["date"], item["value"]) for item in fidelity_series]
    fidelity_flow_by_date = {item["date"]: item["cash_flow"] for item in fidelity_series if item.get("cash_flow")}
    fidelity_401k_history = fidelity_401k_series(start_date, end_date) if fidelity_401k else []
    fidelity_401k_values = [(item["date"], item["value"]) for item in fidelity_401k_history]
    fidelity_401k_cash_flow_by_date = {item["date"]: item["cash_flow"] for item in fidelity_401k_history if item.get("cash_flow")}
    fidelity_401k_basis_flow_by_date = {item["date"]: item["basis_flow"] for item in fidelity_401k_history if item.get("basis_flow")}
    total_flow_by_date = {
        parsed: number(item.get("cash_flow"), 0) or 0
        for item in points_data
        if isinstance(item, dict) and (parsed := parse_date(str(item.get("date") or "")))
    }
    ira_pnl_by_date = {}
    for trade in symbol_trade_records():
        closed = parse_date(trade.get("close_date"))
        if trade.get("status") == "Open" or not closed or trade.get("net_pnl") is None:
            continue
        if broker_source_for_row(trade) == "IRA" and start_date <= closed <= end_date:
            ira_pnl_by_date[closed] = ira_pnl_by_date.get(closed, 0.0) + (number(trade.get("net_pnl"), 0) or 0)

    ira_running_value = ira_current_value - sum(ira_pnl_by_date.values())
    ira_values = []
    current_day = start_date
    while current_day <= end_date:
        ira_running_value += ira_pnl_by_date.get(current_day, 0.0)
        ira_values.append((current_day, ira_running_value))
        current_day += timedelta(days=1)

    def ira_value_at(target_date: date) -> float:
        latest = ira_values[0][1] if ira_values else ira_current_value
        for series_date, series_value in ira_values:
            if series_date > target_date:
                break
            latest = series_value
        return latest

    def fidelity_value_at(target_date: date) -> float:
        latest = 0.0
        for series_date, series_value in fidelity_values:
            if series_date > target_date:
                break
            latest = series_value
        return latest

    def fidelity_401k_value_at(target_date: date) -> float:
        latest = 0.0
        for series_date, series_value in fidelity_401k_values:
            if series_date > target_date:
                break
            latest = series_value
        return latest

    robinhood_values = [
        (
            point_date,
            total_value - fidelity_value_at(point_date) - fidelity_401k_value_at(point_date) - ira_value_at(point_date),
        )
        for point_date, total_value in total_points
    ]
    robinhood_flow_by_date = {}
    previous_point_date = None
    for point_date, _total_value in total_points:
        fidelity_interval_flow = sum(
            amount
            for flow_date, amount in fidelity_flow_by_date.items()
            if (previous_point_date is None or flow_date > previous_point_date) and flow_date <= point_date
        )
        fidelity_401k_interval_flow = sum(
            amount
            for flow_date, amount in fidelity_401k_cash_flow_by_date.items()
            if (previous_point_date is None or flow_date > previous_point_date) and flow_date <= point_date
        )
        robinhood_flow = total_flow_by_date.get(point_date, 0) - fidelity_interval_flow - fidelity_401k_interval_flow
        if robinhood_flow:
            robinhood_flow_by_date[point_date] = robinhood_flow
        previous_point_date = point_date

    result = []
    for key, label, values, fallback_current in (
        ("account-robinhood", account_display_label(robinhood, "Brokerage"), robinhood_values, number(robinhood.get("portfolio_value"), 0) if robinhood else 0),
        ("account-fidelity", account_display_label(fidelity, "External account"), fidelity_values, number(fidelity.get("current_balance"), 0) if fidelity else 0),
        ("account-fidelity-401k", account_display_label(fidelity_401k, "Retirement account"), fidelity_401k_values, number(fidelity_401k.get("current_balance"), 0) if fidelity_401k else 0),
        ("account-ira", account_display_label(ira, "IRA"), ira_values, ira_current_value),
    ):
        if (
            (key == "account-robinhood" and not robinhood)
            or (key == "account-fidelity" and not fidelity)
            or (key == "account-fidelity-401k" and not fidelity_401k)
            or (key == "account-ira" and not ira)
        ):
            continue
        current_value = values[-1][1] if values else fallback_current
        result.append({
            "key": key,
            "label": label,
            "values": values,
            "cash_flows": (
                fidelity_flow_by_date if key == "account-fidelity"
                else fidelity_401k_basis_flow_by_date if key == "account-fidelity-401k"
                else robinhood_flow_by_date if key == "account-robinhood"
                else {}
            ),
            "current_value": current_value,
            "return": (values[-1][1] - values[0][1]) / values[0][1] if values and values[0][1] else None,
        })
    return result


def portfolio_return_controls(points_data: list, selected_benchmarks=None) -> str:
    selected_benchmarks = set(selected_benchmarks or ())
    values = [number(item.get("value"), 0) or 0 for item in points_data if isinstance(item, dict)]
    if not values:
        return ""
    dates = [
        parsed
        for item in points_data
        if isinstance(item, dict) and (parsed := parse_date(str(item.get("date") or "")))
    ]
    start_date = dates[0] if dates else None
    end_date = dates[-1] if dates else None
    benchmarks = (
        ("sp", "S&P", benchmark_series_return(fetch_benchmark_series("SPY", start_date, end_date))),
        ("nasdaq", "Nasdaq", benchmark_series_return(fetch_benchmark_series("QQQ", start_date, end_date))),
    )
    tags = "".join(
        f'<input class="portfolio-benchmark-toggle {escape(key)}-toggle" data-portfolio-overlay="{escape(key)}" id="portfolio-benchmark-{escape(key)}" type="checkbox" {"checked" if key in selected_benchmarks else ""}>'
        f'<label class="portfolio-benchmark-label {escape(key)}" for="portfolio-benchmark-{escape(key)}">'
        f'<span>{escape(label)}</span><b>{pct(value)}</b></label>'
        for key, label, value in benchmarks
    )
    return f'<div class="portfolio-benchmark-controls" aria-label="Portfolio benchmark overlays">{tags}</div>'


PORTFOLIO_RETURN_METHODS = {
    "simple": "Simple weighted",
    "time": "Time weighted",
}


def portfolio_return_method_options(selected_method: str, selected_range: str, selected_account: str = "", selected_benchmarks=None) -> str:
    options = "".join(
        f'<option value="{escape(key)}" {"selected" if key == selected_method else ""}>{escape(label)}</option>'
        for key, label in PORTFOLIO_RETURN_METHODS.items()
    )
    return f'''<form class="portfolio-return-method" method="get" action="/brokerage">
      <input type="hidden" name="range" value="{escape(selected_range)}">
      {f'<input type="hidden" name="account" value="{escape(selected_account)}">' if selected_account else ''}
      {''.join(f'<input type="hidden" name="benchmark" value="{escape(key)}">' for key in sorted(set(selected_benchmarks or ())))}
      <label for="portfolio-return-method">Return method</label>
      <select id="portfolio-return-method" name="method">{options}</select>
    </form>'''


def portfolio_method_note(selected_method: str) -> str:
    notes = {
        "simple": "Simple return subtracts deposits; the chart back-adjusts earlier values for comparability.",
        "time": "Time-weighted return removes deposits by date; the chart back-adjusts earlier values for comparability.",
    }
    return f'<span class="portfolio-method-note">{escape(notes.get(selected_method, notes["simple"]))}</span>'


def portfolio_return_series(points_data: list, baseline_value: float | None = None, return_method: str = "simple") -> list[float | None]:
    if not points_data:
        return []
    values = [number(item.get("value"), 0) or 0 for item in points_data]
    baseline = number(baseline_value, 0) if baseline_value is not None else values[0]
    baseline = baseline or values[0]
    returns: list[float | None] = [0.0 if baseline else None]
    if return_method == "time":
        growth = 1.0
        for index in range(1, len(values)):
            previous = values[index - 1]
            cash_flow = number(points_data[index].get("cash_flow"), 0) or 0
            if previous:
                growth *= (values[index] - cash_flow) / previous
                returns.append(growth - 1)
            else:
                returns.append(None)
        return returns
    cumulative_cash_flow = 0.0
    gross_contributions = max(baseline, 0)
    for index in range(1, len(values)):
        cash_flow = number(points_data[index].get("cash_flow"), 0) or 0
        cumulative_cash_flow += cash_flow
        gross_contributions += max(cash_flow, 0)
        gain = values[index] - baseline - cumulative_cash_flow
        denominator = baseline or gross_contributions
        returns.append(gain / denominator if denominator else None)
    return returns


def portfolio_overview_chart(
    points_data: list,
    baseline_value: float | None = None,
    return_method: str = "simple",
    chart_label: str = "Portfolio",
    show_benchmarks: bool = True,
    active_benchmarks=None,
) -> str:
    return_method = return_method if return_method in PORTFOLIO_RETURN_METHODS else "simple"
    method_label = PORTFOLIO_RETURN_METHODS[return_method]
    points_data = [
        item if isinstance(item, dict) else {"date": "", "value": item}
        for item in (points_data or [])
    ]
    raw_values = [number(item.get("value"), 0) or 0 for item in points_data]
    values = [number(item.get("adjusted_value"), raw_value) or 0 for item, raw_value in zip(points_data, raw_values)]
    if not raw_values:
        return '<div class="portfolio-chart empty">No synced balance history yet.</div>'
    baseline = number(baseline_value, 0) if baseline_value is not None else raw_values[0]
    if not baseline:
        baseline = raw_values[0]
    visual_baseline = values[0] or baseline
    portfolio_returns = portfolio_return_series(points_data, baseline, return_method)
    portfolio_returns = [
        item.get("return_pct") if "return_pct" in item else portfolio_returns[index]
        for index, item in enumerate(points_data)
    ]
    width, height = 960, 260
    top, right, bottom, left = 18, 118, 24, 8
    dated_points = []
    for index, item in enumerate(points_data):
        item_date = parse_date(str(item.get("date") or ""))
        if item_date:
            dated_points.append((index, item_date))
    use_time_scale = len(dated_points) == len(points_data) and len(dated_points) > 1
    benchmark_value_series = []
    if use_time_scale:
        start_date = dated_points[0][1]
        end_date = dated_points[-1][1]
        total_days = max((end_date - start_date).days, 1)
        if show_benchmarks:
            for key, symbol, label in (("sp", "SPY", "S&P"), ("nasdaq", "QQQ", "Nasdaq")):
                series = fetch_benchmark_series(symbol, start_date, end_date)
                if len(series) >= 2 and series[0][1]:
                    benchmark_value_series.append({
                        "key": key,
                        "label": label,
                        "values": [(series_date, visual_baseline * close_value / series[0][1]) for series_date, close_value in series],
                    })
    else:
        x_step = (width - left - right) / max(1, len(values) - 1)
    active_benchmarks = set(active_benchmarks or ())
    scale_values = list(values)
    for series in benchmark_value_series:
        if series["key"] in active_benchmarks:
            scale_values.extend(value for _series_date, value in series["values"])
    high, low = max(scale_values), min(scale_values)
    if math.isclose(high, low):
        pad = max(1, abs(high) * 0.02)
        high += pad
        low -= pad
    else:
        pad = (high - low) * 0.08
        high += pad
        low -= pad

    def y_for(value):
        return top + (high - value) / (high - low) * (height - top - bottom)

    def x_for(index, item):
        if use_time_scale:
            item_date = parse_date(str(item.get("date") or "")) or start_date
            return left + ((item_date - start_date).days / total_days) * (width - left - right)
        return left + index * x_step

    points = [(x_for(index, item), y_for(value)) for index, (item, value) in enumerate(zip(points_data, values))]

    # Add deterministic, display-only bridge points so sparse snapshots read as a
    # continuous history. Real snapshot coordinates remain exact and continue to
    # drive returns, cash-flow markers, and hover details.
    display_points = [points[0]]
    for segment_index, ((start_x, start_y), (end_x, end_y)) in enumerate(zip(points, points[1:])):
        segment_width = abs(end_x - start_x)
        bridge_count = min(28, max(2, math.ceil(segment_width / (10 if show_benchmarks else 18))))
        phase = (segment_index % 5) * 0.73
        amplitude = min(10.0, max(2.4, abs(end_y - start_y) * 0.07))
        for bridge_index in range(1, bridge_count):
            progress = bridge_index / bridge_count
            eased = progress * progress * (3 - 2 * progress)
            bridge_x = start_x + (end_x - start_x) * progress
            base_y = start_y + (end_y - start_y) * eased
            wave = math.sin(math.pi * progress) * (
                0.68 * math.sin((7.2 * math.pi * progress) + phase)
                + 0.32 * math.sin((13.6 * math.pi * progress) + phase * 1.7)
            )
            bridge_y = min(height - bottom, max(top, base_y + wave * amplitude))
            display_points.append((bridge_x, bridge_y))
        display_points.append((end_x, end_y))
    def benchmark_pct_at(series_values, target_date):
        if not target_date or not series_values or not visual_baseline:
            return None
        latest_value = None
        for series_date, series_value in series_values:
            if series_date <= target_date:
                latest_value = series_value
            else:
                break
        return (latest_value - visual_baseline) / visual_baseline if latest_value is not None else None

    hover_comparisons = []
    for index, (item, value, raw_value) in enumerate(zip(points_data, values, raw_values)):
        item_date = parse_date(str(item.get("date") or ""))
        rows = [{
            "key": "portfolio",
            "label": f"{chart_label} ({method_label})",
            "pct": pct(portfolio_returns[index] if index < len(portfolio_returns) else None),
        }]
        if item.get("account_value") is not None:
            rows.append({"key": "balance", "label": "Account value", "pct": money(item.get("account_value"))})
        if not math.isclose(value, raw_value):
            rows.append({"key": "adjustment", "label": "Back-adjusted value", "pct": money(value)})
        cash_flow = number(item.get("activity"), number(item.get("cash_flow"), 0)) or 0
        if cash_flow:
            rows.append({
                "key": "cash-flow",
                "label": "Deposit" if cash_flow > 0 else "Withdrawal",
                "pct": f"+{money(cash_flow)}" if cash_flow > 0 else money(cash_flow),
            })
        for series in benchmark_value_series:
            series_return = benchmark_pct_at(series["values"], item_date)
            rows.append({
                "key": series["key"],
                "label": series.get("label") or series["key"].upper(),
                "pct": pct(series_return),
            })
        hover_comparisons.append(rows)

    benchmark_paths = []
    if use_time_scale:
        for series in benchmark_value_series:
            series_points = []
            for series_date, value in series["values"]:
                x = left + ((series_date - start_date).days / total_days) * (width - left - right)
                series_points.append((x, y_for(value)))
            if len(series_points) >= 2:
                path_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in series_points)
                series_key = escape(str(series["key"]))
                end_x, end_y = series_points[-1]
                benchmark_paths.append(
                    f'<polyline points="{path_points}" class="portfolio-benchmark-line benchmark-{series_key}"/>'
                    f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="3.8" '
                    f'class="portfolio-benchmark-endpoint benchmark-{series_key}"/>'
                )
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in display_points)
    profit_baseline_y = y_for(visual_baseline)
    profit_baseline_ratio = max(0, min(100, (profit_baseline_y - top) / (height - top - bottom) * 100))
    area = f"{display_points[0][0]:.2f},{profit_baseline_y:.2f} {polyline} {display_points[-1][0]:.2f},{profit_baseline_y:.2f}"
    cash_flow_markers = []
    for index, item in enumerate(points_data):
        cash_flow = number(item.get("activity"), number(item.get("cash_flow"), 0)) or 0
        if cash_flow:
            marker_x, marker_y = points[index]
            flow_label = "Deposit" if cash_flow > 0 else "Withdrawal"
            cash_flow_markers.append(
                f'<line x1="{marker_x:.2f}" x2="{marker_x:.2f}" y1="{top}" y2="{height - bottom}" class="portfolio-cash-flow-line"/>'
                f'<circle cx="{marker_x:.2f}" cy="{marker_y:.2f}" r="4" class="portfolio-cash-flow-dot"><title>{flow_label} {money(cash_flow)}</title></circle>'
            )
    cumulative_hover_flow = 0.0
    hover_points = []
    for index, (item, value, raw_value) in enumerate(zip(points_data, values, raw_values)):
        if index:
            cumulative_hover_flow += number(item.get("cash_flow"), 0) or 0
        change_value = value - visual_baseline if baseline else raw_value - cumulative_hover_flow
        point_return = portfolio_returns[index] if index < len(portfolio_returns) else None
        hover_points.append({
            "date": str(item.get("date") or ""),
            "value": value,
            "display": money(value),
            "change": change_value,
            "changeDisplay": money(change_value),
            "changePctDisplay": pct(point_return),
            "changeClass": "positive" if (point_return if point_return is not None else change_value) >= 0 else "negative",
            "comparisons": hover_comparisons[index],
            "x": round(points[index][0], 2),
            "y": round(points[index][1], 2),
        })
    hover_data = escape(json.dumps(hover_points), quote=True)
    grid = []
    labels = []
    for ratio in (0.0, 0.5, 1.0):
        y = top + ratio * (height - top - bottom)
        value = high - ratio * (high - low)
        grid.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" class="portfolio-grid-line"/>')
        labels.append(f'<text x="{width - right + 12}" y="{y + 4:.2f}" class="portfolio-y-label">{money(value)}</text>')
    final_return = portfolio_returns[-1] if portfolio_returns else None
    final_tone = "positive" if (final_return if final_return is not None else values[-1] - visual_baseline) >= 0 else "negative"
    return f'''<svg class="portfolio-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Portfolio value chart" data-portfolio-chart data-return-method="{escape(return_method)}" data-portfolio-points="{hover_data}">
      <defs>
        <linearGradient id="portfolioProfitFill" x1="0" y1="{top}" x2="0" y2="{height - bottom}" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#089981" stop-opacity=".28"/><stop offset="{profit_baseline_ratio:.2f}%" stop-color="#089981" stop-opacity=".05"/>
          <stop offset="{profit_baseline_ratio:.2f}%" stop-color="#f23645" stop-opacity=".05"/><stop offset="100%" stop-color="#f23645" stop-opacity=".30"/>
        </linearGradient>
        <linearGradient id="portfolioLineGradient" x1="0" y1="{top}" x2="0" y2="{height - bottom}" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#089981"/><stop offset="{profit_baseline_ratio:.2f}%" stop-color="#089981"/>
          <stop offset="{profit_baseline_ratio:.2f}%" stop-color="#f23645"/><stop offset="100%" stop-color="#f23645"/>
        </linearGradient>
      </defs>
      <g>{"".join(grid)}</g><line x1="{left}" y1="{profit_baseline_y:.2f}" x2="{width - right}" y2="{profit_baseline_y:.2f}" class="portfolio-profit-baseline"/><polygon points="{area}" class="portfolio-area"/>{''.join(benchmark_paths)}<polyline points="{polyline}" class="portfolio-line"/>{''.join(cash_flow_markers)}
      <circle cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="5" class="portfolio-dot {final_tone}"/><g>{"".join(labels)}</g>
      <line x1="{points[-1][0]:.2f}" x2="{points[-1][0]:.2f}" y1="{top}" y2="{height - bottom}" class="portfolio-hover-line"/>
      <circle cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="5" class="portfolio-hover-dot"/>
      <rect x="{left}" y="{top}" width="{width - left - right}" height="{height - top - bottom}" class="portfolio-hit-area"/>
    </svg>'''


def snapshot_date(row) -> date | None:
    raw_value = row["snapshot_at"] if "snapshot_at" in row.keys() else row.get("snapshot_at")
    raw = str(raw_value or "")[:19]
    for value, fmt in ((raw[:19], "%Y-%m-%d %H:%M:%S"), (raw[:10], "%Y-%m-%d")):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def portfolio_range_values(snapshots, selected_range: str, current_total: float, cash_flows=None) -> list[dict]:
    selected_range = selected_range if selected_range in {"1w", "1m", "3m", "6m", "ytd", "1y", "all"} else "1w"
    manual_values = {
        parsed: value
        for raw_date, value in PORTFOLIO_MANUAL_EQUITY_POINTS
        if (parsed := parse_date(raw_date))
    }
    latest_manual_date = max(manual_values.keys(), default=None)
    values = []
    for row in snapshots:
        snap_date = snapshot_date(row)
        value = number(row["total_value"], 0)
        raw_at = row["snapshot_at"] if "snapshot_at" in row.keys() else ""
        if snap_date and value and (not latest_manual_date or snap_date > latest_manual_date):
            values.append((str(raw_at or ""), snap_date, value))
    values.sort(key=lambda item: item[0])
    daily_values = dict(manual_values)
    for _, snap_date, value in values:
        daily_values[snap_date] = value
    cash_flow_by_date = {}
    for flow in cash_flows or []:
        flow_date = parse_date(str(flow["flow_date"] if "flow_date" in flow.keys() else flow.get("flow_date") or ""))
        amount = number(flow["amount"] if "amount" in flow.keys() else flow.get("amount"), 0) or 0
        if flow_date and amount:
            cash_flow_by_date[flow_date] = cash_flow_by_date.get(flow_date, 0) + amount
    for flow_date, amount in sorted(cash_flow_by_date.items()):
        if flow_date in daily_values:
            continue
        previous_dates = [value_date for value_date in daily_values if value_date < flow_date]
        if previous_dates:
            previous_date = max(previous_dates)
            daily_values[flow_date] = daily_values[previous_date] + amount
    values = sorted(daily_values.items(), key=lambda item: item[0])
    today = date.today()
    cutoff = None
    if selected_range == "1w":
        cutoff = today - timedelta(days=7)
    elif selected_range == "1m":
        cutoff = today - timedelta(days=31)
    elif selected_range == "3m":
        cutoff = today - timedelta(days=93)
    elif selected_range == "6m":
        cutoff = today - timedelta(days=186)
    elif selected_range == "ytd":
        cutoff = date(today.year, 1, 1)
    elif selected_range == "1y":
        cutoff = today - timedelta(days=366)
    if cutoff:
        values = [(snap_date, value) for snap_date, value in values if snap_date >= cutoff]
    points = [
        {"date": snap_date.isoformat(), "value": value, "cash_flow": cash_flow_by_date.get(snap_date, 0)}
        for snap_date, value in values
    ]
    if current_total:
        if points and points[-1]["date"] == today.isoformat():
            points[-1]["value"] = current_total
        elif not points or not math.isclose(points[-1]["value"], current_total):
            points.append({"date": today.isoformat(), "value": current_total, "cash_flow": cash_flow_by_date.get(today, 0)})
    if current_total and len(points) == 1:
        only_date = parse_date(points[0]["date"]) or today
        points.insert(0, {"date": (only_date - timedelta(days=1)).isoformat(), "value": current_total * 0.99, "cash_flow": 0})
    for point in points:
        point_date = parse_date(point["date"])
        future_deposits = sum(
            amount
            for flow_date, amount in cash_flow_by_date.items()
            if point_date and flow_date > point_date
        )
        point["adjusted_value"] = point["value"] + future_deposits
    return points


def portfolio_range_links(selected_range: str, selected_method: str = "simple", selected_account: str = "", selected_benchmarks=None) -> str:
    ranges = (("1w", "1W"), ("1m", "1M"), ("3m", "3M"), ("6m", "6M"), ("ytd", "YTD"), ("1y", "1Y"), ("all", "ALL"))
    account_query = f'&account={quote(selected_account)}' if selected_account else ""
    benchmark_query = "".join(f'&benchmark={quote(key)}' for key in sorted(set(selected_benchmarks or ())))
    return "".join(
        f'<a class="{"active" if key == selected_range else ""}" href="/brokerage?range={key}&method={escape(selected_method)}{account_query}{benchmark_query}">{label}</a>'
        for key, label in ranges
    )


def portfolio_pie_card(
    title: str,
    items: list[dict],
    total_value: float,
    aria_label: str = "Portfolio pie chart",
    slice_total: float | None = None,
) -> str:
    slices = []
    colors = ["#089981", "#ff9500", "#2f80ed", "#9b5cff", "#00a8cc", "#ef476f", "#84cc16", "#f59e0b"]
    filled = 0.0
    slice_denominator = number(slice_total, 0) if slice_total is not None else number(total_value, 0)
    active_label = title
    active_share = "100.00%" if slice_denominator else "--"
    for index, item in enumerate(items):
        raw_value = number(item.get("value"), 0) or 0
        slice_value = abs(raw_value) if item.get("absolute") else max(0, raw_value)
        if not slice_value or not slice_denominator:
            continue
        share = slice_value / slice_denominator
        label = item.get("label") or "Account"
        key = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"slice-{index}"
        dash = max(0.001, share * 100)
        slices.append(
            f'<circle r="42" cx="50" cy="50" pathLength="100" transform="rotate(-90 50 50)" class="portfolio-pie-slice" '
            f'tabindex="0" data-pie-slice="{escape(key)}" data-pie-label="{escape(label)}" data-pie-share="{pct(share)}" '
            f'style="--dash:{dash:.3f};--offset:{-filled:.3f};--slice:{colors[index % len(colors)]}"><title>{escape(label)} {pct(share)}</title></circle>'
        )
        filled += dash
    if not slices:
        slices.append('<circle r="42" cx="50" cy="50" pathLength="100" class="portfolio-pie-empty"/>')
    legend_rows = []
    for index, item in enumerate(items):
        raw_value = number(item.get("value"), 0) or 0
        slice_value = abs(raw_value) if item.get("absolute") else max(0, raw_value)
        if not slice_value:
            continue
        label = item.get("label") or "Account"
        key = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"slice-{index}"
        value_text = item.get("value_text") or (pct(slice_value / slice_denominator) if slice_denominator else "0.00%")
        value_class = str(item.get("value_class") or "").strip()
        class_attr = f' class="{escape(value_class)}"' if value_class else ""
        legend_rows.append(f'''<div class="portfolio-pie-row" data-pie-legend="{escape(key)}" tabindex="0">
          <span><i style="background:{colors[index % len(colors)]}"></i>{escape(label)}</span>
          <b{class_attr}>{escape(value_text)}</b>
        </div>''')
    legend = "".join(legend_rows) or '<div class="portfolio-pie-row muted-row"><span>No allocation yet</span><b>--</b></div>'
    legend_count = len(legend_rows)
    legend_density = "legend-dense" if legend_count >= 13 else "legend-compact" if legend_count >= 9 else "legend-roomy"
    return f'''<aside class="portfolio-pie-card {legend_density}" data-legend-count="{legend_count}" aria-label="{escape(aria_label)}">
      <div class="portfolio-pie-head"><b>{escape(title)}</b><span>{money(total_value)}</span></div>
      <svg class="portfolio-pie" viewBox="0 0 100 100" role="img" aria-label="{escape(aria_label)}">
        <circle r="42" cx="50" cy="50" class="portfolio-pie-track"/>{''.join(slices)}
        <circle r="24" cx="50" cy="50" class="portfolio-pie-hole"/>
        <text x="50" y="47" class="portfolio-pie-center-label" data-pie-center-label>{escape(active_label)}</text>
        <text x="50" y="58" class="portfolio-pie-center-value" data-pie-center-value>{escape(active_share)}</text>
      </svg>
      <div class="portfolio-pie-legend">{legend}</div>
    </aside>'''


def portfolio_allocation_pie(categories: dict, total_value: float) -> str:
    return portfolio_pie_card(
        "Allocation",
        [{"label": data.get("label"), "value": number(data.get("value"), 0)} for data in categories.values()],
        total_value,
        "Portfolio allocation",
    )


def portfolio_composition_pie(accounts: list[dict], external: list[dict]) -> str:
    stocks = sum(number(account.get("stocks_value"), 0) for account in accounts)
    cash = sum(number(account.get("cash_value"), 0) for account in accounts)
    options = sum(number(account.get("options_value"), 0) for account in accounts)
    cash += sum(number(account.get("current_balance"), 0) for account in external if account.get("category") == "banking")
    gross_total = abs(stocks) + abs(cash) + abs(options)
    return portfolio_pie_card(
        "Position mix",
        (
            {"label": "Stocks", "value": stocks, "value_text": money(stocks), "absolute": True},
            {"label": "Cash", "value": cash, "value_text": money(cash), "absolute": True},
            {"label": "Options", "value": options, "value_text": money(options), "absolute": True},
        ),
        gross_total,
        "Cash stock and options mix",
    )


def portfolio_holdings_pie(
    holdings: list[dict],
    option_underlyings: list[dict] | None = None,
    options_value: float = 0,
    cash_value: float = 0,
    total_value_override: float | None = None,
    visible_positions: int = 5,
) -> str:
    positions = []
    options_total = max(0, number(options_value, 0) or 0)
    cash_total = max(0, number(cash_value, 0) or 0)
    for holding in holdings:
        value = number(holding.get("market_value"))
        if value is None:
            value = number(holding.get("cost_basis"), 0)
        if value and value > 0:
            positions.append({"label": holding.get("ticker") or "Holding", "value": value})
    positions.sort(key=lambda item: item["value"], reverse=True)
    stock_total = sum(item["value"] for item in positions)
    calculated_total = cash_total + stock_total + options_total
    total_value = number(total_value_override, calculated_total) if total_value_override is not None else calculated_total
    visible = positions[:visible_positions]
    other_value = sum(item["value"] for item in positions[visible_positions:])
    if other_value:
        visible.append({"label": "Other", "value": other_value})
    items = [
        {"label": item["label"], "value": item["value"], "value_text": money(item["value"])}
        for item in visible
    ]
    if cash_total:
        items.insert(0, {"label": "Cash", "value": cash_total, "value_text": money(cash_total)})
    option_items = []
    for option in option_underlyings or []:
        ticker = str(option.get("ticker") or option.get("symbol") or "").strip().upper()
        market_value = number(option.get("market_value"), 0) or 0
        if not ticker or math.isclose(market_value, 0):
            continue
        option_items.append({
            "label": f"{ticker} options",
            "value": market_value,
            "value_text": money(market_value),
            "value_class": "positive" if market_value > 0 else "negative",
            "absolute": True,
        })
    if option_items:
        items.extend(option_items)
        slice_total = cash_total + stock_total + sum(abs(number(item.get("value"), 0) or 0) for item in option_items)
    elif options_total:
        items.append({"label": "Options", "value": options_total, "value_text": money(options_total)})
        slice_total = total_value
    else:
        slice_total = cash_total + stock_total
    return portfolio_pie_card(
        "Holdings",
        items,
        total_value,
        "Cash stock and option holdings by market value",
        slice_total=slice_total,
    )


def portfolio_category_row(data: dict, total_value: float, selected_account: str = "") -> str:
    value = number(data.get("value"), 0)
    share = value / total_value if total_value else None
    rows = data.get("rows") or []
    if rows:
        detail = "".join(
            f'''<button class="portfolio-account-mini {"is-active" if selected_account and row.get("account_key") == selected_account else ""}" type="button" data-portfolio-account="{escape(row.get("account_key") or "")}" aria-pressed="{"true" if selected_account and row.get("account_key") == selected_account else "false"}" {"" if row.get("account_key") else "disabled"}>
              <span>{escape(row.get("institution") or "")} - {escape(row.get("name") or "")}{(" ****" + escape(row.get("mask"))) if row.get("mask") else ""}</span>
              <b>{money(row.get("value"))}</b>
            </button>'''
            for row in sorted(rows, key=lambda item: number(item.get("value"), 0), reverse=True)
        )
    else:
        detail = f'<div class="portfolio-account-mini muted-row"><span>{escape(data.get("hint") or "Connect an account")}</span><b>--</b></div>'
    return f'''<details class="portfolio-category" {"open" if rows else ""}>
      <summary>
        <div><b>{escape(data.get("label") or "Account")}</b><span>{pct(share) if share is not None else escape(data.get("hint") or "")}</span></div>
        <strong>{money(value)}</strong>
      </summary>
      <div class="portfolio-category-detail">{detail}</div>
    </details>'''


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(db()) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                password_hash TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT OR IGNORE INTO users (id, username, display_name, password_hash)
            VALUES (1, 'root', 'Root', NULL);

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                legacy_id INTEGER,
                ticker TEXT NOT NULL,
                sector TEXT,
                strategy TEXT NOT NULL,
                open_date TEXT NOT NULL,
                expiration TEXT,
                close_date TEXT,
                status TEXT NOT NULL,
                contracts REAL,
                strike REAL,
                long_put_strike REAL,
                short_call_strike REAL,
                long_call_strike REAL,
                premium_in REAL,
                exit_premium REAL,
                stock_pnl REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                capital_used REAL,
                broker_source TEXT,
                earnings_bet_id INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
            CREATE INDEX IF NOT EXISTS idx_trades_close_date ON trades(close_date);

            CREATE TABLE IF NOT EXISTS stock_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                ticker TEXT NOT NULL,
                sector TEXT,
                shares REAL NOT NULL,
                avg_cost REAL,
                current_price REAL,
                as_of TEXT,
                broker_source TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_stock_holdings_ticker ON stock_holdings(ticker);

            CREATE TABLE IF NOT EXISTS brokerage_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                provider TEXT NOT NULL DEFAULT 'Robinhood',
                nickname TEXT,
                account_last4 TEXT,
                account_type TEXT,
                trading_type TEXT,
                portfolio_value REAL,
                buying_power REAL,
                stocks_value REAL,
                options_value REAL,
                cash_value REAL,
                last_sync_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_brokerage_accounts_user_id ON brokerage_accounts(user_id);

            CREATE TABLE IF NOT EXISTS plaid_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                item_id TEXT,
                access_token TEXT NOT NULL,
                institution_name TEXT,
                products TEXT,
                last_sync_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_plaid_items_user_id ON plaid_items(user_id);

            CREATE TABLE IF NOT EXISTS external_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'Manual',
                institution_name TEXT,
                name TEXT NOT NULL,
                mask TEXT,
                account_type TEXT,
                account_subtype TEXT,
                category TEXT,
                current_balance REAL,
                available_balance REAL,
                currency TEXT DEFAULT 'USD',
                plaid_account_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_external_accounts_user_id ON external_accounts(user_id);
            CREATE INDEX IF NOT EXISTS idx_external_accounts_category ON external_accounts(category);

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                total_value REAL NOT NULL,
                snapshot_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_id ON portfolio_snapshots(user_id, snapshot_at);

            CREATE TABLE IF NOT EXISTS portfolio_cash_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                flow_date TEXT NOT NULL,
                amount REAL NOT NULL,
                flow_type TEXT NOT NULL DEFAULT 'deposit',
                account TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_portfolio_cash_flows_user_id ON portfolio_cash_flows(user_id, flow_date);

            CREATE TABLE IF NOT EXISTS day_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                trade_date TEXT NOT NULL,
                open_date TEXT,
                close_date TEXT,
                status TEXT DEFAULT 'Closed',
                ticker TEXT NOT NULL,
                option_type TEXT NOT NULL,
                expiration TEXT,
                strike REAL,
                open_side TEXT NOT NULL,
                contracts REAL NOT NULL,
                open_price REAL NOT NULL,
                close_price REAL NOT NULL,
                fees REAL DEFAULT 0,
                broker_source TEXT,
                earnings_bet_id INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_day_trades_user_id ON day_trades(user_id, trade_date);
            CREATE INDEX IF NOT EXISTS idx_day_trades_ticker ON day_trades(ticker);

            CREATE TABLE IF NOT EXISTS other_option_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                trade_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                strategy_type TEXT NOT NULL,
                option_type TEXT,
                expiration TEXT,
                strike REAL,
                contracts REAL NOT NULL,
                open_price REAL NOT NULL,
                close_price REAL NOT NULL,
                long_strike REAL,
                short_strike REAL,
                long_open_price REAL,
                short_open_price REAL,
                long_close_price REAL,
                short_close_price REAL,
                fees REAL DEFAULT 0,
                description TEXT,
                broker_source TEXT,
                earnings_bet_id INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_other_option_trades_user_id ON other_option_trades(user_id, trade_date);
            CREATE INDEX IF NOT EXISTS idx_other_option_trades_ticker ON other_option_trades(ticker);

            CREATE TABLE IF NOT EXISTS stock_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                trade_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Closed',
                shares REAL NOT NULL,
                price REAL NOT NULL,
                buy_price REAL,
                sell_price REAL,
                current_price REAL,
                as_of TEXT,
                fees REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                broker_source TEXT,
                earnings_bet_id INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_stock_trades_user_id ON stock_trades(user_id, trade_date);
            CREATE INDEX IF NOT EXISTS idx_stock_trades_ticker ON stock_trades(ticker);

            CREATE TABLE IF NOT EXISTS earnings_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                ticker TEXT NOT NULL,
                earnings_date TEXT NOT NULL,
                direction TEXT NOT NULL,
                strategy TEXT,
                position_size REAL,
                cost_basis REAL,
                realized_pnl REAL DEFAULT 0,
                post_earnings_move_pct REAL,
                strategy_type TEXT,
                stock_shares REAL,
                stock_buy_price REAL,
                stock_sell_price REAL,
                option_type TEXT,
                option_contracts REAL,
                option_open_price REAL,
                option_close_price REAL,
                combo_description TEXT,
                combo_units REAL,
                combo_open_cost REAL,
                combo_close_value REAL,
                result TEXT,
                broker_source TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_earnings_bets_user_id ON earnings_bets(user_id, earnings_date);
            CREATE INDEX IF NOT EXISTS idx_earnings_bets_ticker ON earnings_bets(ticker);
        """)
        trade_columns = {row[1] for row in connection.execute("PRAGMA table_info(trades)").fetchall()}
        if "user_id" not in trade_columns:
            connection.execute("ALTER TABLE trades ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)")
        if "sector" not in trade_columns:
            connection.execute("ALTER TABLE trades ADD COLUMN sector TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_sector ON trades(sector)")
        for column, column_type in {
            "broker_source": "TEXT",
            "earnings_bet_id": "INTEGER",
            "short_call_strike": "REAL",
            "long_call_strike": "REAL",
        }.items():
            if column not in trade_columns:
                connection.execute(f"ALTER TABLE trades ADD COLUMN {column} {column_type}")
        holding_columns = {row[1] for row in connection.execute("PRAGMA table_info(stock_holdings)").fetchall()}
        if "user_id" not in holding_columns:
            connection.execute("ALTER TABLE stock_holdings ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_holdings_user_id ON stock_holdings(user_id)")
        if "sector" not in holding_columns:
            connection.execute("ALTER TABLE stock_holdings ADD COLUMN sector TEXT")
        if "broker_source" not in holding_columns:
            connection.execute("ALTER TABLE stock_holdings ADD COLUMN broker_source TEXT")
        stock_trade_columns = {row[1] for row in connection.execute("PRAGMA table_info(stock_trades)").fetchall()}
        if "buy_price" not in stock_trade_columns:
            connection.execute("ALTER TABLE stock_trades ADD COLUMN buy_price REAL")
        if "sell_price" not in stock_trade_columns:
            connection.execute("ALTER TABLE stock_trades ADD COLUMN sell_price REAL")
        if "status" not in stock_trade_columns:
            connection.execute("ALTER TABLE stock_trades ADD COLUMN status TEXT NOT NULL DEFAULT 'Closed'")
        if "current_price" not in stock_trade_columns:
            connection.execute("ALTER TABLE stock_trades ADD COLUMN current_price REAL")
        if "as_of" not in stock_trade_columns:
            connection.execute("ALTER TABLE stock_trades ADD COLUMN as_of TEXT")
        for column, column_type in {
            "broker_source": "TEXT",
            "earnings_bet_id": "INTEGER",
        }.items():
            if column not in stock_trade_columns:
                connection.execute(f"ALTER TABLE stock_trades ADD COLUMN {column} {column_type}")
        day_trade_columns = {row[1] for row in connection.execute("PRAGMA table_info(day_trades)").fetchall()}
        day_trade_additions = {
            "open_date": "TEXT",
            "close_date": "TEXT",
            "status": "TEXT DEFAULT 'Closed'",
            "broker_source": "TEXT",
            "earnings_bet_id": "INTEGER",
        }
        for column, column_type in day_trade_additions.items():
            if column not in day_trade_columns:
                connection.execute(f"ALTER TABLE day_trades ADD COLUMN {column} {column_type}")
        connection.execute("UPDATE day_trades SET open_date = COALESCE(open_date, trade_date), close_date = COALESCE(close_date, trade_date), status = COALESCE(status, 'Closed')")
        other_option_columns = {row[1] for row in connection.execute("PRAGMA table_info(other_option_trades)").fetchall()}
        other_option_additions = {
            "open_date": "TEXT",
            "close_date": "TEXT",
            "status": "TEXT DEFAULT 'Closed'",
            "long_strike": "REAL",
            "short_strike": "REAL",
            "long_open_price": "REAL",
            "short_open_price": "REAL",
            "long_close_price": "REAL",
            "short_close_price": "REAL",
            "broker_source": "TEXT",
            "earnings_bet_id": "INTEGER",
        }
        for column, column_type in other_option_additions.items():
            if column not in other_option_columns:
                connection.execute(f"ALTER TABLE other_option_trades ADD COLUMN {column} {column_type}")
        earnings_bet_columns = {row[1] for row in connection.execute("PRAGMA table_info(earnings_bets)").fetchall()}
        earnings_bet_additions = {
            "strategy_type": "TEXT",
            "stock_shares": "REAL",
            "stock_buy_price": "REAL",
            "stock_sell_price": "REAL",
            "option_type": "TEXT",
            "option_contracts": "REAL",
            "option_open_price": "REAL",
            "option_close_price": "REAL",
            "combo_description": "TEXT",
            "combo_units": "REAL",
            "combo_open_cost": "REAL",
            "combo_close_value": "REAL",
            "broker_source": "TEXT",
        }
        for column, column_type in earnings_bet_additions.items():
            if column not in earnings_bet_columns:
                connection.execute(f"ALTER TABLE earnings_bets ADD COLUMN {column} {column_type}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_sector ON trades(sector)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_holdings_sector ON stock_holdings(sector)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_holdings_user_id ON stock_holdings(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_brokerage_accounts_user_id ON brokerage_accounts(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_plaid_items_user_id ON plaid_items(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_external_accounts_user_id ON external_accounts(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_external_accounts_category ON external_accounts(category)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_id ON portfolio_snapshots(user_id, snapshot_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_cash_flows_user_id ON portfolio_cash_flows(user_id, flow_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_day_trades_user_id ON day_trades(user_id, trade_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_day_trades_ticker ON day_trades(ticker)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_other_option_trades_user_id ON other_option_trades(user_id, trade_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_other_option_trades_ticker ON other_option_trades(ticker)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_trades_user_id ON stock_trades(user_id, trade_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_trades_ticker ON stock_trades(ticker)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_earnings_bets_user_id ON earnings_bets(user_id, earnings_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_earnings_bets_ticker ON earnings_bets(ticker)")
        for table in ("trades", "day_trades", "other_option_trades", "stock_trades", "earnings_bets"):
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_broker_source ON {table}(broker_source)")
        for table in ("trades", "day_trades", "other_option_trades", "stock_trades"):
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_earnings_bet_id ON {table}(earnings_bet_id)")
            connection.execute(f"""
                UPDATE {table}
                SET broker_source = CASE
                    WHEN lower(COALESCE(notes, '')) LIKE '%moomoo%' THEN 'Moomoo'
                    WHEN lower(COALESCE(notes, '')) LIKE '%webull%' THEN 'Webull'
                    WHEN lower(COALESCE(notes, '')) LIKE '%robinhood%' THEN 'Robinhood'
                    ELSE broker_source
                END
                WHERE broker_source IS NULL OR broker_source = ''
            """)
        connection.execute("""
            UPDATE earnings_bets
            SET broker_source = CASE
                WHEN lower(COALESCE(notes, '')) LIKE '%moomoo%' THEN 'Moomoo'
                WHEN lower(COALESCE(notes, '')) LIKE '%webull%' THEN 'Webull'
                WHEN lower(COALESCE(notes, '')) LIKE '%robinhood%' THEN 'Robinhood'
                ELSE broker_source
            END
            WHERE broker_source IS NULL OR broker_source = ''
        """)
        count = connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        if count == 0 and BOOTSTRAP_PATH.exists():
            trades = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))
            fields = ("legacy_id", "ticker", "strategy", "open_date", "expiration", "close_date",
                      "status", "contracts", "strike", "long_put_strike", "premium_in",
                      "exit_premium", "stock_pnl", "capital_used", "notes")
            placeholders = ",".join("?" for _ in fields)
            connection.executemany(
                f"INSERT INTO trades ({','.join(fields)}) VALUES ({placeholders})",
                [[trade.get(field) for field in fields] for trade in trades],
            )
        connection.execute("""
            UPDATE trades
            SET strike = long_put_strike,
                long_put_strike = strike,
                updated_at = CURRENT_TIMESTAMP
            WHERE strike IS NOT NULL
              AND long_put_strike IS NOT NULL
              AND (
                (strategy = 'Put Credit Spread' AND strike < long_put_strike)
                OR (strategy = 'Call Credit Spread' AND strike > long_put_strike)
              )
        """)
        for table in ("trades", "stock_holdings"):
            rows = connection.execute(f"SELECT id, ticker, sector FROM {table}").fetchall()
            for row in rows:
                sector = row["sector"] if row["sector"] in SECTORS and row["sector"] != "Other / Unknown" else sector_for_ticker(row["ticker"])
                if sector != row["sector"]:
                    connection.execute(f"UPDATE {table} SET sector=? WHERE id=?", (sector, row["id"]))
        connection.commit()


def number(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date() if value else None
        if parsed and not 1900 <= parsed.year <= 2200:
            return None
        return parsed
    except ValueError:
        return None


def ticker_search_term(value: str) -> str:
    term = (value or "").strip().upper()
    return term if re.fullmatch(r"[A-Z0-9.]{1,8}", term) else ""


def safe_return_to(value: str | None, default: str = "") -> str:
    value = (value or "").strip()
    if not value:
        return default
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return default
    return value


def form_return_to(form, default: str) -> str:
    return safe_return_to(form.get("return_to"), default)


def symbol_page_href(ticker: str | None, default: str = "/trades") -> str:
    symbol = (ticker or "").strip().upper()
    return f"/symbol/{quote(symbol)}" if symbol else default


def current_currency() -> str:
    return getattr(CURRENCY_CONTEXT, "value", DISPLAY_CURRENCY)


def normalize_broker_source(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    mapping = {
        "rh": "Robinhood",
        "robinhood": "Robinhood",
        "webull": "Webull",
        "wb": "Webull",
        "moomoo": "Moomoo",
        "moo": "Moomoo",
        "fidelity": "Fidelity",
        "fid": "Fidelity",
        "ira": "IRA",
        "individual retirement account": "IRA",
        "external": "External",
        "external account": "External",
        "outside": "External",
    }
    return mapping.get(raw)


def infer_broker_source(notes: str | None) -> str | None:
    text = (notes or "").lower()
    if "moomoo" in text:
        return "Moomoo"
    if "webull" in text:
        return "Webull"
    if "robinhood" in text:
        return "Robinhood"
    if "fidelity" in text:
        return "Fidelity"
    if "ira" in text or "individual retirement account" in text:
        return "IRA"
    if "external account" in text or "external" in text:
        return "External"
    return None


def broker_source_for_row(row: dict) -> str | None:
    return normalize_broker_source(row.get("broker_source")) or infer_broker_source(row.get("notes"))


def exclude_fidelity_holdings(holdings: list[dict]) -> list[dict]:
    return [holding for holding in holdings if broker_source_for_row(holding) != "Fidelity"]


def filter_holdings_by_brokers(holdings: list[dict], brokers: list[str] | None = None) -> list[dict]:
    if brokers is None:
        return exclude_fidelity_holdings(holdings)
    allowed = set(brokers)
    return [holding for holding in holdings if broker_source_for_row(holding) in allowed]


def broker_source_badge(source: str | None) -> str:
    source = normalize_broker_source(source)
    if not source:
        return '<span class="source-empty">-</span>'
    cls = source.lower()
    return f'<span class="source-badge {cls}" title="{escape(source)}"><i>{BROKER_SHORT_LABELS[source]}</i><span>{escape(source)}</span></span>'


def ticker_broker_display(ticker: str, sources=None, extra_html: str = "") -> str:
    if isinstance(sources, str) or sources is None:
        sources = [sources]
    normalized_sources = []
    for source in sources:
        normalized = normalize_broker_source(source)
        if normalized and normalized not in normalized_sources:
            normalized_sources.append(normalized)
    badges = "".join(broker_source_badge(source) for source in normalized_sources)
    return f'<div class="ticker-broker-cell"><a href="/symbol/{quote(ticker)}"><b>{escape(ticker)}</b></a>{badges}{extra_html}</div>'


UNKNOWN_SOURCE_FILTER = "__unknown__"


def source_filter_value(value: str | None) -> str:
    if value == UNKNOWN_SOURCE_FILTER:
        return UNKNOWN_SOURCE_FILTER
    return normalize_broker_source(value) or ""


def broker_source_select(name: str, selected: str | None, blank="Unknown", include_unknown: bool = False) -> str:
    selected_value = source_filter_value(selected)
    html = f'<option value="">{escape(blank)}</option>' if blank else ""
    if include_unknown:
        html += f'<option value="{UNKNOWN_SOURCE_FILTER}" {"selected" if selected_value == UNKNOWN_SOURCE_FILTER else ""}>Unknown source</option>'
    return html + "".join(f'<option value="{escape(x)}" {"selected" if x == selected_value else ""}>{escape(x)}</option>' for x in BROKER_SOURCES)


def broker_filter_values(query: dict, name: str) -> list[str]:
    query = query or {}
    raw_values = query.get(name, []) if query else []
    if not raw_values and not query.get(f"{name}_filter", []):
        return list(BROKER_SOURCES)
    selected = []
    for value in raw_values:
        normalized = normalize_broker_source(value)
        if normalized and normalized not in selected:
            selected.append(normalized)
    return selected


def filter_trades_by_brokers(trades: list[dict], brokers: list[str]) -> list[dict]:
    allowed = set(brokers)
    if allowed == set(BROKER_SOURCES):
        return trades
    return [trade for trade in trades if broker_source_for_row(trade) in allowed]


def trade_book_for_row(row: dict) -> str:
    source = row.get("source") or ""
    if source == "other_option":
        return "buyer"
    if source == "day_trade":
        return "day"
    if source == "stock_trade":
        return "stock"
    return "seller"


def trade_book_filter_values(query: dict, name: str = "trade_book") -> list[str]:
    query = query or {}
    valid = {key for key, _label in TRADE_BOOK_FILTERS}
    raw_values = query.get(name, [])
    if not raw_values and not query.get(f"{name}_filter", []):
        return [key for key, _label in TRADE_BOOK_FILTERS]
    selected = []
    for value in raw_values:
        if value in valid and value not in selected:
            selected.append(value)
    return selected


def filter_trades_by_books(trades: list[dict], books: list[str]) -> list[dict]:
    allowed = set(books)
    if allowed == {key for key, _label in TRADE_BOOK_FILTERS}:
        return trades
    return [trade for trade in trades if trade_book_for_row(trade) in allowed]


def dashboard_filter_values(query: dict) -> tuple[list[str], list[str]]:
    query = query or {}
    brokers = broker_filter_values(query, "dash_broker")
    if not query.get("dash_broker", []) and not query.get("dash_broker_filter", []):
        brokers = [broker for broker in brokers if broker not in {"Fidelity", "External"}]
    return brokers, trade_book_filter_values(query, "trade_book")


def filter_dashboard_trades(trades: list[dict], brokers: list[str], books: list[str]) -> list[dict]:
    return filter_trades_by_books(filter_trades_by_brokers(trades, brokers), books)


def dashboard_filter_params(query: dict, brokers: list[str], books: list[str], omit: set[str] | None = None) -> list[tuple[str, str]]:
    omit = set(omit or ()) | {"dash_broker", "dash_broker_filter", "trade_book", "trade_book_filter", "cal_broker", "cal_broker_filter", "perf_broker", "perf_broker_filter", "currency"}
    params: list[tuple[str, str]] = []
    for key, values in (query or {}).items():
        if key in omit:
            continue
        for value in values:
            if value not in (None, ""):
                params.append((key, str(value)))
    params.append(("dash_broker_filter", "1"))
    params.extend(("dash_broker", broker) for broker in brokers)
    params.append(("trade_book_filter", "1"))
    params.extend(("trade_book", book) for book in books)
    return params


def dashboard_filter_panel(query: dict, brokers: list[str], books: list[str], range_controls: str = "") -> str:
    broker_selected = set(brokers)
    book_selected = set(books)
    hidden_inputs = hidden_inputs_from_params(
        [
            (key, value)
            for key, values in (query or {}).items()
            for value in values
            if key not in {"dash_broker", "dash_broker_filter", "trade_book", "trade_book_filter", "cal_broker", "cal_broker_filter", "perf_broker", "perf_broker_filter", "currency"}
            and value not in (None, "")
        ]
    )
    broker_checks = "".join(
        f'<label class="broker-check {broker.lower()}" title="{escape(broker)}"><input type="checkbox" name="dash_broker" value="{escape(broker)}" aria-label="{escape(broker)}" {"checked" if broker in broker_selected else ""}><i aria-hidden="true">{escape(BROKER_SHORT_LABELS.get(broker, broker[:2].upper()))}</i><span>{escape(broker)}</span></label>'
        for broker in BROKER_SOURCES
    )
    book_checks = "".join(
        f'<label class="book-check {key}"><input type="checkbox" name="trade_book" value="{escape(key)}" {"checked" if key in book_selected else ""}><span>{escape(label)}</span></label>'
        for key, label in TRADE_BOOK_FILTERS
    )
    range_html = f'<div class="dashboard-filter-range">{range_controls}</div>' if range_controls else ""
    return f'''<div class="dashboard-filter-panel">
    <form class="dashboard-filter-main" method="get" data-dashboard-filter>
      {hidden_inputs}
      <input type="hidden" name="dash_broker_filter" value="1">
      <input type="hidden" name="trade_book_filter" value="1">
      <div class="dashboard-filter-group"><span>Broker</span><div>{broker_checks}</div></div>
      <div class="dashboard-filter-group"><span>Trade type</span><div>{book_checks}</div></div>
    </form>
    {range_html}
    </div>'''


def symbol_filter_values(query: dict) -> tuple[list[str], list[str]]:
    return broker_filter_values(query, "symbol_broker"), trade_book_filter_values(query, "symbol_book")


def symbol_filter_params(query: dict, brokers: list[str], books: list[str], omit: set[str] | None = None) -> list[tuple[str, str]]:
    omit = set(omit or ()) | {"symbol_broker", "symbol_broker_filter", "symbol_book", "symbol_book_filter", "source", "page"}
    params: list[tuple[str, str]] = []
    for key, values in (query or {}).items():
        if key in omit:
            continue
        for value in values:
            if value not in (None, ""):
                params.append((key, str(value)))
    params.append(("symbol_broker_filter", "1"))
    params.extend(("symbol_broker", broker) for broker in brokers)
    params.append(("symbol_book_filter", "1"))
    params.extend(("symbol_book", book) for book in books)
    return params


def symbol_filter_panel(query: dict, brokers: list[str], books: list[str], range_controls: str = "") -> str:
    broker_selected = set(brokers)
    book_selected = set(books)
    hidden_inputs = hidden_inputs_from_params(
        [
            (key, value)
            for key, values in (query or {}).items()
            for value in values
            if key not in {"symbol_broker", "symbol_broker_filter", "symbol_book", "symbol_book_filter", "source", "currency", "page"}
            and value not in (None, "")
        ]
    )
    broker_checks = "".join(
        f'<label class="broker-check {broker.lower()}" title="{escape(broker)}"><input type="checkbox" name="symbol_broker" value="{escape(broker)}" aria-label="{escape(broker)}" {"checked" if broker in broker_selected else ""}><i aria-hidden="true">{escape(BROKER_SHORT_LABELS.get(broker, broker[:2].upper()))}</i><span>{escape(broker)}</span></label>'
        for broker in BROKER_SOURCES
    )
    book_checks = "".join(
        f'<label class="book-check {key}"><input type="checkbox" name="symbol_book" value="{escape(key)}" {"checked" if key in book_selected else ""}><span>{escape(label)}</span></label>'
        for key, label in TRADE_BOOK_FILTERS
    )
    range_html = f'<div class="dashboard-filter-range">{range_controls}</div>' if range_controls else ""
    return f'''<div class="dashboard-filter-panel symbol-filter-panel">
    <form class="dashboard-filter-main" method="get" data-dashboard-filter>
      {hidden_inputs}
      <input type="hidden" name="symbol_broker_filter" value="1">
      <input type="hidden" name="symbol_book_filter" value="1">
      <div class="dashboard-filter-group"><span>Broker</span><div>{broker_checks}</div></div>
      <div class="dashboard-filter-group"><span>Trade type</span><div>{book_checks}</div></div>
    </form>
    {range_html}
    </div>'''


def broker_filter_query_params(query: dict, name: str, selected: list[str], omit: set[str] | None = None) -> list[tuple[str, str]]:
    omit = set(omit or ()) | {name, f"{name}_filter", "currency"}
    params: list[tuple[str, str]] = []
    for key, values in (query or {}).items():
        if key in omit:
            continue
        for value in values:
            if value not in (None, ""):
                params.append((key, str(value)))
    params.append((f"{name}_filter", "1"))
    params.extend((name, broker) for broker in selected)
    return params


def broker_checkbox_filter(name: str, selected: list[str], query: dict, label: str) -> str:
    selected_set = set(selected)
    hidden_inputs = "".join(
        f'<input type="hidden" name="{escape(key)}" value="{escape(value)}">'
        for key, value in broker_filter_query_params(query, name, selected, {"page"})
        if key not in {name, f"{name}_filter"}
    )
    checks = "".join(
        f'<label class="broker-check {broker.lower()}" title="{escape(broker)}">'
        f'<input type="checkbox" name="{escape(name)}" value="{escape(broker)}" aria-label="{escape(broker)}" {"checked" if broker in selected_set else ""}>'
        f'<i aria-hidden="true">{escape(BROKER_SHORT_LABELS.get(broker, broker[:2].upper()))}</i><span>{escape(broker)}</span></label>'
        for broker in BROKER_SOURCES
    )
    return f'''<form class="broker-filter-inline" method="get" aria-label="{escape(label)} broker filter">
      {hidden_inputs}
      <input type="hidden" name="{escape(name)}_filter" value="1">
      {checks}
    </form>'''


def query_param_items(params) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not params:
        return items
    raw_items = params.items() if isinstance(params, dict) else params
    for key, value in raw_items:
        if value in (None, ""):
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if item not in (None, ""):
                    items.append((str(key), str(item)))
        else:
            items.append((str(key), str(value)))
    return items


def hidden_inputs_from_params(params) -> str:
    return "".join(
        f'<input type="hidden" name="{escape(key)}" value="{escape(value)}">'
        for key, value in query_param_items(params)
    )


def apply_source_filter(where: list[str], params: list, value: str | None) -> None:
    source = source_filter_value(value)
    if source == UNKNOWN_SOURCE_FILTER:
        where.append("(broker_source IS NULL OR broker_source = '')")
    elif source:
        where.append("broker_source = ?")
        params.append(source)


def earnings_marker(row: dict) -> str:
    if number(row.get("earnings_bet_id")):
        return '<span class="pill earnings-linked" title="Linked to earnings bet">Earnings</span>'
    return ""


def earnings_row_class(row: dict) -> str:
    return ' class="earnings-row"' if number(row.get("earnings_bet_id")) else ""


def earnings_checked(form_or_row: dict) -> bool:
    value = form_or_row.get("is_earnings_bet")
    return bool(number(form_or_row.get("earnings_bet_id")) or value in {"on", "1", "true", "yes", "checked"})


def earnings_bet_toggle(row: dict) -> str:
    checked = "checked" if earnings_checked(row) else ""
    return f'''
      <label class="checkbox-card">
        <input type="checkbox" name="is_earnings_bet" value="on" {checked}>
        <span>
          <b>Earnings bet</b>
          <small>Show this trade in Earnings and highlight it in trade lists.</small>
        </span>
      </label>
    '''


def trade_link_key(table: str, trade_id) -> str:
    return f"{table}:{trade_id}" if trade_id not in (None, "") else ""


def parse_trade_link_key(value: str | None) -> tuple[str, int] | None:
    if not value or ":" not in value:
        return None
    table, raw_id = value.split(":", 1)
    if table not in {"trades", "other_option_trades", "day_trades", "stock_trades"}:
        return None
    try:
        return table, int(raw_id)
    except ValueError:
        return None


def linked_trade_key_for_earnings_bet(bet_id) -> str:
    if not bet_id:
        return ""
    with closing(db()) as connection:
        for table in ("trades", "other_option_trades", "day_trades", "stock_trades"):
            row = connection.execute(
                f"SELECT id FROM {table} WHERE user_id=? AND earnings_bet_id=? ORDER BY id LIMIT 1",
                (current_user_id(), bet_id),
            ).fetchone()
            if row:
                return trade_link_key(table, row["id"])
    return ""


def earnings_trade_link_options(bet: dict) -> str:
    selected = bet.get("linked_trade_key") or linked_trade_key_for_earnings_bet(bet.get("id"))
    ticker = (bet.get("ticker") or "").strip().upper()
    clauses = ["user_id=?"]
    params: list = [current_user_id()]
    if ticker:
        clauses.append("UPPER(ticker)=?")
        params.append(ticker)
    where = " AND ".join(clauses)
    rows = []
    with closing(db()) as connection:
        specs = (
            ("trades", "Option seller", "strategy", "open_date", "close_date"),
            ("other_option_trades", "Option buyer", "strategy_type", "open_date", "close_date"),
            ("day_trades", "Day trade", "option_type", "open_date", "close_date"),
            ("stock_trades", "Stock trade", "side", "trade_date", "trade_date"),
        )
        for table, label, strategy_col, open_col, close_col in specs:
            for row in connection.execute(
                f"""
                SELECT id, ticker, broker_source, earnings_bet_id, notes,
                       {strategy_col} AS strategy_label,
                       {open_col} AS open_label,
                       {close_col} AS close_label
                FROM {table}
                WHERE {where} AND (earnings_bet_id IS NULL OR earnings_bet_id=?)
                ORDER BY COALESCE({open_col}, {close_col}) DESC, id DESC
                LIMIT 80
                """,
                params + [bet.get("id") or -1],
            ).fetchall():
                key = trade_link_key(table, row["id"])
                broker = broker_source_for_row(dict(row)) or ""
                title = f'{label} | {row["ticker"]} | {row["strategy_label"] or "-"} | {row["open_label"] or "-"}'
                if broker:
                    title += f" | {broker}"
                rows.append((key, title))
    html = '<option value="">No linked trade</option>'
    return html + "".join(f'<option value="{escape(key)}" {"selected" if key == selected else ""}>{escape(title)}</option>' for key, title in rows)


def apply_earnings_trade_link(connection, bet_id: int, link_key: str | None) -> None:
    for table in ("trades", "other_option_trades", "day_trades", "stock_trades"):
        connection.execute(
            f"UPDATE {table} SET earnings_bet_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND earnings_bet_id=?",
            (current_user_id(), bet_id),
        )
    parsed = parse_trade_link_key(link_key)
    if parsed:
        table, trade_id = parsed
        connection.execute(
            f"UPDATE {table} SET earnings_bet_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
            (bet_id, trade_id, current_user_id()),
        )


def auto_earnings_note_prefix(table: str, trade_id: int) -> str:
    return f"auto-earnings-from-trade:{table}:{trade_id}"


def fetch_trade_for_earnings(connection, table: str, trade_id: int) -> dict | None:
    if table not in {"trades", "other_option_trades", "day_trades", "stock_trades"}:
        return None
    row = connection.execute(
        f"SELECT * FROM {table} WHERE id=? AND user_id=?",
        (trade_id, current_user_id()),
    ).fetchone()
    return dict(row) if row else None


def earnings_payload_from_trade(table: str, row: dict) -> dict:
    ticker = (row.get("ticker") or "").strip().upper()
    broker = broker_source_for_row(row)
    if table == "stock_trades":
        shares = number(row.get("shares"), 0) or 0
        buy_price = number(row.get("buy_price") if row.get("buy_price") is not None else row.get("price"), 0) or 0
        sell_price = number(row.get("sell_price") if row.get("sell_price") is not None else row.get("price"), 0) or 0
        pnl = number(row.get("realized_pnl"), 0) or (sell_price - buy_price) * shares
        return {
            "ticker": ticker,
            "earnings_date": row.get("trade_date") or date.today().isoformat(),
            "direction": "Bullish" if pnl >= 0 else "Bearish",
            "strategy": f"Stock: {num(shares)} shares",
            "strategy_type": "Stock",
            "position_size": shares * sell_price,
            "cost_basis": shares * buy_price,
            "realized_pnl": pnl,
            "result": "Win" if pnl > 0 else "Loss" if pnl < 0 else "Breakeven",
            "broker_source": broker,
            "stock_shares": shares,
            "stock_buy_price": buy_price,
            "stock_sell_price": sell_price,
            "option_type": None,
            "option_contracts": None,
            "option_open_price": None,
            "option_close_price": None,
            "combo_description": None,
            "combo_units": None,
            "combo_open_cost": None,
            "combo_close_value": None,
        }
    if table == "trades":
        d = derived(row)
        strategy = row.get("strategy") or "Sell option"
        option_type = "Call" if "Call" in strategy else "Put" if "Put" in strategy else None
        return {
            "ticker": ticker,
            "earnings_date": row.get("close_date") or row.get("expiration") or row.get("open_date") or date.today().isoformat(),
            "direction": "Bullish" if (d.get("net_pnl") or 0) >= 0 else "Bearish",
            "strategy": f"Sell option: {strategy}",
            "strategy_type": "Sell option",
            "position_size": abs(number(row.get("premium_in"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
            "cost_basis": number(row.get("capital_used")) or abs(number(row.get("premium_in"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
            "realized_pnl": d.get("net_pnl") or 0,
            "result": d.get("outcome") or "Pending",
            "broker_source": broker,
            "stock_shares": None,
            "stock_buy_price": None,
            "stock_sell_price": None,
            "option_type": option_type,
            "option_contracts": row.get("contracts"),
            "option_open_price": row.get("premium_in"),
            "option_close_price": row.get("exit_premium"),
            "combo_description": strategy,
            "combo_units": row.get("contracts"),
            "combo_open_cost": row.get("capital_used"),
            "combo_close_value": None,
        }
    if table == "day_trades":
        pnl = day_trade_pnl(row)
        sell_side = row.get("open_side") == "Sell to open"
        return {
            "ticker": ticker,
            "earnings_date": row.get("close_date") or row.get("trade_date") or date.today().isoformat(),
            "direction": "Bullish" if pnl >= 0 else "Bearish",
            "strategy": f"{'Sell option' if sell_side else 'Single option'}: {row.get('option_type') or '-'} x{num(row.get('contracts'))}",
            "strategy_type": "Sell option" if sell_side else "Single option",
            "position_size": abs(number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
            "cost_basis": abs(number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
            "realized_pnl": pnl,
            "result": "Win" if pnl > 0 else "Loss" if pnl < 0 else "Breakeven",
            "broker_source": broker,
            "stock_shares": None,
            "stock_buy_price": None,
            "stock_sell_price": None,
            "option_type": row.get("option_type"),
            "option_contracts": row.get("contracts"),
            "option_open_price": row.get("open_price"),
            "option_close_price": row.get("close_price"),
            "combo_description": None,
            "combo_units": None,
            "combo_open_cost": None,
            "combo_close_value": None,
        }
    pnl = other_option_pnl(row)
    strategy_type = row.get("strategy_type") or "Single option"
    return {
        "ticker": ticker,
        "earnings_date": row.get("close_date") or row.get("trade_date") or date.today().isoformat(),
        "direction": "Bullish" if pnl >= 0 else "Bearish",
        "strategy": f"{strategy_type}: {row.get('description') or row.get('option_type') or ''}".strip(),
        "strategy_type": "Combo" if strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES or strategy_type == "Buy combo" else "Single option",
        "position_size": abs(number(row.get("close_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
        "cost_basis": abs(number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100,
        "realized_pnl": pnl,
        "result": "Win" if pnl > 0 else "Loss" if pnl < 0 else "Breakeven",
        "broker_source": broker,
        "stock_shares": None,
        "stock_buy_price": None,
        "stock_sell_price": None,
        "option_type": row.get("option_type"),
        "option_contracts": row.get("contracts"),
        "option_open_price": row.get("open_price"),
        "option_close_price": row.get("close_price"),
        "combo_description": row.get("description"),
        "combo_units": row.get("contracts"),
        "combo_open_cost": row.get("open_price"),
        "combo_close_value": row.get("close_price"),
    }


def sync_trade_earnings_bet(connection, table: str, trade_id: int, checked: bool) -> None:
    row = fetch_trade_for_earnings(connection, table, trade_id)
    if not row:
        return
    existing_id = number(row.get("earnings_bet_id"))
    prefix = auto_earnings_note_prefix(table, trade_id)
    if not checked:
        if existing_id:
            bet = connection.execute(
                "SELECT notes FROM earnings_bets WHERE id=? AND user_id=?",
                (existing_id, current_user_id()),
            ).fetchone()
            connection.execute(
                f"UPDATE {table} SET earnings_bet_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (trade_id, current_user_id()),
            )
            if bet and (bet["notes"] or "").startswith(prefix):
                connection.execute("DELETE FROM earnings_bets WHERE id=? AND user_id=?", (existing_id, current_user_id()))
        return
    payload = earnings_payload_from_trade(table, row)
    payload["notes"] = f"{prefix}; auto-created from trade checkbox"
    payload["user_id"] = current_user_id()
    fields = (
        "ticker", "earnings_date", "direction", "strategy", "position_size", "cost_basis", "realized_pnl",
        "strategy_type", "stock_shares", "stock_buy_price", "stock_sell_price", "option_type", "option_contracts",
        "option_open_price", "option_close_price", "combo_description", "combo_units", "combo_open_cost",
        "combo_close_value", "result", "broker_source", "notes", "user_id",
    )
    if existing_id:
        bet = connection.execute(
            "SELECT notes FROM earnings_bets WHERE id=? AND user_id=?",
            (existing_id, current_user_id()),
        ).fetchone()
        if bet and (bet["notes"] or "").startswith("auto-earnings-from-trade:"):
            update_fields = tuple(field for field in fields if field != "user_id")
            connection.execute(
                f"UPDATE earnings_bets SET {','.join(field + '=?' for field in update_fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                [payload[field] for field in update_fields] + [existing_id, current_user_id()],
            )
        return
    cursor = connection.execute(
        f"INSERT INTO earnings_bets ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
        [payload[field] for field in fields],
    )
    connection.execute(
        f"UPDATE {table} SET earnings_bet_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
        (cursor.lastrowid, trade_id, current_user_id()),
    )


def derived(row) -> dict:
    item = dict(row)
    item["sector"] = resolved_sector(item.get("ticker"), item.get("sector"))
    item["broker_source"] = broker_source_for_row(item)
    contracts = number(item.get("contracts"), 0) or 0
    premium_in = number(item.get("premium_in"))
    exit_premium = number(item.get("exit_premium"))
    stock_pnl = number(item.get("stock_pnl"), 0) or 0
    fees = number(item.get("fees"), 0) or 0
    status = item.get("status")
    if exit_premium is None and status == "Expired":
        exit_premium = 0
    premium_pnl = None if premium_in is None or exit_premium is None or not contracts else (
        premium_in - exit_premium
    ) * 100 * contracts
    trade_pl_pct = premium_pnl / (premium_in * 100 * contracts) if premium_pnl is not None and premium_in and contracts else None
    net_pnl = None if premium_pnl is None else premium_pnl + stock_pnl - fees
    opened = parse_date(item.get("open_date"))
    closed = parse_date(item.get("close_date"))
    held_until = closed or date.today()
    days_held = max(0, (held_until - opened).days) if opened else None
    capital = number(item.get("capital_used"))
    roc = net_pnl / capital if net_pnl is not None and capital else None
    annualized = roc * 365 / days_held if roc is not None and days_held else None
    if net_pnl is None:
        outcome = ""
    elif net_pnl > 0:
        outcome = "Win"
    elif net_pnl < 0:
        outcome = "Loss"
    else:
        outcome = "Breakeven"
    short_strike = number(item.get("strike"))
    long_strike = number(item.get("long_put_strike"))
    spread_width = abs(short_strike - long_strike) if short_strike is not None and long_strike is not None else None
    if item.get("strategy") == "Iron Condor":
        short_call = number(item.get("short_call_strike"))
        long_call = number(item.get("long_call_strike"))
        put_width = short_strike - long_strike if short_strike is not None and long_strike is not None else None
        call_width = long_call - short_call if short_call is not None and long_call is not None else None
        if put_width is not None and call_width is not None:
            spread_width = max(put_width, call_width)
    max_loss = None
    if spread_width is not None and premium_in is not None and contracts:
        max_loss = max(0, (spread_width - premium_in) * 100 * contracts)
    item.update(premium_pnl=premium_pnl, trade_pl_pct=trade_pl_pct, net_pnl=net_pnl, days_held=days_held,
                roc=roc, annualized_return=annualized, outcome=outcome,
                spread_width=spread_width, max_loss=max_loss)
    return item


def holding_derived(row) -> dict:
    item = dict(row)
    item["sector"] = resolved_sector(item.get("ticker"), item.get("sector"))
    shares = number(item.get("shares"), 0) or 0
    avg_cost = number(item.get("avg_cost"))
    current_price = number(item.get("current_price"))
    cost_basis = shares * avg_cost if avg_cost is not None else None
    market_value = shares * current_price if current_price is not None else None
    unrealized_pnl = market_value - cost_basis if market_value is not None and cost_basis is not None else None
    pnl_pct_value = unrealized_pnl / cost_basis if unrealized_pnl is not None and cost_basis else None
    item.update(
        shares=shares,
        avg_cost=avg_cost,
        current_price=current_price,
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        pnl_pct=pnl_pct_value,
    )
    return item


def money(value) -> str:
    if value is None:
        return "-"
    sign = "-" if value < 0 else ""
    amount = abs(value)
    if current_currency() == "rmb":
        return f"{sign}{RMB_SYMBOL}{amount * USD_CNY_RATE:,.2f}"
    return f"{sign}${amount:,.2f}"


def pct(value) -> str:
    return "-" if value is None else f"{value:.2%}"


def num(value) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def strike_display(trade) -> str:
    if trade.get("strategy") == "Iron Condor":
        strikes = (
            trade.get("long_put_strike"),
            trade.get("strike"),
            trade.get("short_call_strike"),
            trade.get("long_call_strike"),
        )
        if all(value is not None for value in strikes):
            return "/".join(num(value) for value in strikes)
    if trade.get("long_strike") is not None and trade.get("short_strike") is not None:
        return f'{num(trade.get("long_strike"))}/{num(trade.get("short_strike"))}'
    if trade.get("strategy") in {"Put Credit Spread", "Call Credit Spread"} and trade.get("long_put_strike") is not None:
        return f'{num(trade.get("strike"))}/{num(trade.get("long_put_strike"))}'
    return num(trade.get("strike"))


def option_instrument_display(trade) -> str:
    if trade.get("strategy") == "Iron Condor":
        return f'{strike_display(trade)} Iron Condor'.strip()
    option_type = str(trade.get("option_type") or "").strip().title()
    if option_type not in {"Call", "Put"}:
        strategy = str(trade.get("strategy") or trade.get("strategy_type") or "").lower()
        option_type = "Put" if "put" in strategy else "Call" if "call" in strategy else "Option"
    strikes = [part for part in strike_display(trade).split("/") if part]
    option_word = f"{option_type}s" if len(strikes) > 1 else option_type
    return f'{strike_display(trade)} {option_word}'.strip()


def normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def black_scholes(option_type: str, spot: float, strike: float, days: float, iv: float, rate: float, dividend: float) -> dict:
    years = max(days, 0.0) / 365
    sigma = max(iv, 0.0001)
    option_type = "call" if option_type == "call" else "put"
    if years <= 0:
        intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
        delta = 1.0 if option_type == "call" and spot > strike else -1.0 if option_type == "put" and spot < strike else 0.0
        return {"price": intrinsic, "delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0, "intrinsic": intrinsic, "extrinsic": 0.0, "d1": None, "d2": None}
    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate - dividend + 0.5 * sigma * sigma) * years) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    discount_rate = math.exp(-rate * years)
    discount_dividend = math.exp(-dividend * years)
    if option_type == "call":
        price = spot * discount_dividend * normal_cdf(d1) - strike * discount_rate * normal_cdf(d2)
        delta = discount_dividend * normal_cdf(d1)
        theta = (
            -spot * discount_dividend * normal_pdf(d1) * sigma / (2 * sqrt_t)
            - rate * strike * discount_rate * normal_cdf(d2)
            + dividend * spot * discount_dividend * normal_cdf(d1)
        ) / 365
        rho = strike * years * discount_rate * normal_cdf(d2) / 100
        intrinsic = max(0.0, spot - strike)
    else:
        price = strike * discount_rate * normal_cdf(-d2) - spot * discount_dividend * normal_cdf(-d1)
        delta = discount_dividend * (normal_cdf(d1) - 1)
        theta = (
            -spot * discount_dividend * normal_pdf(d1) * sigma / (2 * sqrt_t)
            + rate * strike * discount_rate * normal_cdf(-d2)
            - dividend * spot * discount_dividend * normal_cdf(-d1)
        ) / 365
        rho = -strike * years * discount_rate * normal_cdf(-d2) / 100
        intrinsic = max(0.0, strike - spot)
    gamma = discount_dividend * normal_pdf(d1) / (spot * sigma * sqrt_t)
    vega = spot * discount_dividend * normal_pdf(d1) * sqrt_t / 100
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
        "intrinsic": intrinsic,
        "extrinsic": max(0.0, price - intrinsic),
        "d1": d1,
        "d2": d2,
    }


def pl_pct(value, capital) -> float | None:
    if value is None or capital in (None, 0):
        return None
    return value / capital


def weighted_annualized_return(trades) -> float | None:
    total_pnl = 0.0
    capital_days = 0.0
    for trade in trades:
        if trade.get("status") == "Open" or trade.get("net_pnl") is None:
            continue
        capital = number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        days = trade.get("days_held") or 0
        if capital <= 0 or days <= 0:
            continue
        total_pnl += trade.get("net_pnl") or 0
        capital_days += capital * days
    if capital_days <= 0:
        return None
    return total_pnl / capital_days * 365


def trade_open_amount(trade: dict) -> float:
    units = number(trade.get("contracts"), 0) or 0
    price = abs(number(trade.get("premium_in"), 0) or 0)
    multiplier = 1 if trade.get("source") == "stock_trade" else 100
    return price * units * multiplier


def average_outcome_pl_metrics(trades: list[dict], positive: bool) -> tuple[float | None, float | None]:
    rows = [
        trade for trade in trades
        if trade.get("net_pnl") is not None
        and ((trade.get("net_pnl") or 0) > 0 if positive else (trade.get("net_pnl") or 0) < 0)
    ]
    if not rows:
        return None, None
    avg_pl = sum(trade.get("net_pnl") or 0 for trade in rows) / len(rows)
    pct_values = [trade.get("trade_pl_pct") for trade in rows if trade.get("trade_pl_pct") is not None]
    avg_pct = sum(pct_values) / len(pct_values) if pct_values else None
    return avg_pl, avg_pct


def peak_concurrent_capital(trades, start: date, end: date) -> float:
    changes = {}
    for trade in trades:
        opened = parse_date(trade.get("open_date"))
        if not opened or opened > end:
            continue
        active_end = parse_date(trade.get("close_date")) or end
        if active_end < start:
            continue
        capital = number(trade.get("capital_used"), 0) or 0
        if capital <= 0:
            continue
        active_start = max(opened, start)
        active_end = min(active_end, end)
        changes[active_start] = changes.get(active_start, 0.0) + capital
        changes[active_end + timedelta(days=1)] = changes.get(active_end + timedelta(days=1), 0.0) - capital

    peak = 0.0
    current = 0.0
    for day in sorted(changes):
        current += changes[day]
        if day <= end:
            peak = max(peak, current)
    return peak


def monthly_realized_series(trades) -> list[tuple[str, float]]:
    monthly_map = {}
    for trade in trades:
        if trade["net_pnl"] is None or trade["status"] == "Open":
            continue
        key = (trade["close_date"] or trade["open_date"] or "")[:7]
        if key:
            monthly_map[key] = monthly_map.get(key, 0) + trade["net_pnl"]
    return [(datetime.strptime(k, "%Y-%m").strftime("%b %y"), v) for k, v in sorted(monthly_map.items())]


def symbol_summary(trades, sort_by="total_pnl", sort_dir="desc") -> list[dict]:
    grouped = {}
    for trade in trades:
        if trade["net_pnl"] is None:
            continue
        ticker = trade["ticker"]
        entry = grouped.setdefault(ticker, {"ticker": ticker, "sector": trade.get("sector") or sector_for_ticker(ticker), "total_pnl": 0.0, "stock_pnl": 0.0, "option_pnl": 0.0, "capital_used": 0.0, "trades": 0, "wins": 0, "trade_pl_pcts": [], "positions": []})
        pnl_value = trade["net_pnl"] or 0
        entry["total_pnl"] += pnl_value
        if trade.get("source") == "stock_trade":
            entry["stock_pnl"] += pnl_value
        else:
            entry["option_pnl"] += pnl_value
        entry["trades"] += 1
        entry["positions"].append(trade)
        if trade.get("trade_pl_pct") is not None:
            entry["trade_pl_pcts"].append(trade["trade_pl_pct"])
        if trade["net_pnl"] > 0:
            entry["wins"] += 1
    summary = []
    for entry in grouped.values():
        dates = [
            parsed
            for trade in entry["positions"]
            for parsed in (parse_date(trade.get("open_date")), parse_date(trade.get("close_date")))
            if parsed
        ]
        entry["capital_used"] = peak_concurrent_capital(entry["positions"], min(dates), max(dates)) if dates else 0
        entry["pl_pct"] = pl_pct(entry["total_pnl"], entry["capital_used"])
        entry["win_rate"] = entry["wins"] / entry["trades"] if entry["trades"] else 0
        entry["avg_trade_pl_pct"] = sum(entry["trade_pl_pcts"]) / len(entry["trade_pl_pcts"]) if entry["trade_pl_pcts"] else None
        entry.pop("trade_pl_pcts", None)
        entry.pop("positions", None)
        summary.append(entry)
    valid_sort = {"ticker": "ticker", "sector": "sector", "total_pnl": "total_pnl", "stock_pnl": "stock_pnl", "option_pnl": "option_pnl", "capital_used": "capital_used",
                  "pl_pct": "pl_pct", "avg_trade_pl_pct": "avg_trade_pl_pct", "trades": "trades", "win_rate": "win_rate"}
    sort_key = valid_sort.get(sort_by, "total_pnl")
    reverse = sort_dir == "desc"

    def sort_value(item):
        value = broker_source_for_row(item) if sort_key == "source" else item.get(sort_key)
        if value is None:
            return (1, 0)
        return (0, value)

    summary.sort(key=sort_value, reverse=reverse)
    return summary


def normalized_strategy_name(strategy: str | None) -> str:
    raw = (strategy or "").strip()
    text = raw.lower()
    if "iron condor" in text:
        return "Iron Condor"
    if "call debit spread" in text:
        return "Call Debit Spread"
    if "put debit spread" in text:
        return "Put Debit Spread"
    if "call credit spread" in text:
        return "Call Credit Spread"
    if "put credit spread" in text:
        return "Put Credit Spread"
    if text.startswith("option buyer call"):
        return "Option Buyer Call"
    if text.startswith("option buyer put"):
        return "Option Buyer Put"
    if text.startswith("day trade call"):
        return "Day Trade Call"
    if text.startswith("day trade put"):
        return "Day Trade Put"
    return raw


def strategy_summary(trades, sort_by="total_pnl", sort_dir="desc") -> list[dict]:
    grouped = {}
    for trade in trades:
        if trade["net_pnl"] is None:
            continue
        strategy = normalized_strategy_name(trade["strategy"])
        entry = grouped.setdefault(strategy, {"strategy": strategy, "total_pnl": 0.0, "capital_used": 0.0, "trades": 0, "wins": 0})
        entry["total_pnl"] += trade["net_pnl"] or 0
        entry["capital_used"] += number(trade.get("capital_used"), 0) or 0
        entry["trades"] += 1
        if trade["net_pnl"] > 0:
            entry["wins"] += 1
    summary = []
    for entry in grouped.values():
        entry["pl_pct"] = pl_pct(entry["total_pnl"], entry["capital_used"])
        entry["win_rate"] = entry["wins"] / entry["trades"] if entry["trades"] else 0
        summary.append(entry)
    valid_sort = {"strategy": "strategy", "total_pnl": "total_pnl", "capital_used": "capital_used",
                  "pl_pct": "pl_pct", "trades": "trades", "win_rate": "win_rate"}
    sort_key = valid_sort.get(sort_by, "total_pnl")
    reverse = sort_dir == "desc"

    def sort_value(item):
        value = item.get(sort_key)
        if value is None:
            return (1, 0)
        return (0, value)

    summary.sort(key=sort_value, reverse=reverse)
    return summary


def line_chart_svg(monthly: list[tuple[str, float]]) -> str:
    if not monthly:
        return '<div class="empty">No closed-trade history yet.</div>'
    width, height, left, right, top, bottom = 760, 220, 28, 28, 18, 32
    values = [v for _, v in monthly]
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1)
    points = []
    for index, (_, value) in enumerate(monthly):
        x = left + (index / max(len(monthly) - 1, 1)) * (width - left - right)
        y = top + ((max_v - value) / span) * (height - top - bottom)
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    area = f"{points[0]} {points[-1]} {width-right},{height-bottom} {left},{height-bottom}"
    y_grid = [
        f'<line x1="{left}" y1="{top + i * ((height - top - bottom) / 4):.1f}" x2="{width-right}" y2="{top + i * ((height - top - bottom) / 4):.1f}" class="grid-line"/>'
        for i in range(5)
    ]
    labels = ''.join(f'<text x="{left + (idx / max(len(monthly)-1, 1)) * (width - left - right):.1f}" y="{height - 10}" text-anchor="middle" class="axis-label">{escape(label)}</text>' for idx, (label, _) in enumerate(monthly))
    return f'''<svg class="line-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Monthly realized P&L trend"><g>{''.join(y_grid)}</g><polygon points="{area}" class="area-fill"/><polyline points="{polyline}" class="line-series"/><g>{labels}</g></svg>'''


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def trade_close_dates(trades) -> list[date]:
    return sorted({
        closed for trade in trades
        if (closed := parse_date(trade.get("close_date"))) and trade.get("net_pnl") is not None
    })


def resolve_perf_range(trades, range_key: str, custom_start: str = "", custom_end: str = "") -> tuple[date | None, date | None, str, str]:
    close_dates = trade_close_dates(trades)
    if not close_dates:
        return None, None, "all", "No closed-trade history"
    end = close_dates[-1]
    start = close_dates[0]
    labels = {
        "5d": "5D",
        "1m": "1M",
        "3m": "3M",
        "6m": "6M",
        "ytd": "YTD",
        "1y": "1Y",
        "all": "Since Inception",
        "custom": "Custom",
    }
    if range_key == "5d":
        start = end - timedelta(days=4)
    elif range_key == "1m":
        start = add_months(end, -1) + timedelta(days=1)
    elif range_key == "3m":
        start = add_months(end, -3) + timedelta(days=1)
    elif range_key == "6m":
        start = add_months(end, -6) + timedelta(days=1)
    elif range_key == "ytd":
        start = date(end.year, 1, 1)
    elif range_key == "1y":
        start = add_months(end, -12) + timedelta(days=1)
    elif range_key == "custom":
        parsed_start = parse_date(custom_start)
        parsed_end = parse_date(custom_end)
        start = parsed_start or start
        end = parsed_end or end
        if start > end:
            start, end = end, start
    else:
        range_key = "all"
    return start, end, range_key, labels[range_key]


def filter_trades_by_perf_range(trades: list[dict], range_key: str = "all", custom_start: str = "", custom_end: str = "") -> list[dict]:
    start, end, _range_key, _label = resolve_perf_range(trades, range_key, custom_start, custom_end)
    if not start or not end:
        return trades
    activity_dates = [
        parsed
        for trade in trades
        for parsed in (parse_date(trade.get("close_date")), parse_date(trade.get("open_date")))
        if parsed
    ]
    if activity_dates:
        if _range_key == "all":
            start, end = min(activity_dates), max(activity_dates)
        else:
            end = max(end, max((parse_date(trade.get("open_date")) for trade in trades if trade.get("status") == "Open" and parse_date(trade.get("open_date"))), default=end))
    scoped = []
    for trade in trades:
        trade_date = parse_date(trade.get("open_date")) if trade.get("status") == "Open" else parse_date(trade.get("close_date")) or parse_date(trade.get("open_date"))
        if trade_date and start <= trade_date <= end:
            scoped.append(trade)
    return scoped


def sampled_chart_points(points: list, max_points: int = 260) -> list:
    if len(points) <= max_points:
        return points
    step = max(1, math.ceil(len(points) / max_points))
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def performance_range_controls(trades, range_key="all", metric="pnl", custom_start="", custom_end="", ticker="", extra_params=None) -> str:
    metric = "pct" if metric == "pct" else "pnl"
    start, end, range_key, _ = resolve_perf_range(trades, range_key, custom_start, custom_end)
    if not start or not end:
        return ""
    base_path = f"/symbol/{quote(ticker)}" if ticker else "/"
    custom_query = ""
    if range_key == "custom":
        custom_query = f'&perf_start={quote(custom_start or start.isoformat())}&perf_end={quote(custom_end or end.isoformat())}'
    ticker_query = f'&ticker={quote(ticker)}' if ticker else ""
    extra_items = query_param_items(extra_params)
    extra_query = f'&{urlencode(extra_items)}' if extra_items else ""
    extra_inputs = hidden_inputs_from_params(extra_items)
    range_buttons = "".join(
        f'<a class="perf-range {"active" if range_key == key else ""}" href="{base_path}?perf_metric={metric}&perf_range={key}{custom_query if key == "custom" else ""}{ticker_query}{extra_query}">{label}</a>'
        for key, label in (("5d", "5D"), ("1m", "1M"), ("3m", "3M"), ("6m", "6M"), ("ytd", "YTD"), ("1y", "1Y"), ("all", "All"))
    )
    custom_active = "active" if range_key == "custom" else ""
    custom_inputs = (
        f'<input type="date" name="perf_start" value="{escape(custom_start or start.isoformat())}">'
        f'<input type="date" name="perf_end" value="{escape(custom_end or end.isoformat())}">'
    )
    return f'''<div class="perf-controls">{range_buttons}
        <form class="perf-custom {custom_active}" method="get" action="{base_path}">
          <input type="hidden" name="perf_metric" value="{metric}">
          <input type="hidden" name="perf_range" value="custom">
          <input type="hidden" name="ticker" value="{escape(ticker)}">
          {extra_inputs}
          {custom_inputs}
          <button type="submit">Custom</button>
        </form>
      </div>'''


def performance_chart(trades, range_key="all", metric="pnl", custom_start="", custom_end="", ticker="", extra_params=None, header_actions="") -> str:
    metric = "pct" if metric == "pct" else "pnl"
    start, end, range_key, range_label = resolve_perf_range(trades, range_key, custom_start, custom_end)
    if not start or not end:
        chart_title = "Cumulative P&L" if metric == "pnl" else "Cumulative P&L %"
        return f'''<section class="panel performance-panel">
          <div class="perf-top"><div><div class="panel-title-row"><h2>{chart_title}</h2>{header_actions}</div></div><span>by close date</span></div>
          <div class="empty">No closed-trade history yet.</div>
        </section>'''

    daily = {}
    for trade in trades:
        closed = parse_date(trade.get("close_date"))
        if not closed or closed < start or closed > end or trade.get("net_pnl") is None:
            continue
        daily[closed] = daily.get(closed, 0.0) + (trade.get("net_pnl") or 0)
    capital = peak_concurrent_capital(trades, start, end)

    width, height = 760, 260
    left, right, top, bottom = 16, 70, 20, 36
    total_days = max((end - start).days, 1)
    points = []
    cumulative = 0.0
    current = start
    while current <= end:
        cumulative += daily.get(current, 0.0)
        value = cumulative if metric == "pnl" else pl_pct(cumulative, capital)
        points.append((current, value or 0.0))
        current += timedelta(days=1)

    values = [value for _, value in points] + [0]
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        min_v -= 1
        max_v += 1
    span = max_v - min_v

    def x_for(day: date) -> float:
        return left + ((day - start).days / total_days) * (width - left - right)

    def y_for(value: float) -> float:
        return top + ((max_v - value) / span) * (height - top - bottom)

    zero_y = y_for(0)
    chart_points = sampled_chart_points(points)
    positive_segments, negative_segments = [], []
    if chart_points:
        first_day, first_value = chart_points[0]
        previous_x = x_for(first_day)
        previous_value = first_value
        current_tone = "positive" if first_value >= 0 else "negative"
        current_segment = [f"{previous_x:.2f},{y_for(first_value):.2f}"]
        for day, value in chart_points[1:]:
            current_x = x_for(day)
            next_tone = "positive" if value >= 0 else "negative"
            point = f"{current_x:.2f},{y_for(value):.2f}"
            if next_tone != current_tone:
                denominator = abs(previous_value) + abs(value)
                ratio = abs(previous_value) / denominator if denominator else 0.0
                crossing_x = previous_x + (current_x - previous_x) * ratio
                crossing = f"{crossing_x:.2f},{zero_y:.2f}"
                current_segment.append(crossing)
                (positive_segments if current_tone == "positive" else negative_segments).append(" ".join(current_segment))
                current_segment = [crossing, point]
                current_tone = next_tone
            else:
                current_segment.append(point)
            previous_x = current_x
            previous_value = value
        (positive_segments if current_tone == "positive" else negative_segments).append(" ".join(current_segment))

    grid_values = [min_v + span * index / 4 for index in range(5)]
    grid = "".join(
        f'<line x1="{left}" x2="{width-right}" y1="{y_for(value):.2f}" y2="{y_for(value):.2f}" class="perf-grid-line"/>'
        for value in grid_values
    )
    axis_labels = "".join(
        f'<text x="{width - right + 10}" y="{y_for(value) + 4:.2f}" class="perf-y-label">{compact_currency(value) if metric == "pnl" else pct(value)}</text>'
        for value in reversed(grid_values)
    )
    line_svg = "".join(f'<polyline points="{segment}" class="perf-line positive"/>' for segment in positive_segments)
    line_svg += "".join(f'<polyline points="{segment}" class="perf-line negative"/>' for segment in negative_segments)
    area_points = ""
    if chart_points:
        plotted_points = " ".join(f"{x_for(day):.2f},{y_for(value):.2f}" for day, value in chart_points)
        area_points = (
            f"{x_for(chart_points[0][0]):.2f},{zero_y:.2f} "
            f"{plotted_points} "
            f"{x_for(chart_points[-1][0]):.2f},{zero_y:.2f}"
        )
    hover_points = [
        {
            "date": day.isoformat(),
            "label": day.strftime("%m/%d/%Y"),
            "value": value,
            "display": money(value) if metric == "pnl" else pct(value),
            "x": round(x_for(day), 2),
            "y": round(y_for(value), 2),
        }
        for day, value in chart_points
    ]
    hover_data = escape(json.dumps(hover_points), quote=True)
    start_label = start.strftime("%m/%d/%Y")
    end_label = end.strftime("%m/%d/%Y")
    total_value = points[-1][1] if points else 0
    total_class = "gain" if total_value >= 0 else "loss"
    capital_note = f' - Peak capital: {money(capital)}' if metric == "pct" and capital else ""
    custom_query = ""
    if range_key == "custom":
        custom_query = f'&perf_start={quote(custom_start or start.isoformat())}&perf_end={quote(custom_end or end.isoformat())}'
    base_path = f"/symbol/{quote(ticker)}" if ticker else "/"
    ticker_query = f'&ticker={quote(ticker)}' if ticker else ""
    extra_items = query_param_items(extra_params)
    extra_query = f'&{urlencode(extra_items)}' if extra_items else ""
    metric_tabs = "".join(
        f'<a class="perf-tab {"active" if metric == key else ""}" href="{base_path}?perf_metric={key}&perf_range={range_key}{custom_query}{ticker_query}{extra_query}">{label}</a>'
        for key, label in (("pnl", "P&L"), ("pct", "P&L%"))
    )
    chart_title = "Cumulative P&L" if metric == "pnl" else "Cumulative P&L %"
    return f'''<section class="panel performance-panel">
      <div class="perf-top">
        <div>
          <div class="panel-title-row"><h2>{chart_title}</h2>{header_actions}</div>
          <div class="perf-tabs">{metric_tabs}</div>
        </div>
        <span>by close date</span>
      </div>
      <div class="perf-summary">
        <strong class="{total_class}">{money(total_value) if metric == "pnl" else pct(total_value)}</strong>
        <small>Selected Range: {escape(range_label)} - {start_label} to {end_label}{capital_note}</small>
      </div>
      <svg class="performance-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Realized performance trend" data-points="{hover_data}" data-metric="{metric}" data-left="{left}" data-right="{width - right}" data-top="{top}" data-bottom="{height - bottom}">
        <defs>
          <linearGradient id="perfPositiveFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#089981" stop-opacity=".32"/><stop offset="100%" stop-color="#089981" stop-opacity="0"/></linearGradient>
          <linearGradient id="perfNegativeFill" gradientUnits="userSpaceOnUse" x1="0" y1="{zero_y:.2f}" x2="0" y2="{height-bottom:.2f}"><stop offset="0%" stop-color="#f23645" stop-opacity=".34"/><stop offset="100%" stop-color="#f23645" stop-opacity="0"/></linearGradient>
          <clipPath id="perfPositiveClip" clipPathUnits="userSpaceOnUse"><rect x="{left}" y="{top}" width="{width-left-right}" height="{max(zero_y-top, 0):.2f}"/></clipPath>
          <clipPath id="perfNegativeClip" clipPathUnits="userSpaceOnUse"><rect x="{left}" y="{zero_y:.2f}" width="{width-left-right}" height="{max(height-bottom-zero_y, 0):.2f}"/></clipPath>
        </defs>
        {grid}
        <line x1="{left}" x2="{width-right}" y1="{zero_y:.2f}" y2="{zero_y:.2f}" class="perf-zero-line"/>
        <polygon points="{area_points}" class="perf-area positive" clip-path="url(#perfPositiveClip)"/>
        <polygon points="{area_points}" class="perf-area negative" clip-path="url(#perfNegativeClip)"/>
        {line_svg}
        <line class="perf-hover-x" x1="{left}" x2="{width-right}" y1="{zero_y:.2f}" y2="{zero_y:.2f}"/>
        <line class="perf-hover-y" x1="{left}" x2="{left}" y1="{top}" y2="{height-bottom}"/>
        <circle class="perf-hover-dot" cx="{left}" cy="{zero_y:.2f}" r="4"/>
        <rect class="perf-hit-area" x="{left}" y="{top}" width="{width - left - right}" height="{height - top - bottom}"/>
        {axis_labels}
        <text x="{left}" y="{height - 8}" class="perf-x-label">{start_label}</text>
        <text x="{width - right}" y="{height - 8}" text-anchor="end" class="perf-x-label">{end_label}</text>
      </svg>
    </section>'''


def strategy_performance_panel(trades, range_key="all", custom_start="", custom_end="") -> str:
    start, end, range_key, range_label = resolve_perf_range(trades, range_key, custom_start, custom_end)
    if not start or not end:
        return '<section class="panel strategy-panel"><div class="empty">No closed-trade history yet.</div></section>'

    scoped = []
    for trade in trades:
        closed = parse_date(trade.get("close_date"))
        if closed and start <= closed <= end and trade.get("net_pnl") is not None:
            scoped.append(trade)

    entries = sorted(strategy_summary(scoped), key=lambda item: abs(item.get("total_pnl", 0) or 0), reverse=True)
    total = sum(abs(item.get("total_pnl", 0)) for item in entries) or 1
    colors = [
        "#2962ff", "#7c4dff", "#00bfa5", "#ff6d00",
        "#ff3d71", "#00a8cc", "#d946ef", "#84cc16",
        "#f59e0b", "#22d3ee", "#f43f5e", "#8b5cf6",
    ]
    cards = []
    for index, item in enumerate(entries[:12]):
        value = item.get("total_pnl", 0) or 0
        pct_value = abs(value) / total * 100
        color = colors[index % len(colors)]
        cards.append(
            f'<div class="strategy-donut-card">'
            f'<div class="strategy-ring" style="--percent:{pct_value:.2f};--ring-color:{color};">'
            f'<span>{pct_value:.2f}%</span></div>'
            f'<div class="strategy-name">{escape(item["strategy"])}</div>'
            f'<div class="strategy-meta"><span class="strategy-value {"gain" if value >= 0 else "loss"}">{money(value)}</span>'
            f'<span class="strategy-win-rate">WR {pct(item.get("win_rate"))}</span></div>'
            f'</div>'
        )
    if not cards:
        cards.append('<div class="empty">No strategy P&L in this range.</div>')

    return f'''<section class="panel strategy-panel">
      <div class="strategy-panel-head">
        <h2>P&L by Strategy</h2>
        <span>Selected Range: {escape(range_label)} - {start.strftime("%m/%d/%Y")} to {end.strftime("%m/%d/%Y")}</span>
      </div>
      <div class="strategy-donut-grid">{"".join(cards)}</div>
    </section>'''


def donut_chart_svg(entries: list[dict], value_key: str, label_key: str, name: str) -> str:
    if not entries:
        return '<div class="empty">No data available.</div>'
    total = sum(abs(item.get(value_key, 0)) for item in entries)
    if total == 0:
        total = 1
    colors = ["#6aa9d6", "#7c71d9", "#8cb7b4", "#ebb06d", "#dd6d75", "#7bb99b"]
    cards = []
    for index, item in enumerate(entries[:6]):
        raw = item.get(value_key, 0)
        pct = abs(raw) / total * 100 if total else 0
        color = colors[index % len(colors)]
        value = item.get(label_key)
        cards.append(f'''<div class="donut-card"><div class="donut-ring" style="--percent:{min(max(pct, 0.1), 100):.1f};--ring-color:{color};"><div class="donut-center">{pct:.1f}%</div></div><div class="donut-label">{escape(str(value))}</div><div class="donut-value {"gain" if raw >= 0 else "loss"}">{money(raw)}</div></div>''')
    return f'<div class="donut-grid" data-chart="{escape(name)}">{"".join(cards)}</div>'


def pie_chart_svg(entries: list[dict], value_key: str, label_key: str, name: str) -> str:
    entries = [item for item in entries if item.get(value_key) not in (None, 0)]
    if not entries:
        return '<div class="empty">No data available.</div>'
    colors = ["#2e6f83", "#d97745", "#7c71d9", "#8cb7b4", "#c64b55", "#ebb06d"]
    total = sum(abs(item.get(value_key, 0)) for item in entries) or 1
    cx, cy, radius = 120, 120, 94
    start_angle = -90
    slices = []
    legend = []

    def point(angle):
        radians = math.radians(angle)
        return cx + radius * math.cos(radians), cy + radius * math.sin(radians)

    for index, item in enumerate(entries[:6]):
        raw = item.get(value_key, 0) or 0
        pct_value = abs(raw) / total
        end_angle = start_angle + pct_value * 360
        start_x, start_y = point(start_angle)
        end_x, end_y = point(end_angle)
        large_arc = 1 if end_angle - start_angle > 180 else 0
        color = colors[index % len(colors)]
        label = str(item.get(label_key, ""))
        pct_label = pct_value * 100
        if pct_value >= 0.999:
            path = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{color}"><title>{escape(label)}: {pct_label:.1f}%</title></circle>'
        else:
            path = (
                f'<path d="M {cx} {cy} L {start_x:.2f} {start_y:.2f} '
                f'A {radius} {radius} 0 {large_arc} 1 {end_x:.2f} {end_y:.2f} Z" '
                f'fill="{color}"><title>{escape(label)}: {pct_label:.1f}%</title></path>'
            )
        slices.append(path)
        legend.append(
            f'<div class="pie-legend-row"><span class="pie-swatch" style="background:{color}"></span>'
            f'<span class="pie-label">{escape(label)}</span><b class="{"gain" if raw >= 0 else "loss"}">{money(raw)}</b>'
            f'<small>{pct_label:.1f}%</small></div>'
        )
        start_angle = end_angle

    return (
        f'<div class="pie-chart" data-chart="{escape(name)}">'
        f'<svg viewBox="0 0 240 240" role="img" aria-label="{escape(name)} pie chart">{"".join(slices)}</svg>'
        f'<div class="pie-legend">{"".join(legend)}</div></div>'
    )


def compact_money(value) -> str:
    if value is None:
        return "0.00"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    amount = abs(value) * (USD_CNY_RATE if current_currency() == "rmb" else 1)
    symbol = RMB_SYMBOL if current_currency() == "rmb" else ""
    return f"{sign}{symbol}{amount:,.2f}"


def compact_currency(value) -> str:
    if value is None:
        return "-"
    sign = "-" if value < 0 else ""
    amount = abs(value) * (USD_CNY_RATE if current_currency() == "rmb" else 1)
    symbol = RMB_SYMBOL if current_currency() == "rmb" else "$"
    if amount >= 1000:
        return f"{sign}{symbol}{amount / 1000:.2f}K"
    return f"{sign}{symbol}{amount:,.0f}"


def compact_money(value) -> str:
    if value is None:
        return "0.00"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    amount = abs(value) * (USD_CNY_RATE if current_currency() == "rmb" else 1)
    symbol = RMB_SYMBOL if current_currency() == "rmb" else ""
    return f"{sign}{symbol}{amount:,.2f}"


def compact_currency(value) -> str:
    if value is None:
        return "-"
    sign = "-" if value < 0 else ""
    amount = abs(value) * (USD_CNY_RATE if current_currency() == "rmb" else 1)
    symbol = RMB_SYMBOL if current_currency() == "rmb" else "$"
    if amount >= 1000:
        return f"{sign}{symbol}{amount / 1000:.2f}K"
    return f"{sign}{symbol}{amount:,.0f}"


def signed_pct(value) -> str:
    if value is None:
        return "0.00%"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2%}"


def close_date_calendar(trades, selected_year=None, selected_month=None, selected_view="month", extra_params=None, header_actions="") -> str:
    today = date.today()
    year = selected_year if selected_year else today.year
    month = selected_month if selected_month else today.month
    view = "year" if selected_view == "year" else "month"
    if month < 1 or month > 12:
        month = today.month
    if year < 1900 or year > 2200:
        year = today.year
    extra_items = query_param_items(extra_params)
    extra_inputs = hidden_inputs_from_params(extra_items)

    def calendar_href(**params):
        merged = [(key, value) for key, value in extra_items if key not in params]
        merged.extend((key, str(value)) for key, value in params.items())
        return f"/?{urlencode(merged)}"

    daily = {}
    for trade in trades:
        closed = parse_date(trade.get("close_date"))
        if not closed:
            continue
        entry = daily.setdefault(closed, {"pnl": 0.0, "capital": 0.0, "count": 0})
        entry["pnl"] += trade.get("net_pnl") or 0
        entry["capital"] += number(trade.get("capital_used"), 0) or 0
        entry["count"] += 1

    selected = date(year, month, 1)
    previous_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    years = sorted({today.year, year} | {parse_date(t.get("close_date")).year for t in trades if parse_date(t.get("close_date"))})
    if not years:
        years = [today.year]
    first_year = min(years) - 2
    last_year = max(years) + 2
    year_options = "".join(f'<option value="{item}" {"selected" if item == year else ""}>{item}</option>' for item in range(first_year, last_year + 1))
    month_options = "".join(
        f'<option value="{item}" {"selected" if item == month else ""}>{calendar.month_abbr[item]}</option>'
        for item in range(1, 13)
    )

    if view == "year":
        monthly = {item: {"pnl": 0.0, "capital": 0.0, "count": 0} for item in range(1, 13)}
        for day, item in daily.items():
            if day.year != year:
                continue
            monthly[day.month]["pnl"] += item["pnl"]
            monthly[day.month]["capital"] += item["capital"]
            monthly[day.month]["count"] += item["count"]
        max_abs = max((abs(item["pnl"]) for item in monthly.values()), default=0) or 1
        month_cells = []
        for item_month in range(1, 13):
            item = monthly[item_month]
            pnl = item["pnl"]
            has_data = item["capital"] or pnl
            month_pct = pl_pct(pnl, item["capital"]) if has_data else None
            tone = "gain" if pnl > 0 else "loss" if pnl < 0 else "flat"
            current_month = " today" if today.year == year and today.month == item_month else ""
            strength = min(abs(pnl) / max_abs, 1)
            if has_data:
                values = f'<b>{compact_money(pnl)}</b><span>{signed_pct(month_pct)}</span>'
            else:
                values = '<b>--</b><span>--</span>'
            month_cells.append(
                f'<a class="calendar-month-cell {tone}{current_month}" style="--strength:{strength:.2f}" href="{calendar_href(cal_view="month", cal_year=year, cal_month=item_month)}">'
                f'<span>{calendar.month_abbr[item_month]}</span><div>{values}</div></a>'
            )
        return f'''<section class="panel calendar-panel">
      <div class="panel-head calendar-head">
        <div><div class="panel-title-row"><h2>Close Date Calendar</h2>{header_actions}</div><span>{year} realized P&L by close date</span></div>
        <form class="calendar-controls" method="get">
          <a class="calendar-nav" href="{calendar_href(cal_view="year", cal_year=year - 1, cal_month=month)}" aria-label="Previous year">&#9664;</a>
          <select name="cal_year">{year_options}</select>
          <input type="hidden" name="cal_month" value="{month}">
          <input type="hidden" name="cal_view" value="year">
          {extra_inputs}
          <a class="calendar-nav" href="{calendar_href(cal_view="year", cal_year=year + 1, cal_month=month)}" aria-label="Next year">&#9654;</a>
          <div class="calendar-modes">
            <a class="calendar-mode" href="{calendar_href(cal_view="month", cal_year=year, cal_month=month)}">Month</a>
            <a class="calendar-mode active" href="{calendar_href(cal_view="year", cal_year=year, cal_month=month)}">Year</a>
          </div>
        </form>
      </div>
      <div class="calendar-year-grid">{"".join(month_cells)}</div>
    </section>'''

    max_abs = max((abs(item["pnl"]) for day, item in daily.items() if day.year == year and day.month == month), default=0) or 1
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    weekday_header = "".join(f'<div class="calendar-weekday">{name}</div>' for name in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"))
    cells = []
    for week in weeks:
        for day in week:
            item = daily.get(day, {"pnl": 0.0, "capital": 0.0, "count": 0})
            pnl = item["pnl"]
            day_pct = pl_pct(pnl, item["capital"]) or 0
            tone = "gain" if pnl > 0 else "loss" if pnl < 0 else "flat"
            outside = " outside" if day.month != month else ""
            today_class = " today" if day == today else ""
            strength = min(abs(pnl) / max_abs, 1)
            cells.append(
                f'<div class="calendar-day {tone}{outside}{today_class}" style="--strength:{strength:.2f}">'
                f'<div class="calendar-date">{day.day}</div>'
                f'<div class="calendar-values"><b>{compact_money(pnl)}</b><span>{signed_pct(day_pct)}</span></div>'
                f'</div>'
            )

    return f'''<section class="panel calendar-panel">
      <div class="panel-head calendar-head">
        <div><div class="panel-title-row"><h2>Close Date Calendar</h2>{header_actions}</div><span>{selected.strftime("%B %Y")} realized P&L by close date</span></div>
        <form class="calendar-controls" method="get">
          <a class="calendar-nav" href="{calendar_href(cal_view="month", cal_year=previous_month.year, cal_month=previous_month.month)}" aria-label="Previous month">&#9664;</a>
          <select name="cal_month">{month_options}</select>
          <select name="cal_year">{year_options}</select>
          <input type="hidden" name="cal_view" value="month">
          {extra_inputs}
          <a class="calendar-nav" href="{calendar_href(cal_view="month", cal_year=next_month.year, cal_month=next_month.month)}" aria-label="Next month">&#9654;</a>
          <div class="calendar-modes">
            <a class="calendar-mode active" href="{calendar_href(cal_view="month", cal_year=year, cal_month=month)}">Month</a>
            <a class="calendar-mode" href="{calendar_href(cal_view="year", cal_year=year, cal_month=month)}">Year</a>
          </div>
        </form>
      </div>
      <div class="calendar-grid">{weekday_header}{"".join(cells)}</div>
    </section>'''


def command_palette() -> str:
    items = [
        {"label": "Dashboard", "meta": "Overview", "href": "/"},
        {"label": "Options Calculator", "meta": "Black-Scholes and spread math", "href": "/options-calculator"},
        {"label": "Review", "meta": "Weekly trade and portfolio review", "href": "/trade-journal-review"},
        {"label": "Portfolio", "meta": "Robinhood snapshot", "href": "/brokerage"},
        {"label": "Sentiment", "meta": "GreedyFear market mood", "href": "/sentiment"},
        {"label": "Market News", "meta": "Jin10 red flashes", "href": "/market-news"},
        {"label": "Assistant", "meta": "AI holdings review", "href": "/assistant"},
        {"label": "Symbols", "meta": "Ticker summary", "href": "/symbols"},
        {"label": "Trades", "meta": "Trade ledger", "href": "/trades"},
        {"label": "Stock Trades", "meta": "Stock trade ledger", "href": "/trades?view=stock-trades"},
        {"label": "Record trade", "meta": "New option trade", "href": "/option-trade/new"},
        {"label": "Account", "meta": "Users and login", "href": "/account"},
    ]
    symbols = sorted({trade.get("ticker", "").upper() for trade in all_trades()} | {holding.get("ticker", "").upper() for holding in all_holdings()})
    for ticker in symbols:
        if ticker:
            items.append({"label": ticker, "meta": f"{sector_for_ticker(ticker)} symbol detail", "href": f"/symbol/{quote(ticker)}"})
    rows = "".join(
        f'<a class="command-item" href="{escape(item["href"])}" data-command-text="{escape((item["label"] + " " + item["meta"]).lower())}"><b>{escape(item["label"])}</b><span>{escape(item["meta"])}</span></a>'
        for item in items
    )
    return f'''<div class="command-palette" hidden>
      <div class="command-backdrop" data-command-close></div>
      <section class="command-dialog" role="dialog" aria-modal="true" aria-label="Command palette">
        <input class="command-input" type="search" placeholder="Search pages, symbols, actions..." autocomplete="off">
        <div class="command-list">{rows}</div>
        <div class="command-empty" hidden>No matches.</div>
      </section>
    </div>'''


def layout(title: str, body: str, active: str = "") -> bytes:
    user = current_user()
    username = user["username"] if user else "root"
    user_links = "".join(
        f'<span class="nav-menu-meta">{"Current" if row["username"] == username else "User"}: {escape(row["username"])}</span>'
        for row in all_users()
    )
    primary_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("dashboard", "/", "Dashboard"),
        )
    )
    tools_active = active in {"option-calculator", "sentiment", "market-news"}
    tools_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("option-calculator", "/options-calculator", "Options Calculator"),
            ("sentiment", "/sentiment", "Sentiment"),
            ("market-news", "/market-news", "Market News"),
        )
    )
    records_links = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("symbols", "/symbols", "Symbols"),
            ("trades", "/trades", "Trades"),
            ("earnings-bets", "/earnings-bets", "Earnings"),
        )
    )
    nav = (
        primary_nav
        + records_links
        + f'<a class="{"active" if active == "trade-journal-review" else ""}" href="/trade-journal-review">Review</a>'
        + f'<div class="nav-menu {"active" if tools_active else ""}"><button class="nav-menu-button" type="button">Tools</button><div class="nav-menu-list">{tools_nav}</div></div>'
        + '<button class="command-trigger" type="button" aria-label="Open command palette">Search</button>'
        + f'<div class="nav-menu account-menu {"active" if active == "account" else ""}"><button class="nav-menu-button account-button" type="button">@{escape(username)}</button><div class="nav-menu-list account-menu-list"><a class="{"active" if active == "account" else ""}" href="/account">Account settings</a>{user_links}<form method="post" action="/logout"><button type="submit">Use root account</button></form></div></div>'
    )
    font_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (
            ("Tahoma", "Tahoma"),
            ("Inter", "Inter"),
            ("Segoe UI", "Segoe UI"),
            ("Arial", "Arial"),
            ("Verdana", "Verdana"),
            ("Calibri", "Calibri"),
            ("Trebuchet MS", "Trebuchet MS"),
            ("Century Gothic", "Century Gothic"),
            ("Georgia", "Georgia"),
            ("Times New Roman", "Times New Roman"),
            ("Consolas", "Consolas"),
            ("Courier New", "Courier New"),
            ("Microsoft YaHei", "Microsoft YaHei"),
            ("DengXian", "DengXian"),
            ("OpenDyslexic", "OpenDyslexic"),
            ("Vazirmatn", "Vazirmatn"),
            ("Quicksand", "Quicksand"),
            ("Comfortaa", "Comfortaa"),
            ("Fredoka", "Fredoka"),
            ("Ubuntu", "Ubuntu"),
            ("Cantarell", "Cantarell"),
            ("San Francisco", "San Francisco"),
            ("Segoe UI Variable", "Segoe UI Variable"),
            ("Cascadia Code", "Cascadia Code"),
            ("Noto Sans SC", "Noto Sans SC"),
            ("Noto Serif SC", "Noto Serif SC"),
            ("Roboto", "Roboto"),
            ("Roboto Condensed", "Roboto Condensed"),
            ("Roboto Mono", "Roboto Mono"),
            ("IBM Plex Sans", "IBM Plex Sans"),
            ("IBM Plex Mono", "IBM Plex Mono"),
            ("Source Sans 3", "Source Sans 3"),
            ("Source Serif 4", "Source Serif 4"),
            ("Manrope", "Manrope"),
            ("Space Grotesk", "Space Grotesk"),
            ("JetBrains Mono", "JetBrains Mono"),
            ("Fira Sans", "Fira Sans"),
            ("Fira Code", "Fira Code"),
            ("Work Sans", "Work Sans"),
        )
    )
    currency_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (("usd", "USD"), ("rmb", "RMB"))
    )
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
    <link rel="stylesheet" href="/static/style.css?v=20261102-2"></head><body>
    <header><div class="brand"><span class="logo">OL</span><div><b>Option Ledger</b><small>Trading Dashboard</small></div></div><nav>{nav}<select class="currency-picker" aria-label="Choose currency">{currency_options}</select><button class="theme-toggle" type="button" aria-label="Toggle color theme" title="Theme: Auto"><span class="theme-toggle-icon" aria-hidden="true">&#9728;</span></button><select class="font-picker" aria-label="Choose site font">{font_options}</select></nav></header>
    {command_palette()}<main>{body}</main><footer>Local data | Your SQLite file stays on this computer</footer>
    <script src="/static/app.js?v=20261102-2"></script></body></html>"""
    return html.encode("utf-8")


def layout(title: str, body: str, active: str = "") -> bytes:
    user = current_user()
    username = user["username"] if user else "root"
    display_name = user["display_name"] if user and user["display_name"] else username
    initials = "".join(part[:1] for part in display_name.replace("_", " ").split()[:2]).upper() or username[:2].upper()
    font_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (
            ("Tahoma", "Tahoma"),
            ("Inter", "Inter"),
            ("Segoe UI", "Segoe UI"),
            ("Arial", "Arial"),
            ("Verdana", "Verdana"),
            ("Calibri", "Calibri"),
            ("Trebuchet MS", "Trebuchet MS"),
            ("Century Gothic", "Century Gothic"),
            ("Georgia", "Georgia"),
            ("Times New Roman", "Times New Roman"),
            ("Consolas", "Consolas"),
            ("Courier New", "Courier New"),
            ("Microsoft YaHei", "Microsoft YaHei"),
            ("DengXian", "DengXian"),
            ("OpenDyslexic", "OpenDyslexic"),
            ("Vazirmatn", "Vazirmatn"),
            ("Quicksand", "Quicksand"),
            ("Comfortaa", "Comfortaa"),
            ("Fredoka", "Fredoka"),
            ("Ubuntu", "Ubuntu"),
            ("Cantarell", "Cantarell"),
            ("San Francisco", "San Francisco"),
            ("Segoe UI Variable", "Segoe UI Variable"),
            ("Cascadia Code", "Cascadia Code"),
            ("Noto Sans SC", "Noto Sans SC"),
            ("Noto Serif SC", "Noto Serif SC"),
            ("Roboto", "Roboto"),
            ("Roboto Condensed", "Roboto Condensed"),
            ("Roboto Mono", "Roboto Mono"),
            ("IBM Plex Sans", "IBM Plex Sans"),
            ("IBM Plex Mono", "IBM Plex Mono"),
            ("Source Sans 3", "Source Sans 3"),
            ("Source Serif 4", "Source Serif 4"),
            ("Manrope", "Manrope"),
            ("Space Grotesk", "Space Grotesk"),
            ("JetBrains Mono", "JetBrains Mono"),
            ("Fira Sans", "Fira Sans"),
            ("Fira Code", "Fira Code"),
            ("Work Sans", "Work Sans"),
        )
    )
    currency_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (("usd", "USD"), ("rmb", "RMB"))
    )
    other_users = [row for row in all_users() if row["username"] != username]
    user_links = "".join(
        f'<span class="account-user-row"><span class="tiny-avatar">{escape((row["display_name"] or row["username"])[:1].upper())}</span><span>{escape(row["username"])}</span><b>User</b></span>'
        for row in other_users
    ) or '<span class="account-user-row muted-row">No other users yet</span>'
    primary_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("dashboard", "/", "Dashboard"),
        )
    )
    tools_active = active in {"option-calculator", "sentiment", "market-news"}
    tools_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("option-calculator", "/options-calculator", "Options Calculator"),
            ("sentiment", "/sentiment", "Sentiment"),
            ("market-news", "/market-news", "Market News"),
        )
    )
    records_links = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("symbols", "/symbols", "Symbols"),
            ("trades", "/trades", "Trades"),
            ("earnings-bets", "/earnings-bets", "Earnings"),
        )
    )
    account_active = "active" if active == "account" else ""
    account_menu = position_notification_menu() + f'''<div class="nav-menu account-menu {account_active}">
      <button class="nav-menu-button account-button" type="button"><span class="account-avatar">{escape(initials)}</span><span>{escape(display_name)}</span></button>
      <div class="nav-menu-list account-menu-list">
        <div class="account-menu-head"><span class="account-avatar large">{escape(initials)}</span><div><b>{escape(display_name)}</b><small>{escape(username)}@local</small></div><em>Local</em></div>
        <div class="account-menu-users">{user_links}</div>
        <label class="account-menu-row"><span>Language</span><select class="language-picker" aria-label="Choose language"><option value="en">English</option><option value="zh">&#31616;&#20307;&#20013;&#25991;</option></select></label>
        <label class="account-menu-row"><span>Currency</span><select class="currency-picker" aria-label="Choose currency">{currency_options}</select></label>
        <div class="account-menu-row"><span>Theme</span><button class="theme-toggle" type="button" aria-label="Toggle color theme" title="Theme: Auto"><span class="theme-toggle-icon" aria-hidden="true">&#9728;</span></button></div>
        <label class="account-menu-row"><span>Font</span><select class="font-picker" aria-label="Choose site font">{font_options}</select></label>
        <a class="account-menu-link {account_active}" href="/account">Account settings</a>
        <a class="account-menu-link" href="/assistant">Assistant review</a>
        <form method="post" action="/logout"><button type="submit">Use root account</button></form>
      </div>
    </div>'''
    nav = (
        '<button class="command-trigger" type="button" aria-label="Open command palette">Search</button>'
        + primary_nav
        + records_links
        + f'<a class="{"active" if active == "brokerage" else ""}" href="/brokerage">Portfolio</a>'
        + f'<a class="{"active" if active == "trade-journal-review" else ""}" href="/trade-journal-review">Review</a>'
        + f'<div class="nav-menu {"active" if tools_active else ""}"><button class="nav-menu-button" type="button">Tools</button><div class="nav-menu-list">{tools_nav}</div></div>'
        + '<div class="market-clock" data-market-clock><span class="clock-dot"></span><b data-clock-time>--:--</b><span data-clock-label>to open</span><span data-clock-countdown>--:--:--</span></div>'
        + position_notification_menu()
        + account_menu
    )
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
    <link rel="stylesheet" href="/static/style.css?v=20261102-2"></head><body>
    <header><div class="brand"><span class="logo">OL</span><div><b>Option Ledger</b><small>Trading Dashboard</small></div></div><nav>{nav}</nav></header>
    {command_palette()}<main>{body}</main><footer>Local data | Your SQLite file stays on this computer</footer>
    <script src="/static/app.js?v=20261102-2"></script></body></html>"""
    return html.encode("utf-8")


def layout(title: str, body: str, active: str = "") -> bytes:
    user = current_user()
    username = user["username"] if user else "root"
    display_name = user["display_name"] if user and user["display_name"] else username
    initials = "".join(part[:1] for part in display_name.replace("_", " ").split()[:2]).upper() or username[:2].upper()
    font_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (
            ("Tahoma", "Tahoma"),
            ("Inter", "Inter"),
            ("Segoe UI", "Segoe UI"),
            ("Arial", "Arial"),
            ("Verdana", "Verdana"),
            ("Calibri", "Calibri"),
            ("Trebuchet MS", "Trebuchet MS"),
            ("Century Gothic", "Century Gothic"),
            ("Georgia", "Georgia"),
            ("Times New Roman", "Times New Roman"),
            ("Consolas", "Consolas"),
            ("Courier New", "Courier New"),
            ("Microsoft YaHei", "Microsoft YaHei"),
            ("DengXian", "DengXian"),
            ("OpenDyslexic", "OpenDyslexic"),
            ("Vazirmatn", "Vazirmatn"),
            ("Quicksand", "Quicksand"),
            ("Comfortaa", "Comfortaa"),
            ("Fredoka", "Fredoka"),
            ("Ubuntu", "Ubuntu"),
            ("Cantarell", "Cantarell"),
            ("San Francisco", "San Francisco"),
            ("Segoe UI Variable", "Segoe UI Variable"),
            ("Cascadia Code", "Cascadia Code"),
            ("Noto Sans SC", "Noto Sans SC"),
            ("Noto Serif SC", "Noto Serif SC"),
            ("Roboto", "Roboto"),
            ("Roboto Condensed", "Roboto Condensed"),
            ("Roboto Mono", "Roboto Mono"),
            ("IBM Plex Sans", "IBM Plex Sans"),
            ("IBM Plex Mono", "IBM Plex Mono"),
            ("Source Sans 3", "Source Sans 3"),
            ("Source Serif 4", "Source Serif 4"),
            ("Manrope", "Manrope"),
            ("Space Grotesk", "Space Grotesk"),
            ("JetBrains Mono", "JetBrains Mono"),
            ("Fira Sans", "Fira Sans"),
            ("Fira Code", "Fira Code"),
            ("Work Sans", "Work Sans"),
        )
    )
    currency_options = "".join(
        f'<option value="{escape(value)}">{escape(label)}</option>'
        for value, label in (("usd", "USD"), ("rmb", "RMB"))
    )
    other_users = [row for row in all_users() if row["username"] != username]
    user_links = "".join(
        f'<span class="account-user-row"><span class="tiny-avatar">{escape((row["display_name"] or row["username"])[:1].upper())}</span><span>{escape(row["username"])}</span><b>User</b></span>'
        for row in other_users
    ) or '<span class="account-user-row muted-row">No other users yet</span>'
    primary_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("dashboard", "/", "Dashboard"),
        )
    )
    tools_active = active in {"option-calculator", "sentiment", "market-news"}
    tools_nav = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("option-calculator", "/options-calculator", "Options Calculator"),
            ("sentiment", "/sentiment", "Sentiment"),
            ("market-news", "/market-news", "Market News"),
        )
    )
    records_links = "".join(
        f'<a class="{"active" if active == key else ""}" href="{href}">{label}</a>'
        for key, href, label in (
            ("symbols", "/symbols", "Symbols"),
            ("trades", "/trades", "Trades"),
            ("earnings-bets", "/earnings-bets", "Earnings"),
        )
    )
    account_active = "active" if active == "account" else ""
    account_menu = position_notification_menu() + f'''<div class="nav-menu account-menu {account_active}">
      <button class="nav-menu-button account-button" type="button"><span class="account-avatar">{escape(initials)}</span><span>{escape(display_name)}</span></button>
      <div class="nav-menu-list account-menu-list">
        <div class="account-menu-head"><span class="account-avatar large">{escape(initials)}</span><div><b>{escape(display_name)}</b><small>{escape(username)}@local</small></div><em>Local</em></div>
        <div class="account-menu-users">{user_links}</div>
        <label class="account-menu-row"><span>Language</span><select class="language-picker" aria-label="Choose language"><option value="en">English</option><option value="zh">&#31616;&#20307;&#20013;&#25991;</option></select></label>
        <label class="account-menu-row"><span>Currency</span><select class="currency-picker" aria-label="Choose currency">{currency_options}</select></label>
        <div class="account-menu-row"><span>Theme</span><button class="theme-toggle" type="button" aria-label="Toggle color theme" title="Theme: Auto"><span class="theme-toggle-icon" aria-hidden="true">&#9728;</span></button></div>
        <label class="account-menu-row"><span>Font</span><select class="font-picker" aria-label="Choose site font">{font_options}</select></label>
        <a class="account-menu-link {account_active}" href="/account">Account settings</a>
        <a class="account-menu-link" href="/assistant">Assistant review</a>
        <form method="post" action="/logout"><button type="submit">Use root account</button></form>
      </div>
    </div>'''
    nav = (
        '<button class="command-trigger" type="button" aria-label="Open command palette">Search</button>'
        + primary_nav
        + records_links
        + f'<a class="{"active" if active == "brokerage" else ""}" href="/brokerage">Portfolio</a>'
        + f'<a class="{"active" if active == "trade-journal-review" else ""}" href="/trade-journal-review">Review</a>'
        + f'<div class="nav-menu {"active" if tools_active else ""}"><button class="nav-menu-button" type="button">Tools</button><div class="nav-menu-list">{tools_nav}</div></div>'
        + '<div class="market-clock" data-market-clock><span class="clock-dot"></span><b data-clock-time>--:--</b><span data-clock-label>to open</span><span data-clock-countdown>--:--:--</span></div>'
        + account_menu
    )
    page_title = (
        title.replace("Option Ledger", "dandan.com")
        .replace("Ãƒâ€šÃ‚Â·", "-")
        .replace("Ã‚Â·", "-")
    )
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(page_title)}</title>
    <link rel="icon" type="image/png" href="/static/dandan-avatar.png">
    <style>html{{background:#eeede6}}</style>
    <link rel="stylesheet" href="/static/style.css?v=20261102-2"></head><body><script>
    (function(){{try{{var m=localStorage.getItem("optionLedgerTheme")||"auto";var r=m==="auto"?"light":m;document.body.dataset.themeMode=m;document.body.dataset.theme=r;document.documentElement.dataset.theme=r;}}catch(e){{document.body.dataset.theme="light";document.documentElement.dataset.theme="light";}}}})();
    </script>
    <header><a class="brand" href="/welcome" aria-label="Open welcome page"><span class="logo"><img src="/static/dandan-avatar.png" alt=""></span><span><b>dandan.com</b><small>Trading Dashboard</small></span></a><nav>{nav}</nav></header>
    <div class="ticker-tape" data-ticker-tape data-refresh-seconds="{MARKET_TAPE_REFRESH_SECONDS}"><div class="ticker-track"><span class="ticker-item muted"><b>Loading</b><span>Market prices</span></span></div></div>
    {command_palette()}<main>{body}</main><footer>Local data | Your SQLite file stays on this computer</footer>
    <div class="ragdoll-companion" data-ragdoll-companion>
      <span class="ragdoll-speech" data-ragdoll-speech aria-live="polite">Stay patient.</span>
      <button class="ragdoll-cat-button" type="button" data-ragdoll-cat aria-label="Open Dandan menu" aria-haspopup="menu" aria-expanded="false" title="Drag Dandan or click for options">
        <span class="ragdoll-purr" aria-hidden="true">rrr...</span>
        <canvas class="ragdoll-sprite" data-ragdoll-sprite width="352" height="316" aria-hidden="true"></canvas>
        <img class="ragdoll-pose is-active" data-ragdoll-pose="idle" src="/static/dandan-mascot.png" alt="" aria-hidden="true" draggable="false">
        <img class="ragdoll-pose" data-ragdoll-pose="pet" src="/static/dandan-pet.png" alt="" aria-hidden="true" draggable="false">
        <img class="ragdoll-pose" data-ragdoll-pose="sleep" src="/static/dandan-sleep.png" alt="" aria-hidden="true" draggable="false">
        <img class="ragdoll-pose" data-ragdoll-pose="stretch" src="/static/dandan-stretch.png" alt="" aria-hidden="true" draggable="false">
        <img class="ragdoll-pose" data-ragdoll-pose="wave" src="/static/dandan-wave.png" alt="" aria-hidden="true" draggable="false">
      </button>
      <div class="ragdoll-actions" data-ragdoll-actions role="menu" hidden>
        <strong>Dandan</strong>
        <button type="button" data-ragdoll-action="pet">Pet Dandan</button>
        <button type="button" data-ragdoll-action="reminder">Trade reminder</button>
        <button type="button" data-ragdoll-action="nap">Let Dandan nap</button>
        <button type="button" data-ragdoll-action="home">Back to corner</button>
        <button type="button" data-ragdoll-action="hide">Hide</button>
      </div>
      <button class="ragdoll-restore" type="button" data-ragdoll-restore aria-label="Show Dandan" title="Show Dandan">
        <img src="/static/dandan-avatar.png" alt="" aria-hidden="true" draggable="false">
      </button>
    </div>
    <script src="/static/app.js?v=20261102-2"></script></body></html>"""
    return html.encode("utf-8")


def all_trades(filters=None, sort_by="open_date", sort_dir="desc"):
    filters = filters or {}
    where, params = ["user_id = ?"], [current_user_id()]
    if filters.get("q"):
        ticker_term = ticker_search_term(filters["q"])
        if ticker_term:
            where.append("UPPER(ticker) = ?")
            params.append(ticker_term)
        else:
            where.append("(UPPER(ticker) LIKE ? OR UPPER(sector) LIKE ? OR UPPER(notes) LIKE ?)")
            term = f"%{filters['q'].strip().upper()}%"
            params += [term, term, term]
    if filters.get("status"):
        where.append("status = ?"); params.append(filters["status"])
    if filters.get("strategy"):
        where.append("strategy = ?"); params.append(filters["strategy"])
    if filters.get("sector"):
        where.append("sector = ?"); params.append(filters["sector"])
    apply_source_filter(where, params, filters.get("source"))
    if parse_date(filters.get("date_from")):
        where.append("open_date >= ?"); params.append(filters["date_from"])
    if parse_date(filters.get("date_to")):
        where.append("open_date <= ?"); params.append(filters["date_to"])
    sql = "SELECT * FROM trades" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY open_date DESC, id DESC"
    with closing(db()) as connection:
        trades = [derived(row) for row in connection.execute(sql, params).fetchall()]
    valid_sort = {"ticker": "ticker", "sector": "sector", "strategy": "strategy", "status": "status", "source": "broker_source",
                  "open_date": "open_date", "close_date": "close_date", "expiration": "expiration",
                  "contracts": "contracts", "strike": "strike",
                  "net_pnl": "net_pnl", "trade_pl": "trade_pl_pct", "roc": "roc"}
    sort_key = valid_sort.get(sort_by, "open_date")
    reverse = sort_dir == "desc"

    def sort_value(item):
        value = item.get(sort_key)
        if value is None:
            return (1, 0)
        if sort_key in {"contracts", "strike", "net_pnl", "trade_pl_pct", "roc"}:
            return (0, float(value))
        return (0, str(value).lower())

    trades.sort(key=sort_value, reverse=reverse)
    return trades


def day_trade_as_trade(row: dict) -> dict:
    pnl = row.get("pnl", day_trade_pnl(row))
    contracts = number(row.get("contracts"), 0) or 0
    open_price = number(row.get("open_price"), 0) or 0
    capital = max(abs(open_price), abs(number(row.get("close_price"), 0) or 0)) * contracts * 100
    trade_pl_pct = pnl / capital if capital else None
    option_type = row.get("option_type") or "Option"
    open_date = row.get("open_date") or row.get("trade_date")
    close_date = row.get("close_date") or row.get("trade_date")
    return {
        "id": f'day-{row.get("id")}',
        "source": "day_trade",
        "broker_source": broker_source_for_row(row),
        "earnings_bet_id": row.get("earnings_bet_id"),
        "ticker": row.get("ticker"),
        "sector": sector_for_ticker(row.get("ticker")),
        "strategy": f"Day Trade {option_type}",
        "status": row.get("status") or "Closed",
        "open_date": open_date,
        "close_date": close_date,
        "expiration": row.get("expiration"),
        "contracts": contracts,
        "strike": number(row.get("strike")),
        "long_put_strike": None,
        "premium_in": open_price,
        "exit_premium": number(row.get("close_price"), 0),
        "stock_pnl": 0,
        "fees": number(row.get("fees"), 0) or 0,
        "capital_used": capital,
        "notes": row.get("notes"),
        "premium_pnl": pnl,
        "trade_pl_pct": trade_pl_pct,
        "net_pnl": pnl,
        "days_held": 0,
        "roc": trade_pl_pct,
        "annualized_return": None,
        "outcome": "Win" if pnl > 0 else "Loss" if pnl < 0 else "Breakeven",
        "spread_width": None,
        "max_loss": None,
    }


def other_option_pnl(row: dict) -> float:
    status = row.get("status") or "Closed"
    contracts = number(row.get("contracts"), 0) or 0
    open_price = number(row.get("open_price"), 0) or 0
    close_price = number(row.get("close_price"), 0) or 0
    fees = number(row.get("fees"), 0) or 0
    if status == "Open" and not close_price:
        return -fees
    return (close_price - open_price) * contracts * 100 - fees


def other_option_as_trade(row: dict) -> dict:
    pnl = row.get("pnl", other_option_pnl(row))
    contracts = number(row.get("contracts"), 0) or 0
    open_price = number(row.get("open_price"), 0) or 0
    capital = open_price * contracts * 100
    trade_pl_pct = pnl / capital if capital else None
    status = row.get("status") or "Closed"
    open_date = row.get("open_date") or row.get("trade_date")
    close_date = row.get("close_date") or (row.get("trade_date") if status != "Open" else None)
    opened = parse_date(open_date)
    closed = parse_date(close_date)
    held_until = closed or date.today()
    days_held = max(1, (held_until - opened).days) if opened else None
    annualized_return = trade_pl_pct * 365 / days_held if trade_pl_pct is not None and days_held and status != "Open" else None
    strategy_type = row.get("strategy_type") or "Other option"
    option_type = row.get("option_type") or ""
    description = row.get("description") or ""
    if strategy_type == "Single option":
        strategy = f"Option Buyer {option_type}".strip()
    elif strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES:
        strategy = strategy_type
    elif strategy_type == "Buy combo":
        strategy = f"Option Buyer Combo: {description or 'custom'}"
    else:
        strategy = f"Option Buyer {strategy_type}: {description or 'custom'}"
    return {
        "id": f'other-option-{row.get("id")}',
        "source": "other_option",
        "broker_source": broker_source_for_row(row),
        "earnings_bet_id": row.get("earnings_bet_id"),
        "ticker": row.get("ticker"),
        "sector": sector_for_ticker(row.get("ticker")),
        "strategy": strategy,
        "status": status,
        "open_date": open_date,
        "close_date": close_date,
        "expiration": row.get("expiration"),
        "contracts": contracts,
        "strike": number(row.get("strike")),
        "long_put_strike": None,
        "long_strike": number(row.get("long_strike")),
        "short_strike": number(row.get("short_strike")),
        "premium_in": open_price,
        "exit_premium": number(row.get("close_price"), 0),
        "stock_pnl": 0,
        "fees": number(row.get("fees"), 0) or 0,
        "capital_used": capital,
        "notes": row.get("notes"),
        "premium_pnl": pnl,
        "trade_pl_pct": trade_pl_pct,
        "net_pnl": pnl,
        "days_held": days_held,
        "roc": trade_pl_pct,
        "annualized_return": annualized_return,
        "outcome": "Win" if pnl > 0 else "Loss" if pnl < 0 else "Breakeven",
        "spread_width": None,
        "max_loss": None,
    }


def symbol_trade_records(filters=None) -> list[dict]:
    filters = filters or {}
    seller_filters = dict(filters)
    strategy_filter = filters.get("strategy", "")
    if strategy_filter in {"Option Seller", "Option Buyer", "Day Trade", "Stock"} or strategy_filter.startswith("Option Buyer") or strategy_filter.startswith("Day Trade") or strategy_filter == "Stock Sell":
        seller_filters["strategy"] = ""
    records = all_trades(seller_filters)
    day_filters = {key: filters.get(key, "") for key in ("q", "option_type", "open_side", "strategy_type", "date_from", "date_to", "expiration_from", "expiration_to", "source")}
    day_records = [day_trade_as_trade(row) for row in all_day_trades(day_filters)]
    other_records = [other_option_as_trade(row) for row in all_other_option_trades(day_filters)]
    stock_records = [stock_trade_as_trade(row) for row in all_stock_trades(day_filters)]
    if filters.get("status"):
        day_records = [row for row in day_records if row.get("status") == filters["status"]]
        other_records = [row for row in other_records if row.get("status") == filters["status"]]
        stock_records = [row for row in stock_records if row.get("status") == filters["status"]]
    if strategy_filter:
        if strategy_filter == "Option Seller":
            day_records = []
            other_records = []
            stock_records = []
        elif strategy_filter == "Option Buyer":
            records = []
            day_records = []
            stock_records = []
        elif strategy_filter == "Day Trade":
            records = []
            other_records = []
            stock_records = []
        elif strategy_filter == "Stock":
            records = []
            day_records = []
            other_records = []
        elif strategy_filter == "Option Buyer Combo":
            records = []
            day_records = []
            stock_records = []
            other_records = [row for row in other_records if "Combo" in (row.get("strategy") or "") or "combo" in (row.get("strategy") or "")]
        else:
            records = [row for row in records if row.get("strategy") == strategy_filter]
            day_records = [row for row in day_records if row.get("strategy") == strategy_filter]
            other_records = [row for row in other_records if row.get("strategy") == strategy_filter or (row.get("strategy") or "").startswith(f"{strategy_filter}:")]
            stock_records = [row for row in stock_records if row.get("strategy") == strategy_filter]
    if filters.get("sector"):
        day_records = [row for row in day_records if row.get("sector") == filters["sector"]]
        other_records = [row for row in other_records if row.get("sector") == filters["sector"]]
        stock_records = [row for row in stock_records if row.get("sector") == filters["sector"]]
    return sorted(records + day_records + other_records + stock_records, key=lambda row: (row.get("open_date") or "", str(row.get("id") or "")), reverse=True)


def filter_symbol_detail_trades(rows: list[dict], filters: dict) -> list[dict]:
    filters = filters or {}
    q = (filters.get("q") or "").strip().lower()
    status = filters.get("status") or ""
    strategy_filter = filters.get("strategy") or ""
    option_type = filters.get("option_type") or ""
    source_filter = source_filter_value(filters.get("source"))
    date_from = filters.get("date_from") if parse_date(filters.get("date_from")) else ""
    date_to = filters.get("date_to") if parse_date(filters.get("date_to")) else ""

    def row_option_type(row: dict) -> str:
        strategy = row.get("strategy") or ""
        if strategy == "Iron Condor":
            return "Call / Put"
        if "Call" in strategy or strategy in {"Covered Call", "Call Credit Spread"}:
            return "Call"
        if "Put" in strategy or strategy in {"Sell Put", "Put Credit Spread"}:
            return "Put"
        return ""

    def strategy_matches(row: dict) -> bool:
        if not strategy_filter:
            return True
        strategy = row.get("strategy") or ""
        source = row.get("source") or ""
        if strategy_filter == "Option Seller":
            return source not in {"day_trade", "other_option", "stock_trade"}
        if strategy_filter == "Option Buyer":
            return source == "other_option"
        if strategy_filter == "Day Trade":
            return source == "day_trade"
        if strategy_filter == "Stock":
            return source == "stock_trade"
        if strategy_filter == "Option Buyer Combo":
            return source == "other_option" and ("Combo" in strategy or "combo" in strategy)
        return strategy == strategy_filter or strategy.startswith(f"{strategy_filter}:")

    filtered = []
    for row in rows:
        if q:
            haystack = " ".join(str(row.get(key) or "") for key in ("strategy", "status", "notes", "open_date", "close_date", "expiration", "strike"))
            if q not in haystack.lower():
                continue
        if status and row.get("status") != status:
            continue
        if not strategy_matches(row):
            continue
        if option_type and row_option_type(row) != option_type and not (
            row.get("strategy") == "Iron Condor" and option_type in {"Call", "Put"}
        ):
            continue
        if source_filter == UNKNOWN_SOURCE_FILTER and broker_source_for_row(row):
            continue
        if source_filter not in {"", UNKNOWN_SOURCE_FILTER} and broker_source_for_row(row) != source_filter:
            continue
        open_date = row.get("open_date") or ""
        if date_from and open_date < date_from:
            continue
        if date_to and open_date > date_to:
            continue
        filtered.append(row)
    return filtered


def performance_records_for_query(query) -> tuple[list[dict], str]:
    ticker = query.get("ticker", [""])[0].strip().upper()
    if query.get("dashboard", [""])[0] == "option-buyer":
        trades = [other_option_as_trade(row) for row in all_other_option_trades()]
        return filter_trades_by_brokers(trades, broker_filter_values(query, "perf_broker")), ticker
    if query.get("dashboard", [""])[0] == "day-trades":
        trades = [day_trade_as_trade(row) for row in all_day_trades()]
        return filter_trades_by_brokers(trades, broker_filter_values(query, "perf_broker")), ticker
    if query.get("dashboard", [""])[0] == "stock-trades":
        trades = [stock_trade_as_trade(row) for row in all_stock_trades()]
        return filter_trades_by_brokers(trades, broker_filter_values(query, "perf_broker")), ticker
    if ticker:
        trades = [trade for trade in symbol_trade_records() if (trade.get("ticker") or "").upper() == ticker]
        return filter_trades_by_brokers(trades, broker_filter_values(query, "perf_broker")), ticker
    brokers, books = dashboard_filter_values(query)
    return filter_dashboard_trades(symbol_trade_records(), brokers, books), ticker


def all_holdings(sort_by="ticker", sort_dir="asc"):
    with closing(db()) as connection:
        open_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM stock_trades WHERE user_id=? AND COALESCE(status, 'Closed')='Open' ORDER BY trade_date, id",
            (current_user_id(),),
        ).fetchall()]
        legacy_prices = {
            (row["ticker"] or "").upper(): dict(row)
            for row in connection.execute("SELECT * FROM stock_holdings WHERE user_id=?", (current_user_id(),)).fetchall()
        }
    grouped = {}
    for row in open_rows:
        ticker = (row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        shares = number(row.get("shares"), 0) or 0
        if shares <= 0:
            continue
        buy_price = number(row.get("buy_price"), number(row.get("price"), 0)) or 0
        item = grouped.setdefault(
            ticker,
            {
                "id": ticker,
                "source": "stock_trades",
                "ticker": ticker,
                "sector": sector_for_ticker(ticker),
                "shares": 0.0,
                "_cost": 0.0,
                "current_price": None,
                "as_of": None,
                "notes": "Derived from open stock trades",
                "_broker_source_counts": {},
            },
        )
        item["shares"] += shares
        item["_cost"] += shares * buy_price
        broker_source = broker_source_for_row(row) or "Unknown"
        item["_broker_source_counts"][broker_source] = item["_broker_source_counts"].get(broker_source, 0) + 1
        current_price = number(row.get("current_price"))
        as_of = row.get("as_of") or row.get("updated_at") or row.get("trade_date")
        if current_price is not None and (not item.get("as_of") or str(as_of or "") >= str(item.get("as_of") or "")):
            item["current_price"] = current_price
            item["as_of"] = as_of
    holdings = []
    for ticker, item in grouped.items():
        if item["current_price"] is None and ticker in legacy_prices:
            item["current_price"] = number(legacy_prices[ticker].get("current_price"))
            item["as_of"] = legacy_prices[ticker].get("as_of")
        item["avg_cost"] = item["_cost"] / item["shares"] if item["shares"] else None
        known_sources = [source for source in item.get("_broker_source_counts", {}) if source != "Unknown"]
        if len(known_sources) == 1:
            item["broker_source"] = known_sources[0]
        item.pop("_cost", None)
        holdings.append(holding_derived(item))
    for ticker, row in legacy_prices.items():
        if ticker not in grouped:
            holdings.append(holding_derived(row))
    total_market_value = sum(holding.get("market_value") or 0 for holding in holdings)
    for holding in holdings:
        holding["allocation_pct"] = (holding.get("market_value") or 0) / total_market_value if total_market_value else None
    valid_sort = {"ticker", "source", "sector", "shares", "avg_cost", "current_price", "cost_basis", "market_value", "allocation_pct", "unrealized_pnl", "pnl_pct", "as_of"}
    sort_key = sort_by if sort_by in valid_sort else "ticker"
    reverse = sort_dir == "desc"

    def sort_value(item):
        value = item.get(sort_key)
        if value is None:
            return (1, 0)
        if sort_key in {"shares", "avg_cost", "current_price", "cost_basis", "market_value", "allocation_pct", "unrealized_pnl", "pnl_pct"}:
            return (0, float(value))
        return (0, str(value).lower())

    holdings.sort(key=sort_value, reverse=reverse)
    return holdings


def fetch_latest_equity_price(ticker: str) -> tuple[float | None, str | None]:
    symbol = (ticker or "").strip().upper().replace(".", "-")
    if symbol == "BTCUSD":
        symbol = "BTC-USD"
    if not symbol:
        return None, "missing ticker"
    if symbol in PRIVATE_MARKET_SYMBOLS:
        return None, "private symbol has no public quote"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=1d&interval=1m"
    request = urllib.request.Request(url, headers={"User-Agent": "options-seller-tracker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return None, str(exc)
    try:
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        price = meta.get("postMarketPrice")
        if price is None:
            price = meta.get("preMarketPrice")
        if price is None:
            price = meta.get("regularMarketPrice")
        if price is None:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            price = next((item for item in reversed(closes) if item is not None), None)
        return (float(price), None) if price is not None else (None, "no price returned")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return None, f"unexpected quote response: {exc}"


def fetch_market_quote(symbol: str, label: str | None = None) -> dict:
    ticker = (symbol or "").strip().upper().replace(".", "-")
    if ticker == "BTCUSD":
        ticker = "BTC-USD"
    now = time.time()
    with MARKET_QUOTE_CACHE_LOCK:
        cached = MARKET_QUOTE_CACHE.get(ticker)
        if cached and now - cached.get("at", 0) < MARKET_QUOTE_CACHE_SECONDS:
            return dict(cached["quote"])
    quote_data = {
        "label": label or ticker,
        "symbol": ticker,
        "price": None,
        "change": None,
        "change_pct": None,
        "session": "",
        "error": None,
    }
    if not ticker:
        quote_data["error"] = "missing ticker"
        return quote_data
    if ticker in PRIVATE_MARKET_SYMBOLS:
        quote_data["error"] = "private symbol has no public quote"
        return quote_data
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?range=1d&interval=1m"
    request = urllib.request.Request(url, headers={"User-Agent": "options-seller-tracker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        price = meta.get("postMarketPrice")
        session = "After" if price is not None else ""
        if price is None:
            price = meta.get("preMarketPrice")
            session = "Pre" if price is not None else ""
        if price is None:
            price = meta.get("regularMarketPrice")
            session = "Live" if price is not None else ""
        previous = meta.get("regularMarketPreviousClose") or meta.get("chartPreviousClose")
        if price is None:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            price = next((item for item in reversed(closes) if item is not None), None)
        if previous in {None, 0}:
            previous = meta.get("previousClose")
        if price is not None:
            quote_data["price"] = float(price)
            quote_data["session"] = session
        if quote_data["price"] is not None and previous not in {None, 0}:
            quote_data["change"] = quote_data["price"] - float(previous)
            quote_data["change_pct"] = quote_data["change"] / float(previous)
    except Exception as exc:
        quote_data["error"] = str(exc)
    with MARKET_QUOTE_CACHE_LOCK:
        MARKET_QUOTE_CACHE[ticker] = {"at": now, "quote": dict(quote_data)}
    return quote_data


def tracked_symbols() -> set[str]:
    symbols = {holding.get("ticker", "").upper() for holding in all_holdings()}
    symbols.update(trade.get("ticker", "").upper() for trade in all_trades() if trade.get("status") == "Open")
    return {symbol for symbol in symbols if symbol}


def earnings_lookup_symbols(extra_symbols: set[str] | None = None) -> list[str]:
    symbols = []
    seen = set()

    def add(symbol: str) -> None:
        ticker = (symbol or "").strip().upper()
        if not ticker or ticker in seen or ticker.startswith("^") or "=" in ticker or "-" in ticker:
            return
        seen.add(ticker)
        symbols.append(ticker)

    for symbol in tracked_symbols():
        add(symbol)
    for symbol in EARNINGS_SYMBOL_FALLBACKS:
        add(symbol)
    trade_counts = {}
    for trade in all_trades():
        ticker = (trade.get("ticker") or "").strip().upper()
        if ticker:
            trade_counts[ticker] = trade_counts.get(ticker, 0) + 1
    for ticker, _count in sorted(trade_counts.items(), key=lambda item: (-item[1], item[0])):
        add(ticker)
    for symbol in extra_symbols or set():
        add(symbol)
    return symbols[:max(EARNINGS_SYMBOL_LOOKUP_LIMIT, 0)]


def fetch_finnhub_json(path: str, params: dict, timeout: int = 12) -> tuple[dict | list | None, str | None]:
    if not FINNHUB_API_KEY:
        return None, "Set FINNHUB_API_KEY to enable Finnhub data."
    params = dict(params)
    params["token"] = FINNHUB_API_KEY
    url = f"https://finnhub.io/api/v1/{path}?{urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "options-seller-tracker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except Exception as exc:
        return None, str(exc)


def fetch_finnhub_market_cap(symbol: str) -> tuple[float | None, str | None]:
    ticker = (symbol or "").strip().upper()
    if not ticker:
        return None, "missing symbol"
    now = time.time()
    with EARNINGS_CACHE_LOCK:
        cached = EARNINGS_PROFILE_CACHE.get(ticker)
        if cached and now - cached.get("at", 0) < EARNINGS_CACHE_SECONDS:
            return cached.get("market_cap"), cached.get("error")
    payload, error = fetch_finnhub_json("stock/profile2", {"symbol": ticker})
    market_cap = None
    if isinstance(payload, dict):
        try:
            value = payload.get("marketCapitalization")
            if value is not None:
                market_cap = float(value) * 1_000_000
        except (TypeError, ValueError):
            market_cap = None
    if market_cap is None and error is None:
        error = "market cap unavailable"
    with EARNINGS_CACHE_LOCK:
        EARNINGS_PROFILE_CACHE[ticker] = {"at": now, "market_cap": market_cap, "error": error}
    return market_cap, error


def finnhub_feature_error(error: str | None, feature: str = "Finnhub data") -> str | None:
    if not error:
        return None
    lowered = error.lower()
    if "expecting value" in lowered or "json" in lowered:
        return f"{feature} did not return usable data for this symbol."
    if "403" in error or "forbidden" in lowered:
        return f"{feature} requires a Finnhub plan with this endpoint."
    if "429" in error or "too many" in lowered:
        return f"{feature} is rate limited right now."
    return error


def fetch_symbol_intel(ticker: str, force: bool = False) -> dict:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {}
    now = time.time()
    with SYMBOL_INTEL_CACHE_LOCK:
        cached = SYMBOL_INTEL_CACHE.get(symbol)
        if cached and not force and now - cached.get("at", 0) < SYMBOL_INTEL_CACHE_SECONDS:
            return dict(cached["data"])

    today = date.today()
    start = today - timedelta(days=180)
    requests = {
        "recommendation": ("stock/recommendation", {"symbol": symbol}, "Analyst recommendations"),
        "price_target": ("stock/price-target", {"symbol": symbol}, "Price targets"),
        "insider": ("stock/insider-transactions", {"symbol": symbol, "from": start.isoformat(), "to": today.isoformat()}, "Insider transactions"),
        "institutional": ("stock/institutional-ownership", {"symbol": symbol, "from": start.isoformat(), "to": today.isoformat()}, "Institutional ownership"),
    }
    data = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_finnhub_json, path, params, 8): key for key, (path, params, _label) in requests.items()}
        for future in as_completed(futures):
            key = futures[future]
            label = requests[key][2]
            try:
                payload, error = future.result()
            except Exception as exc:
                payload, error = None, str(exc)
            data[key] = {"payload": payload, "error": finnhub_feature_error(error, label)}
    with SYMBOL_INTEL_CACHE_LOCK:
        SYMBOL_INTEL_CACHE[symbol] = {"at": now, "data": dict(data)}
    return data


def symbol_intel_panel(ticker: str, force: bool = False) -> str:
    symbol = (ticker or "").strip().upper()
    if not force:
        now = time.time()
        with SYMBOL_INTEL_CACHE_LOCK:
            cached = SYMBOL_INTEL_CACHE.get(symbol)
        if not cached or now - cached.get("at", 0) >= SYMBOL_INTEL_CACHE_SECONDS:
            return f'''<section class="panel symbol-intel-panel">
      <div class="panel-head"><h2>Symbol intelligence</h2><span>load on demand</span></div>
      <div class="empty">Market intelligence is paused so this page opens quickly. <a href="/symbol/{quote(symbol)}?refresh=1">Refresh intelligence</a></div>
    </section>'''
    intel = fetch_symbol_intel(ticker, force=force)
    recommendation = intel.get("recommendation", {})
    target = intel.get("price_target", {})
    insider = intel.get("insider", {})
    institutional = intel.get("institutional", {})

    rec_rows = recommendation.get("payload") if isinstance(recommendation.get("payload"), list) else []
    latest_rec = rec_rows[0] if rec_rows else {}
    rec_error = recommendation.get("error")
    strong_buy = number(latest_rec.get("strongBuy"), 0) or 0
    buy_count = number(latest_rec.get("buy"), 0) or 0
    hold_count = number(latest_rec.get("hold"), 0) or 0
    sell_count = (number(latest_rec.get("sell"), 0) or 0) + (number(latest_rec.get("strongSell"), 0) or 0)
    total_rec = strong_buy + buy_count + hold_count + sell_count
    bullish_pct = (strong_buy + buy_count) / total_rec * 100 if total_rec else 0
    hold_pct = hold_count / total_rec * 100 if total_rec else 0
    sell_pct = sell_count / total_rec * 100 if total_rec else 0
    rec_body = (
        f'''<div class="analyst-bar" aria-label="Analyst recommendation mix">
          <span class="buy" style="width:{bullish_pct:.1f}%"></span>
          <span class="hold" style="width:{hold_pct:.1f}%"></span>
          <span class="sell" style="width:{sell_pct:.1f}%"></span>
        </div>
        <div class="analyst-bar-legend">
          <span><i class="buy"></i><b>{num(strong_buy + buy_count)}</b>Buy</span>
          <span><i class="hold"></i><b>{num(hold_count)}</b>Hold</span>
          <span><i class="sell"></i><b>{num(sell_count)}</b>Sell</span>
        </div>
        <small>{escape(str(latest_rec.get("period") or "latest"))}</small>'''
        if latest_rec else f'<div class="muted-row">{escape(rec_error or "No analyst recommendation data.")}</div>'
    )

    target_payload = target.get("payload") if isinstance(target.get("payload"), dict) else {}
    target_error = target.get("error")
    target_body = (
        f'''<div class="intel-counts price-targets">
          <span><b>{money(number(target_payload.get("targetLow")))}</b>Low</span>
          <span><b>{money(number(target_payload.get("targetMean")))}</b>Mean</span>
          <span><b>{money(number(target_payload.get("targetHigh")))}</b>High</span>
        </div><small>{escape(str(target_payload.get("lastUpdated") or "latest"))}</small>'''
        if any(target_payload.get(key) is not None for key in ("targetLow", "targetMean", "targetHigh")) else f'<div class="muted-row">{escape(target_error or "No price target data.")}</div>'
    )

    insider_payload = insider.get("payload")
    insider_rows = []
    if isinstance(insider_payload, dict):
        rows = insider_payload.get("data") or insider_payload.get("transactions") or []
    elif isinstance(insider_payload, list):
        rows = insider_payload
    else:
        rows = []
    for row in rows[:6]:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("personName") or row.get("ownerName") or "Insider"
        when = row.get("transactionDate") or row.get("filingDate") or row.get("date") or "-"
        code = row.get("transactionCode") or row.get("transactionType") or row.get("changeType") or "-"
        shares = number(row.get("change") if row.get("change") is not None else row.get("share"))
        price = number(row.get("transactionPrice") or row.get("price"))
        insider_rows.append(f'<tr><td>{escape(str(when))}</td><td>{escape(str(name))}</td><td>{escape(str(code))}</td><td>{num(shares)}</td><td>{money(price)}</td></tr>')
    insider_body = (
        f'<div class="table-wrap"><table><thead><tr><th>Date</th><th>Name</th><th>Code</th><th>Shares</th><th>Price</th></tr></thead><tbody>{"".join(insider_rows)}</tbody></table></div>'
        if insider_rows else f'<div class="muted-row">{escape(insider.get("error") or "No recent insider transactions.")}</div>'
    )

    institutional_payload = institutional.get("payload")
    if isinstance(institutional_payload, dict):
        inst_rows_source = institutional_payload.get("ownership") or institutional_payload.get("data") or []
    elif isinstance(institutional_payload, list):
        inst_rows_source = institutional_payload
    else:
        inst_rows_source = []
    inst_rows = []
    for row in inst_rows_source[:6]:
        if not isinstance(row, dict):
            continue
        holder = row.get("name") or row.get("holder") or row.get("institution") or "Institution"
        report = row.get("reportDate") or row.get("date") or "-"
        shares = number(row.get("share") or row.get("shares"))
        change = number(row.get("change"))
        pct_value = number(row.get("portfolioPercent") or row.get("ownershipPercent"))
        inst_rows.append(f'<tr><td>{escape(str(report))}</td><td>{escape(str(holder))}</td><td>{num(shares)}</td><td>{num(change)}</td><td>{pct(pct_value / 100 if pct_value and pct_value > 1 else pct_value)}</td></tr>')
    inst_body = (
        f'<div class="table-wrap"><table><thead><tr><th>Report</th><th>Holder</th><th>Shares</th><th>Change</th><th>Weight</th></tr></thead><tbody>{"".join(inst_rows)}</tbody></table></div>'
        if inst_rows else f'<div class="muted-row">{escape(institutional.get("error") or "No recent 13F / institutional data.")}</div>'
    )

    return f'''<section class="panel symbol-intel-panel">
      <div class="panel-head"><h2>Insider / 13F / Analyst Changes</h2><span>Finnhub supplemental data</span></div>
      <div class="symbol-intel-grid">
        <section class="intel-card"><h3>Analyst Snapshot</h3>{rec_body}</section>
        <section class="intel-card"><h3>Price Targets</h3>{target_body}</section>
        <section class="intel-card wide"><h3>Insider Transactions</h3>{insider_body}</section>
        <section class="intel-card wide"><h3>Institutional / 13F</h3>{inst_body}</section>
      </div>
    </section>'''


def normalize_earnings_item(item: dict, tracked: set[str], skip_market_cap: bool = False) -> dict | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    report_date = str(item.get("date") or "").strip()
    if not symbol or not parse_date(report_date):
        return None
    hour = str(item.get("hour") or "").strip().lower()
    hour_label = {"bmo": "BMO", "amc": "AMC", "dmh": "During market"}.get(hour, hour.upper() or "TBD")
    market_cap, cap_error = (None, None) if skip_market_cap else fetch_finnhub_market_cap(symbol)
    if market_cap is not None and market_cap < EARNINGS_MIN_MARKET_CAP and symbol not in tracked:
        return None
    if market_cap is None and symbol not in tracked and not skip_market_cap:
        return None
    return {
        "symbol": symbol,
        "date": report_date,
        "hour": hour_label,
        "eps_estimate": number(item.get("epsEstimate")),
        "eps_actual": number(item.get("epsActual")),
        "revenue_estimate": number(item.get("revenueEstimate")),
        "revenue_actual": number(item.get("revenueActual")),
        "quarter": item.get("quarter"),
        "year": item.get("year"),
        "market_cap": market_cap,
        "cap_error": cap_error,
        "tracked": symbol in tracked,
    }


def has_earnings_estimates(item: dict) -> bool:
    return item.get("eps_estimate") is not None and item.get("revenue_estimate") is not None


def compact_revenue(value) -> str:
    amount = number(value)
    if amount is None:
        return "-"
    sign = "-" if amount < 0 else ""
    amount = abs(amount) * (USD_CNY_RATE if current_currency() == "rmb" else 1)
    symbol = RMB_SYMBOL if current_currency() == "rmb" else "$"
    if amount >= 1_000_000_000_000:
        return f"{sign}{symbol}{amount / 1_000_000_000_000:.2f}T"
    if amount >= 1_000_000_000:
        return f"{sign}{symbol}{amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"{sign}{symbol}{amount / 1_000_000:.1f}M"
    return f"{sign}{symbol}{amount:,.0f}"


def filter_large_cap_earnings(items: list[dict], trusted_symbols: set[str]) -> list[dict]:
    if not items:
        return []
    symbols = sorted({item["symbol"] for item in items if item.get("symbol") and item["symbol"] not in trusted_symbols})
    market_caps = {}
    if symbols:
        with ThreadPoolExecutor(max_workers=min(6, len(symbols))) as executor:
            futures = {executor.submit(fetch_finnhub_market_cap, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    market_cap, _error = future.result()
                except Exception:
                    market_cap = None
                market_caps[symbol] = market_cap
    filtered = []
    for item in items:
        symbol = item.get("symbol")
        market_cap = item.get("market_cap")
        if symbol in trusted_symbols:
            filtered.append(item)
            continue
        if market_cap is None:
            market_cap = market_caps.get(symbol)
            item["market_cap"] = market_cap
        if market_cap is not None and market_cap >= EARNINGS_MIN_MARKET_CAP:
            filtered.append(item)
    return filtered


def finnhub_earnings_rows(params: dict) -> tuple[list[dict], str | None]:
    payload, error = fetch_finnhub_json("calendar/earnings", params, timeout=5)
    rows = payload.get("earningsCalendar") if isinstance(payload, dict) else []
    return (rows if isinstance(rows, list) else []), error


def fetch_earnings_calendar(start: date, end: date, scope="all", force: bool = False) -> tuple[list[dict], str | None]:
    tracked = tracked_symbols()
    lookup_symbols = earnings_lookup_symbols()
    lookup_symbol_set = set(lookup_symbols)
    cache_key = (start.isoformat(), end.isoformat(), scope, current_user_id(), EARNINGS_MIN_MARKET_CAP, tuple(lookup_symbols))
    now = time.time()
    with EARNINGS_CACHE_LOCK:
        cached = EARNINGS_CACHE.get(cache_key)
        if not force and cached and now - cached.get("at", 0) < EARNINGS_CACHE_SECONDS:
            return list(cached.get("items") or []), cached.get("error")
    rows, error = finnhub_earnings_rows({"from": start.isoformat(), "to": end.isoformat()})
    errors = [error] if error else []
    seen = set()
    items = []

    def add_rows(source_rows: list[dict], skip_market_cap: bool = False) -> None:
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            normalized = normalize_earnings_item(row, tracked, skip_market_cap=skip_market_cap)
            if not normalized:
                continue
            if normalized["symbol"] not in lookup_symbol_set:
                continue
            if not has_earnings_estimates(normalized):
                continue
            if scope == "tracked" and not normalized["tracked"]:
                continue
            key = (normalized["symbol"], normalized["date"], normalized["hour"])
            if key in seen:
                continue
            seen.add(key)
            items.append(normalized)

    add_rows(rows, skip_market_cap=True)
    if lookup_symbols:
        with ThreadPoolExecutor(max_workers=min(8, len(lookup_symbols))) as executor:
            futures = {
                executor.submit(
                    finnhub_earnings_rows,
                    {"from": start.isoformat(), "to": end.isoformat(), "symbol": symbol},
                ): symbol
                for symbol in lookup_symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    symbol_rows, symbol_error = future.result()
                except Exception as exc:
                    symbol_rows, symbol_error = [], str(exc)
                if symbol_error:
                    errors.append(f"{symbol}: {symbol_error}")
                add_rows(symbol_rows, skip_market_cap=True)
    items = filter_large_cap_earnings(items, set(EARNINGS_SYMBOL_FALLBACKS) | tracked)
    items.sort(key=lambda item: (item["date"], item["hour"], item["symbol"]))
    error = errors[0] if errors and not items else None
    if error is None and not items:
        error = "No large-cap earnings found in this range."
    with EARNINGS_CACHE_LOCK:
        cached = EARNINGS_CACHE.get(cache_key)
        if error and not items and cached and cached.get("items"):
            return list(cached.get("items") or []), error
    with EARNINGS_CACHE_LOCK:
        EARNINGS_CACHE[cache_key] = {"at": now, "items": items, "error": error}
    return items, error


def next_earnings_for_symbol(ticker: str, allow_fetch: bool = True) -> tuple[dict | None, str | None]:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return None, "missing symbol"
    today = date.today()
    end = today + timedelta(days=180)
    cache_key = ("next-earnings", symbol, today.isoformat(), end.isoformat())
    now = time.time()
    with EARNINGS_CACHE_LOCK:
        cached = EARNINGS_CACHE.get(cache_key)
        if cached and now - cached.get("at", 0) < EARNINGS_CACHE_SECONDS:
            return cached.get("item"), cached.get("error")
    if not allow_fetch:
        return None, "No cached earnings date."
    rows, error = finnhub_earnings_rows({"from": today.isoformat(), "to": end.isoformat(), "symbol": symbol})
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = normalize_earnings_item(row, {symbol}, skip_market_cap=True)
        if not normalized:
            continue
        report_date = parse_date(normalized.get("date"))
        if report_date and report_date >= today:
            items.append(normalized)
    items.sort(key=lambda item: (item.get("date") or "", item.get("hour") or ""))
    item = items[0] if items else None
    if error and ("403" in error or "forbidden" in error.lower()):
        error = "Earnings date requires Finnhub access."
    elif error is None and item is None:
        error = "No upcoming earnings date found."
    with EARNINGS_CACHE_LOCK:
        EARNINGS_CACHE[cache_key] = {"at": now, "item": item, "error": error if item is None else None}
    return item, error if item is None else None


def next_earnings_label(ticker: str) -> str:
    item, _error = next_earnings_for_symbol(ticker, allow_fetch=False)
    if not item:
        return "-"
    report_date = parse_date(item.get("date"))
    date_label = report_date.strftime("%b %d") if report_date else item.get("date") or "-"
    hour = item.get("hour") or "TBD"
    return f"{date_label} {hour}"


def format_event_time(value) -> str:
    if value in {None, ""}:
        return "TBD"
    if isinstance(value, (int, float)):
        event_dt = datetime.fromtimestamp(value, timezone.utc)
    else:
        text = str(value).strip().replace("Z", "+00:00")
        event_dt = None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                event_dt = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
        if event_dt is None:
            try:
                event_dt = datetime.fromisoformat(text)
            except ValueError:
                return str(value)
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
    try:
        local_dt = event_dt.astimezone(ZoneInfo(LOCAL_TIMEZONE))
        return f'{local_dt.strftime("%m/%d %H:%M")} {LOCAL_TIME_LABEL}'
    except ZoneInfoNotFoundError:
        return event_dt.strftime("%m/%d %H:%M UTC")


def is_red_economic_event(item: dict) -> bool:
    joined = " ".join(str(item.get(key, "")) for key in ("event", "name", "title", "indicator", "impact", "importance")).lower()
    impact = str(item.get("impact") or item.get("importance") or item.get("level") or "").lower()
    numeric_impact = number(item.get("impact") or item.get("importance") or item.get("level"))
    high_impact = impact in {"high", "red", "3", "important"} or numeric_impact == 3
    tracked_term = any(term in joined for term in ECONOMIC_EVENT_TERMS)
    return high_impact or tracked_term


def normalize_economic_event(item: dict) -> dict | None:
    name = str(item.get("event") or item.get("name") or item.get("title") or item.get("indicator") or "").strip()
    country = str(item.get("country") or item.get("region") or "").strip()
    if not name:
        return None
    if country and country.upper() not in {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"}:
        return None
    if not is_red_economic_event(item):
        return None
    impact = str(item.get("impact") or item.get("importance") or "High").title()
    raw_time = item.get("time") or item.get("datetime") or item.get("date")
    event_date = str(item.get("date") or raw_time or "").split("T")[0].split(" ")[0]
    if isinstance(raw_time, (int, float)) and not item.get("date"):
        try:
            event_date = datetime.fromtimestamp(raw_time, timezone.utc).astimezone(ZoneInfo(LOCAL_TIMEZONE)).date().isoformat()
        except ZoneInfoNotFoundError:
            event_date = datetime.fromtimestamp(raw_time, timezone.utc).date().isoformat()
    return {
        "date": event_date,
        "time": format_event_time(raw_time),
        "name": name,
        "country": country or "US",
        "impact": "High" if impact in {"3", "Red"} else impact,
        "actual": item.get("actual"),
        "estimate": item.get("estimate", item.get("forecast")),
        "previous": item.get("prev", item.get("previous")),
        "unit": item.get("unit") or "",
    }


def fetch_economic_calendar(start: date, end: date) -> tuple[list[dict], str | None]:
    cache_key = (start.isoformat(), end.isoformat())
    now = time.time()
    with ECONOMIC_CACHE_LOCK:
        cached = ECONOMIC_CACHE.get(cache_key)
        if cached and now - cached.get("at", 0) < ECONOMIC_CACHE_SECONDS:
            return list(cached.get("items") or []), cached.get("error")
    payload, error = fetch_finnhub_json("calendar/economic", {"from": start.isoformat(), "to": end.isoformat()})
    rows = []
    if isinstance(payload, dict):
        for key in ("economicCalendar", "calendar", "data", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
    elif isinstance(payload, list):
        rows = payload
    items = []
    for row in rows:
        if isinstance(row, dict):
            normalized = normalize_economic_event(row)
            if normalized:
                items.append(normalized)
    items.sort(key=lambda item: (item.get("date") or "", item.get("time") or "", item.get("name") or ""))
    if error is None and not items:
        error = "No high-impact US macro events found in this range."
    if error and ("403" in error or "forbidden" in error.lower()):
        error = "Economic calendar requires Finnhub premium access."
    with ECONOMIC_CACHE_LOCK:
        ECONOMIC_CACHE[cache_key] = {"at": now, "items": items, "error": error}
    return items, error


def compact_market_cap(value) -> str:
    if value is None:
        return "-"
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    return f"${value / 1_000_000_000:.1f}B"


def market_tape_symbols() -> list[tuple[str, str]]:
    symbols = list(MARKET_TAPE_BASE_SYMBOLS)
    seen = {symbol for _, symbol in symbols}
    for holding in all_holdings():
        ticker = (holding.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            symbols.append((ticker, ticker))
            seen.add(ticker)
    return symbols


def watchlist_heatmap_symbols() -> list[tuple[str, str, str]]:
    symbols = []
    seen = set()

    def add(label: str, symbol: str, source: str) -> None:
        normalized = (symbol or "").strip().upper()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        symbols.append((label, normalized, source))

    for label, symbol in MARKET_TAPE_BASE_SYMBOLS:
        normalized = (symbol or "").strip().upper()
        if normalized in {"BTC-USD", "^GSPC", "^IXIC", "CL=F"}:
            continue
        add(label, symbol, "Core")
    for holding in all_holdings():
        ticker = (holding.get("ticker") or "").strip().upper()
        add(ticker, ticker, "Holding")
    trade_counts = {}
    for trade in all_trades():
        ticker = (trade.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        if trade.get("status") == "Open":
            add(ticker, ticker, "Open")
        trade_counts[ticker] = trade_counts.get(ticker, 0) + 1
    for ticker, _count in sorted(trade_counts.items(), key=lambda item: (-item[1], item[0]))[:12]:
        add(ticker, ticker, "Frequent")
    return symbols[:28]


def fetch_support_resistance(symbol: str) -> dict:
    ticker = (symbol or "").strip().upper().replace(".", "-")
    now = time.time()
    with SUPPORT_RESISTANCE_CACHE_LOCK:
        cached = SUPPORT_RESISTANCE_CACHE.get(ticker)
        if cached and now - cached.get("at", 0) < SUPPORT_RESISTANCE_CACHE_SECONDS:
            return dict(cached["data"])
    data = {"low_20d": None, "high_20d": None, "range_position": None, "error": None}
    if not ticker or ticker in PRIVATE_MARKET_SYMBOLS:
        data["error"] = "no public chart"
        return data
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?range=3mo&interval=1d"
    request = urllib.request.Request(url, headers={"User-Agent": "options-seller-tracker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        quote_rows = result.get("indicators", {}).get("quote", [{}])[0]
        highs = [float(value) for value in quote_rows.get("high", [])[-20:] if value is not None]
        lows = [float(value) for value in quote_rows.get("low", [])[-20:] if value is not None]
        closes = [float(value) for value in quote_rows.get("close", [])[-20:] if value is not None]
        if highs and lows:
            high = max(highs)
            low = min(lows)
            latest = closes[-1] if closes else None
            data["high_20d"] = high
            data["low_20d"] = low
            if latest is not None and high > low:
                data["range_position"] = min(max((latest - low) / (high - low), 0), 1)
    except Exception as exc:
        data["error"] = str(exc)
    with SUPPORT_RESISTANCE_CACHE_LOCK:
        SUPPORT_RESISTANCE_CACHE[ticker] = {"at": now, "data": dict(data)}
    return data


def upcoming_earnings_map(symbols: set[str]) -> dict[str, dict]:
    if not FINNHUB_API_KEY or not symbols:
        return {}
    items, _error = fetch_earnings_calendar(date.today(), date.today() + timedelta(days=90), "all")
    result = {}
    for item in items:
        symbol = item.get("symbol")
        if symbol in symbols and symbol not in result:
            result[symbol] = item
    return result


def heatmap_cards_html(force=False) -> str:
    rows = watchlist_heatmap_symbols()
    earnings = upcoming_earnings_map({symbol for _label, symbol, _source in rows})
    cards = []
    for label, symbol, source in rows:
        quote_data = fetch_market_quote(symbol, label)
        support = fetch_support_resistance(symbol)
        price = quote_data.get("price")
        change_pct = quote_data.get("change_pct")
        change = quote_data.get("change")
        tone = "neutral"
        if change_pct is not None:
            tone = "gain" if change_pct >= 0 else "loss"
        heat = min(abs(change_pct or 0) / 0.05, 1)
        position = support.get("range_position")
        low = support.get("low_20d")
        high = support.get("high_20d")
        low_distance = (price - low) / low if price is not None and low else None
        high_distance = (price - high) / high if price is not None and high else None
        next_earnings = earnings.get(symbol)
        earnings_text = next_earnings["date"] if next_earnings else "N/A"
        session = quote_data.get("session") or "Live"
        price_text = money(price) if price is not None else "N/A"
        change_text = f'{change:+.2f} {change_pct:+.2%}' if change is not None and change_pct is not None else "N/A"
        range_text = "N/A"
        if position is not None and low is not None and high is not None:
            range_text = f'{position:.0%} of 20D range'
        cards.append(f'''<article class="heatmap-card {tone}" style="--heat:{heat:.2f}">
          <div class="heatmap-card-top"><span>{escape(source)}</span><small>{escape(session)}</small></div>
          <h3><a href="/symbol/{quote(symbol)}">{escape(label)}</a></h3>
          <strong>{price_text}</strong>
          <b class="{tone}">{escape(change_text)}</b>
          <div class="heatmap-mini">
            <span>IV <em>N/A</em></span>
            <span>Earnings <em>{escape(earnings_text)}</em></span>
            <span>20D <em>{escape(range_text)}</em></span>
            <span>Low <em>{pct(low_distance)}</em></span>
            <span>High <em>{pct(high_distance)}</em></span>
            <span>Sector <em>{escape(sector_for_ticker(symbol))}</em></span>
          </div>
        </article>''')
    return "".join(cards) or '<div class="empty">No watchlist symbols yet.</div>'


def ticker_tape_html() -> str:
    items = []
    for label, symbol in market_tape_symbols():
        quote_data = fetch_market_quote(symbol, label)
        price = quote_data.get("price")
        change = quote_data.get("change")
        change_pct = quote_data.get("change_pct")
        if price is None:
            items.append(
                f'<span class="ticker-item muted"><b>{escape(label)}</b><span>N/A</span></span>'
            )
            continue
        tone = "up" if (change or 0) >= 0 else "down"
        change_text = ""
        if change is not None and change_pct is not None:
            change_text = f'<em class="{tone}">{change:+.2f} {change_pct:+.2%}</em>'
        session_text = f'<small>{escape(quote_data.get("session") or "")}</small>' if quote_data.get("session") else ""
        items.append(
            f'<span class="ticker-item"><b>{escape(label)}</b>{session_text}<span>{money(price)}</span>{change_text}</span>'
        )
    if not items:
        items.append('<span class="ticker-item muted"><b>No positions</b><span>Add holdings to track prices</span></span>')
    html = "".join(items)
    return f'<div class="ticker-track">{html}{html}</div>'


def refresh_holding_prices(user_id=None) -> tuple[int, list[str]]:
    user_id = user_id or current_user_id()
    with closing(db()) as connection:
        symbols = [
            row["ticker"].upper()
            for row in connection.execute(
                """
                SELECT DISTINCT UPPER(ticker) AS ticker
                FROM stock_trades
                WHERE user_id=?
                  AND COALESCE(status, 'Closed')='Open'
                  AND COALESCE(notes, '') NOT LIKE 'Synced from Robinhood%'
                """,
                (user_id,),
            ).fetchall()
            if row["ticker"]
        ]
    updated = 0
    errors = []
    today = date.today().isoformat()
    for ticker in symbols:
        price, error = fetch_latest_equity_price(ticker)
        if price is None:
            errors.append(f"{ticker}: {error or 'unknown error'}")
            continue
        with closing(db()) as connection:
            cursor = connection.execute(
                """
                UPDATE stock_trades
                SET current_price=?, as_of=?, updated_at=CURRENT_TIMESTAMP
                WHERE UPPER(ticker)=?
                  AND user_id=?
                  AND COALESCE(status, 'Closed')='Open'
                  AND COALESCE(notes, '') NOT LIKE 'Synced from Robinhood%'
                """,
                (price, today, ticker, user_id),
            )
            connection.execute(
                """
                UPDATE stock_holdings
                SET current_price=?, as_of=?, updated_at=CURRENT_TIMESTAMP
                WHERE UPPER(ticker)=?
                  AND user_id=?
                  AND COALESCE(notes, '') NOT LIKE 'Synced from Robinhood%'
                """,
                (price, today, ticker, user_id),
            )
            connection.commit()
        updated += cursor.rowcount
    return updated, errors


def refresh_symbol_price(ticker: str) -> tuple[float | None, int, str | None]:
    symbol = (ticker or "").strip().upper()
    price, error = fetch_latest_equity_price(symbol)
    if price is None:
        return None, 0, error
    today = date.today().isoformat()
    with closing(db()) as connection:
        trade_cursor = connection.execute(
            "UPDATE stock_trades SET current_price=?, as_of=?, updated_at=CURRENT_TIMESTAMP WHERE UPPER(ticker)=? AND user_id=? AND COALESCE(status, 'Closed')='Open'",
            (price, today, symbol, current_user_id()),
        )
        holding_cursor = connection.execute(
            "UPDATE stock_holdings SET current_price=?, as_of=?, updated_at=CURRENT_TIMESTAMP WHERE UPPER(ticker)=? AND user_id=?",
            (price, today, symbol, current_user_id()),
        )
        connection.commit()
        return price, trade_cursor.rowcount + holding_cursor.rowcount, None


def parse_refresh_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = (value or "00:00").split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (TypeError, ValueError):
        pass
    return 0, 0


def seconds_until_next_refresh(now=None, refresh_time=None) -> float:
    now = now or datetime.now()
    hour, minute = parse_refresh_time(refresh_time or PRICE_REFRESH_TIME)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max((target - now).total_seconds(), 1)


def auto_refresh_prices_loop() -> None:
    print(f"Automatic holding price refresh is scheduled daily at {PRICE_REFRESH_TIME}.")
    while True:
        time.sleep(seconds_until_next_refresh())
        try:
            updated = 0
            errors = []
            for user_id in all_user_ids():
                user_updated, user_errors = refresh_holding_prices(user_id)
                updated += user_updated
                errors.extend(user_errors)
            message = f"Automatic holding price refresh updated {updated} rows"
            if errors:
                message += f"; {len(errors)} failed"
            print(message)
        except Exception as exc:
            print(f"Automatic holding price refresh failed: {exc}")


def start_auto_refresh_prices() -> None:
    if not AUTO_REFRESH_PRICES:
        return
    thread = threading.Thread(target=auto_refresh_prices_loop, name="holding-price-refresh", daemon=True)
    thread.start()


def auto_refresh_portfolio_loop() -> None:
    print(f"Automatic portfolio refresh is scheduled daily at {PORTFOLIO_REFRESH_TIME}.")
    while True:
        time.sleep(seconds_until_next_refresh(refresh_time=PORTFOLIO_REFRESH_TIME))
        try:
            USER_CONTEXT.id = PORTFOLIO_REFRESH_USER_ID
            result = refresh_portfolio_snapshot()
            message = (
                f"Automatic portfolio refresh saved {money(result['total'])}; "
                f"Robinhood accounts {result['synced_robinhood_accounts']}, "
                f"holdings {result['synced_robinhood_holdings']}, "
                f"Plaid accounts {result['synced_plaid_accounts']}"
            )
            if result["errors"]:
                message += f"; {len(result['errors'])} errors"
            print(message)
        except Exception as exc:
            print(f"Automatic portfolio refresh failed: {exc}")


def start_auto_refresh_portfolio() -> None:
    if not AUTO_REFRESH_PORTFOLIO:
        return
    thread = threading.Thread(target=auto_refresh_portfolio_loop, name="portfolio-refresh", daemon=True)
    thread.start()


def symbol_price_panel(ticker: str, query=None) -> str:
    query = query or {}
    ticker = ticker.upper()
    holdings = [holding for holding in all_holdings() if holding.get("ticker", "").upper() == ticker]
    refreshed_price = number(query.get("price", [""])[0])
    price_error = query.get("price_error", [""])[0]
    total_shares = sum(holding.get("shares") or 0 for holding in holdings)
    market_value = sum(holding.get("market_value") or 0 for holding in holdings)
    latest_holding = max(holdings, key=lambda holding: holding.get("as_of") or "") if holdings else None
    display_price = refreshed_price if refreshed_price is not None else (latest_holding.get("current_price") if latest_holding else None)
    as_of = date.today().isoformat() if refreshed_price is not None else (latest_holding.get("as_of") if latest_holding else "Not refreshed")
    status = f'Updated {escape(query.get("updated", ["0"])[0])} holding rows' if refreshed_price is not None else f'{num(total_shares)} shares tracked' if holdings else "No stock holding tracked"
    notice = f'<div class="alert">{escape(price_error)}</div>' if price_error else ""
    return f'''<section class="panel symbol-price-panel">
      <div class="panel-head"><h2>Live Price</h2><span>{escape(status)}</span></div>
      {notice}
      <div class="symbol-price-grid">
        <div class="price-quote"><span>Current price</span><strong>{money(display_price)}</strong><small>As of {escape(as_of or "-")}</small></div>
        <div class="price-quote"><span>Stock value</span><strong>{money(market_value) if holdings else "-"}</strong><small>{num(total_shares)} shares</small></div>
        <form method="post" action="/symbol/{quote(ticker)}/refresh-price"><button class="button secondary" type="submit">Refresh price</button></form>
      </div>
    </section>'''


def symbol_price_panel(ticker: str, query=None) -> str:
    query = query or {}
    ticker = ticker.upper()
    holdings = [holding for holding in all_holdings() if holding.get("ticker", "").upper() == ticker]
    refreshed_price = number(query.get("price", [""])[0])
    price_error = query.get("price_error", [""])[0]
    live_quote = fetch_market_quote(ticker, ticker)
    live_price = live_quote.get("price")
    live_change = live_quote.get("change")
    live_change_pct = live_quote.get("change_pct")
    total_shares = sum(holding.get("shares") or 0 for holding in holdings)
    stored_market_value = sum(holding.get("market_value") or 0 for holding in holdings)
    latest_holding = max(holdings, key=lambda holding: holding.get("as_of") or "") if holdings else None
    display_price = live_price if live_price is not None else refreshed_price if refreshed_price is not None else (latest_holding.get("current_price") if latest_holding else None)
    market_value = total_shares * display_price if total_shares and display_price is not None else stored_market_value
    as_of = "Live quote" if live_price is not None else date.today().isoformat() if refreshed_price is not None else (latest_holding.get("as_of") if latest_holding else "Not refreshed")
    if live_price is not None:
        status = f'{live_quote.get("session") or "Live"} - refreshes every {MARKET_TAPE_REFRESH_SECONDS}s'
    else:
        status = f'Updated {escape(query.get("updated", ["0"])[0])} holding rows' if refreshed_price is not None else f'{num(total_shares)} shares tracked' if holdings else "No stock holding tracked"
    tone = "gain" if (live_change or 0) >= 0 else "loss"
    change_line = f'<small class="{tone}">{live_change:+.2f} {live_change_pct:+.2%}</small>' if live_change is not None and live_change_pct is not None else ""
    notice = f'<div class="alert">{escape(price_error)}</div>' if price_error else ""
    if live_quote.get("error") and display_price is None:
        notice += f'<div class="alert">{escape(live_quote["error"])}</div>'
    return f'''<section class="panel symbol-price-panel" data-symbol-price-panel data-ticker="{escape(ticker)}" data-refresh-seconds="{MARKET_TAPE_REFRESH_SECONDS}">
      <div class="panel-head"><h2>Live Price</h2><span>{escape(status)}</span></div>
      {notice}
      <div class="symbol-price-grid">
        <div class="price-quote"><span>Current price</span><strong>{money(display_price)}</strong><small>As of {escape(as_of or "-")}</small>{change_line}</div>
        <div class="price-quote"><span>Stock value</span><strong>{money(market_value) if holdings else "-"}</strong><small>{num(total_shares)} shares</small></div>
        <form method="post" action="/symbol/{quote(ticker)}/refresh-price"><button class="button secondary" type="submit">Refresh price</button></form>
      </div>
    </section>'''


def symbol_2027_valuation_panel(ticker: str) -> str:
    symbol = ticker.upper()
    quote_data = fetch_market_quote(symbol, symbol)
    current_price = number(quote_data.get("price"))
    return f'''<section class="panel symbol-valuation-panel" data-symbol-valuation data-ticker="{escape(symbol)}" data-current-price="{current_price or ""}" data-usd-cny-rate="{USD_CNY_RATE}">
      <div class="panel-head"><h2>2027 Year-End Valuation</h2><span>EPS x P/E</span></div>
      <div class="valuation-current"><span>Current price</span><strong>{money(current_price)}</strong></div>
      <div class="valuation-assumptions">
        <label><span>2027 EPS</span><input type="number" inputmode="decimal" step="0.01" min="0" placeholder="0.00" data-valuation-eps></label>
        <label><span>Bear P/E</span><input type="number" inputmode="decimal" step="0.5" min="0" value="15" data-valuation-multiple="bear"></label>
        <label><span>Base P/E</span><input type="number" inputmode="decimal" step="0.5" min="0" value="25" data-valuation-multiple="base"></label>
        <label><span>Bull P/E</span><input type="number" inputmode="decimal" step="0.5" min="0" value="35" data-valuation-multiple="bull"></label>
      </div>
      <div class="valuation-scenarios">
        <div data-valuation-result="bear"><span>Bear</span><strong>-</strong><small>-</small></div>
        <div data-valuation-result="base"><span>Base</span><strong>-</strong><small>-</small></div>
        <div data-valuation-result="bull"><span>Bull</span><strong>-</strong><small>-</small></div>
      </div>
    </section>'''


def chart_svg(monthly: list[tuple[str, float]]) -> str:
    if not monthly:
        return '<div class="empty">No closed-trade history yet.</div>'
    width, height, pad = 720, 240, 34
    values = [v for _, v in monthly]
    hi, lo = max(max(values), 0), min(min(values), 0)
    span = hi - lo or 1
    zero_y = pad + (hi / span) * (height - 2 * pad)
    bar_area = (width - 2 * pad) / len(values)
    bars = [f'<line x1="{pad}" y1="{zero_y:.1f}" x2="{width-pad}" y2="{zero_y:.1f}" class="axis"/>']
    for index, (label, value) in enumerate(monthly):
        x = pad + index * bar_area + bar_area * .18
        y = pad + ((hi - max(value, 0)) / span) * (height - 2 * pad)
        h = abs(value) / span * (height - 2 * pad)
        if value < 0: y = zero_y
        color = "positive" if value >= 0 else "negative"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_area*.64:.1f}" height="{max(h,1):.1f}" rx="5" class="{color}"><title>{escape(label)}: {money(value)}</title></rect>')
        bars.append(f'<text x="{x+bar_area*.32:.1f}" y="{height-10}" text-anchor="middle">{escape(label)}</text>')
    return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Monthly realized profit and loss">{"".join(bars)}</svg>'


def active_positions(trades):
    return [trade for trade in trades if trade.get("status") == "Open"]


def position_risk_capital(trade: dict) -> float:
    explicit = number(trade.get("capital_used"))
    if explicit is not None:
        return max(0.0, explicit)
    max_loss = number(trade.get("max_loss"))
    if max_loss is not None:
        return max(0.0, max_loss)
    contracts = number(trade.get("contracts"), 0) or 0
    strike = number(trade.get("strike"), 0) or 0
    return max(0.0, contracts * strike * 100)


def stress_price_for_trade(trade: dict, quote_cache: dict[str, dict]) -> float | None:
    ticker = (trade.get("ticker") or "").upper()
    quoted = quote_cache.get(ticker, {}).get("price")
    if quoted is not None:
        return number(quoted)
    strike = number(trade.get("strike"))
    return strike


def stress_option_impact(trade: dict, current_price: float | None, shocked_price: float | None, move_pct: float) -> tuple[float, str]:
    strategy = trade.get("strategy") or ""
    contracts = number(trade.get("contracts"), 0) or 0
    short_strike = number(trade.get("strike"))
    long_strike = number(trade.get("long_put_strike"))
    credit = number(trade.get("premium_in"), 0) or 0
    max_loss = position_risk_capital(trade)
    if not contracts or short_strike is None or shocked_price is None:
        return 0.0, "Missing contracts, strike, or live price."

    if strategy == "Iron Condor" and long_strike is not None:
        short_call = number(trade.get("short_call_strike"))
        long_call = number(trade.get("long_call_strike"))
        if short_call is None or long_call is None:
            return 0.0, "Missing Iron Condor call strikes."
        if shocked_price <= long_strike or shocked_price >= long_call:
            return -max_loss, "Beyond a long wing: near max loss."
        if shocked_price < short_strike:
            intrinsic = (short_strike - shocked_price) * 100 * contracts
            return min(0.0, credit * 100 * contracts - intrinsic), "Inside the put wing."
        if shocked_price > short_call:
            intrinsic = (shocked_price - short_call) * 100 * contracts
            return min(0.0, credit * 100 * contracts - intrinsic), "Inside the call wing."
        return -max_loss * min(abs(move_pct) * 1.5, 0.25), "Between short strikes; mark-to-market estimate."

    if strategy == "Put Credit Spread" and long_strike is not None:
        low, high = sorted((long_strike, short_strike))
        if shocked_price <= low:
            return -max_loss, "Below long put: near max loss."
        if shocked_price < high:
            intrinsic = max(0.0, high - shocked_price) * 100 * contracts
            return min(0.0, credit * 100 * contracts - intrinsic), "Between strikes."
        return -max_loss * min(abs(move_pct) * 2.0, 0.35), "Still above short put; mark-to-market estimate."

    if strategy == "Call Credit Spread" and long_strike is not None:
        low, high = sorted((short_strike, long_strike))
        if shocked_price >= high:
            return -max_loss, "Above long call: near max loss."
        if shocked_price > low:
            intrinsic = max(0.0, shocked_price - low) * 100 * contracts
            return min(0.0, credit * 100 * contracts - intrinsic), "Between strikes."
        return -max_loss * min(max(move_pct, 0) * 2.0, 0.35), "Still below short call; mark-to-market estimate."

    if strategy == "Sell Put":
        if shocked_price < short_strike:
            intrinsic = (short_strike - shocked_price) * 100 * contracts
            return min(0.0, credit * 100 * contracts - intrinsic), "Put is in the money under this shock."
        return -max_loss * min(abs(move_pct) * 0.25, 0.2), "Put remains out of the money; mark-to-market estimate."

    if strategy == "Covered Call":
        if current_price is None:
            return 0.0, "Missing live stock price."
        shares = 100 * contracts
        return shares * current_price * move_pct, "Stock-like downside estimate for covered shares."

    return -max_loss * min(abs(move_pct) * 0.3, 0.25), "Generic mark-to-market estimate."


def portfolio_stress_test_page(query=None) -> bytes:
    query = query or {}
    market_move = number(query.get("market_move", ["-5"])[0], -5) or -5
    ticker_shock = (query.get("ticker", [""])[0] or "").strip().upper()
    ticker_move = number(query.get("ticker_move", [""])[0])
    move_decimal = market_move / 100
    ticker_move_decimal = ticker_move / 100 if ticker_move is not None else None

    holdings = all_holdings()
    open_trades = active_positions(all_trades())
    symbols = sorted({item.get("ticker", "").upper() for item in holdings + open_trades if item.get("ticker")})
    quote_cache = {symbol: fetch_market_quote(symbol) for symbol in symbols}

    stock_rows, option_rows = [], []
    stock_impact = 0.0
    option_impact = 0.0
    worst = ("-", 0.0)
    for holding in holdings:
        ticker = holding.get("ticker", "").upper()
        quote_data = quote_cache.get(ticker, {})
        current_price = number(quote_data.get("price"), holding.get("current_price"))
        shares = number(holding.get("shares"), 0) or 0
        applied_move = ticker_move_decimal if ticker and ticker == ticker_shock and ticker_move_decimal is not None else move_decimal
        value = shares * current_price if current_price is not None else number(holding.get("market_value"), 0) or 0
        impact = value * applied_move
        stock_impact += impact
        if impact < worst[1]:
            worst = (ticker, impact)
        stock_rows.append(f'''<tr><td><a href="/symbol/{quote(ticker)}"><b>{escape(ticker)}</b></a></td><td>Stock</td><td>{money(current_price)}</td><td>{signed_pct(applied_move)}</td><td class="{"positive" if impact >= 0 else "negative"}">{money(impact)}</td><td>{num(shares)} shares</td></tr>''')

    for trade in open_trades:
        ticker = trade.get("ticker", "").upper()
        current_price = stress_price_for_trade(trade, quote_cache)
        applied_move = ticker_move_decimal if ticker and ticker == ticker_shock and ticker_move_decimal is not None else move_decimal
        shocked_price = current_price * (1 + applied_move) if current_price is not None else None
        impact, note = stress_option_impact(trade, current_price, shocked_price, applied_move)
        option_impact += impact
        if impact < worst[1]:
            worst = (ticker, impact)
        option_rows.append(f'''<tr><td><a href="/symbol/{quote(ticker)}"><b>{escape(ticker)}</b></a></td><td>{escape(trade.get("strategy") or "-")}</td><td>{money(current_price)}</td><td>{signed_pct(applied_move)}</td><td class="{"positive" if impact >= 0 else "negative"}">{money(impact)}</td><td>{escape(note)}</td></tr>''')

    total_impact = stock_impact + option_impact
    scenario_buttons = "".join(
        f'<a class="range-pill {"active" if market_move == value and not ticker_shock else ""}" href="/portfolio-stress-test?market_move={value}">SPY {value}%</a>'
        for value in (-2, -5, -10)
    )
    rows = "".join(stock_rows + option_rows) or '<tr><td colspan="6" class="empty">No open positions or holdings to stress test.</td></tr>'
    body = f'''<div class="page-head"><div><p class="eyebrow">Risk tool</p><h1>Portfolio Stress Test</h1></div><a class="button secondary" href="/">Dashboard</a></div>
    <section class="panel stress-panel">
      <div class="panel-head"><h2>Scenario</h2><span>estimated live-position impact</span></div>
      <form class="filters stress-form" method="get">
        <input name="market_move" type="number" step="0.1" value="{num(market_move)}" aria-label="Market move percent">
        <input name="ticker" value="{escape(ticker_shock)}" placeholder="Ticker shock, e.g. NVDA">
        <input name="ticker_move" type="number" step="0.1" value="{"" if ticker_move is None else num(ticker_move)}" placeholder="Ticker move %">
        <button class="button secondary">Run</button>
      </form>
      <div class="range-pills">{scenario_buttons}</div>
    </section>
    <div class="metrics stress-metrics">
      <section class="metric"><span>Estimated impact</span><strong class="{"positive" if total_impact >= 0 else "negative"}">{money(total_impact)}</strong></section>
      <section class="metric"><span>Stock impact</span><strong class="{"positive" if stock_impact >= 0 else "negative"}">{money(stock_impact)}</strong></section>
      <section class="metric"><span>Options impact</span><strong class="{"positive" if option_impact >= 0 else "negative"}">{money(option_impact)}</strong></section>
      <section class="metric"><span>Worst ticker</span><strong class="negative">{escape(worst[0])} {money(worst[1])}</strong></section>
    </div>
    <section class="panel"><div class="panel-head"><h2>Position Impact</h2><span>quotes refresh through Yahoo cache</span></div><div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Position</th><th>Current</th><th>Move</th><th>Impact</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''
    return layout("Portfolio Stress Test - Option Ledger", body, "portfolio-stress-test")


def aggregate_bucket(rows: list[dict], label: str) -> dict:
    total = sum(row.get("net_pnl") or 0 for row in rows)
    wins = sum(1 for row in rows if (row.get("net_pnl") or 0) > 0)
    roc_values = [row.get("roc") for row in rows if row.get("roc") is not None]
    return {
        "label": label,
        "trades": len(rows),
        "total_pnl": total,
        "win_rate": wins / len(rows) if rows else None,
        "avg_roc": sum(roc_values) / len(roc_values) if roc_values else None,
    }


def weekly_trade_review_report(all_records: list[dict]) -> str:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    start_text = week_start.isoformat()
    end_text = today.isoformat()
    closed = [
        trade for trade in all_records
        if trade.get("status") != "Open"
        and trade.get("net_pnl") is not None
        and start_text <= str(trade.get("close_date") or "")[:10] <= end_text
    ]
    closed.sort(key=lambda trade: trade.get("close_date") or "")

    snapshots = [dict(row) for row in portfolio_snapshots(500)]
    week_snapshots = [
        row for row in snapshots
        if start_text <= str(row.get("snapshot_at") or "")[:10] <= end_text
    ]
    all_cash_flows = [dict(row) for row in portfolio_cash_flows()]
    cash_flows = [
        row for row in all_cash_flows
        if start_text <= str(row.get("flow_date") or "")[:10] <= end_text
    ]

    total_pnl = sum(trade.get("net_pnl") or 0 for trade in closed)
    winners = [trade for trade in closed if (trade.get("net_pnl") or 0) > 0]
    losers = [trade for trade in closed if (trade.get("net_pnl") or 0) < 0]
    win_rate = len(winners) / len(closed) if closed else None
    gross_profit = sum(trade.get("net_pnl") or 0 for trade in winners)
    gross_loss = abs(sum(trade.get("net_pnl") or 0 for trade in losers))
    profit_factor = gross_profit / gross_loss if gross_loss else None
    close_days = {str(trade.get("close_date") or "")[:10] for trade in closed}
    trades_per_day = len(closed) / len(close_days) if close_days else 0

    start_value = week_snapshots[0]["total_value"] if week_snapshots else None
    end_value = week_snapshots[-1]["total_value"] if week_snapshots else None
    portfolio_change = end_value - start_value if start_value is not None and end_value is not None else None
    portfolio_change_pct = portfolio_change / start_value if portfolio_change is not None and start_value else None
    net_cash_flow = sum(
        (number(row.get("amount"), 0) or 0) * (-1 if str(row.get("flow_type") or "").lower() == "withdrawal" else 1)
        for row in cash_flows
    )
    adjusted_portfolio_change = portfolio_change - net_cash_flow if portfolio_change is not None else None
    unexplained_change = adjusted_portfolio_change - total_pnl if adjusted_portfolio_change is not None else None

    strategy_groups = {}
    for trade in closed:
        label = trade.get("strategy") or "Other"
        bucket = strategy_groups.setdefault(label, {"trades": 0, "wins": 0, "pnl": 0.0})
        bucket["trades"] += 1
        bucket["wins"] += int((trade.get("net_pnl") or 0) > 0)
        bucket["pnl"] += trade.get("net_pnl") or 0
    strategy_rows = sorted(strategy_groups.items(), key=lambda item: item[1]["pnl"])

    ticker_groups = {}
    for trade in closed:
        ticker = trade.get("ticker") or "-"
        ticker_groups[ticker] = ticker_groups.get(ticker, 0.0) + (trade.get("net_pnl") or 0)
    ticker_rows = sorted(ticker_groups.items(), key=lambda item: item[1])
    largest_losses = sorted(losers, key=lambda trade: trade.get("net_pnl") or 0)[:5]
    top_three_loss = abs(sum(trade.get("net_pnl") or 0 for trade in largest_losses[:3]))
    top_three_share = top_three_loss / gross_loss if gross_loss else None

    period_label = f'{start_text} to {end_text}'
    metrics = (
        ("Portfolio change", money(portfolio_change), pct(portfolio_change_pct), "negative" if (portfolio_change or 0) < 0 else "positive"),
        ("Realized P&L", money(total_pnl), f'{len(closed)} closed trades', "negative" if total_pnl < 0 else "positive"),
        ("Win rate", pct(win_rate), f'{len(winners)}W / {len(losers)}L', "negative" if win_rate is not None and win_rate < 0.5 else "positive"),
        ("Profit factor", num(profit_factor) if profit_factor is not None else "-", f'{money(gross_profit)} / {money(-gross_loss)}', "negative" if profit_factor is not None and profit_factor < 1 else "positive"),
        ("Trade pace", f'{trades_per_day:.1f}/day', f'{len(close_days)} active days', "negative" if trades_per_day > 5 else ""),
    )
    metrics_html = "".join(
        f'<div class="weekly-review-metric"><span>{escape(label)}</span><strong class="{css_class}">{value}</strong><small>{escape(detail)}</small></div>'
        for label, value, detail, css_class in metrics
    )

    strategy_html = "".join(
        f'''<tr><td><b>{escape(label)}</b></td><td>{data["trades"]}</td><td>{pct(data["wins"] / data["trades"] if data["trades"] else None)}</td><td class="{"positive" if data["pnl"] >= 0 else "negative"}">{money(data["pnl"])}</td></tr>'''
        for label, data in strategy_rows
    ) or '<tr><td colspan="4" class="empty">No closed trades this week.</td></tr>'
    loss_rows = "".join(
        f'''<tr><td><b>{escape(trade.get("ticker") or "-")}</b></td><td>{escape(trade.get("strategy") or "-")}</td><td class="negative">{money(trade.get("net_pnl"))}</td><td>{pct(trade.get("trade_pl_pct"))}</td><td>{money(trade.get("capital_used"))}</td></tr>'''
        for trade in largest_losses
    ) or '<tr><td colspan="5" class="empty">No losing closes this week.</td></tr>'

    worst_strategy = strategy_rows[0] if strategy_rows else None
    worst_ticker = ticker_rows[0] if ticker_rows else None
    current_value = end_value or current_portfolio_total()
    risk_unit = current_value * 0.01 if current_value else 0
    daily_stop = current_value * 0.015 if current_value else 0
    diagnosis = []
    if worst_strategy:
        diagnosis.append(
            f'The largest drag was {worst_strategy[0]}: {worst_strategy[1]["trades"]} trades, {pct(worst_strategy[1]["wins"] / worst_strategy[1]["trades"]) } win rate, and {money(worst_strategy[1]["pnl"])} total. This is the first strategy to pause and review, not ordinary weekly noise.'
        )
    if worst_ticker:
        diagnosis.append(f'Losses were concentrated: {worst_ticker[0]} contributed {money(worst_ticker[1])}, while the three largest losses made up {pct(top_three_share)} of gross losses. A few oversized mistakes drove the week.')
    if trades_per_day > 5:
        diagnosis.append(f'Trade frequency was high: {len(closed)} closes across {len(close_days)} sessions, or {trades_per_day:.1f} per day. At a {pct(win_rate)} win rate, frequency amplified both decision errors and emotional pressure.')
    if unexplained_change is not None and abs(unexplained_change) >= 100:
        diagnosis.append(f'Portfolio movement differed from realized P&L by about {money(unexplained_change)}. Open-position marks, option pricing, cash flows, or account-sync differences explain the remainder; closed trades alone do not.')
    diagnosis_html = "".join(f'<li>{escape(item)}</li>' for item in diagnosis) or '<li>There is not enough activity for a weekly diagnosis yet.</li>'

    controls = [
        f'Limit new risk per idea to about 1% of the portfolio ({money(risk_unit)} at the latest snapshot) until results stabilize for two consecutive weeks.',
        f'Use a 1.5% daily loss limit (about {money(daily_stop)}). Once reached, open no additional directional positions that day.',
        'Pause new outright Long Calls for the first two sessions next week. Manage existing positions and write the entry thesis, invalidation condition, and exit price for each one.',
        'Allow at most three new directional ideas per day. Treat highly correlated technology names or the same theme as one risk basket.',
        'Review the three largest losses before restoring position size. The immediate goal is not to win it back; it is to stop extending the drawdown.',
    ]
    controls_html = "".join(f'<li>{escape(item)}</li>' for item in controls)

    return f'''<section class="panel weekly-review-report">
      <div class="panel-head"><div><p class="eyebrow">Weekly review</p><h2>{escape(period_label)}</h2></div><span>Data through {escape(end_text)}</span></div>
      <div class="weekly-review-reassurance"><b>Take a breath:</b> this was a difficult risk event, not a verdict on your ability. The priority is not to win the money back immediately; it is to make risk controllable again.</div>
      <div class="weekly-review-metrics">{metrics_html}</div>
      <div class="weekly-review-grid">
        <div class="weekly-review-section"><h3>What happened this week</h3><ul>{diagnosis_html}</ul></div>
        <div class="weekly-review-section"><h3>Rules for next week</h3><ol>{controls_html}</ol></div>
      </div>
      <div class="weekly-review-grid weekly-review-tables">
        <div class="weekly-review-section"><h3>Strategy attribution</h3><div class="table-wrap"><table><thead><tr><th>Strategy</th><th>Trades</th><th>Win rate</th><th>P&L</th></tr></thead><tbody>{strategy_html}</tbody></table></div></div>
        <div class="weekly-review-section"><h3>Largest losses</h3><div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Strategy</th><th>P&L</th><th>P/L %</th><th>Capital</th></tr></thead><tbody>{loss_rows}</tbody></table></div></div>
      </div>
      <p class="weekly-review-note">Portfolio change equals the account snapshot change less net cash flow. It includes realized P&L, unrealized marks, and quote changes, so it will not exactly match closed-trade P&L. Annualized return magnifies historical results and can fall sharply after a short losing period; it is not the account's actual weekly loss percentage.</p>
    </section>'''


def trade_journal_review_page(query=None) -> bytes:
    query = query or {}
    all_records = symbol_trade_records()
    closed = [trade for trade in all_records if trade.get("status") != "Open" and trade.get("net_pnl") is not None]
    closed.sort(key=lambda trade: trade.get("close_date") or trade.get("open_date") or "", reverse=True)
    total_pnl = sum(trade.get("net_pnl") or 0 for trade in closed)
    winners = [trade for trade in closed if (trade.get("net_pnl") or 0) > 0]
    losers = [trade for trade in closed if (trade.get("net_pnl") or 0) < 0]
    gross_profit = sum(trade.get("net_pnl") or 0 for trade in winners)
    gross_loss = abs(sum(trade.get("net_pnl") or 0 for trade in losers))
    profit_factor = gross_profit / gross_loss if gross_loss else None
    expectancy = total_pnl / len(closed) if closed else None
    avg_win = gross_profit / len(winners) if winners else None
    avg_loss = -gross_loss / len(losers) if losers else None
    trade_pl_values = [trade.get("trade_pl_pct") for trade in closed if trade.get("trade_pl_pct") is not None]

    book_labels = {
        "trade": "Option Seller",
        "other_option": "Option Buyer",
        "day_trade": "Day Trades",
        "stock_trade": "Stock Trades",
    }
    book_groups = {label: [] for label in book_labels.values()}
    dte_groups = {"0-7": [], "8-14": [], "15-30": [], "31-45": [], "46+": []}
    holding_groups = {"0D": [], "1-7D": [], "8-21D": [], "22D+": []}
    width_groups = {"single-leg / stock": [], "<=2.5% width": [], "2.5-5% width": [], ">5% width": []}
    for trade in closed:
        book_groups.setdefault(book_labels.get(trade.get("source") or "trade", "Option Seller"), []).append(trade)
        opened = parse_date(trade.get("open_date"))
        expiration = parse_date(trade.get("expiration"))
        dte = (expiration - opened).days if opened and expiration else None
        if dte is not None:
            if dte <= 7:
                dte_groups["0-7"].append(trade)
            elif dte <= 14:
                dte_groups["8-14"].append(trade)
            elif dte <= 30:
                dte_groups["15-30"].append(trade)
            elif dte <= 45:
                dte_groups["31-45"].append(trade)
            else:
                dte_groups["46+"].append(trade)
        held = number(trade.get("days_held"), 0) or 0
        if held <= 0:
            holding_groups["0D"].append(trade)
        elif held <= 7:
            holding_groups["1-7D"].append(trade)
        elif held <= 21:
            holding_groups["8-21D"].append(trade)
        else:
            holding_groups["22D+"].append(trade)
        width = number(trade.get("spread_width"))
        strike = number(trade.get("strike"))
        if not width or not strike:
            width_groups["single-leg / stock"].append(trade)
        else:
            width_pct = width / strike
            if width_pct <= 0.025:
                width_groups["<=2.5% width"].append(trade)
            elif width_pct <= 0.05:
                width_groups["2.5-5% width"].append(trade)
            else:
                width_groups[">5% width"].append(trade)

    strategy_rows = strategy_summary(closed)
    ticker_rows = symbol_summary(closed)
    book_rows = [aggregate_bucket(rows, label) for label, rows in book_groups.items() if rows]
    dte_rows = [aggregate_bucket(rows, label) for label, rows in dte_groups.items() if rows]
    holding_rows = [aggregate_bucket(rows, label) for label, rows in holding_groups.items() if rows]
    width_rows = [aggregate_bucket(rows, label) for label, rows in width_groups.items() if rows]

    def summary_table(items, name_key="label", metric_label="Avg P/L %", limit=None) -> str:
        if not items:
            return '<div class="empty">No data yet.</div>'
        scoped = items[:limit] if limit else items
        body_rows = "".join(
            f'<tr><td><b>{escape(str(item.get(name_key) or item.get("strategy") or item.get("ticker") or "-"))}</b></td><td>{item.get("trades", 0)}</td><td class="{"positive" if (item.get("total_pnl") or 0) >= 0 else "negative"}">{money(item.get("total_pnl"))}</td><td>{pct(item.get("win_rate"))}</td><td>{pct(item.get("avg_roc") if item.get("avg_roc") is not None else item.get("avg_trade_pl_pct") if item.get("avg_trade_pl_pct") is not None else item.get("pl_pct"))}</td></tr>'
            for item in scoped
        )
        return f'<div class="table-wrap"><table><thead><tr><th>Group</th><th>Trades</th><th>P&L</th><th>Win rate</th><th>{escape(metric_label)}</th></tr></thead><tbody>{body_rows}</tbody></table></div>'

    def page_int(name):
        try:
            return max(1, int(query.get(name, ["1"])[0]))
        except ValueError:
            return 1

    def journal_pagination(items, page, param_name, page_size=8):
        total_pages = max(1, math.ceil(len(items) / page_size))
        page = min(max(page, 1), total_pages)
        params_prev = {
            "loss_page": query.get("loss_page", ["1"])[0],
            "largest_page": query.get("largest_page", ["1"])[0],
        }
        params_next = dict(params_prev)
        params_prev[param_name] = str(max(1, page - 1))
        params_next[param_name] = str(min(total_pages, page + 1))
        start = (page - 1) * page_size
        end = min(start + page_size, len(items))
        summary = f"Showing {start + 1}-{end} of {len(items)}" if items else "Showing 0 of 0"
        controls = (
            f'<div class="pagination"><span class="pagination-summary">{summary}</span>'
            f'<div class="pagination-pages">'
            f'<a class="{"disabled" if page == 1 else ""}" href="/trade-journal-review?{urlencode({k: v for k, v in params_prev.items() if v and v != "1"})}">Prev</a>'
            f'<span class="pagination-current">{page}</span>'
            f'<a class="{"disabled" if page == total_pages else ""}" href="/trade-journal-review?{urlencode({k: v for k, v in params_next.items() if v and v != "1"})}">Next</a>'
            f'</div></div>'
        )
        return items[start:end], controls

    recent_losses = sorted(losers, key=lambda row: row.get("close_date") or row.get("open_date") or "", reverse=True)
    largest_losses = sorted(losers, key=lambda row: row.get("net_pnl") or 0)
    recent_loss_page_items, recent_loss_pagination = journal_pagination(recent_losses, page_int("loss_page"), "loss_page")
    largest_loss_page_items, largest_loss_pagination = journal_pagination(largest_losses, page_int("largest_page"), "largest_page")

    recent_loss_rows = "".join(
        f'''<tr>
          <td>{escape(trade.get("close_date") or trade.get("open_date") or "-")}</td>
          <td><a href="/symbol/{quote(trade.get("ticker") or "")}"><b>{escape(trade.get("ticker") or "-")}</b></a></td>
          <td>{escape(trade.get("strategy") or "-")}</td>
          <td class="negative">{money(trade.get("net_pnl"))}</td>
          <td>{pct(trade.get("trade_pl_pct"))}</td>
          <td>{escape((trade.get("notes") or "")[:90]) or "-"}</td>
        </tr>'''
        for trade in recent_loss_page_items
    ) or '<tr><td colspan="6" class="empty">No losing trades to review.</td></tr>'
    largest_loss_rows = "".join(
        f'''<tr>
          <td><a href="/symbol/{quote(trade.get("ticker") or "")}"><b>{escape(trade.get("ticker") or "-")}</b></a></td>
          <td>{escape(trade.get("strategy") or "-")}</td>
          <td class="negative">{money(trade.get("net_pnl"))}</td>
          <td>{money(trade.get("capital_used"))}</td>
          <td>{pct(trade.get("trade_pl_pct"))}</td>
        </tr>'''
        for trade in largest_loss_page_items
    ) or '<tr><td colspan="5" class="empty">No large losses yet.</td></tr>'

    rules = []
    strong_strategy = next((item for item in strategy_rows if item.get("trades", 0) >= 3 and (item.get("total_pnl") or 0) > 0), strategy_rows[0] if strategy_rows else None)
    weak_strategy = next((row for row in sorted(strategy_rows, key=lambda row: row.get("total_pnl") or 0) if row.get("trades", 0) >= 2), None)
    best_book = max(book_rows, key=lambda row: row.get("total_pnl") or 0) if book_rows else None
    worst_book = min(book_rows, key=lambda row: row.get("total_pnl") or 0) if book_rows else None
    best_dte = max(dte_rows, key=lambda row: row.get("total_pnl") or 0) if dte_rows else None
    worst_ticker = min(ticker_rows, key=lambda row: row.get("total_pnl") or 0) if ticker_rows else None
    if strong_strategy:
        rules.append(f'Keep leaning into {strong_strategy["strategy"]}: {strong_strategy["trades"]} trades, {money(strong_strategy["total_pnl"])} realized.')
    if weak_strategy and (weak_strategy.get("total_pnl") or 0) < 0:
        rules.append(f'Tighten entries for {weak_strategy["strategy"]}: weakest strategy bucket at {money(weak_strategy["total_pnl"])}.')
    if best_book and worst_book and best_book != worst_book:
        rules.append(f'Best book is {best_book["label"]} at {money(best_book["total_pnl"])}; weakest book is {worst_book["label"]} at {money(worst_book["total_pnl"])}.')
    if best_dte:
        rules.append(f'Best DTE bucket so far: {best_dte["label"]} with {money(best_dte["total_pnl"])}.')
    if worst_ticker and (worst_ticker.get("total_pnl") or 0) < 0:
        rules.append(f'Review sizing or thesis quality on {worst_ticker["ticker"]}: worst ticker at {money(worst_ticker["total_pnl"])}.')
    if profit_factor is not None and profit_factor < 1:
        rules.append(f'Profit factor is below 1.0; reduce loss size before scaling frequency.')
    rules_html = "".join(f'<li>{escape(rule)}</li>' for rule in rules) or '<li>No closed-trade pattern yet. Close a few trades and this will get sharper.</li>'

    metrics = (
        ("Closed trades", f"{len(closed):,}", ""),
        ("Total P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Win rate", pct(len(winners) / len(closed) if closed else None), ""),
        ("Profit factor", num(profit_factor) if profit_factor is not None else "-", "positive" if profit_factor is not None and profit_factor >= 1 else "negative"),
        ("Expectancy", money(expectancy), "positive" if expectancy is not None and expectancy >= 0 else "negative"),
        ("Avg Trade P/L %", pct(sum(trade_pl_values) / len(trade_pl_values) if trade_pl_values else None), ""),
        ("Avg win", money(avg_win), "positive"),
        ("Avg loss", money(avg_loss), "negative"),
    )

    weekly_report_html = weekly_trade_review_report(all_records)
    body = f'''<div class="page-head"><div><p class="eyebrow">Weekly review</p><h1>Review</h1></div><div class="actions"><a class="button secondary" href="/symbols">Symbols</a><a class="button secondary" href="/trades">Trades</a></div></div>
    {weekly_report_html}'''
    return layout("Review - Option Ledger", body, "trade-journal-review")


def brokerage_page(message: str = "", error: str = "", query=None) -> bytes:
    query = query or {}
    selected_range = query.get("range", ["ytd"])[0]
    if selected_range not in {"1w", "1m", "3m", "6m", "ytd", "1y", "all"}:
        selected_range = "ytd"
    selected_method = query.get("method", ["simple"])[0]
    if selected_method not in PORTFOLIO_RETURN_METHODS:
        selected_method = "simple"
    selected_benchmarks = {
        value for value in query.get("benchmark", [])
        if value in {"sp", "nasdaq"}
    }
    selected_account = query.get("account", [""])[0]
    if selected_account not in {"account-robinhood", "account-fidelity", "account-fidelity-401k", "account-ira"}:
        selected_account = ""
    accounts = [dict(account) for account in brokerage_accounts()]
    external = [dict(account) for account in external_accounts()]
    primary_brokerage = primary_brokerage_account(accounts)
    taxable_external = external_taxable_account(external)
    retirement_external = external_retirement_account(external)
    live_robinhood_tickers = robinhood_equity_tickers()
    holdings = [
        holding for holding in exclude_fidelity_holdings(all_holdings(sort_by="market_value", sort_dir="desc"))
        if broker_source_for_row(holding) != "External"
        and (
            broker_source_for_row(holding) != "Robinhood"
            or live_robinhood_tickers is None
            or str(holding.get("ticker") or "").strip().upper() in live_robinhood_tickers
        )
    ]
    plaid_count = len(plaid_items())
    message_html = f'<div class="notice">{escape(message)}</div>' if message else ""
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    robinhood_value = sum(number(account.get("portfolio_value"), 0) for account in accounts)
    external_value = sum(number(account.get("current_balance"), 0) for account in external)
    total_value = robinhood_value + external_value
    last_sync = max(
        [account.get("last_sync_at") or "" for account in accounts] + [account.get("updated_at") or "" for account in external],
        default="",
    ) or "Never"
    snapshots = portfolio_snapshots(500)
    cash_flows = portfolio_cash_flows()
    robinhood_cash_flows = [
        flow for flow in cash_flows
        if not any(marker in str(flow["account"] if "account" in flow.keys() else "").lower()
                   for marker in ("fidelity", "401k", "401(k)", "external"))
    ]
    snapshot_status = robinhood_snapshot_status()
    option_underlyings = robinhood_option_underlyings()
    snapshot_marker = snapshot_status.get("marker") or ""
    if total_value:
        if not snapshots:
            today = date.today()
            ratios = (0.965, 0.958, 0.974, 0.982, 0.991, 1.0)
            snapshot_values = [
                {"date": (today - timedelta(days=len(ratios) - index - 1)).isoformat(), "value": robinhood_value * ratio}
                for index, ratio in enumerate(ratios)
            ]
        else:
            snapshot_values = portfolio_range_values(snapshots, selected_range, robinhood_value, robinhood_cash_flows)
            if not snapshot_values:
                today = date.today()
                snapshot_values = [
                    {"date": (today - timedelta(days=1)).isoformat(), "value": robinhood_value * 0.99},
                    {"date": today.isoformat(), "value": robinhood_value},
                ]
        snapshot_values = add_fidelity_taxable_to_portfolio_points(snapshot_values)
        snapshot_values = add_fidelity_401k_to_portfolio_points(snapshot_values)
    else:
        snapshot_values = []
    account_series = portfolio_account_estimates(snapshot_values, accounts, external)
    selected_series = next((series for series in account_series if series.get("key") == selected_account), None)
    display_snapshot_values = (
        [
            {
                "date": series_date.isoformat(),
                "value": series_value,
                "cash_flow": selected_series.get("cash_flows", {}).get(series_date, 0),
            }
            for series_date, series_value in selected_series.get("values", [])
        ]
        if selected_series else snapshot_values
    )
    snapshot_amounts = [number(item.get("value"), 0) if isinstance(item, dict) else number(item, 0) for item in display_snapshot_values]
    chart_baseline = (
        PORTFOLIO_DEPOSIT_BASIS or (snapshot_amounts[0] if snapshot_amounts else None)
        if selected_range == "all"
        else (snapshot_amounts[0] if snapshot_amounts else None)
    )
    if selected_series:
        chart_baseline = snapshot_amounts[0] if snapshot_amounts else None
    return_values = portfolio_return_series(display_snapshot_values, chart_baseline, selected_method)
    if selected_account == "account-fidelity-401k" and selected_method == "simple":
        cumulative_basis_flow = 0.0
        basis_returns = [0.0 if chart_baseline else None]
        for index, item in enumerate(display_snapshot_values[1:], start=1):
            cumulative_basis_flow += number(item.get("cash_flow"), 0) or 0
            gain = snapshot_amounts[index] - (chart_baseline or 0) - cumulative_basis_flow
            invested_basis = (chart_baseline or 0) + cumulative_basis_flow
            basis_returns.append(gain / invested_basis if invested_basis > 0 else None)
        return_values = basis_returns
    delta_pct = return_values[-1] if return_values else None
    if selected_series and snapshot_amounts:
        future_cash_flow = sum(
            number(item.get("cash_flow"), 0) or 0
            for item in display_snapshot_values[1:]
        )
        normalized_points = []
        for index, item in enumerate(display_snapshot_values):
            activity = number(item.get("cash_flow"), 0) or 0
            if index:
                future_cash_flow -= activity
            account_value = number(item.get("value"), 0) or 0
            adjusted_value = account_value + future_cash_flow
            normalized_points.append({
                "date": item.get("date"),
                "value": adjusted_value,
                "account_value": account_value,
                "activity": activity,
                "cash_flow": 0,
                "return_pct": return_values[index] if index < len(return_values) else None,
            })
        display_snapshot_values = normalized_points
        chart_baseline = number(normalized_points[0].get("value"), 0) or 0
        delta = (number(normalized_points[-1].get("value"), 0) or 0) - chart_baseline
    else:
        delta = (chart_baseline or 0) * delta_pct if delta_pct is not None else 0
    delta_class = "positive" if delta >= 0 else "negative"
    display_value = number(selected_series.get("current_value"), 0) if selected_series else total_value
    display_label = f'{selected_series.get("label")} (estimated)' if selected_series else "Portfolio overview"
    categories = {
        "banking": {"label": "Banking", "hint": "cash and bank balances", "value": 0.0, "rows": []},
        "crypto": {"label": "Crypto", "hint": "crypto accounts", "value": 0.0, "rows": []},
        "investments": {"label": "Investments", "hint": "taxable brokerage", "value": 0.0, "rows": []},
        "retirement": {"label": "Retirement", "hint": "IRA and retirement", "value": 0.0, "rows": []},
    }
    for account in accounts:
        account_type = (account.get("account_type") or "").lower()
        category = "retirement" if is_retirement_account(account) else "investments"
        value = number(account.get("portfolio_value"), 0)
        categories[category]["value"] += value
        categories[category]["rows"].append({
            "name": account.get("nickname") or account.get("provider") or "Brokerage",
            "institution": account.get("provider") or "Brokerage",
            "mask": account.get("account_last4") or "",
            "value": value,
            "subtype": account.get("trading_type") or account.get("account_type") or "",
            "account_key": (
                "account-robinhood" if account is primary_brokerage
                else "account-ira" if is_retirement_account(account)
                else ""
            ),
        })
    for account in external:
        category = account.get("category") if account.get("category") in categories else "banking"
        value = number(account.get("current_balance"), 0)
        categories[category]["value"] += value
        categories[category]["rows"].append({
            "name": account.get("name") or "Account",
            "institution": account.get("institution_name") or account.get("source") or "External",
            "mask": account.get("mask") or "",
            "value": value,
            "subtype": account.get("account_subtype") or account.get("account_type") or "",
            "account_key": (
                "account-fidelity-401k" if account is retirement_external
                else "account-fidelity" if account is taxable_external
                else ""
            ),
        })
    category_html = "".join(portfolio_category_row(data, total_value, selected_account) for data in categories.values())
    active_benchmarks = set() if selected_series else selected_benchmarks
    benchmark_controls_html = "" if selected_series else portfolio_return_controls(display_snapshot_values, active_benchmarks)
    method_options_html = portfolio_return_method_options(selected_method, selected_range, selected_account, active_benchmarks)
    method_note_html = (
        '<span class="portfolio-method-note">Cash-flow-adjusted account value; deposits and withdrawals are back-adjusted for comparability.</span>'
        if selected_series else portfolio_method_note(selected_method)
    )
    chart_label = f'{selected_series.get("label")} adjusted value' if selected_series else "Portfolio"
    chart_html = portfolio_overview_chart(
        display_snapshot_values,
        chart_baseline,
        selected_method,
        chart_label,
        show_benchmarks=not selected_series,
        active_benchmarks=active_benchmarks,
    )
    account_reset_html = (
        '<button class="button secondary portfolio-account-reset" type="button" data-portfolio-account="">All accounts</button>'
        if selected_series else ""
    )
    portfolio_cash_value = sum(number(account.get("cash_value"), 0) for account in accounts)
    allocation_html = (
        f'<div class="portfolio-pie-stack two-up">'
        f'{portfolio_allocation_pie(categories, total_value)}'
        f'{portfolio_holdings_pie(holdings, option_underlyings, sum(number(account.get("options_value"), 0) for account in accounts), portfolio_cash_value, robinhood_value)}'
        f'</div>'
    )
    range_html = portfolio_range_links(selected_range, selected_method, selected_account, active_benchmarks)
    account_cards = []
    for account in accounts:
        masked = f'****{escape(account.get("account_last4") or "----")}'
        nickname = account.get("nickname") or "Robinhood"
        account_type = account.get("account_type") or "-"
        trading_type = account.get("trading_type") or "-"
        sync_text = account.get("last_sync_at") or "Never"
        account_cards.append(f'''<section class="panel brokerage-account-card">
          <div class="panel-head"><h2>{escape(nickname)}</h2><span>{masked}</span></div>
          <div class="brokerage-tags"><span>{escape(account_type)}</span><span>{escape(trading_type)}</span></div>
          <div class="brokerage-breakdown">
            <span><b>Portfolio</b><strong>{money(account.get("portfolio_value"))}</strong></span>
            <span><b>Buying power</b><strong>{money(account.get("buying_power"))}</strong></span>
            <span><b>Stocks</b><strong>{money(account.get("stocks_value"))}</strong></span>
            <span><b>Options</b><strong>{money(account.get("options_value"))}</strong></span>
            <span><b>Cash</b><strong>{money(account.get("cash_value"))}</strong></span>
          </div>
          <p class="muted-row">Last sync {escape(str(sync_text))}</p>
        </section>''')
    for account in external:
        masked = f'****{escape(account.get("mask") or "----")}'
        account_cards.append(f'''<section class="panel brokerage-account-card">
          <div class="panel-head"><h2>{escape(account.get("name") or "Account")}</h2><span>{masked}</span></div>
          <div class="brokerage-tags"><span>{escape(account.get("institution_name") or "Plaid")}</span><span>{escape(account.get("account_subtype") or account.get("account_type") or "-")}</span></div>
          <div class="brokerage-breakdown">
            <span><b>Current</b><strong>{money(account.get("current_balance"))}</strong></span>
            <span><b>Available</b><strong>{money(account.get("available_balance"))}</strong></span>
            <span><b>Category</b><strong>{escape(account.get("category") or "banking")}</strong></span>
          </div>
          <p class="muted-row">Updated {escape(str(account.get("updated_at") or "Never"))}</p>
        </section>''')
    accounts_html = "".join(account_cards) if account_cards else '<section class="panel"><div class="empty">No account snapshot yet.</div></section>'
    portfolio_status = "Synced" if accounts or external else "No snapshot"
    portfolio_status_class = "positive" if accounts or external else "negative"
    body = f'''<div class="page-head" data-portfolio-page data-robinhood-snapshot-marker="{escape(snapshot_marker)}" data-refresh-seconds="30">
      <div><p class="eyebrow">Portfolio</p><h1>Portfolio overview</h1></div>
      <div class="actions">
        <a class="button secondary" href="/portfolio-deposit/new">Add deposit</a>
        <form method="post" action="/brokerage/robinhood/sync"><button class="button" type="submit">Sync Robinhood</button></form>
      </div>
    </div>
    {message_html}{error_html}
    <section class="portfolio-hero panel">
      <div class="portfolio-hero-head">
        <div>
          <span data-portfolio-live-label data-default-value="{escape(display_label)}">{escape(display_label)}</span>
          <strong data-portfolio-live-value data-default-value="{escape(money(display_value))}">{money(display_value)}</strong>
          <small class="{delta_class}" data-portfolio-live-change data-default-value="{escape(money(delta))} ({escape(pct(delta_pct))})" data-default-class="{delta_class}">{money(delta)} ({pct(delta_pct)})</small>
        </div>
        <div class="portfolio-sync-meta">
          <b class="{portfolio_status_class}">{portfolio_status}</b>
          <span>{len(accounts) + len(external)} accounts - {plaid_count} Plaid items - Last sync {escape(str(last_sync))}</span>
        </div>
      </div>
      <div class="portfolio-visual-grid">
        <div data-portfolio-chart-column>
          <div class="portfolio-chart-toolbar">
            {benchmark_controls_html}{account_reset_html}
            {method_options_html}
          </div>
          {method_note_html}
          {chart_html}
          <div class="portfolio-ranges">{range_html}</div>
        </div>
        <section class="portfolio-categories portfolio-categories-side">
          {category_html}
        </section>
      </div>
      {allocation_html}
    </section>
    '''
    return layout("Portfolio - Option Ledger", body, "brokerage")


def portfolio_deposit_form(form_data=None, error: str = "") -> bytes:
    data = dict(form_data or {})
    data.setdefault("flow_date", date.today().isoformat())
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""

    account_names = []
    for account in brokerage_accounts():
        name = account["nickname"] or account["provider"] or "Brokerage"
        last4 = account["account_last4"] or ""
        account_names.append(f"{name} ****{last4}" if last4 else str(name))
    for account in external_accounts():
        name = account["name"] or account["institution_name"] or "External account"
        mask = account["mask"] or ""
        account_names.append(f"{name} ****{mask}" if mask else str(name))
    account_names = list(dict.fromkeys(account_names))
    selected_account = str(data.get("account") or "")
    account_options = ['<option value="">Portfolio / unassigned</option>']
    account_options.extend(
        f'<option value="{escape(name)}" {"selected" if name == selected_account else ""}>{escape(name)}</option>'
        for name in account_names
    )

    history_rows = []
    for flow in reversed(portfolio_cash_flows()[-25:]):
        account = flow["account"] or "Portfolio"
        notes = flow["notes"] or "-"
        history_rows.append(f'''<tr>
          <td>{escape(str(flow["flow_date"]))}</td>
          <td>{escape(str(account))}</td>
          <td class="positive">+{money(flow["amount"])}</td>
          <td>{escape(str(notes))}</td>
          <td class="row-actions"><form method="post" action="/portfolio-deposit/{int(flow["id"])}/delete"><button class="danger-link" type="submit">Delete</button></form></td>
        </tr>''')
    history_html = "".join(history_rows) or '<tr><td colspan="5" class="empty">No deposits recorded yet.</td></tr>'

    body = f'''<div class="narrow portfolio-deposit-page">
      <div class="page-head"><div><p class="eyebrow">Portfolio cash flow</p><h1>Add deposit</h1></div><a class="clear" href="/brokerage">Back to portfolio</a></div>
      {error_html}
      <form class="trade-form panel portfolio-deposit-form" method="post" action="/portfolio-deposit/new">
        <fieldset><legend>Deposit details</legend><div class="form-grid">
          {field('Deposit date', 'flow_date', data.get('flow_date', ''), 'date', 'required')}
          {field('Amount', 'amount', data.get('amount', ''), 'number', 'required min="0.01" step="0.01" placeholder="0.00"')}
          <label><span>Account</span><select name="account">{"".join(account_options)}</select></label>
        </div></fieldset>
        <fieldset><legend>Notes</legend><label><textarea name="notes" rows="3" maxlength="240" placeholder="Optional transfer reference or note">{escape(str(data.get('notes') or ''))}</textarea></label></fieldset>
        <div class="form-actions"><a class="clear" href="/brokerage">Cancel</a><button class="button" type="submit">Add deposit</button></div>
      </form>
      <section class="panel portfolio-deposit-history">
        <div class="panel-head"><h2>Deposit history</h2><span>Used to remove contributions from portfolio returns</span></div>
        <div class="table-wrap"><table><thead><tr><th>Date</th><th>Account</th><th>Amount</th><th>Notes</th><th></th></tr></thead><tbody>{history_html}</tbody></table></div>
      </section>
    </div>'''
    return layout("Add deposit - Option Ledger", body, "brokerage")

def option_position_side(trade: dict) -> tuple[str, str]:
    strategy = (trade.get("strategy") or "").lower()
    bullish_patterns = ("put credit spread", "call debit spread", "sell put", "buyer call")
    bearish_patterns = ("call credit spread", "put debit spread", "covered call", "buyer put")
    if any(pattern in strategy for pattern in bullish_patterns):
        return "Long", "long"
    if any(pattern in strategy for pattern in bearish_patterns):
        return "Short", "short"

    option_type = (trade.get("option_type") or "").lower()
    is_sell = trade.get("open_side") == "Sell to open"
    if option_type == "put":
        is_long = is_sell
    elif option_type == "call":
        is_long = not is_sell
    else:
        is_long = trade.get("source") == "other_option"
    return ("Long", "long") if is_long else ("Short", "short")


def open_positions_risk_panel(trades) -> str:
    today = date.today()
    positions = []
    for trade in active_positions(trades):
        expiration = parse_date(trade.get("expiration"))
        dte = (expiration - today).days if expiration else None
        capital = number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        dte_class = "loss" if dte is not None and dte <= 7 else "gain" if dte is not None and dte > 21 else ""
        position_side, position_class = option_position_side(trade)
        positions.append({
            "trade": trade,
            "dte": dte,
            "dte_sort": dte if dte is not None else 99999,
            "dte_class": dte_class,
            "capital": capital,
            "position_side": position_side,
            "position_class": position_class,
        })

    grouped = {}
    for position in positions:
        grouped.setdefault(position["trade"]["ticker"], []).append(position)

    def position_edit_href(trade):
        if trade.get("source") == "other_option":
            trade_id = str(trade["id"]).replace("other-option-", "")
            path = f"/other-option/{trade_id}/edit"
        else:
            path = f'/trade/{trade["id"]}/edit'
        return f'{path}?{urlencode({"return_to": "/"})}'

    def position_row(position, group_id=""):
        trade = position["trade"]
        child_attrs = f' class="option-position-child" data-option-group-row="{group_id}" hidden' if group_id else ""
        ticker_cell = '<span class="option-position-detail">Detail</span>' if group_id else f'<a href="/symbol/{quote(trade["ticker"])}"><b>{escape(trade["ticker"])}</b></a>'
        edit_href = position_edit_href(trade)
        return f'''<tr{child_attrs}>
          <td>{ticker_cell}</td>
          <td>{broker_source_badge(broker_source_for_row(trade))}</td>
          <td>{escape(trade["strategy"])}</td>
          <td><span class="position-side {position["position_class"]}">{escape(position["position_side"])}</span></td>
          <td>{strike_display(trade)}</td>
          <td class="{position["dte_class"]}">{position["dte"] if position["dte"] is not None else "-"}</td>
          <td>{escape(trade.get("expiration") or "-")}</td>
          <td>{money(position["capital"])}</td>
          <td><a class="text-button" href="{edit_href}">Edit</a></td>
        </tr>'''

    rows = []
    sorted_groups = sorted(grouped.items(), key=lambda item: min(position["dte_sort"] for position in item[1]))
    for group_index, (ticker, ticker_positions) in enumerate(sorted_groups):
        ticker_positions.sort(key=lambda position: position["dte_sort"])
        if len(ticker_positions) == 1:
            rows.append(position_row(ticker_positions[0]))
            continue

        group_id = f'option-{group_index}-{re.sub(r"[^a-z0-9]+", "-", ticker.lower())}'
        sides = {position["position_side"] for position in ticker_positions}
        side_label = next(iter(sides)) if len(sides) == 1 else "Mixed"
        side_class = side_label.lower() if side_label != "Mixed" else "mixed"
        strikes = list(dict.fromkeys(strike_display(position["trade"]) for position in ticker_positions))
        expirations = list(dict.fromkeys(position["trade"].get("expiration") or "-" for position in ticker_positions))
        nearest_dte = ticker_positions[0]["dte"]
        nearest_dte_class = ticker_positions[0]["dte_class"]
        total_group_capital = sum(position["capital"] for position in ticker_positions)
        source_names = {broker_source_for_row(position["trade"]) for position in ticker_positions}
        source_display = broker_source_badge(next(iter(source_names))) if len(source_names) == 1 else f'<span class="option-group-summary-text">{len(source_names)} sources</span>'
        expiration_display = expirations[0] if len(expirations) == 1 else f'{len(expirations)} expirations'
        rows.append(f'''<tr class="option-position-group-row">
          <td><button class="option-position-toggle" type="button" data-option-group-toggle="{group_id}" aria-expanded="false"><span class="option-position-chevron" aria-hidden="true"></span><b>{escape(ticker)}</b><small>{len(ticker_positions)}</small></button></td>
          <td>{source_display}</td>
          <td><span class="option-group-summary-text">{len(ticker_positions)} positions</span></td>
          <td><span class="position-side {side_class}">{side_label}</span></td>
          <td><span class="option-group-strikes" title="{escape(', '.join(strikes))}">{escape(' / '.join(strikes))}</span></td>
          <td class="{nearest_dte_class}">{nearest_dte if nearest_dte is not None else "-"}</td>
          <td><span class="option-group-summary-text">{escape(expiration_display)}</span></td>
          <td>{money(total_group_capital)}</td>
          <td></td>
        </tr>''')
        rows.extend(position_row(position, group_id) for position in ticker_positions)
    total_capital = sum(number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0 for trade in active_positions(trades))
    if not rows:
        body = '<div class="empty">No open positions.</div>'
    else:
        body = f'''<div class="panel-kpi"><span>Open capital</span><strong>{money(total_capital)}</strong></div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Source</th><th>Strategy</th><th>Position</th><th>Strike</th><th>DTE</th><th>Expiration</th><th>Capital</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'''
    return f'<section class="panel open-risk-panel"><div class="panel-head"><h2>Open Positions Risk</h2><span>{len(active_positions(trades))} open</span></div>{body}</section>'


def expiration_panel(trades) -> str:
    grouped = {}
    today = date.today()
    for trade in active_positions(trades):
        expiration = parse_date(trade.get("expiration"))
        if not expiration:
            continue
        item = grouped.setdefault(expiration, {"count": 0, "capital": 0.0, "tickers": set()})
        item["count"] += 1
        item["capital"] += number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        item["tickers"].add(trade["ticker"])
    cards = []
    for expiration, item in sorted(grouped.items())[:8]:
        dte = (expiration - today).days
        cards.append(f'''<div class="expiry-card">
          <b>{expiration.strftime("%b %d")}</b>
          <span class="{"loss" if dte <= 7 else ""}">{dte} DTE</span>
          <strong>{money(item["capital"])}</strong>
          <small>{item["count"]} positions - {", ".join(sorted(item["tickers"])[:4])}</small>
        </div>''')
    if not cards:
        cards.append('<div class="empty">No upcoming expirations.</div>')
    return f'<section class="panel"><div class="panel-head"><h2>Expiration Watch</h2><span>open positions</span></div><div class="expiry-grid">{"".join(cards)}</div></section>'


def current_holdings_monitor_panel() -> str:
    holdings = exclude_fidelity_holdings(all_holdings())
    total_value = sum(holding.get("market_value") or 0 for holding in holdings)
    rows = []
    for holding in holdings[:10]:
        pnl = holding.get("unrealized_pnl") or 0
        edit_href = (
            f'/symbol/{quote(holding["ticker"])}'
            if holding.get("source") == "stock_trades"
            else f'/holding/{holding["id"]}/edit'
        )
        rows.append(f'''<tr>
          <td><a href="/symbol/{quote(holding["ticker"])}"><b>{escape(holding["ticker"])}</b></a></td>
          <td>{broker_source_badge(broker_source_for_row(holding))}</td>
          <td>{num(holding.get("shares"))}</td>
          <td>{money(holding.get("avg_cost"))}</td>
          <td>{money(holding.get("current_price"))}</td>
          <td>{money(holding.get("market_value"))}</td>
          <td>{pct(holding.get("allocation_pct"))}</td>
          <td class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</td>
          <td class="{"positive" if (holding.get("pnl_pct") or 0) >= 0 else "negative"}">{pct(holding.get("pnl_pct"))}</td>
          <td><a class="text-button" href="{edit_href}">Edit</a></td>
        </tr>''')
    if not rows:
        body = '<div class="empty">No current holdings yet.</div>'
    else:
        body = f'''<div class="panel-kpi"><span>Total holdings</span><strong>{money(total_value)}</strong></div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Source</th><th>Shares</th><th>Avg cost</th><th>Current</th><th>Value</th><th>Allocation</th><th>Unrealized P&L</th><th>Return</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'''
    return f'''<section class="panel open-risk-panel">
      <div class="panel-head"><h2>Current Holdings</h2><div class="panel-head-actions"><span>{len(holdings)} positions</span><form method="post" action="/holdings/refresh-prices"><input type="hidden" name="return_to" value="/"><button class="button secondary small-button" type="submit">Refresh prices</button></form></div></div>
      {body}
    </section>'''


def combined_holdings_monitor_panel(option_trades, include_stocks=True, brokers=None) -> str:
    today = date.today()
    option_positions = []
    for trade in active_positions(option_trades):
        expiration = parse_date(trade.get("expiration"))
        dte = (expiration - today).days if expiration else None
        capital = number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        position_side, position_class = option_position_side(trade)
        option_positions.append({
            "trade": trade,
            "expiration": expiration,
            "dte": dte,
            "dte_sort": dte if dte is not None else 99999,
            "capital": capital,
            "position_side": position_side,
            "position_class": position_class,
        })

    grouped = {}
    for position in option_positions:
        grouped.setdefault(position["trade"]["ticker"], []).append(position)

    def edit_href(trade):
        if trade.get("source") == "other_option":
            trade_id = str(trade["id"]).replace("other-option-", "")
            path = f"/other-option/{trade_id}/edit"
        else:
            path = f'/trade/{trade["id"]}/edit'
        return f'{path}?{urlencode({"return_to": "/"})}'

    def compact_date(value):
        return f"{value.month}/{value.day}/{value.year}" if value else "No expiry"

    def option_holding_lines(trade):
        ticker = escape(trade["ticker"])
        is_iron_condor = trade.get("strategy") == "Iron Condor"
        option_type = str(trade.get("option_type") or "").strip().title()
        if option_type not in {"Call", "Put"}:
            strategy_lower = str(trade.get("strategy") or "").lower()
            option_type = "Put" if "put" in strategy_lower else "Call" if "call" in strategy_lower else "Option"
        strike_parts = [part.strip() for part in strike_display(trade).split("/") if part.strip()]
        strikes = " / ".join(f"${part.lstrip('$')}" for part in strike_parts) or "-"
        option_word = "Iron Condor" if is_iron_condor else f"{option_type}s" if len(strike_parts) > 1 else option_type
        contracts = number(trade.get("contracts"), 0) or 0
        contract_count = num(contracts)
        strategy = str(trade.get("strategy") or "Option")
        strategy_lower = strategy.lower()
        if "credit spread" in strategy_lower:
            descriptor = "Credit Spread" if contracts == 1 else "Credit Spreads"
        elif "debit spread" in strategy_lower:
            descriptor = "Debit Spread" if contracts == 1 else "Debit Spreads"
        elif "covered call" in strategy_lower:
            descriptor = "Covered Call" if contracts == 1 else "Covered Calls"
        elif "sell put" in strategy_lower:
            descriptor = "Short Put" if contracts == 1 else "Short Puts"
        elif "buyer" in strategy_lower or "single option" in strategy_lower:
            descriptor = "Buy" if contracts == 1 else "Buys"
        else:
            descriptor = strategy
        expiration = parse_date(trade.get("expiration"))
        primary = ticker
        strike_label = f"{strikes} {escape(option_word)}"
        secondary = f"{compact_date(expiration)} · {contract_count} {escape(descriptor)}"
        return primary, strike_label, secondary

    def option_row(position, group_id=""):
        trade = position["trade"]
        attrs = f' class="option-position-child" data-option-group-row="{group_id}" hidden' if group_id else ""
        primary, strike_label, secondary = option_holding_lines(trade)
        return f'''<tr{attrs}>
          <td><div class="holding-primary"><a class="holding-edit-link" href="{edit_href(trade)}">{primary}</a>{broker_source_badge(broker_source_for_row(trade))}</div><div class="holding-secondary">{secondary}</div></td>
          <td><a class="holding-strike-link" href="{edit_href(trade)}">{strike_label}</a></td>
          <td><span class="position-side {position["position_class"]}">{escape(position["position_side"])}</span></td>
          <td class="holding-exposure">{money(position["capital"])}</td>
        </tr>'''

    rows = []
    sorted_groups = sorted(grouped.items(), key=lambda item: min(position["dte_sort"] for position in item[1]))
    for group_index, (ticker, positions) in enumerate(sorted_groups):
        positions.sort(key=lambda position: position["dte_sort"])
        if len(positions) == 1:
            rows.append(option_row(positions[0]))
            continue
        group_id = f'holding-{group_index}-{re.sub(r"[^a-z0-9]+", "-", ticker.lower())}'
        sides = {position["position_side"] for position in positions}
        side_label = next(iter(sides)) if len(sides) == 1 else "Mixed"
        side_class = side_label.lower() if side_label != "Mixed" else "mixed"
        source_names = {broker_source_for_row(position["trade"]) for position in positions}
        source = next(iter(source_names)) if len(source_names) == 1 else None
        total_contracts = sum(number(position["trade"].get("contracts"), 0) or 0 for position in positions)
        nearest_expiration = positions[0]["expiration"]
        group_strikes = list(dict.fromkeys(option_holding_lines(position["trade"])[1] for position in positions))
        rows.append(f'''<tr class="option-position-group-row">
          <td><div class="holding-primary"><button class="option-position-toggle" type="button" data-option-group-toggle="{group_id}" aria-expanded="false"><span class="option-position-chevron" aria-hidden="true"></span><b>{escape(ticker)}</b><small>{len(positions)}</small></button>{broker_source_badge(source) if source else ""}</div><div class="holding-secondary">{compact_date(nearest_expiration)} nearest · {num(total_contracts)} contracts</div></td>
          <td><span class="holding-group-strikes" title="{escape(', '.join(group_strikes))}">{escape(' · '.join(group_strikes))}</span></td>
          <td><span class="position-side {side_class}">{side_label}</span></td>
          <td class="holding-exposure">{money(sum(position["capital"] for position in positions))}</td>
        </tr>''')
        rows.extend(option_row(position, group_id) for position in positions)

    holdings = filter_holdings_by_brokers(all_holdings(), brokers) if include_stocks else []
    for holding in holdings:
        market_value = holding.get("market_value") or 0
        pnl = holding.get("unrealized_pnl") or 0
        pnl_class = "positive" if pnl >= 0 else "negative"
        stock_edit_href = (
            f'/symbol/{quote(holding["ticker"])}'
            if holding.get("source") == "stock_trades"
            else f'/holding/{holding["id"]}/edit'
        )
        stock_title = f'Avg {money(holding.get("avg_cost"))} | Current {money(holding.get("current_price"))}'
        rows.append(f'''<tr class="stock-holding-row">
          <td><div class="holding-primary"><a class="holding-edit-link" href="{stock_edit_href}">{escape(holding["ticker"])}</a>{broker_source_badge(broker_source_for_row(holding))}</div><div class="holding-secondary">{money(holding.get("avg_cost"))} avg · {money(holding.get("current_price"))} current</div></td>
          <td><span class="holding-stock-qty">{num(holding.get("shares"))} Shares</span></td>
          <td><span class="position-side long">Long</span></td>
          <td class="holding-exposure" title="{escape(stock_title)}">{money(market_value)}<small class="{pnl_class}">{money(pnl)} · {pct(holding.get("pnl_pct"))}</small></td>
        </tr>''')

    option_capital = sum(position["capital"] for position in option_positions)
    stock_value = sum(holding.get("market_value") or 0 for holding in holdings)
    if not rows:
        body = '<div class="empty">No current holdings yet.</div>'
    else:
        body = f'''<div class="panel-kpi unified-holdings-kpi"><span>Total exposure <small>Options {money(option_capital)} · Stocks {money(stock_value)}</small></span><strong>{money(option_capital + stock_value)}</strong></div>
        <div class="table-wrap unified-holdings-table"><table><thead><tr><th>Holding</th><th>Strike</th><th>Side</th><th>Exposure</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'''
    return f'<section class="panel open-risk-panel unified-holdings-panel">{body}</section>'


def recent_trades_panel(trades, href="/trades") -> str:
    def edit_href(trade):
        if trade.get("source") == "day_trade":
            path = f'/day-trade/{str(trade["id"]).replace("day-", "")}/edit'
        elif trade.get("source") == "stock_trade":
            path = f'/stock-trade/{str(trade["id"]).replace("stock-", "")}/edit'
        elif trade.get("source") == "other_option":
            path = f'/other-option/{str(trade["id"]).replace("other-option-", "")}/edit'
        else:
            path = f'/trade/{trade["id"]}/edit'
        return f'{path}?{urlencode({"return_to": "/"})}'

    rows = []
    for trade in trades[:10]:
        pnl = number(trade.get("net_pnl"), 0) or 0
        trade_pl = number(trade.get("trade_pl_pct"), 0) or 0
        pnl_class = "positive" if pnl >= 0 else "negative"
        status = escape(str(trade.get("status") or "-"))
        opened = parse_date(trade.get("open_date"))
        opened_label = f"{opened.month}/{opened.day}/{opened.year}" if opened else escape(str(trade.get("open_date") or "-"))
        rows.append(f'''<tr{earnings_row_class(trade)}>
          <td><div class="holding-primary"><a class="holding-edit-link" href="{edit_href(trade)}">{escape(trade["ticker"])}</a>{broker_source_badge(broker_source_for_row(trade))}{earnings_marker(trade)}</div><div class="holding-secondary">{opened_label} · {escape(str(trade.get("strategy") or "-"))}</div></td>
          <td><span class="pill {status.lower()}">{status}</span></td>
          <td class="recent-trade-pnl {pnl_class}">{money(pnl)}<small>{pct(trade_pl)}</small></td>
        </tr>''')
    rows = "".join(rows)
    if not rows:
        rows = '<tr><td colspan="3" class="empty">No trades yet.</td></tr>'
    return f'''<section class="panel recent-trades-panel">
      <div class="panel-head"><h2>Recent trades</h2><a href="{escape(href)}">View all</a></div>
      <div class="table-wrap compact-recent-table"><table><thead><tr><th>Trade</th><th>Status</th><th>P&L</th></tr></thead><tbody>{rows}</tbody></table></div>
    </section>'''


def position_alert_items(trades) -> list[tuple[str, str, str, str, date, int]]:
    open_rows = active_positions(trades)
    alerts = []
    today = date.today()
    for trade in open_rows:
        expiration = parse_date(trade.get("expiration"))
        if not expiration:
            continue
        dte = (expiration - today).days
        if 0 <= dte <= 7:
            alerts.append(("urgent", trade["ticker"], f"{dte} DTE", f"{trade['strategy']} expires {trade.get('expiration')}", expiration, 0))
        elif 8 <= dte <= 14:
            alerts.append(("watch", trade["ticker"], f"{dte} DTE", f"{trade['strategy']} expires {trade.get('expiration')}", expiration, 0))
    symbols = {trade.get("ticker", "").upper() for trade in open_rows if trade.get("ticker")}
    symbols.update(holding.get("ticker", "").upper() for holding in all_holdings() if holding.get("ticker"))
    for symbol in sorted(symbols)[:24]:
        item, _error = next_earnings_for_symbol(symbol, allow_fetch=False)
        if not item:
            continue
        report_date = parse_date(item.get("date"))
        if not report_date:
            continue
        days_until = (report_date - today).days
        if 0 <= days_until <= 14:
            hour = item.get("hour") or "TBD"
            eps = f" EPS est. {num(item.get('eps_estimate'))}" if item.get("eps_estimate") is not None else ""
            revenue = f" Revenue est. {compact_money(item.get('revenue_estimate'))}" if item.get("revenue_estimate") is not None else ""
            alerts.append(("earnings", symbol, f"Earnings in {days_until}D", f"{report_date.isoformat()} {hour}{eps}{revenue}", report_date, 1))
    return sorted(alerts, key=lambda item: (item[4], item[5], item[1]))


def position_alert_cards(alerts, limit=6) -> str:
    if not alerts:
        return '<div class="alert-card clear-alert"><b>All clear</b><span>No open positions expiring or tracked earnings within 14 days.</span></div>'
    return "".join(
        f'<a class="alert-card {tone}" href="/symbol/{quote(ticker)}"><b>{escape(ticker)}</b><strong>{escape(title)}</strong><span>{escape(note)}</span></a>'
        for tone, ticker, title, note, _event_date, _priority in alerts[:limit]
    )


def position_notification_menu() -> str:
    alerts = position_alert_items(all_trades())
    dot = '<span class="notification-dot" aria-hidden="true"></span>' if alerts else ''
    return f'''<div class="notification-menu" data-notification-menu>
      <button class="notification-button {"has-alerts" if alerts else ""}" type="button" aria-label="Open position alerts" aria-expanded="false" data-notification-button>
        <span class="mail-icon" aria-hidden="true"></span>{dot}
      </button>
      <div class="notification-popover" data-notification-popover>
        <div class="notification-head"><b>Position & Earnings Alerts</b><span>{len(alerts)} active signals</span></div>
        <div class="alerts-grid">{position_alert_cards(alerts, 8)}</div>
      </div>
    </div>'''


def position_alerts_panel(trades) -> str:
    alerts = position_alert_items(trades)
    content = position_alert_cards(alerts, 6)
    return f'''<section class="panel alerts-panel">
      <div class="panel-head"><h2>Position & Earnings Alerts</h2><span>{len(alerts)} active signals</span></div>
      <div class="alerts-grid">{content}</div>
    </section>'''


def weekly_win_rates(closed_trades: list[tuple[date, float]]) -> dict[date, float]:
    weekly_outcomes: dict[date, list[int]] = {}
    for closed, pnl in closed_trades:
        week_start = closed - timedelta(days=closed.weekday())
        weekly_outcomes.setdefault(week_start, []).append(1 if pnl > 0 else 0)
    return {
        week_start: sum(outcomes) / len(outcomes)
        for week_start, outcomes in weekly_outcomes.items()
        if outcomes
    }


def capital_usage_chart(trades, range_key="all", custom_start="", custom_end="") -> str:
    start, end, range_key, range_label = resolve_perf_range(trades, range_key, custom_start, custom_end)
    if not start or not end:
        return '<section class="panel capital-panel"><div class="empty">No capital history yet.</div></section>'
    width, height = 760, 260
    left, right, top, bottom = 16, 118, 20, 36
    total_days = max((end - start).days, 1)
    capital_intervals = []
    closed_trades = []
    for trade in trades:
        opened = parse_date(trade.get("open_date"))
        closed = parse_date(trade.get("close_date")) or end
        if not opened or closed < start or opened > end:
            continue
        capital = number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        if capital:
            capital_intervals.append((max(opened, start), min(closed, end), capital))
        actual_close = parse_date(trade.get("close_date"))
        if actual_close and start <= actual_close <= end and trade.get("net_pnl") is not None:
            closed_trades.append((actual_close, number(trade.get("net_pnl"), 0) or 0))
    closed_trades.sort(key=lambda item: item[0])
    capital_changes = {}
    for opened, closed, capital in capital_intervals:
        capital_changes[opened] = capital_changes.get(opened, 0.0) + capital
        after_close = closed + timedelta(days=1)
        capital_changes[after_close] = capital_changes.get(after_close, 0.0) - capital
    win_rates = weekly_win_rates(closed_trades)
    points = []
    current = start
    current_capital = 0.0
    while current <= end:
        current_capital += capital_changes.get(current, 0.0)
        week_start = current - timedelta(days=current.weekday())
        win_rate = win_rates.get(week_start)
        points.append((current, current_capital, win_rate))
        current += timedelta(days=1)
    capital_values = [capital for _, capital, _win_rate in points] + [0]
    max_v = max(capital_values) or 1
    upper_top, upper_base = 20, 124
    lower_top, lower_base = 136, height - bottom

    def x_for(day):
        return left + ((day - start).days / total_days) * (width - left - right)

    def y_for(value):
        return upper_base - (max(value, 0) / max_v) * (upper_base - upper_top)

    def y_for_rate(value):
        if value is None:
            return None
        return lower_top + min(max(value, 0), 1) * (lower_base - lower_top)

    chart_points = sampled_chart_points(points)
    plot_width = width - left - right
    bar_width = max(1.2, min(18.0, (plot_width / max(len(chart_points), 1)) * 0.76))
    capital_bars = "".join(
        f'<rect x="{max(left, min(x_for(day) - bar_width / 2, width - right - bar_width)):.2f}" '
        f'y="{y_for(capital):.2f}" width="{bar_width:.2f}" '
        f'height="{max(upper_base - y_for(capital), 0.6):.2f}" class="capital-bar"/>'
        for day, capital, _win_rate in chart_points
    )
    win_rate_bars = "".join(
        f'<rect x="{max(left, min(x_for(day) - bar_width / 2, width - right - bar_width)):.2f}" '
        f'y="{lower_top:.2f}" width="{bar_width:.2f}" '
        f'height="{max(y_for_rate(win_rate) - lower_top, 0.6):.2f}" class="capital-bar win-rate-bar"/>'
        for day, _capital, win_rate in chart_points
        if win_rate is not None
    )
    hover_points = [
        {
            "x": round(x_for(day), 2),
            "y": round(y_for(capital), 2),
            "label": day.strftime("%m/%d/%Y"),
            "display": f"{money(capital)} | Weekly win {pct(win_rate)}",
        }
        for day, capital, win_rate in chart_points
    ]
    hover_data = escape(json.dumps(hover_points, separators=(",", ":")), quote=True)
    capital_grid_values = [max_v, max_v / 2, 0]
    capital_grid = "".join(f'<line x1="{left}" x2="{width-right}" y1="{y_for(value):.2f}" y2="{y_for(value):.2f}" class="perf-grid-line"/>' for value in capital_grid_values)
    capital_labels = "".join(f'<text x="{width-right+10}" y="{y_for(value)+4:.2f}" class="perf-y-label">{compact_currency(value)}</text>' for value in capital_grid_values)
    win_grid_values = [0, 0.5, 1]
    win_grid = "".join(f'<line x1="{left}" x2="{width-right}" y1="{y_for_rate(value):.2f}" y2="{y_for_rate(value):.2f}" class="perf-grid-line win-rate-grid"/>' for value in win_grid_values)
    win_labels = "".join(f'<text x="{width-right+10}" y="{y_for_rate(value)+4:.2f}" class="perf-y-label win-rate-label">{pct(value)}</text>' for value in win_grid_values)
    legend = f'''<span class="capital-legend"><i class="capital-key capital-key-capital"></i>Capital <i class="capital-key capital-key-win"></i>Weekly win rate</span>'''
    peak = max(capital_values)
    return f'''<section class="panel capital-panel">
      <div class="panel-head"><h2>Capital Usage</h2><span>{escape(range_label)} - peak {money(peak)} {legend}</span></div>
      <svg class="capital-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Capital usage bars over time" data-points="{hover_data}">
        {capital_grid}<g class="capital-bars capital-bars-upper">{capital_bars}</g>
        <line x1="{left}" x2="{width-right}" y1="130" y2="130" class="capital-quadrant-axis"/>
        {win_grid}<g class="capital-bars win-rate-bars">{win_rate_bars}</g>{capital_labels}{win_labels}
        <text x="{left}" y="{height - 8}" class="perf-x-label">{start.strftime("%m/%d/%Y")}</text>
        <text x="{width-right}" y="{height - 8}" text-anchor="end" class="perf-x-label">{end.strftime("%m/%d/%Y")}</text>
        <line class="perf-hover-x" x1="{left}" x2="{width-right}" y1="0" y2="0"/>
        <line class="perf-hover-y" x1="0" x2="0" y1="{upper_top}" y2="{lower_base}"/>
        <circle class="perf-hover-dot capital-hover-dot" cx="0" cy="0" r="5"/>
        <rect class="perf-hit-area capital-hit-area" x="{left}" y="{upper_top}" width="{width-left-right}" height="{lower_base-upper_top}"/>
      </svg>
    </section>'''


def monthly_summary_panel(trades) -> str:
    monthly = {}
    for trade in trades:
        closed = parse_date(trade.get("close_date"))
        if not closed or trade.get("net_pnl") is None:
            continue
        key = date(closed.year, closed.month, 1)
        item = monthly.setdefault(key, {"trades": [], "pnl": 0.0, "wins": 0})
        item["trades"].append(trade)
        item["pnl"] += trade["net_pnl"] or 0
        if trade["net_pnl"] > 0:
            item["wins"] += 1
    cards = []
    for month, item in sorted(monthly.items(), reverse=True)[:6]:
        trades_for_month = item["trades"]
        peak = peak_concurrent_capital(trades_for_month, month, date(month.year, month.month, calendar.monthrange(month.year, month.month)[1]))
        best = max(trades_for_month, key=lambda trade: trade["net_pnl"])
        worst = min(trades_for_month, key=lambda trade: trade["net_pnl"])
        cards.append(f'''<div class="month-card">
          <b>{month.strftime("%b %Y")}</b>
          <strong class="{"gain" if item["pnl"] >= 0 else "loss"}">{money(item["pnl"])}</strong>
          <span>PL% {pct(pl_pct(item["pnl"], peak))}</span>
          <span>Win {pct(item["wins"] / len(trades_for_month))}</span>
          <small>Best {escape(best["ticker"])} - Worst {escape(worst["ticker"])}</small>
        </div>''')
    if not cards:
        cards.append('<div class="empty">No monthly summaries yet.</div>')
    return f'<section class="panel"><div class="panel-head"><h2>Monthly Summary</h2><span>latest 6 months</span></div><div class="month-grid">{"".join(cards)}</div></section>'


def realized_window_stats(trades, start: date, end: date) -> dict:
    rows = [
        trade for trade in trades
        if trade.get("net_pnl") is not None
        and (closed := parse_date(trade.get("close_date")))
        and start <= closed <= end
    ]
    pnl = sum(trade.get("net_pnl") or 0 for trade in rows)
    wins = sum((trade.get("net_pnl") or 0) > 0 for trade in rows)
    peak = peak_concurrent_capital(rows, start, end) if rows else 0
    return {
        "pnl": pnl,
        "trades": len(rows),
        "win_rate": wins / len(rows) if rows else None,
        "pl_pct": pl_pct(pnl, peak),
    }


def period_summary_panel(trades) -> str:
    today = date.today()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    month_start = date(today.year, today.month, 1)
    ytd_start = date(today.year, 1, 1)
    periods = (
        ("This week", week_start, today),
        ("This month", month_start, today),
        ("YTD", ytd_start, today),
    )
    cards = []
    for label, start, end in periods:
        stats = realized_window_stats(trades, start, end)
        cls = "gain" if stats["pnl"] >= 0 else "loss"
        cards.append(f'''<div class="period-card">
          <span>{escape(label)}</span>
          <strong class="{cls}">{money(stats["pnl"])}</strong>
          <small>{stats["trades"]} trades - Win {pct(stats["win_rate"])} - PL% {pct(stats["pl_pct"])}</small>
        </div>''')
    return f'<section class="panel period-panel"><div class="panel-head"><h2>Period Summary</h2><span>realized by close date</span></div><div class="period-grid">{"".join(cards)}</div></section>'


def max_drawdown_stats(trades) -> dict:
    closes = trade_close_dates(trades)
    if not closes:
        return {"drawdown": None, "drawdown_pct": None, "peak": None, "trough": None}
    start, end = closes[0], closes[-1]
    daily = {}
    for trade in trades:
        closed = parse_date(trade.get("close_date"))
        if closed and trade.get("net_pnl") is not None:
            daily[closed] = daily.get(closed, 0.0) + (trade.get("net_pnl") or 0)
    cumulative = 0.0
    running_peak = 0.0
    peak_day = start
    worst = 0.0
    worst_peak_day = start
    trough_day = start
    current = start
    while current <= end:
        cumulative += daily.get(current, 0.0)
        if cumulative > running_peak:
            running_peak = cumulative
            peak_day = current
        drawdown = cumulative - running_peak
        if drawdown < worst:
            worst = drawdown
            worst_peak_day = peak_day
            trough_day = current
        current += timedelta(days=1)
    peak_capital = peak_concurrent_capital(trades, start, end)
    return {
        "drawdown": worst,
        "drawdown_pct": worst / peak_capital if peak_capital else None,
        "peak": worst_peak_day,
        "trough": trough_day,
    }


def risk_snapshot_panel(trades) -> str:
    open_rows = active_positions(trades)
    open_capital = sum(number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0 for trade in open_rows)
    dtes = [
        (parse_date(trade.get("expiration")) - date.today()).days
        for trade in open_rows
        if parse_date(trade.get("expiration"))
    ]
    min_dte = min(dtes) if dtes else None
    drawdown = max_drawdown_stats(trades)
    cards = (
        ("Open capital", money(open_capital), f"{len(open_rows)} open positions", ""),
        ("Nearest DTE", str(min_dte) if min_dte is not None else "-", "days until closest expiration", "warning" if min_dte is not None and min_dte <= 7 else ""),
        ("Max drawdown", money(drawdown["drawdown"]), f'{drawdown["peak"] or "-"} to {drawdown["trough"] or "-"}', "loss" if (drawdown["drawdown"] or 0) < 0 else ""),
        ("Drawdown %", pct(drawdown["drawdown_pct"]), "vs peak concurrent capital", "loss" if (drawdown["drawdown_pct"] or 0) < 0 else ""),
    )
    content = "".join(f'<div class="risk-card {cls}"><span>{label}</span><strong>{value}</strong><small>{escape(note)}</small></div>' for label, value, note, cls in cards)
    return f'<section class="panel risk-panel"><div class="panel-head"><h2>Risk Snapshot</h2><span>open risk & realized curve</span></div><div class="risk-grid">{content}</div></section>'


def risk_tabs_panel(trades) -> str:
    open_count = len(active_positions(trades))
    recent_count = min(len(trades), 10)
    return f'''<section class="panel risk-tabs-panel">
      <div class="panel-head compact-tabs-head"><span>{open_count} open positions - {recent_count} recent trades</span></div>
      <div class="tab-shell">
        <input type="radio" name="risk_tab" id="risk-tab-open" checked>
        <input type="radio" name="risk_tab" id="risk-tab-expiration">
        <input type="radio" name="risk_tab" id="risk-tab-recent">
        <div class="tab-buttons">
          <label for="risk-tab-open">Open Positions</label>
          <label for="risk-tab-expiration">Expiration Watch</label>
          <label for="risk-tab-recent">Recent Trades</label>
        </div>
        <div class="tab-panes">
          <div class="tab-pane open-pane">{open_positions_risk_panel(trades)}</div>
          <div class="tab-pane expiration-pane">{expiration_panel(trades)}</div>
          <div class="tab-pane recent-pane">{recent_trades_panel(trades)}</div>
        </div>
      </div>
    </section>'''


def risk_tabs_panel(trades, mode="options", show_holdings=True, brokers=None) -> str:
    option_trades = [trade for trade in trades if trade_book_for_row(trade) != "stock"]
    open_positions = active_positions(option_trades)
    open_count = len(open_positions)
    recent_count = min(len(trades), 10)
    holdings = filter_holdings_by_brokers(all_holdings(), brokers) if show_holdings or mode == "stock-trades" else []
    if mode == "day-trades":
        return f'''<section class="panel risk-tabs-panel">
          <div class="panel-head compact-tabs-head"><span>{recent_count} recent trades</span></div>
          {recent_trades_panel(trades, "/trades?view=day-trades")}
        </section>'''
    if mode == "stock-trades":
        return f'''<section class="panel risk-tabs-panel">
          <div class="panel-head compact-tabs-head"><span>current holdings | {recent_count} recent trades</span></div>
          <div class="tab-shell">
            <input type="radio" name="risk_tab" id="risk-tab-open" checked>
            <input type="radio" name="risk_tab" id="risk-tab-recent">
            <div class="tab-buttons">
              <label for="risk-tab-open">Current Holdings</label>
              <label for="risk-tab-recent">Recent Trades</label>
            </div>
            <div class="tab-panes">
              <div class="tab-pane open-pane">{current_holdings_monitor_panel()}</div>
              <div class="tab-pane recent-pane">{recent_trades_panel(trades, "/trades?view=stock-trades")}</div>
            </div>
          </div>
        </section>'''
    holdings_summary = f' | {len(holdings)} current holdings' if show_holdings else ""
    holdings_refresh = (
        '<form method="post" action="/holdings/refresh-prices">'
        '<input type="hidden" name="return_to" value="/">'
        '<button class="button secondary small-button" type="submit">Refresh prices</button>'
        '</form>'
        if show_holdings else ""
    )
    return f'''<section class="panel risk-tabs-panel">
      <div class="panel-head compact-tabs-head"><span>{open_count} open options{holdings_summary} | {recent_count} recent trades</span>{holdings_refresh}</div>
      <div class="tab-shell">
        <input type="radio" name="risk_tab" id="risk-tab-holdings" checked>
        <input type="radio" name="risk_tab" id="risk-tab-expiration">
        <input type="radio" name="risk_tab" id="risk-tab-recent">
        <div class="tab-buttons">
          <label for="risk-tab-holdings">Holdings</label>
          <label for="risk-tab-expiration">Expiration Watch</label>
          <label for="risk-tab-recent">Recent Trades</label>
        </div>
        <div class="tab-panes">
          <div class="tab-pane holdings-pane">{combined_holdings_monitor_panel(option_trades, show_holdings, brokers)}</div>
          <div class="tab-pane expiration-pane">{expiration_panel(option_trades)}</div>
          <div class="tab-pane recent-pane">{recent_trades_panel(trades)}</div>
        </div>
      </div>
    </section>'''


def analytics_tabs_panel(trades) -> str:
    return f'''<section class="panel analytics-tabs-panel">
      <div class="panel-head"><h2>Risk Review</h2><span>snapshot and concentration</span></div>
      <div class="tab-shell">
        <input type="radio" name="analytics_tab" id="analytics-tab-risk" checked>
        <input type="radio" name="analytics_tab" id="analytics-tab-exposure">
        <div class="tab-buttons">
          <label for="analytics-tab-risk">Risk Snapshot</label>
          <label for="analytics-tab-exposure">Ticker Exposure</label>
        </div>
        <div class="tab-panes">
          <div class="tab-pane analytics-risk-pane">{risk_snapshot_panel(trades)}</div>
          <div class="tab-pane analytics-exposure-pane">{ticker_exposure_panel(trades)}</div>
        </div>
      </div>
    </section>'''


def ticker_exposure_panel(trades) -> str:
    exposures = {}
    for trade in active_positions(trades):
        ticker = trade["ticker"]
        entry = exposures.setdefault(ticker, {"ticker": ticker, "options": 0.0, "stock": 0.0, "open": 0})
        entry["options"] += number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        entry["open"] += 1
    for holding in all_holdings():
        ticker = holding["ticker"]
        entry = exposures.setdefault(ticker, {"ticker": ticker, "options": 0.0, "stock": 0.0, "open": 0})
        entry["stock"] += holding.get("market_value") or 0
    rows = []
    total = sum(item["options"] + item["stock"] for item in exposures.values())
    for item in sorted(exposures.values(), key=lambda row: row["options"] + row["stock"], reverse=True)[:10]:
        exposure = item["options"] + item["stock"]
        share = exposure / total if total else None
        rows.append(f'''<tr>
          <td><a href="/symbol/{quote(item["ticker"])}"><b>{escape(item["ticker"])}</b></a></td>
          <td>{money(item["options"])}</td>
          <td>{money(item["stock"])}</td>
          <td>{money(exposure)}</td>
          <td>{pct(share)}</td>
          <td>{item["open"]}</td>
        </tr>''')
    if not rows:
        rows.append('<tr><td colspan="6" class="empty">No current ticker exposure yet.</td></tr>')
    return f'''<section class="panel exposure-panel">
      <div class="panel-head"><h2>Ticker Exposure</h2><span>open options + stock holdings</span></div>
      <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Options capital</th><th>Stock value</th><th>Total exposure</th><th>Share</th><th>Open</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
    </section>'''


def dashboard_switch(active_mode: str) -> str:
    return f'''<div class="dashboard-switch">
      <a class="{"active" if active_mode == "options" else ""}" href="/">Options Selling</a>
      <a class="{"active" if active_mode == "option-buyer" else ""}" href="/?dashboard=option-buyer">Option Buyer</a>
      <a class="{"active" if active_mode == "day-trades" else ""}" href="/?dashboard=day-trades">Day Trades</a>
      <a class="{"active" if active_mode == "stock-trades" else ""}" href="/?dashboard=stock-trades">Stock Trades</a>
    </div>'''


def dashboard_summary_list(metrics) -> str:
    rows = "".join(
        f'<div class="dashboard-summary-row"><span>{escape(label)}</span><strong class="{cls}">{value}</strong></div>'
        for label, value, cls in metrics
    )
    return f'''<section class="dashboard-summary dashboard-summary-list">
      {rows}
    </section>'''


def trade_extreme_value(rows, pnl_key, best=True) -> tuple[str, str]:
    if not rows:
        return "-", ""
    row = max(rows, key=lambda item: number(item.get(pnl_key), 0) or 0) if best else min(rows, key=lambda item: number(item.get(pnl_key), 0) or 0)
    value = number(row.get(pnl_key), 0) or 0
    ticker = escape(row.get("ticker") or "-")
    cls = "positive" if value >= 0 else "negative"
    return f"{ticker} {money(value)}", cls


def option_contract_total(rows) -> float:
    return sum(
        number(row.get("contracts"), 0) or 0
        for row in rows
        if row.get("source") != "stock_trade"
    )


def paginate_items(items, query, base_path, base_params=None, page_size=25):
    base_params = dict(base_params or {})
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / page_size))
    try:
        page = int(query.get("page", ["1"])[0])
    except ValueError:
        page = 1
    page = min(max(page, 1), total_pages)
    start = (page - 1) * page_size
    end = min(start + page_size, total_items)

    def page_href(page_number):
        params = dict(base_params)
        params["page"] = str(page_number)
        return f"{base_path}?{urlencode(query_param_items(params))}"

    if total_items:
        page_numbers = sorted(set([1, total_pages, page - 1, page, page + 1]))
        page_links = []
        previous = 0
        for page_number in page_numbers:
            if page_number < 1 or page_number > total_pages:
                continue
            if previous and page_number - previous > 1:
                page_links.append('<span class="pagination-gap">...</span>')
            page_links.append(
                f'<span class="pagination-current">{page_number}</span>'
                if page_number == page else
                f'<a href="{page_href(page_number)}">{page_number}</a>'
            )
            previous = page_number
        pagination = (
            f'<div class="pagination">'
            f'<span class="pagination-summary">Showing {start + 1}-{end} of {total_items}</span>'
            f'<div class="pagination-pages">'
            f'<a class="{"disabled" if page == 1 else ""}" href="{page_href(max(1, page - 1))}">Prev</a>'
            f'{"".join(page_links)}'
            f'<a class="{"disabled" if page == total_pages else ""}" href="{page_href(min(total_pages, page + 1))}">Next</a>'
            f'</div></div>'
        )
    else:
        pagination = '<div class="pagination"><span class="pagination-summary">Showing 0 of 0</span></div>'
    return items[start:end], pagination


def apply_table_sort(rows, query, valid_sort, default_sort, default_dir="desc"):
    sort_by = query.get("sort_by", [default_sort])[0]
    sort_dir = query.get("sort_dir", [default_dir])[0]
    sort_key = sort_by if sort_by in valid_sort else default_sort
    sort_dir = "asc" if sort_dir == "asc" else "desc"
    rows.sort(key=valid_sort[sort_key], reverse=sort_dir == "desc")
    return sort_key, sort_dir


def table_sort_link(base_path, base_params, sort_key, sort_dir, key, label):
    next_dir = "asc" if sort_key != key or sort_dir == "desc" else "desc"
    params = dict(base_params or {})
    params.update({"sort_by": key, "sort_dir": next_dir, "page": "1"})
    href = f"{base_path}?{urlencode({k: v for k, v in params.items() if v})}"
    active = "active" if sort_key == key else ""
    arrow = "+" if sort_key == key and sort_dir == "asc" else "-" if sort_key == key else "*"
    return f'<th class="sortable {active}"><a href="{href}">{escape(label)} <span>{arrow}</span></a></th>'


def stock_trade_dashboard_page(query=None) -> bytes:
    query = query or {}
    try:
        calendar_year = int(query.get("cal_year", [""])[0])
    except ValueError:
        calendar_year = None
    try:
        calendar_month = int(query.get("cal_month", [""])[0])
    except ValueError:
        calendar_month = None
    calendar_view = query.get("cal_view", ["month"])[0]
    perf_range = query.get("perf_range", ["ytd"])[0]
    perf_metric = query.get("perf_metric", ["pnl"])[0]
    perf_start = query.get("perf_start", [""])[0]
    perf_end = query.get("perf_end", [""])[0]
    trades = [stock_trade_as_trade(row) for row in all_stock_trades()]
    calendar_brokers = broker_filter_values(query, "cal_broker")
    performance_brokers = broker_filter_values(query, "perf_broker")
    calendar_trades = filter_trades_by_brokers(trades, calendar_brokers)
    performance_trades = filter_trades_by_brokers(trades, performance_brokers)
    calendar_extra = broker_filter_query_params(query, "cal_broker", calendar_brokers, {"cal_year", "cal_month", "cal_view"})
    performance_extra = broker_filter_query_params(query, "perf_broker", performance_brokers, {"perf_metric", "perf_range", "perf_start", "perf_end"})
    total_pnl = sum(trade.get("net_pnl") or 0 for trade in trades)
    winners = sum(1 for trade in trades if (trade.get("net_pnl") or 0) > 0)
    total_notional = sum(number(trade.get("capital_used"), 0) or 0 for trade in trades)
    total_pl_pct = total_pnl / total_notional if total_notional else None
    trade_pl_pcts = [trade.get("trade_pl_pct") for trade in trades if trade.get("trade_pl_pct") is not None]
    avg_trade_pl_pct = sum(trade_pl_pcts) / len(trade_pl_pcts) if trade_pl_pcts else None
    best, best_class = trade_extreme_value(trades, "net_pnl", True)
    worst, worst_class = trade_extreme_value(trades, "net_pnl", False)
    summary_metrics = (
        ("Realized net P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Notional", money(total_notional), ""),
        ("Trades", f"{len(trades):,}", ""),
        ("Win rate", pct(winners / len(trades) if trades else None), ""),
        ("Avg Trade P/L %", pct(avg_trade_pl_pct), "positive" if avg_trade_pl_pct is not None and avg_trade_pl_pct >= 0 else "negative"),
        ("Average P&L", money(total_pnl / len(trades) if trades else 0), "positive" if total_pnl >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    )
    summary_html = "".join(
        f'<div class="dashboard-summary-row"><span>{label}</span><strong class="{cls}">{value}</strong></div>'
        for label, value, cls in summary_metrics
    )
    body = f'''<div class="page-head"><div><p class="eyebrow">Stock performance</p><h1>Stock Trade Dashboard</h1>{dashboard_switch("stock-trades")}</div><div class="actions"><form method="post" action="/holdings/refresh-prices"><button class="button secondary" type="submit">Refresh prices</button></form><a class="button" href="/stock-trade/new">Record stock trade</a></div></div>
    <section class="dashboard-summary dashboard-summary-list">
      {summary_html}
    </section>
    <div class="section-divider"><span>Position Monitor</span></div>
    {risk_tabs_panel(trades, "stock-trades")}
    <div class="section-divider"><span>Calendar</span></div>
    {close_date_calendar(calendar_trades, calendar_year, calendar_month, calendar_view, calendar_extra)}
    <div class="section-divider"><span>Performance</span></div>
    <section class="dashboard-performance-card">
      {performance_chart(performance_trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)}
      {performance_range_controls(performance_trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)}
    </section>'''
    return layout("Stock Trade Dashboard - Option Ledger", body, "dashboard")


def option_activity_dashboard_page(query=None, *, mode: str, title: str, eyebrow: str, trades: list[dict], record_href: str, record_label: str) -> bytes:
    query = query or {}
    try:
        calendar_year = int(query.get("cal_year", [""])[0])
    except ValueError:
        calendar_year = None
    try:
        calendar_month = int(query.get("cal_month", [""])[0])
    except ValueError:
        calendar_month = None
    calendar_view = query.get("cal_view", ["month"])[0]
    perf_range = query.get("perf_range", ["ytd"])[0]
    perf_metric = query.get("perf_metric", ["pnl"])[0]
    perf_start = query.get("perf_start", [""])[0]
    perf_end = query.get("perf_end", [""])[0]
    calendar_brokers = broker_filter_values(query, "cal_broker")
    performance_brokers = broker_filter_values(query, "perf_broker")
    calendar_trades = filter_trades_by_brokers(trades, calendar_brokers)
    performance_trades = filter_trades_by_brokers(trades, performance_brokers)
    calendar_extra = broker_filter_query_params(query, "cal_broker", calendar_brokers, {"cal_year", "cal_month", "cal_view"})
    performance_extra = broker_filter_query_params(query, "perf_broker", performance_brokers, {"perf_metric", "perf_range", "perf_start", "perf_end"})
    total_pnl = sum(trade.get("net_pnl") or 0 for trade in trades)
    winners = sum(1 for trade in trades if (trade.get("net_pnl") or 0) > 0)
    total_contracts = option_contract_total(trades)
    total_notional = sum(number(trade.get("capital_used"), 0) or 0 for trade in trades)
    trade_pl_pcts = [trade.get("trade_pl_pct") for trade in trades if trade.get("trade_pl_pct") is not None]
    avg_trade_pl_pct = sum(trade_pl_pcts) / len(trade_pl_pcts) if trade_pl_pcts else None
    weighted_annualized = weighted_annualized_return(trades)
    best, best_class = trade_extreme_value(trades, "net_pnl", True)
    worst, worst_class = trade_extreme_value(trades, "net_pnl", False)
    summary_metrics = [
        ("Realized net P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Notional", money(total_notional), ""),
        ("Trades / Contracts", f"{len(trades):,} / {num(total_contracts)}", ""),
        ("Win rate", pct(winners / len(trades) if trades else None), ""),
        ("Avg Trade P/L %", pct(avg_trade_pl_pct), "positive" if avg_trade_pl_pct is not None and avg_trade_pl_pct >= 0 else "negative"),
        ("Avg P&L", money(total_pnl / len(trades) if trades else 0), "positive" if total_pnl >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    ]
    if mode == "option-buyer":
        summary_metrics.insert(
            5,
            ("Weighted annualized", pct(weighted_annualized), "positive" if weighted_annualized is not None and weighted_annualized >= 0 else "negative"),
        )
    summary_html = "".join(
        f'<div class="dashboard-summary-row"><span>{label}</span><strong class="{cls}">{value}</strong></div>'
        for label, value, cls in summary_metrics
    )
    body = f'''<div class="page-head"><div><p class="eyebrow">{escape(eyebrow)}</p><h1>{escape(title)}</h1>{dashboard_switch(mode)}</div><a class="button" href="{record_href}">{escape(record_label)}</a></div>
    <section class="dashboard-summary dashboard-summary-list">
      {summary_html}
    </section>
    <div class="section-divider"><span>Position Monitor</span></div>
    {risk_tabs_panel(trades, mode)}
    <div class="section-divider"><span>Calendar</span></div>
    {close_date_calendar(calendar_trades, calendar_year, calendar_month, calendar_view, calendar_extra)}
    <div class="section-divider"><span>Performance</span></div>
    <section class="dashboard-performance-card">
      {performance_chart(performance_trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)}
      {performance_range_controls(performance_trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)}
    </section>'''
    return layout(f"{title} - Option Ledger", body, "dashboard")


def option_buyer_dashboard_page(query=None) -> bytes:
    trades = [other_option_as_trade(row) for row in all_other_option_trades()]
    return option_activity_dashboard_page(
        query,
        mode="option-buyer",
        title="Option Buyer Dashboard",
        eyebrow="Buyer performance",
        trades=trades,
        record_href="/option-trade/new?book=buyer",
        record_label="Record trade",
    )


def day_trade_dashboard_page(query=None) -> bytes:
    trades = [day_trade_as_trade(row) for row in all_day_trades()]
    return option_activity_dashboard_page(
        query,
        mode="day-trades",
        title="Day Trade Dashboard",
        eyebrow="Intraday performance",
        trades=trades,
        record_href="/day-trade/new",
        record_label="Record day trade",
    )


def welcome_page(query=None) -> bytes:
    body = '''<div class="site-cover">
      <section class="dashboard-motion-hero" data-dashboard-hero>
        <div class="dashboard-hero-glow" aria-hidden="true"></div>
        <div class="dashboard-hero-copy">
          <p class="dashboard-hero-kicker"><i aria-hidden="true"></i><span>Local-first trading intelligence</span></p>
          <h1>Trading Dashboard</h1>
          <p class="dashboard-hero-type-line"><span>Built for</span> <strong data-dashboard-typing>stocks, options, and portfolios</strong><i aria-hidden="true"></i></p>
          <div class="dashboard-hero-chips">
            <span>Private by default</span><span>Bilingual workflow</span><span>Fast local analytics</span>
          </div>
          <div class="dashboard-hero-actions"><a class="button" href="/">Enter dashboard</a><a class="button secondary" href="/brokerage">View portfolio</a></div>
        </div>
        <div class="dashboard-hero-visual" aria-hidden="true">
          <div class="dashboard-hero-orbit orbit-one"></div>
          <div class="dashboard-hero-orbit orbit-two"></div>
          <div class="dashboard-hero-core"><small>LOCAL</small><b>&infin;</b><span>YOUR DATA</span></div>
          <div class="dashboard-hero-node node-stocks">STOCKS</div>
          <div class="dashboard-hero-node node-options">OPTIONS</div>
          <div class="dashboard-hero-node node-portfolio">PORTFOLIO</div>
        </div>
      </section>
    </div>'''
    return layout("Welcome - Option Ledger", body)


def dashboard_page(query=None) -> bytes:
    query = query or {}
    if query.get("dashboard", [""])[0] == "option-buyer":
        return option_buyer_dashboard_page(query)
    if query.get("dashboard", [""])[0] == "day-trades":
        return day_trade_dashboard_page(query)
    if query.get("dashboard", [""])[0] == "stock-trades":
        return stock_trade_dashboard_page(query)
    try:
        calendar_year = int(query.get("cal_year", [""])[0])
    except ValueError:
        calendar_year = None
    try:
        calendar_month = int(query.get("cal_month", [""])[0])
    except ValueError:
        calendar_month = None
    calendar_view = query.get("cal_view", ["month"])[0]
    perf_range = query.get("perf_range", ["ytd"])[0]
    perf_metric = query.get("perf_metric", ["pnl"])[0]
    perf_start = query.get("perf_start", [""])[0]
    perf_end = query.get("perf_end", [""])[0]
    brokers, books = dashboard_filter_values(query)
    scoped_trades = filter_dashboard_trades(symbol_trade_records(), brokers, books)
    calendar_extra = dashboard_filter_params(query, brokers, books, {"cal_year", "cal_month", "cal_view"})
    performance_extra = dashboard_filter_params(query, brokers, books, {"perf_metric", "perf_range", "perf_start", "perf_end"})
    range_controls = performance_range_controls(scoped_trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)
    trades = filter_trades_by_perf_range(scoped_trades, perf_range, perf_start, perf_end)
    closed = [t for t in trades if t["status"] != "Open" and t["net_pnl"] is not None]
    opened = [t for t in trades if t["status"] == "Open" and t["net_pnl"] is not None]
    realized = sum(t["net_pnl"] for t in closed)
    close_dates = trade_close_dates(trades)
    peak_capital = peak_concurrent_capital(trades, close_dates[0], close_dates[-1]) if close_dates else 0
    realized_pl_pct = pl_pct(realized, peak_capital)
    winners = sum(t["net_pnl"] > 0 for t in closed)
    win_rate = winners / len(closed) if closed else 0
    trade_pl_pcts = [t["trade_pl_pct"] for t in closed if t.get("trade_pl_pct") is not None]
    avg_trade_pl_pct = sum(trade_pl_pcts) / len(trade_pl_pcts) if trade_pl_pcts else None
    avg_win_pl, avg_win_pl_pct = average_outcome_pl_metrics(closed, True)
    avg_loss_pl, avg_loss_pl_pct = average_outcome_pl_metrics(closed, False)
    avg_trade_amount = (
        sum(trade_open_amount(t) for t in closed) / len(closed)
        if closed else 0
    )
    weighted_annualized = weighted_annualized_return(closed)
    best, best_class = trade_extreme_value(closed, "net_pnl", True)
    worst, worst_class = trade_extreme_value(closed, "net_pnl", False)
    total_contracts = option_contract_total(trades)
    primary_metrics = (
        ("Realized net P&L", money(realized), "positive" if realized >= 0 else "negative"),
        ("PL %", pct(realized_pl_pct) if realized_pl_pct is not None else "-", "positive" if realized_pl_pct is not None and realized_pl_pct >= 0 else "negative"),
    )
    secondary_metrics = (
        ("Win rate", pct(win_rate), ""),
        ("Trades / Contracts", f"{len(trades):,} / {num(total_contracts)}", ""),
        ("Weighted annualized", pct(weighted_annualized), "positive" if weighted_annualized is not None and weighted_annualized >= 0 else "negative"),
        ("Best / Worst", f'<span class="{best_class}">{best}</span> / <span class="{worst_class}">{worst}</span>', ""),
        ("Avg Win P/L / %", f"{money(avg_win_pl)} / {pct(avg_win_pl_pct)}", "positive"),
        ("Avg Loss P/L / %", f"{money(avg_loss_pl)} / {pct(avg_loss_pl_pct)}", "negative"),
    )
    summary_metrics = primary_metrics + secondary_metrics
    summary_html = "".join(
        f'<div class="dashboard-summary-row"><span>{label}</span><strong class="{cls}">{value}</strong></div>'
        for label, value, cls in summary_metrics
    )
    card_html = f'''<section class="dashboard-summary dashboard-summary-list">
      {summary_html}
    </section>'''

    body = f'''{dashboard_filter_panel(query, brokers, books, range_controls)}
    <div class="overview-dashboard-layout webull-dashboard-layout" data-dashboard-layout>
      <div class="overview-dashboard-column overview-dashboard-left webull-dashboard-side">
        {card_html}
        <div class="section-divider"><span>Position Monitor</span></div>
        {risk_tabs_panel(trades, show_holdings="stock" in books, brokers=brokers)}
      </div>
      <div class="webull-dashboard-splitter" data-dashboard-splitter title="Drag to resize"></div>
      <div class="overview-dashboard-column overview-dashboard-right webull-dashboard-main">
        <div class="webull-dashboard-grid">
          {performance_chart(trades, perf_range, perf_metric, perf_start, perf_end, extra_params=performance_extra)}
          {capital_usage_chart(trades, perf_range, perf_start, perf_end)}
          {close_date_calendar(trades, calendar_year, calendar_month, calendar_view, calendar_extra)}
          {strategy_performance_panel(trades, perf_range, perf_start, perf_end)}
        </div>
      </div>
    </div>
    '''
    return layout("Dashboard - Option Ledger", body, "dashboard")


def analytics_page(query=None) -> bytes:
    trades = all_trades()
    closed = [t for t in trades if t["status"] != "Open" and t["net_pnl"] is not None]
    symbol_rows = symbol_summary(closed)[:12]
    symbol_table = ''.join(
        f'<tr><td><a href="/symbol/{quote(item["ticker"])}"><b>{escape(item["ticker"])}</b></a></td><td><span class="sector-chip">{escape(item.get("sector") or sector_for_ticker(item["ticker"]))}</span></td><td class="{"gain" if item["total_pnl"] >= 0 else "loss"}">{money(item["total_pnl"])}</td><td>{pct(item["pl_pct"])}</td><td>{item["trades"]}</td><td>{pct(item["win_rate"])}</td></tr>'
        for item in symbol_rows
    )
    if not symbol_table:
        symbol_table = '<tr><td colspan="6" class="empty">No closed trades yet.</td></tr>'

    body = f'''<div class="page-head"><div><p class="eyebrow">Deeper review</p><h1>Analytics</h1></div><div class="actions"><a class="button secondary" href="/">Dashboard</a><a class="button" href="/symbols">All symbols</a></div></div>
    {period_summary_panel(trades)}
    {analytics_tabs_panel(trades)}
    {monthly_summary_panel(trades)}
    <section class="panel"><div class="panel-head"><h2>Symbol performance</h2><a href="/symbols">View all &gt;</a></div><div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Sector</th><th>Total P&L</th><th>PL %</th><th>Trades</th><th>Win rate</th></tr></thead><tbody>{symbol_table}</tbody></table></div></section>'''
    return layout("Analytics - Option Ledger", body, "analytics")


def strip_html_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def jin10_payload_rows(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "list", "items"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return rows
        if isinstance(rows, dict):
            nested = jin10_payload_rows(rows)
            if nested:
                return nested
    return []


def jin10_is_red_flash(item) -> bool:
    if not isinstance(item, dict):
        return False
    important = item.get("important")
    if important is True or str(important).lower() in {"1", "true", "yes"}:
        return True
    text = " ".join(str(item.get(key, "")) for key in ("type", "level", "color", "class", "tag"))
    return any(token in text.lower() for token in ("red", "important", "high"))


def format_jin10_time(raw_time: str) -> str:
    raw_time = (raw_time or "").strip()
    if not raw_time:
        return ""
    try:
        source_tz = ZoneInfo(JIN10_SOURCE_TIMEZONE)
    except ZoneInfoNotFoundError:
        source_tz = timezone(timedelta(hours=8), "CST")
    try:
        local_tz = ZoneInfo("America/Los_Angeles")
        if LOCAL_TIMEZONE != "America/Los_Angeles":
            local_tz = ZoneInfo(LOCAL_TIMEZONE)
    except ZoneInfoNotFoundError:
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(raw_time[:19], pattern)
            local_time = parsed_time.replace(tzinfo=source_tz).astimezone(local_tz)
            label = LOCAL_TIME_LABEL or local_time.tzname() or "Local"
            return f'{local_time.strftime("%m/%d %H:%M:%S")} {label}'
        except ValueError:
            continue
    return raw_time


def normalize_jin10_flash(item) -> dict | None:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    content = strip_html_tags(data.get("content") or item.get("content") or item.get("title") or "")
    if not content:
        return None
    flash_id = str(item.get("id") or data.get("id") or "").strip()
    raw_time = str(item.get("time") or item.get("created_at") or data.get("time") or "").strip()
    display_time = format_jin10_time(raw_time)
    return {
        "id": flash_id,
        "time": display_time,
        "raw_time": raw_time,
        "important": jin10_is_red_flash(item),
        "content": content,
        "url": f"https://flash.jin10.com/detail/{quote(flash_id)}" if flash_id else "https://www.jin10.com/",
    }


def merge_jin10_items(fresh_items: list[dict], old_items: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for item in fresh_items + old_items:
        key = item.get("id") or item.get("content")
        if not key or key in seen:
            continue
        seen.add(key)
        if item.get("raw_time"):
            item = dict(item)
            item["time"] = format_jin10_time(str(item.get("raw_time") or ""))
        merged.append(item)
    return merged[:max(JIN10_KEEP_ITEMS, 1)]


def load_saved_jin10_items() -> list[dict]:
    try:
        saved = json.loads(JIN10_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(saved, list):
        return []
    items = []
    for item in saved:
        if isinstance(item, dict) and item.get("content"):
            if item.get("raw_time"):
                item = dict(item)
                item["time"] = format_jin10_time(str(item.get("raw_time") or ""))
            items.append(item)
    return items[:max(JIN10_KEEP_ITEMS, 1)]


def save_jin10_items(items: list[dict]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        JIN10_CACHE_PATH.write_text(
            json.dumps(items[:max(JIN10_KEEP_ITEMS, 1)], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def fetch_jin10_flash_items(force=False) -> tuple[list[dict], str | None]:
    now = time.time()
    with JIN10_CACHE_LOCK:
        if not force and now - float(JIN10_CACHE.get("at") or 0) < JIN10_CACHE_SECONDS:
            return list(JIN10_CACHE.get("items") or []), JIN10_CACHE.get("error")
    separator = "&" if "?" in JIN10_FLASH_URL else "?"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.jin10.com",
        "Referer": "https://www.jin10.com/",
        "User-Agent": "Mozilla/5.0 OptionLedger/1.0",
        "x-version": "1.0.0",
    }
    try:
        app_ids = [value.strip() for value in JIN10_APP_ID.split(",") if value.strip()] or [""]
        last_error = None
        seen = set()
        items = []
        max_time = ""
        for _page in range(max(JIN10_FETCH_PAGES, 1)):
            params = {"channel": "-8200", "vip": "1", "limit": str(max(JIN10_FETCH_LIMIT, JIN10_KEEP_ITEMS))}
            if max_time:
                params["max_time"] = max_time
            url = f"{JIN10_FLASH_URL}{separator}{urlencode(params)}"
            payload = None
            for app_id in app_ids:
                request_headers = dict(headers)
                if app_id:
                    request_headers["x-app-id"] = app_id
                try:
                    request = urllib.request.Request(url, headers=request_headers)
                    with urllib.request.urlopen(request, timeout=10) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                    break
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                    last_error = exc
            if payload is None:
                if not items:
                    raise last_error or urllib.error.URLError("No Jin10 response")
                break
            rows = jin10_payload_rows(payload)
            if not rows:
                break
            for row in rows:
                if not jin10_is_red_flash(row):
                    continue
                normalized = normalize_jin10_flash(row)
                if not normalized or normalized["content"] in seen:
                    continue
                seen.add(normalized["content"])
                items.append(normalized)
                if len(items) >= JIN10_KEEP_ITEMS:
                    break
            if len(items) >= JIN10_KEEP_ITEMS:
                break
            next_time = ""
            for row in reversed(rows):
                data = row.get("data") if isinstance(row, dict) and isinstance(row.get("data"), dict) else {}
                next_time = str(row.get("time") or row.get("created_at") or data.get("time") or "").strip()
                if next_time:
                    break
            if not next_time or next_time == max_time:
                break
            max_time = next_time
        with JIN10_CACHE_LOCK:
            old_items = list(JIN10_CACHE.get("items") or []) or load_saved_jin10_items()
            merged_items = merge_jin10_items(items, old_items)
            error = None if merged_items else "No red market flashes right now."
            JIN10_CACHE.update({"at": now, "items": merged_items, "error": error})
            save_jin10_items(merged_items)
        return merged_items, error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        error = f"Jin10 fetch failed: {exc}"
        with JIN10_CACHE_LOCK:
            cached = list(JIN10_CACHE.get("items") or []) or load_saved_jin10_items()
            JIN10_CACHE.update({"at": now, "error": error})
        return cached, error


def jin10_feed_html(items: list[dict], error: str | None = None) -> str:
    status = f'<div class="jin10-status">{escape(error)}</div>' if error else ""
    if not items:
        return status or '<div class="empty">No red market flashes right now.</div>'
    rows = "".join(
        f'''<article class="jin10-card {"important" if item.get("important") else "standard"}">
          <div class="jin10-time"><span></span>{escape(item["time"] or "Live")}</div>
          <p class="jin10-content">{escape(item["content"])}</p>
          <a class="jin10-source" href="{escape(item["url"])}" target="_blank" rel="noreferrer">source</a>
        </article>'''
        for item in items
    )
    return status + rows


def market_news_page(query=None) -> bytes:
    query = query or {}
    items, error = fetch_jin10_flash_items(force=query.get("refresh", ["0"])[0] == "1")
    body = f'''<div class="page-head">
      <div><p class="eyebrow">Jin10 red flash</p><h1>Market News</h1></div>
      <div class="actions">
        <a class="button secondary" href="/market-news?refresh=1">Refresh now</a>
        <a class="button" href="https://www.jin10.com/" target="_blank" rel="noreferrer">Open Jin10</a>
      </div>
    </div>
    <section class="panel jin10-panel">
      <div class="panel-head">
        <div><h2>Jin10 Red Market Alerts</h2><span>Data from Jin10. Polling is rate-limited locally.</span></div>
        <span class="jin10-live"><i></i>auto refresh {JIN10_REFRESH_SECONDS}s</span>
      </div>
      <div class="jin10-feed" data-jin10-feed data-refresh-seconds="{JIN10_REFRESH_SECONDS}">
        {jin10_feed_html(items, error)}
      </div>
    </section>'''
    return layout("Market News - Option Ledger", body, "market-news")


def earnings_calendar_rows_html(items: list[dict]) -> str:
    if not items:
        return '<tr><td colspan="8" class="empty">No earnings found.</td></tr>'
    rows = []
    for item in items:
        tracked_badge = '<span class="pill open">Tracked</span>' if item.get("tracked") else ""
        quarter = f'Q{escape(str(item.get("quarter")))} {escape(str(item.get("year")))}' if item.get("quarter") and item.get("year") else "-"
        rows.append(
            "<tr>"
            f'<td><b>{escape(item["date"])}</b></td>'
            f'<td><a href="/symbol/{quote(item["symbol"])}"><b>{escape(item["symbol"])}</b></a> {tracked_badge}</td>'
            f'<td>{escape(item["hour"])}</td>'
            f'<td>{escape(quarter)}</td>'
            f'<td>{compact_market_cap(item.get("market_cap"))}</td>'
            f'<td>{num(item.get("eps_estimate"))}</td>'
            f'<td>{num(item.get("eps_actual"))}</td>'
            f'<td>{money(item.get("revenue_estimate"))}</td>'
            "</tr>"
        )
    return "".join(rows)


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def earnings_time_bucket(hour: str) -> str:
    value = (hour or "").strip().lower()
    if value in {"bmo", "before open", "before market", "before market open"}:
        return "Before Open"
    if value in {"amc", "after close", "after market", "after market close"}:
        return "After Close"
    if value in {"dmh", "during market"}:
        return "During Market"
    return "TBD"


def earnings_week_calendar_html(items: list[dict], start: date, macro_items: list[dict] | None = None, macro_error: str | None = None) -> str:
    weekdays = [start + timedelta(days=offset) for offset in range(5)]
    grouped = {
        day.isoformat(): {"Important Macro": [], "Before Open": [], "During Market": [], "After Close": []}
        for day in weekdays
    }
    for event in macro_items or []:
        event_date = event.get("date") or ""
        if event_date in grouped:
            grouped[event_date]["Important Macro"].append(event)
    for item in items:
        item_date = item.get("date") or ""
        bucket = earnings_time_bucket(item.get("hour"))
        if item_date in grouped and bucket in grouped[item_date]:
            grouped[item_date][bucket].append(item)
    columns = []
    for day in weekdays:
        sections = []
        macro_cards = []
        for event in grouped[day.isoformat()]["Important Macro"]:
            macro_cards.append(f'''<span class="earnings-macro-card">
              <b>{escape(event.get("name") or "")}</b>
              <span>{escape(event.get("time") or "TBD")}</span>
            </span>''')
        if day == weekdays[0] and not macro_cards and not any(grouped[item.isoformat()]["Important Macro"] for item in weekdays):
            macro_cards.append(f'<span class="earnings-macro-card empty"><b>{escape(macro_error or "No important macro events this week.")}</b></span>')
        if macro_cards:
            sections.append(f'''<div class="earnings-bucket macro">
              <div class="earnings-bucket-title">Important Macro</div>
              <div class="earnings-macro-grid">{"".join(macro_cards)}</div>
            </div>''')
        for bucket in ("Before Open", "During Market", "After Close"):
            cards = []
            for item in grouped[day.isoformat()][bucket]:
                tracked = '<span class="earnings-badge">Tracked</span>' if item.get("tracked") else ""
                quarter = f'Q{escape(str(item.get("quarter")))}' if item.get("quarter") else ""
                eps_estimate = num(item.get("eps_estimate"))
                revenue_estimate = compact_revenue(item.get("revenue_estimate"))
                cards.append(f'''<a class="earnings-company" href="/symbol/{quote(item["symbol"])}">
                  <b>{escape(item["symbol"])}</b>
                  <span>{escape(quarter or bucket)}</span>
                  {tracked}
                  <span class="earnings-hover">
                    <em>EPS est.</em><strong>{escape(eps_estimate)}</strong>
                    <em>Revenue est.</em><strong>{revenue_estimate}</strong>
                  </span>
                </a>''')
            if cards:
                sections.append(f'''<div class="earnings-bucket">
                  <div class="earnings-bucket-title">{escape(bucket)}</div>
                  <div class="earnings-company-grid">{"".join(cards)}</div>
                </div>''')
        if not sections:
            sections.append('<div class="earnings-empty-day">No reports</div>')
        columns.append(f'''<section class="earnings-day">
          <div class="earnings-day-head"><b>{day.strftime("%A")}</b><span>{day.strftime("%b %d")}</span></div>
          {"".join(sections)}
        </section>''')
    return f'<div class="earnings-week-grid">{"".join(columns)}</div>'


def current_week_earnings_reminder_html(force: bool = False) -> str:
    start = week_start(date.today())
    end = start + timedelta(days=4)
    items, error = fetch_earnings_calendar(start, end, "all", force=force)
    weekdays = [start + timedelta(days=offset) for offset in range(5)]
    grouped = {day.isoformat(): [] for day in weekdays}
    for item in items:
        if item.get("date") in grouped:
            grouped[item["date"]].append(item)
    day_columns = []
    for day in weekdays:
        events = sorted(
            grouped[day.isoformat()],
            key=lambda item: (not item.get("tracked"), earnings_time_bucket(item.get("hour")), item.get("symbol") or ""),
        )
        event_html = []
        for item in events:
            time_label = {
                "Before Open": "BMO",
                "After Close": "AMC",
                "During Market": "Market",
            }.get(earnings_time_bucket(item.get("hour")), "TBD")
            position_badge = '<i>Position</i>' if item.get("tracked") else ""
            tracked_class = " tracked" if item.get("tracked") else ""
            event_html.append(f'''<a class="earnings-reminder-event{tracked_class}" href="/symbol/{quote(item["symbol"])}">
              <b>{escape(item["symbol"])}</b><span>{escape(time_label)}</span>{position_badge}
            </a>''')
        if not event_html:
            event_html.append('<span class="earnings-reminder-empty">No reports</span>')
        day_columns.append(f'''<div class="earnings-reminder-day">
          <div><b>{day.strftime("%a")}</b><span>{day.strftime("%b %d")}</span></div>
          <div class="earnings-reminder-events">{"".join(event_html)}</div>
        </div>''')
    tracked_count = sum(1 for item in items if item.get("tracked"))
    if error and not items:
        status = error
    else:
        status = f'{start.strftime("%b %d")} - {end.strftime("%b %d")} | {len(items)} reports | {tracked_count} positions'
    return f'''<section class="panel earnings-reminder-panel" id="this-week" data-earnings-reminder>
      <div class="panel-head earnings-reminder-head">
        <div><h2>This Week Earnings</h2><span>{escape(status)}</span></div>
        <button class="button secondary small-button" type="button" data-earnings-reminder-refresh>Refresh</button>
      </div>
      <div class="earnings-reminder-grid">{"".join(day_columns)}</div>
    </section>'''


def macro_events_week_html(items: list[dict], error: str | None = None) -> str:
    if not items:
        message = error or "No important macro events this week."
        return f'''<section class="macro-week-strip">
          <div class="macro-week-head"><b>Important Macro</b><span>{escape(message)}</span></div>
        </section>'''
    chips = []
    for item in items[:12]:
        name = item.get("name") or ""
        time_text = item.get("time") or "TBD"
        date_text = item.get("date") or ""
        chips.append(f'''<span class="macro-event-chip">
          <b>{escape(date_text)}</b>
          <em>{escape(time_text)}</em>
          <strong>{escape(name)}</strong>
        </span>''')
    tail = f'<span class="macro-more">+{len(items) - 12} more</span>' if len(items) > 12 else ""
    return f'''<section class="macro-week-strip">
      <div class="macro-week-head"><b>Important Macro</b><span>{len(items)} high-impact events</span></div>
      <div class="macro-event-row">{"".join(chips)}{tail}</div>
    </section>'''


def earnings_calendar_page(query=None) -> bytes:
    query = query or {}
    today = date.today()
    start = week_start(parse_date(query.get("week", [""])[0]) or today)
    end = start + timedelta(days=6)
    scope = query.get("scope", ["all"])[0]
    scope = "tracked" if scope == "tracked" else "all"
    force_refresh = query.get("refresh", ["0"])[0] == "1"
    items, error = fetch_earnings_calendar(start, end, scope, force=force_refresh)
    macro_items, macro_error = fetch_economic_calendar(start, end)
    tracked_count = sum(1 for item in items if item.get("tracked"))
    scope_options = "".join(
        f'<option value="{value}" {"selected" if scope == value else ""}>{label}</option>'
        for value, label in (("all", "Large caps"), ("tracked", "My symbols"))
    )
    status = error or f'{len(items)} large-cap reports - {tracked_count} tracked'
    notice = '<div class="notice">Combines Finnhub calendar with targeted symbol lookups for tracked and high-interest tickers. The fallback list includes DELL, PANW, MDB and other large-cap names so major reports are less likely to be missed.</div>'
    body = f'''<div class="page-head">
      <div><p class="eyebrow">Tools</p><h1>Earnings Calendar</h1></div>
      <div class="actions"><a class="button secondary" href="/earnings-calendar">Today</a></div>
    </div>
    {notice}
    <section class="panel earnings-panel">
      <div class="panel-head">
        <div><h2>Large-cap Earnings</h2><span>{escape(status)}</span></div>
        <div class="range-pills">{range_buttons}</div>
      </div>
      <form class="filters earnings-filters" method="get">
        <input type="date" name="from" value="{start.isoformat()}">
        <input type="date" name="to" value="{end.isoformat()}">
        <select name="scope">{scope_options}</select>
        <button class="button secondary">Filter</button>
      </form>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Symbol</th><th>Time</th><th>Quarter</th><th>Market cap</th><th>EPS est.</th><th>EPS actual</th><th>Revenue est.</th></tr></thead><tbody>{earnings_calendar_rows_html(items)}</tbody></table></div>
    </section>'''
    return layout("Earnings Calendar - Option Ledger", body, "earnings-calendar")


def earnings_calendar_page(query=None) -> bytes:
    query = query or {}
    today = date.today()
    start = week_start(parse_date(query.get("week", [""])[0]) or today)
    end = start + timedelta(days=6)
    scope = query.get("scope", ["all"])[0]
    scope = "tracked" if scope == "tracked" else "all"
    force_refresh = query.get("refresh", ["0"])[0] == "1"
    items, error = fetch_earnings_calendar(start, end, scope, force=force_refresh)
    macro_items, macro_error = fetch_economic_calendar(start, end)
    tracked_count = sum(1 for item in items if item.get("tracked"))
    scope_options = "".join(
        f'<option value="{value}" {"selected" if scope == value else ""}>{label}</option>'
        for value, label in (("all", "Large caps"), ("tracked", "My symbols"))
    )
    previous_week = start - timedelta(days=7)
    next_week = start + timedelta(days=7)
    this_week = week_start(today)
    week_label = f'{start.strftime("%b %d")} - {end.strftime("%b %d, %Y")}'
    status = error or f"{len(items)} reports | {compact_market_cap(EARNINGS_MIN_MARKET_CAP)}+ market cap | {tracked_count} tracked"
    body = f'''<div class="page-head">
      <div><p class="eyebrow">Tools</p><h1>Earnings Calendar</h1></div>
      <div class="actions"><a class="button secondary" href="/earnings-calendar?week={this_week.isoformat()}&scope={scope}">This week</a><a class="button" href="/earnings-calendar?week={start.isoformat()}&scope={scope}&refresh=1">Refresh</a></div>
    </div>
    <section class="panel earnings-panel earnings-week-panel">
      <div class="panel-head">
        <div><h2>Large-cap Earnings</h2><span>{escape(status)}</span></div>
        <div class="earnings-week-nav">
          <a class="calendar-nav" href="/earnings-calendar?week={previous_week.isoformat()}&scope={scope}" aria-label="Previous week">&#9664;</a>
          <strong>{escape(week_label)}</strong>
          <a class="calendar-nav" href="/earnings-calendar?week={next_week.isoformat()}&scope={scope}" aria-label="Next week">&#9654;</a>
        </div>
      </div>
      <form class="filters earnings-filters weekly" method="get">
        <input type="date" name="week" value="{start.isoformat()}">
        <select name="scope">{scope_options}</select>
        <button class="button secondary">Filter</button>
      </form>
      {earnings_week_calendar_html(items, start, macro_items, macro_error)}
    </section>'''
    return layout("Earnings Calendar - Option Ledger", body, "earnings-calendar")


def economic_calendar_rows_html(items: list[dict]) -> str:
    if not items:
        return '<tr><td colspan="8" class="empty">No macro events found.</td></tr>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f'<td><b>{escape(item.get("date") or "")}</b></td>'
            f'<td>{escape(item.get("time") or "TBD")}</td>'
            f'<td><span class="pill urgent">{escape(item.get("impact") or "High")}</span></td>'
            f'<td><b>{escape(item.get("name") or "")}</b></td>'
            f'<td>{escape(item.get("country") or "US")}</td>'
            f'<td>{escape(str(item.get("actual") if item.get("actual") not in {None, ""} else "N/A"))}</td>'
            f'<td>{escape(str(item.get("estimate") if item.get("estimate") not in {None, ""} else "N/A"))}</td>'
            f'<td>{escape(str(item.get("previous") if item.get("previous") not in {None, ""} else "N/A"))}</td>'
            "</tr>"
        )
    return "".join(rows)


def watchlist_heatmap_page(query=None) -> bytes:
    body = f'''<div class="page-head">
      <div><p class="eyebrow">Tools</p><h1>Watchlist Heatmap</h1></div>
      <div class="actions"><a class="button secondary" href="/watchlist-heatmap">Refresh now</a></div>
    </div>
    <section class="panel heatmap-panel">
      <div class="panel-head">
        <div><h2>Watchlist Heatmap</h2><span>Holdings, open trades, frequent tickers, core ETFs and Magnificent 7. Refreshes every {HEATMAP_REFRESH_SECONDS}s.</span></div>
        <span class="jin10-live"><i></i>live prices</span>
      </div>
      <div class="heatmap-grid" data-watchlist-heatmap data-refresh-seconds="{HEATMAP_REFRESH_SECONDS}">
        {heatmap_cards_html(force=True)}
      </div>
    </section>'''
    return layout("Watchlist Heatmap - Option Ledger", body, "watchlist-heatmap")


def option_calculator_page(query=None) -> bytes:
    query = query or {}
    calc_mode = query.get("calc_mode", ["single"])[0]
    calc_mode = calc_mode if calc_mode in {"put_credit_spread", "call_credit_spread"} else "single"
    option_type = query.get("option_type", ["put"])[0].lower()
    option_type = "call" if option_type == "call" else "put"
    if calc_mode in {"put_credit_spread", "call_credit_spread"}:
        option_type = "call" if calc_mode == "call_credit_spread" else "put"
    spot = number(query.get("spot", [""])[0], 100.0)
    strike = number(query.get("strike", [""])[0], 95.0)
    expiration_text = query.get("expiration", [""])[0]
    expiration = parse_date(expiration_text)
    if not expiration:
        fallback_days = int(number(query.get("days", [""])[0], 30.0) or 30)
        expiration = date.today() + timedelta(days=max(fallback_days, 0))
        expiration_text = expiration.isoformat()
    days = max((expiration - date.today()).days, 0)
    iv_pct = number(query.get("iv", [""])[0], 35.0)
    short_iv_pct = number(query.get("short_iv", [""])[0], iv_pct)
    long_iv_pct = number(query.get("long_iv", [""])[0], iv_pct)
    rate_pct = number(query.get("rate", [""])[0], 4.5)
    dividend_pct = number(query.get("dividend", [""])[0], 0.0)
    short_strike = number(query.get("short_strike", [""])[0], strike)
    default_long_strike = (short_strike or strike) + 5 if calc_mode == "call_credit_spread" else max((short_strike or strike) - 5, 0.01)
    long_strike = number(query.get("long_strike", [""])[0], default_long_strike)
    credit = number(query.get("credit", [""])[0], 1.0)
    contracts = number(query.get("contracts", [""])[0], 1.0)
    result = black_scholes(option_type, max(spot, 0.0001), max(strike, 0.0001), max(days, 0.0), (iv_pct or 0) / 100, (rate_pct or 0) / 100, (dividend_pct or 0) / 100)
    spread_option_type = "call" if calc_mode == "call_credit_spread" else "put"
    short_leg = black_scholes(spread_option_type, max(spot, 0.0001), max(short_strike or strike, 0.0001), max(days, 0.0), (short_iv_pct or 0) / 100, (rate_pct or 0) / 100, (dividend_pct or 0) / 100)
    long_leg = black_scholes(spread_option_type, max(spot, 0.0001), max(long_strike or 0.01, 0.0001), max(days, 0.0), (long_iv_pct or 0) / 100, (rate_pct or 0) / 100, (dividend_pct or 0) / 100)
    spread_width = abs((long_strike or 0) - (short_strike or 0))
    contract_count = max(contracts or 0, 0)
    net_credit = max(credit or 0, 0)
    max_profit = net_credit * 100 * contract_count
    max_loss = max(0.0, (spread_width - net_credit) * 100 * contract_count)
    breakeven = (short_strike or 0) + net_credit if calc_mode == "call_credit_spread" else (short_strike or 0) - net_credit
    theoretical_credit = max(0.0, short_leg["price"] - long_leg["price"])
    spread_delta = short_leg["delta"] - long_leg["delta"]
    spread_gamma = short_leg["gamma"] - long_leg["gamma"]
    spread_theta = short_leg["theta"] - long_leg["theta"]
    spread_vega = short_leg["vega"] - long_leg["vega"]
    spread_rho = short_leg["rho"] - long_leg["rho"]
    credit_pct_width = net_credit / spread_width if spread_width else None
    roc_value = max_profit / max_loss if max_loss else None
    call_selected = "selected" if option_type == "call" else ""
    put_selected = "selected" if option_type == "put" else ""
    single_selected = "selected" if calc_mode == "single" else ""
    put_spread_selected = "selected" if calc_mode == "put_credit_spread" else ""
    call_spread_selected = "selected" if calc_mode == "call_credit_spread" else ""
    spread_hidden = " hidden" if calc_mode not in {"put_credit_spread", "call_credit_spread"} else ""
    single_hidden = " hidden" if calc_mode != "single" else ""
    option_type_hidden = " hidden" if calc_mode in {"put_credit_spread", "call_credit_spread"} else ""
    spread_title = "Call Credit Spread" if calc_mode == "call_credit_spread" else "Put Credit Spread"
    single_results = f'''<div class="metrics calculator-metrics{single_hidden}">
          <section class="metric"><span>Theoretical price</span><strong>{money(result["price"])}</strong></section>
          <section class="metric"><span>Intrinsic</span><strong>{money(result["intrinsic"])}</strong></section>
          <section class="metric"><span>Extrinsic</span><strong>{money(result["extrinsic"])}</strong></section>
          <section class="metric"><span>Delta</span><strong>{num(result["delta"])}</strong></section>
          <section class="metric"><span>Gamma</span><strong>{num(result["gamma"])}</strong></section>
          <section class="metric"><span>Theta / day</span><strong>{money(result["theta"])}</strong></section>
          <section class="metric"><span>Vega / 1%</span><strong>{money(result["vega"])}</strong></section>
          <section class="metric"><span>Rho / 1%</span><strong>{money(result["rho"])}</strong></section>
        </div>'''
    spread_results = f'''<div class="metrics calculator-metrics{spread_hidden}">
          <section class="metric"><span>Theoretical credit</span><strong>{money(theoretical_credit)}</strong></section>
          <section class="metric"><span>Entered credit</span><strong>{money(net_credit)}</strong></section>
          <section class="metric"><span>Max profit</span><strong class="gain">{money(max_profit)}</strong></section>
          <section class="metric"><span>Max loss</span><strong class="loss">{money(max_loss)}</strong></section>
          <section class="metric"><span>Breakeven</span><strong>{money(breakeven)}</strong></section>
          <section class="metric"><span>Credit / width</span><strong>{pct(credit_pct_width)}</strong></section>
          <section class="metric"><span>ROC</span><strong>{pct(roc_value)}</strong></section>
          <section class="metric"><span>Spread Delta</span><strong>{num(spread_delta)}</strong></section>
          <section class="metric"><span>Spread Gamma</span><strong>{num(spread_gamma)}</strong></section>
          <section class="metric"><span>Spread Theta / day</span><strong>{money(spread_theta)}</strong></section>
          <section class="metric"><span>Spread Vega / 1%</span><strong>{money(spread_vega)}</strong></section>
          <section class="metric"><span>Spread Rho / 1%</span><strong>{money(spread_rho)}</strong></section>
        </div>'''
    quick_days = (7, 14, 30, 45, 60, 90)
    expiry_buttons = "".join(
        f'<button type="button" data-expiry-days="{quick_day}" class="calc-date-pill {"active" if abs(days - quick_day) <= 1 else ""}">{quick_day}D</button>'
        for quick_day in quick_days
    )
    today_iso = date.today().isoformat()
    body = f'''<div class="page-head">
      <div><p class="eyebrow">Tools</p><h1>Options Calculator</h1></div>
    </div>
    <section class="panel calculator-workbench" data-options-calculator data-today="{today_iso}">
      <form class="calc-control-grid" method="get" data-options-calculator-form>
        <label><span>Strategy</span><select name="calc_mode" data-calculator-mode><option value="single" {single_selected}>Single Option</option><option value="put_credit_spread" {put_spread_selected}>Put Credit Spread</option><option value="call_credit_spread" {call_spread_selected}>Call Credit Spread</option></select></label>
        <label class="single-field{option_type_hidden}"><span>Option type</span><select name="option_type"><option value="put" {put_selected}>Put</option><option value="call" {call_selected}>Call</option></select></label>
        <label><span>Stock price</span><input type="number" step="0.01" name="spot" value="{num(spot)}" data-calc-sync="spot"></label>
        <label><span>Expiration</span><input type="date" name="expiration" value="{escape(expiration_text)}" data-calc-sync="expiration"><small data-calc-dte>{num(days)} DTE</small></label>
        <label class="single-field{option_type_hidden}"><span>IV %</span><input type="number" step="0.1" name="iv" value="{num(iv_pct)}" data-calc-sync="iv"></label>
        <label class="spread-field{spread_hidden}"><span>Short leg IV %</span><input type="number" step="0.1" name="short_iv" value="{num(short_iv_pct)}" data-calc-sync="short_iv"></label>
        <label class="spread-field{spread_hidden}"><span>Long leg IV %</span><input type="number" step="0.1" name="long_iv" value="{num(long_iv_pct)}" data-calc-sync="long_iv"></label>
        <label><span>Risk-free %</span><input type="number" step="0.1" name="rate" value="{num(rate_pct)}"></label>
        <label><span>Dividend %</span><input type="number" step="0.1" name="dividend" value="{num(dividend_pct)}"></label>
        <label class="spread-field{spread_hidden}"><span>Net credit</span><input type="number" step="0.01" name="credit" value="{num(credit)}"></label>
        <input type="hidden" name="strike" value="{num(strike)}" data-calc-hidden-strike>
        <input type="hidden" name="short_strike" value="{num(short_strike)}" data-calc-hidden-short>
        <input type="hidden" name="long_strike" value="{num(long_strike)}" data-calc-hidden-long>
      </form>

      <div class="calc-topline">
        <div>
          <h2 data-calc-title>{spread_title if calc_mode in {"put_credit_spread", "call_credit_spread"} else ("Long Call" if option_type == "call" else "Long Put")}</h2>
          <div class="calc-market-line"><b data-calc-spot>{money(spot)}</b><span>Black-Scholes estimate</span></div>
        </div>
        <div class="calc-date-row">{expiry_buttons}</div>
      </div>

      <div class="calc-slider-stack">
        <label class="single-field{option_type_hidden}">
          <span>Strike <b data-calc-strike-label>{money(strike)}</b></span>
          <input type="range" min="{num(max(1, spot * 0.65))}" max="{num(max(2, spot * 1.35))}" step="0.5" value="{num(strike)}" data-calc-slider="strike">
        </label>
        <label class="spread-field{spread_hidden}">
          <span>Short strike <b data-calc-short-label>{money(short_strike)}</b></span>
          <input type="range" min="{num(max(1, spot * 0.65))}" max="{num(max(2, spot * 1.35))}" step="0.5" value="{num(short_strike)}" data-calc-slider="short">
        </label>
        <label class="spread-field{spread_hidden}">
          <span>Long strike <b data-calc-long-label>{money(long_strike)}</b></span>
          <input type="range" min="{num(max(1, spot * 0.65))}" max="{num(max(2, spot * 1.35))}" step="0.5" value="{num(long_strike)}" data-calc-slider="long">
        </label>
        <label class="single-field{option_type_hidden}">
          <span>Implied volatility <b data-calc-iv-label>{num(iv_pct)}%</b></span>
          <input type="range" min="5" max="150" step="1" value="{num(iv_pct)}" data-calc-slider="iv">
        </label>
        <label class="spread-field{spread_hidden}">
          <span>Short leg IV <b data-calc-short-iv-label>{num(short_iv_pct)}%</b></span>
          <input type="range" min="5" max="150" step="1" value="{num(short_iv_pct)}" data-calc-slider="short_iv">
        </label>
        <label class="spread-field{spread_hidden}">
          <span>Long leg IV <b data-calc-long-iv-label>{num(long_iv_pct)}%</b></span>
          <input type="range" min="5" max="150" step="1" value="{num(long_iv_pct)}" data-calc-slider="long_iv">
        </label>
        <label>
          <span>Range <b data-calc-range-label>+/-10%</b></span>
          <input type="range" name="range" min="4" max="30" step="1" value="10" data-calc-slider="range">
        </label>
      </div>

      <div class="calc-stat-row">
        <section><span>Contract Value</span><strong data-calc-metric="value">{money(result["price"])}</strong></section>
        <section><span>Max profit</span><strong class="gain" data-calc-metric="profit">{money(max_profit) if calc_mode in {"put_credit_spread", "call_credit_spread"} else "Infinite"}</strong></section>
        <section><span>Max loss</span><strong class="loss" data-calc-metric="loss">{money(max_loss) if calc_mode in {"put_credit_spread", "call_credit_spread"} else money(result["price"] * 100)}</strong></section>
        <section><span>Breakeven</span><strong data-calc-metric="breakeven">{money(breakeven) if calc_mode in {"put_credit_spread", "call_credit_spread"} else money(strike + result["price"] if option_type == "call" else strike - result["price"])}</strong></section>
        <section><span>Delta</span><strong data-calc-metric="delta">{num(spread_delta if calc_mode in {"put_credit_spread", "call_credit_spread"} else result["delta"])}</strong></section>
      </div>

      <div class="calc-table-wrap">
        <table class="calc-matrix" data-calc-matrix></table>
      </div>
      <div class="calc-mode-tabs" role="tablist">
        <button type="button" class="active" data-calc-table-mode="value">Contract Value</button>
        <button type="button" data-calc-table-mode="pl">Profit / Loss $</button>
        <button type="button" data-calc-table-mode="pl_pct">Profit / Loss %</button>
      </div>
    </section>'''
    return layout("Options Calculator - Option Ledger", body, "option-calculator")


GREEDYFEAR_GROUPS = {
    "Market Sentiment": (
        "Crypto", "U.S. Equities", "Gold", "Crude Oil",
    ),
    "Mega-cap Companies": ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "TSM"),
}
GREEDYFEAR_RATINGS = ("Extreme Greed", "Extreme Fear", "Greed", "Fear", "Neutral")
GREEDYFEAR_BASE_URL = GREEDYFEAR_URL.rstrip("/")
GREEDYFEAR_API_SPECS = (
    ("Market Sentiment", "Crypto", "Alternative.me Fear & Greed Index", "crypto", "https://api.alternative.me/fng/"),
    ("Market Sentiment", "U.S. Equities", "CNN Fear & Greed Index proxy", "us", f"{GREEDYFEAR_BASE_URL}/api/us"),
    ("Market Sentiment", "Gold", "CBOE Gold Volatility (GVZ), inverted", "vix", f"{GREEDYFEAR_BASE_URL}/api/vix?region=gold"),
    ("Market Sentiment", "Crude Oil", "CBOE Oil Volatility (OVX), inverted", "vix", f"{GREEDYFEAR_BASE_URL}/api/vix?region=oil"),
    ("Mega-cap Companies", "AAPL", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=AAPL"),
    ("Mega-cap Companies", "MSFT", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=MSFT"),
    ("Mega-cap Companies", "NVDA", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=NVDA"),
    ("Mega-cap Companies", "GOOGL", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=GOOGL"),
    ("Mega-cap Companies", "AMZN", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=AMZN"),
    ("Mega-cap Companies", "META", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=META"),
    ("Mega-cap Companies", "TSLA", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=TSLA"),
    ("Mega-cap Companies", "TSM", "52-week range position", "stock", f"{GREEDYFEAR_BASE_URL}/api/stock?symbol=TSM"),
)


def greedyfear_text_lines(html: str) -> list[str]:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", "\n", cleaned)
    lines = []
    for line in unescape(cleaned).splitlines():
        text = re.sub(r"\s+", " ", line).strip()
        if text:
            lines.append(text)
    return lines


def parse_greedyfear_value(line: str) -> tuple[int | None, str, str]:
    text = line.strip()
    if not text or text.startswith("-") or "No data" in text:
        return None, "No data", text.lstrip("-").strip() or "No data"
    score = None
    rest = text
    match = re.match(r"^(\d{1,3})\s+(.+)$", text)
    if match:
        score = max(0, min(100, int(match.group(1))))
        rest = match.group(2).strip()
    rating = ""
    detail = rest
    for candidate in GREEDYFEAR_RATINGS:
        if rest.startswith(candidate):
            rating = candidate
            detail = rest[len(candidate):].strip()
            break
    if not rating:
        rating = "Neutral" if score is not None else "No data"
    return score, rating, detail


def parse_greedyfear_html(html: str) -> list[dict]:
    lines = greedyfear_text_lines(html)
    cards = []
    seen = set()
    for group, names in GREEDYFEAR_GROUPS.items():
        try:
            group_index = lines.index(group)
        except ValueError:
            group_index = 0
        for name in names:
            try:
                index = lines.index(name, group_index)
            except ValueError:
                continue
            key = (group, name)
            if key in seen:
                continue
            seen.add(key)
            source = ""
            value_line = ""
            updated = ""
            for candidate in lines[index + 1:index + 9]:
                if candidate.startswith("Updated") or candidate.startswith("Awaiting"):
                    updated = candidate
                    break
                if not source:
                    source = candidate
                    continue
                if not value_line:
                    value_line = candidate
            score, rating, detail = parse_greedyfear_value(value_line)
            cards.append({
                "group": group,
                "name": name,
                "source": source,
                "score": score,
                "rating": rating,
                "detail": detail,
                "updated": updated,
            })
    return cards


def greedyfear_band(score: int | float | None) -> str:
    if score is None:
        return "No data"
    value = int(round(float(score)))
    if value <= 25:
        return "Extreme Fear"
    if value <= 45:
        return "Fear"
    if value <= 54:
        return "Neutral"
    if value <= 74:
        return "Greed"
    return "Extreme Greed"


def greedyfear_updated(timestamp) -> str:
    if not timestamp:
        return "Awaiting data"
    text = str(timestamp).strip()
    try:
        if re.fullmatch(r"\d{10,13}", text):
            seconds = int(text[:10])
            parsed = datetime.fromtimestamp(seconds)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return "Updated " + parsed.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")
    except (ValueError, OSError):
        return text if text.startswith(("Updated", "Awaiting")) else f"Updated {text}"


def fetch_greedyfear_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": GREEDYFEAR_URL,
            "User-Agent": "Mozilla/5.0 OptionLedger/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_greedyfear_api_card(spec: tuple[str, str, str, str, str]) -> dict:
    group, name, source, source_type, url = spec
    payload = fetch_greedyfear_json(url)
    score = None
    rating = "No data"
    detail = ""
    timestamp = None
    if source_type == "crypto":
        row = (payload.get("data") or [{}])[0]
        score = int(round(float(row.get("value"))))
        rating = row.get("value_classification") or greedyfear_band(score)
        timestamp = row.get("timestamp")
    elif source_type == "us":
        score = int(round(float(payload.get("score"))))
        rating = str(payload.get("rating") or greedyfear_band(score)).title()
        timestamp = payload.get("timestamp")
    elif source_type == "vix":
        score = int(round(float(payload.get("score"))))
        rating = greedyfear_band(score)
        raw_value = number(payload.get("value"), None)
        if raw_value is not None:
            detail = f"Raw volatility {raw_value:.2f}"
        if payload.get("source") == "mock":
            detail = (detail + " - Simulated data").strip(" -")
        timestamp = payload.get("timestamp")
    elif source_type == "stock":
        score = int(round(float(payload.get("score"))))
        rating = greedyfear_band(score)
        price = number(payload.get("price"), None)
        change_pct = number(payload.get("changePercent"), None)
        if price is not None:
            detail = f"${price:,.2f}"
            if change_pct is not None:
                detail += f" - {'+' if change_pct >= 0 else ''}{change_pct:.2f}% today"
        timestamp = payload.get("timestamp")
    return {
        "group": group,
        "name": name,
        "source": source,
        "score": max(0, min(100, score)) if score is not None else None,
        "rating": rating,
        "detail": detail,
        "updated": greedyfear_updated(timestamp),
    }


def fetch_greedyfear_api_cards() -> tuple[list[dict], dict[str, str]]:
    cards = []
    errors = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(normalize_greedyfear_api_card, spec): spec for spec in GREEDYFEAR_API_SPECS}
        for future in as_completed(futures):
            group, name, *_ = futures[future]
            try:
                cards.append(future.result())
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError, TypeError) as exc:
                errors[name] = str(exc)
    order = {(group, name): index for index, (group, name, *_rest) in enumerate(GREEDYFEAR_API_SPECS)}
    cards.sort(key=lambda card: order.get((card.get("group"), card.get("name")), 999))
    return cards, errors


def fetch_greedyfear_cards(force=False) -> tuple[list[dict], str | None]:
    now = time.time()
    with GREEDYFEAR_CACHE_LOCK:
        if not force and now - float(GREEDYFEAR_CACHE.get("at") or 0) < GREEDYFEAR_CACHE_SECONDS:
            return list(GREEDYFEAR_CACHE.get("cards") or []), GREEDYFEAR_CACHE.get("error")
    try:
        cards, errors = fetch_greedyfear_api_cards()
        if cards:
            error = None
            if errors:
                names = ", ".join(sorted(errors)[:4])
                error = f"Some GreedyFear sources are unavailable: {names}."
            with GREEDYFEAR_CACHE_LOCK:
                GREEDYFEAR_CACHE.update({"at": now, "cards": cards, "error": error})
            return cards, error
        request = urllib.request.Request(
            GREEDYFEAR_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 OptionLedger/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")
        cards = parse_greedyfear_html(html)
        error = None if cards else "No GreedyFear cards found."
        with GREEDYFEAR_CACHE_LOCK:
            GREEDYFEAR_CACHE.update({"at": now, "cards": cards, "error": error})
        return cards, error
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
        error = f"GreedyFear fetch failed: {exc}"
        with GREEDYFEAR_CACHE_LOCK:
            cached = list(GREEDYFEAR_CACHE.get("cards") or [])
            GREEDYFEAR_CACHE.update({"at": now, "error": error})
        return cached, error


def greedyfear_card_class(card: dict) -> str:
    rating = str(card.get("rating") or "").lower().replace(" ", "-")
    if rating in {"extreme-greed", "greed", "neutral", "fear", "extreme-fear"}:
        return rating
    return "no-data"


def greedyfear_cards_html(cards: list[dict], error: str | None = None) -> str:
    status = f'<div class="sentiment-status">{escape(error)}</div>' if error else ""
    if not cards:
        return status or '<div class="empty">No sentiment data yet.</div>'
    grouped = []
    for group in GREEDYFEAR_GROUPS:
        group_cards = [card for card in cards if card.get("group") == group]
        if not group_cards:
            continue
        rows = "".join(
            f'''<article class="sentiment-card {greedyfear_card_class(card)}">
              <div class="sentiment-card-top"><span>{escape(card.get("source") or "GreedyFear")}</span><b>{escape(card["name"])}</b></div>
              <div class="sentiment-score">{escape(str(card["score"]) if card.get("score") is not None else "-")}</div>
              <div class="sentiment-rating">{escape(card.get("rating") or "No data")}</div>
              <p>{escape(card.get("detail") or "")}</p>
              <small>{escape(card.get("updated") or "")}</small>
            </article>'''
            for card in group_cards
        )
        grouped.append(f'<section class="sentiment-section"><h3>{escape(group)}</h3><div class="sentiment-grid">{rows}</div></section>')
    return status + "".join(grouped)


def sentiment_page(query=None) -> bytes:
    query = query or {}
    cards, error = fetch_greedyfear_cards(force=query.get("refresh", ["0"])[0] == "1")
    body = f'''<div class="page-head">
      <div><p class="eyebrow">GreedyFear</p><h1>Market Sentiment</h1></div>
      <div class="actions">
        <a class="button secondary" href="/sentiment?refresh=1">Refresh now</a>
        <a class="button" href="{escape(GREEDYFEAR_URL)}" target="_blank" rel="noreferrer">Open GreedyFear</a>
      </div>
    </div>
    <section class="panel sentiment-panel">
      <div class="panel-head">
        <div><h2>Global Fear & Greed</h2><span>Data from greedyfear.com. Cached locally.</span></div>
        <span class="jin10-live"><i></i>auto refresh {GREEDYFEAR_CACHE_SECONDS}s</span>
      </div>
      <div class="sentiment-feed" data-greedyfear-feed data-refresh-seconds="{GREEDYFEAR_CACHE_SECONDS}">
        {greedyfear_cards_html(cards, error)}
      </div>
    </section>'''
    return layout("Market Sentiment - Option Ledger", body, "sentiment")


def assistant_snapshot() -> dict:
    trades = all_trades()
    open_rows = active_positions(trades)
    holdings = all_holdings()
    closed = [trade for trade in trades if trade.get("status") != "Open" and trade.get("net_pnl") is not None]
    close_dates = trade_close_dates(trades)
    realized = sum(trade["net_pnl"] for trade in closed)
    peak_capital = peak_concurrent_capital(trades, close_dates[0], close_dates[-1]) if close_dates else 0
    open_capital = sum(number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0 for trade in open_rows)
    stock_value = sum(holding.get("market_value") or 0 for holding in holdings)
    sector_exposure = {}
    ticker_exposure = {}
    for trade in open_rows:
        capital = number(trade.get("capital_used"), 0) or trade.get("max_loss") or 0
        sector = trade.get("sector") or sector_for_ticker(trade.get("ticker"))
        ticker = trade.get("ticker")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + capital
        ticker_exposure[ticker] = ticker_exposure.get(ticker, 0) + capital
    for holding in holdings:
        value = holding.get("market_value") or 0
        sector = holding.get("sector") or sector_for_ticker(holding.get("ticker"))
        ticker = holding.get("ticker")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + value
        ticker_exposure[ticker] = ticker_exposure.get(ticker, 0) + value
    return {
        "as_of": date.today().isoformat(),
        "realized_pnl": realized,
        "realized_pl_pct": pl_pct(realized, peak_capital),
        "open_capital": open_capital,
        "stock_value": stock_value,
        "open_positions": open_rows,
        "holdings": holdings,
        "recent_closed": closed[:12],
        "sector_exposure": sorted(sector_exposure.items(), key=lambda item: item[1], reverse=True),
        "ticker_exposure": sorted(ticker_exposure.items(), key=lambda item: item[1], reverse=True),
        "drawdown": max_drawdown_stats(trades),
    }


def assistant_prompt(extra_focus="") -> str:
    snapshot = assistant_snapshot()
    lines = [
        "You are an options portfolio risk assistant. Analyze the current portfolio using only the data below.",
        "Do not give personalized buy/sell orders. Focus on risk, concentration, expiration pressure, position sizing, and follow-up checks.",
        "Return concise sections: Summary, Key Risks, Position Notes, Questions to Check, Next Review.",
        "",
        f"As of: {snapshot['as_of']}",
        f"Realized P&L: {money(snapshot['realized_pnl'])}",
        f"Realized PL%: {pct(snapshot['realized_pl_pct'])}",
        f"Open options capital: {money(snapshot['open_capital'])}",
        f"Stock market value: {money(snapshot['stock_value'])}",
        f"Max drawdown: {money(snapshot['drawdown']['drawdown'])} ({pct(snapshot['drawdown']['drawdown_pct'])})",
        "",
        "Open option positions:",
    ]
    if snapshot["open_positions"]:
        for trade in snapshot["open_positions"]:
            opened = parse_date(trade.get("open_date"))
            expiration = parse_date(trade.get("expiration"))
            dte = (expiration - date.today()).days if expiration else None
            lines.append(
                f"- {trade.get('ticker')} | {trade.get('strategy')} | sector {trade.get('sector')} | strike {strike_display(trade)} | "
                f"opened {opened or '-'} | expiration {expiration or '-'} | DTE {num(dte)} | capital {money(number(trade.get('capital_used'), 0) or trade.get('max_loss') or 0)}"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("Stock holdings:")
    if snapshot["holdings"]:
        for holding in snapshot["holdings"]:
            lines.append(
                f"- {holding.get('ticker')} | sector {holding.get('sector')} | shares {num(holding.get('shares'))} | "
                f"market value {money(holding.get('market_value'))} | unrealized P&L {money(holding.get('unrealized_pnl'))} | return {pct(holding.get('pnl_pct'))}"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("Top ticker exposure:")
    for ticker, exposure in snapshot["ticker_exposure"][:8]:
        lines.append(f"- {ticker}: {money(exposure)}")
    lines.append("")
    lines.append("Sector exposure:")
    for sector, exposure in snapshot["sector_exposure"][:8]:
        lines.append(f"- {sector}: {money(exposure)}")
    lines.append("")
    lines.append("Recent closed trades:")
    for trade in snapshot["recent_closed"]:
        lines.append(
            f"- {trade.get('ticker')} | {trade.get('strategy')} | close {trade.get('close_date') or '-'} | "
            f"P&L {money(trade.get('net_pnl'))} | ROC {pct(trade.get('roc'))}"
        )
    if extra_focus.strip():
        lines.extend(["", "User focus:", extra_focus.strip()])
    return "\n".join(lines)


def call_ai_assistant(prompt: str) -> tuple[str | None, str | None]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not set. The prompt below is ready to copy into an AI chat."
    payload = {
        "model": AI_MODEL,
        "input": prompt,
        "text": {"verbosity": "medium"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"OpenAI API error {exc.code}: {detail[:500]}"
    except Exception as exc:
        return None, f"AI request failed: {exc}"
    if data.get("output_text"):
        return data["output_text"], None
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return ("\n".join(chunks).strip() or None), None


def assistant_page(result=None, error=None, focus="") -> bytes:
    prompt = assistant_prompt(focus)
    api_ready = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    status = f'Using model {escape(AI_MODEL)}' if api_ready else "Set OPENAI_API_KEY to run analysis here"
    if result:
        result_html = f'<section class="panel ai-result-panel"><div class="panel-head"><h2>AI Analysis</h2><span>{status}</span></div><pre class="ai-output">{escape(result)}</pre></section>'
    elif error:
        result_html = f'<section class="panel ai-result-panel"><div class="panel-head"><h2>AI Assistant</h2><span>{status}</span></div><div class="alert">{escape(error)}</div><pre class="ai-output">{escape(prompt)}</pre></section>'
    else:
        result_html = f'<section class="panel ai-result-panel"><div class="panel-head"><h2>Portfolio Prompt</h2><span>{status}</span></div><pre class="ai-output">{escape(prompt)}</pre></section>'
    body = f'''<div class="page-head"><div><p class="eyebrow">Position review</p><h1>AI Assistant</h1></div><div class="actions"><a class="button secondary" href="/">Dashboard</a><a class="button" href="/option-trade/new">Record trade</a></div></div>
    <section class="panel ai-compose-panel">
      <div class="panel-head"><h2>Analyze Current Holdings</h2><span>open options, stock holdings, exposure, recent closes</span></div>
      <form method="post" action="/assistant">
        <label><span>Focus</span><textarea name="focus" rows="4" placeholder="Example: focus on assignment risk, concentration, and next 2 weeks.">{escape(focus)}</textarea></label>
        <div class="form-actions"><button class="button" type="submit">Analyze</button></div>
      </form>
    </section>
    {result_html}'''
    return layout("AI Assistant - Option Ledger", body, "assistant")


def trade_row(t, compact=False, return_to: str = "", show_broker: bool = True) -> str:
    pnl_class = "gain" if (t["net_pnl"] or 0) >= 0 else "loss"
    trade_pl_class = "gain" if (t["trade_pl_pct"] or 0) >= 0 else "loss"
    ticker_html = (
        ticker_broker_display(t["ticker"], broker_source_for_row(t), earnings_marker(t))
        if show_broker
        else f'<div class="ticker-broker-cell"><a href="/symbol/{quote(t["ticker"])}"><b>{escape(t["ticker"])}</b></a>{earnings_marker(t)}</div>'
    )
    cells = [
        f'<td data-sort-value="{escape(str(t["ticker"]))}">{ticker_html}</td>',
        f'<td data-sort-value="{escape(str(t.get("sector") or ""))}"><span class="sector-chip">{escape(t.get("sector") or sector_for_ticker(t.get("ticker")))}</span></td>',
        f'<td data-sort-value="{escape(str(t["strategy"]))}">{escape(t["strategy"])}</td>',
        f'<td data-sort-value="{escape(str(t["status"]))}"><span class="pill {t["status"].lower()}">{escape(t["status"])}</span></td>',
        f'<td data-sort-value="{escape(str(t["open_date"] or ""))}">{escape(t["open_date"] or "-")}</td>'
    ]
    if not compact:
        close_date = None if t.get("status") == "Open" else t.get("close_date")
        cells += [
            f'<td data-sort-value="{escape(str(close_date or ""))}">{escape(close_date or "-")}</td>',
            f'<td data-sort-value="{escape(str(t["expiration"] or ""))}">{escape(t["expiration"] or "-")}</td>',
            f'<td data-sort-value="{escape(str(t["contracts"]))}">{num(t["contracts"])}</td>',
            f'<td data-sort-value="{escape(str(t["strike"]))}">{strike_display(t)}</td>'
        ]
    cells += [
        f'<td class="{pnl_class}" data-sort-value="{escape(str(t["net_pnl"]))}">{money(t["net_pnl"])}</td>',
        f'<td class="{trade_pl_class}" data-sort-value="{escape(str(t["trade_pl_pct"]))}">{pct(t["trade_pl_pct"])}</td>',
    ]
    if t.get("source") == "day_trade":
        edit_href = f'/day-trade/{str(t["id"]).replace("day-", "")}/edit'
    elif t.get("source") == "stock_trade":
        edit_href = f'/stock-trade/{str(t["id"]).replace("stock-", "")}/edit'
    elif t.get("source") == "other_option":
        edit_href = f'/other-option/{str(t["id"]).replace("other-option-", "")}/edit'
    else:
        edit_href = f'/trade/{t["id"]}/edit'
    if return_to:
        edit_href += f'?{urlencode({"return_to": return_to})}'
    cells.append(f'<td><a class="text-button" href="{edit_href}">Edit</a></td>')
    return f"<tr{earnings_row_class(t)}>" + "".join(cells) + "</tr>"


def compact_sort_options(options, selected: str) -> str:
    return "".join(
        f'<option value="{escape(value)}" {"selected" if value == selected else ""}>{escape(label)}</option>'
        for value, label in options
    )


def seller_trade_item(trade: dict) -> str:
    pnl = number(trade.get("net_pnl"), 0) or 0
    trade_pct = trade.get("trade_pl_pct")
    side_label, side_class = option_position_side(trade)
    status = trade.get("status") or "Closed"
    close_date = trade.get("close_date") if status != "Open" else None
    expiration = trade.get("expiration") or "No expiration"
    contracts = num(trade.get("contracts"))
    edit_href = f'/trade/{trade["id"]}/edit'
    earnings_class = " earnings-row" if number(trade.get("earnings_bet_id")) else ""
    return f'''<article class="transaction-item{earnings_class}">
      <div class="transaction-primary">
        {ticker_broker_display(trade.get("ticker") or "-", broker_source_for_row(trade))}
        <div class="holding-secondary">{escape(trade.get("open_date") or "-")} · {escape(trade.get("strategy") or "-")}</div>
      </div>
      <div class="transaction-contract"><strong>{escape(option_instrument_display(trade))}</strong><small>{escape(expiration)} · {contracts} contracts</small></div>
      <div class="transaction-state"><span class="position-side {side_class}">{side_label}</span><small class="pill {escape(status.lower())}">{escape(status)}</small></div>
      <div class="transaction-result"><strong class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</strong><small class="{"positive" if (trade_pct or 0) >= 0 else "negative"}">{pct(trade_pct)}</small>{f'<em>Closed {escape(close_date)}</em>' if close_date else ''}</div>
      <a class="transaction-edit" href="{edit_href}">Edit</a>
    </article>'''


def symbol_summary_item(item: dict) -> str:
    ticker = item.get("ticker") or "-"
    total_pnl = number(item.get("total_pnl"), 0) or 0
    stock_pnl = number(item.get("stock_pnl"), 0) or 0
    option_pnl = number(item.get("option_pnl"), 0) or 0
    pl_pct_value = item.get("pl_pct")
    avg_trade_pl_pct = item.get("avg_trade_pl_pct")
    return f'''<article class="transaction-item symbol-transaction-item">
      <div class="transaction-primary">
        <div class="ticker-broker-cell"><a href="/symbol/{quote(ticker)}"><b>{escape(ticker)}</b></a></div>
        <div class="holding-secondary"><span class="sector-chip">{escape(item.get("sector") or sector_for_ticker(ticker))}</span></div>
      </div>
      <div class="transaction-contract"><strong class="{"positive" if total_pnl >= 0 else "negative"}">{money(total_pnl)}</strong><small>Stocks {money(stock_pnl)} &middot; Options {money(option_pnl)}</small></div>
      <div class="transaction-state"><strong>{int(item.get("trades") or 0)} trades</strong><small>Win rate {pct(item.get("win_rate"))}</small></div>
      <div class="transaction-result"><strong class="{"positive" if (pl_pct_value or 0) >= 0 else "negative"}">{pct(pl_pct_value)}</strong><small>Avg {pct(avg_trade_pl_pct)}</small></div>
      <a class="transaction-edit" href="/symbol/{quote(ticker)}">View</a>
    </article>'''


def select_options(options, selected, blank=""):
    html = f'<option value="">{escape(blank)}</option>' if blank else ""
    return html + "".join(f'<option value="{escape(x)}" {"selected" if x == selected else ""}>{escape(x)}</option>' for x in options)


def holding_row(holding) -> str:
    pnl_class = "gain" if (holding.get("unrealized_pnl") or 0) >= 0 else "loss"
    as_of = holding.get("as_of") or "-"
    edit_href = (
        f'/symbol/{quote(holding["ticker"])}'
        if holding.get("source") == "stock_trades"
        else f'/holding/{holding["id"]}/edit'
    )
    cells = [
        f'<td data-sort-value="{escape(str(holding["ticker"]))}"><a href="/symbol/{quote(holding["ticker"])}"><b>{escape(holding["ticker"])}</b></a></td>',
        f'<td data-sort-value="{escape(str(broker_source_for_row(holding) or ""))}">{broker_source_badge(broker_source_for_row(holding))}</td>',
        f'<td data-sort-value="{escape(str(holding.get("sector") or ""))}"><span class="sector-chip">{escape(holding.get("sector") or sector_for_ticker(holding.get("ticker")))}</span></td>',
        f'<td data-sort-value="{escape(str(holding["shares"]))}">{num(holding["shares"])}</td>',
        f'<td data-sort-value="{escape(str(holding["avg_cost"]))}">{money(holding["avg_cost"])}</td>',
        f'<td data-sort-value="{escape(str(holding["current_price"]))}">{money(holding["current_price"])}</td>',
        f'<td data-sort-value="{escape(str(holding["cost_basis"]))}">{money(holding["cost_basis"])}</td>',
        f'<td data-sort-value="{escape(str(holding["market_value"]))}">{money(holding["market_value"])}</td>',
        f'<td data-sort-value="{escape(str(holding.get("allocation_pct")))}">{pct(holding.get("allocation_pct"))}</td>',
        f'<td class="{pnl_class}" data-sort-value="{escape(str(holding["unrealized_pnl"]))}">{money(holding["unrealized_pnl"])}</td>',
        f'<td class="{pnl_class}" data-sort-value="{escape(str(holding["pnl_pct"]))}">{pct(holding["pnl_pct"])}</td>',
        f'<td data-sort-value="{escape(str(holding.get("as_of") or ""))}">{escape(as_of)}</td>',
        f'<td><a class="text-button" href="{edit_href}">Edit</a></td>',
    ]
    return "<tr>" + "".join(cells) + "</tr>"


def holdings_rows_html(holdings) -> str:
    rows = "".join(holding_row(holding) for holding in holdings)
    return rows or '<tr><td colspan="13" class="empty">No stock holdings yet.</td></tr>'


def holdings_summary_strip(holdings) -> str:
    profitable = [holding for holding in holdings if (holding.get("unrealized_pnl") or 0) > 0]
    returns = [holding.get("pnl_pct") for holding in holdings if holding.get("pnl_pct") is not None]
    total_value = sum(holding.get("market_value") or 0 for holding in holdings)
    win_share = len(profitable) / len(holdings) if holdings else None
    avg_return = sum(returns) / len(returns) if returns else None
    ranked = [holding for holding in holdings if holding.get("pnl_pct") is not None]
    best = max(ranked, key=lambda holding: holding.get("pnl_pct") or 0) if ranked else None
    worst = min(ranked, key=lambda holding: holding.get("pnl_pct") or 0) if ranked else None

    def ticker_return(holding):
        if not holding:
            return "-", "neutral", "-"
        value = holding.get("pnl_pct")
        cls = "gain" if (value or 0) >= 0 else "loss"
        return escape(holding.get("ticker") or "-"), cls, pct(value)

    best_ticker, best_class, best_return = ticker_return(best)
    worst_ticker, worst_class, worst_return = ticker_return(worst)
    avg_class = "gain" if (avg_return or 0) >= 0 else "loss"
    return dashboard_summary_list((
        ("Positions", f"{len(holdings):,}", ""),
        ("Total value", money(total_value), ""),
        ("Profitable", pct(win_share), "positive"),
        ("Average", pct(avg_return), "positive" if (avg_return or 0) >= 0 else "negative"),
        ("Best", f"{best_ticker} {best_return}", "positive" if best_class == "gain" else "negative"),
        ("Worst", f"{worst_ticker} {worst_return}", "negative" if worst_class == "loss" else ""),
    )).replace("dashboard-summary-list", "dashboard-summary-list holdings-summary-strip").replace("<section ", '<section data-holdings-summary ', 1)


def holdings_live_payload(query=None, refresh=False) -> dict:
    query = query or {}
    sort_by = query.get("sort_by", ["ticker"])[0]
    sort_dir = query.get("sort_dir", ["asc"])[0]
    updated = 0
    errors = []
    if refresh:
        updated, errors = refresh_holding_prices()
    holdings = all_holdings(sort_by, sort_dir)
    return {
        "count": len(holdings),
        "updated": updated,
        "errors": len(errors),
        "summary": holdings_summary_strip(holdings),
        "rows": holdings_rows_html(holdings),
    }


def holdings_switch(active_view: str) -> str:
    return f'''<div class="dashboard-switch">
      <a class="{"active" if active_view == "trades" else ""}" href="/trades?view=stock-trades">Stock Trades</a>
    </div>'''


def holdings_page(query=None) -> bytes:
    query = query or {}
    if query.get("view", [""])[0] == "trades":
        return stock_trades_page(query)
    sort_by = query.get("sort_by", ["ticker"])[0]
    sort_dir = query.get("sort_dir", ["asc"])[0]
    refresh_message = ""
    if query.get("prices", [""])[0]:
        updated = escape(query.get("prices", ["0"])[0])
        failed = escape(query.get("price_errors", ["0"])[0])
        refresh_message = f'<div class="notice">Updated {updated} holding prices. Failed {failed}.</div>'
    holdings = all_holdings(sort_by, sort_dir)
    rows = holdings_rows_html(holdings)
    def sort_link(key, label):
        next_dir = "asc" if sort_by != key or sort_dir == "desc" else "desc"
        href = f"/holdings?{urlencode({'sort_by': key, 'sort_dir': next_dir})}"
        active = "active" if sort_by == key else ""
        arrow = "+" if sort_by == key and sort_dir == "asc" else "-" if sort_by == key else "*"
        return f'<th class="sortable {active}"><a href="{href}">{escape(label)} <span>{arrow}</span></a></th>'

    body = f"""<div class="page-head"><div><p class="eyebrow">Stock book</p><h1>Stock Holdings <span class="count" data-holdings-count>{len(holdings)}</span></h1>{holdings_switch("holdings")}</div><div class="actions"><form method="post" action="/holdings/refresh-prices"><input type="hidden" name="return_to" value="/holdings"><button class="button secondary" type="submit">Refresh prices</button></form><a class="button secondary" href="/holding/new">Add holding</a><a class="button" href="/stock-trade/new?status=Open">Record open stock</a></div></div>
    {refresh_message}
    {holdings_summary_strip(holdings)}
    <section class="panel holdings-live-panel" data-holdings-live data-refresh-seconds="{MARKET_TAPE_REFRESH_SECONDS}"><div class="table-wrap"><table><thead><tr>
      {sort_link('ticker','Ticker')}{sort_link('source','Source')}{sort_link('sector','Sector')}{sort_link('shares','Shares')}{sort_link('avg_cost','Avg cost')}{sort_link('current_price','Current')}{sort_link('cost_basis','Cost basis')}{sort_link('market_value','Market value')}{sort_link('allocation_pct','Allocation')}{sort_link('unrealized_pnl','Unrealized P&L')}{sort_link('pnl_pct','Return')}{sort_link('as_of','As of')}<th></th>
    </tr></thead><tbody data-holdings-rows>{rows}</tbody></table></div></section>"""
    return layout("Stock Holdings - Option Ledger", body, "holdings")


def option_trades_summary_strip(trades) -> str:
    closed = [t for t in trades if t.get("status") != "Open" and t.get("net_pnl") is not None]
    realized = sum(t.get("net_pnl") or 0 for t in closed)
    close_dates = trade_close_dates(trades)
    peak_capital = peak_concurrent_capital(trades, close_dates[0], close_dates[-1]) if close_dates else 0
    realized_pl_pct = pl_pct(realized, peak_capital)
    winners = sum(1 for t in closed if (t.get("net_pnl") or 0) > 0)
    total_contracts = option_contract_total(trades)
    trade_pl_pcts = [t.get("trade_pl_pct") for t in closed if t.get("trade_pl_pct") is not None]
    avg_trade_pl_pct = sum(trade_pl_pcts) / len(trade_pl_pcts) if trade_pl_pcts else None
    best, best_class = trade_extreme_value(closed, "net_pnl", True)
    worst, worst_class = trade_extreme_value(closed, "net_pnl", False)
    metrics = (
        ("Realized net P&L", money(realized), "positive" if realized >= 0 else "negative"),
        ("PL %", pct(realized_pl_pct) if realized_pl_pct is not None else "-", "positive" if realized_pl_pct is not None and realized_pl_pct >= 0 else "negative"),
        ("Max capital usage", money(peak_capital), ""),
        ("Win rate", pct(winners / len(closed) if closed else None), ""),
        ("Trades / Contracts", f"{len(trades):,} / {num(total_contracts)}", ""),
        ("Avg Trade P/L %", pct(avg_trade_pl_pct), "positive" if avg_trade_pl_pct is not None and avg_trade_pl_pct >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    )
    return compact_summary_cards(metrics, "trades-summary-compact")


def trades_rankings_panel(
    trades,
    pnl_key="net_pnl",
    edit_prefix="trade",
    date_fields=("close_date", "open_date", "trade_date"),
    strategy_fields=("strategy", "strategy_type", "option_type"),
    include_sectors=True,
    best_label="Best Trades",
    worst_label="Worst Trades",
) -> str:
    closed = [
        trade for trade in trades
        if trade.get(pnl_key) is not None
        and trade.get("status") != "Open"
        and trade.get("result") != "Pending"
    ]
    best_trades = sorted(
        closed,
        key=lambda trade: (number(trade.get(pnl_key), 0) or 0, next((trade.get(key) for key in date_fields if trade.get(key)), "")),
        reverse=True,
    )[:5]
    worst_trades = sorted(
        closed,
        key=lambda trade: (number(trade.get(pnl_key), 0) or 0, next((trade.get(key) for key in date_fields if trade.get(key)), "")),
    )[:5]
    sectors = {}
    for trade in trades:
        sector = trade.get("sector") or sector_for_ticker(trade.get("ticker") or "") or "Unclassified"
        entry = sectors.setdefault(sector, {"sector": sector, "trades": 0, "total_pnl": 0.0})
        entry["trades"] += 1
        entry["total_pnl"] += number(trade.get(pnl_key), 0) or 0
    sector_leaders = sorted(
        sectors.values(),
        key=lambda item: (item["trades"], item["total_pnl"]),
        reverse=True,
    )[:5]

    def ranked_trade_rows(items):
        rendered = []
        for rank, trade in enumerate(items, 1):
            pnl = number(trade.get(pnl_key), 0) or 0
            strategy = next((trade.get(key) for key in strategy_fields if trade.get(key)), "-")
            trade_date = next((trade.get(key) for key in date_fields if trade.get(key)), "-")
            rendered.append(f'''<a class="symbols-leader-row" href="/{edit_prefix}/{trade["id"]}/edit">
              <span>{rank}</span><b>{escape(trade.get("ticker") or "-")}</b>
              <div><strong class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</strong><small>{escape(strategy)} · {escape(trade_date)}</small></div>
            </a>''')
        return "".join(rendered)

    best_rows = ranked_trade_rows(best_trades)
    worst_rows = ranked_trade_rows(worst_trades)
    sector_rows = []
    for rank, item in enumerate(sector_leaders, 1):
        pnl = item["total_pnl"]
        sector_rows.append(f'''<div class="symbols-leader-row sector-leader-row">
          <span>{rank}</span><b>{escape(item["sector"])}</b>
          <div><strong>{item["trades"]} trades</strong><small class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)} P&L</small></div>
        </div>''')
    trade_empty = '<div class="empty">No closed trades yet.</div>'
    sector_empty = '<div class="empty">No sector activity yet.</div>'
    sector_section = f'<section class="symbols-ranking-section"><h3>Sectors by Trade Count</h3><div class="symbols-leader-list">{"".join(sector_rows) or sector_empty}</div></section>' if include_sectors else ""
    return f'''<section class="panel symbols-leaders-panel ledger-rankings-panel">
      <div class="panel-head"><div><h2>Top 5 Rankings</h2><span>Current filters</span></div></div>
      <section class="symbols-ranking-section"><h3>{escape(best_label)}</h3><div class="symbols-leader-list">{best_rows or trade_empty}</div></section>
      <section class="symbols-ranking-section"><h3>{escape(worst_label)}</h3><div class="symbols-leader-list">{worst_rows or trade_empty}</div></section>
      {sector_section}
    </section>'''


def compact_summary_cards(metrics, class_name="compact-summary-cards") -> str:
    cards = []
    metric_list = list(metrics)
    for index in range(0, len(metric_list), 2):
        pair = metric_list[index:index + 2]
        rows = "".join(
            f'<div class="compact-summary-row"><span>{escape(label)}</span><strong class="{escape(css_class)}">{value}</strong></div>'
            for label, value, css_class in pair
        )
        cards.append(f'<div class="compact-summary-card">{rows}</div>')
    return f'<section class="compact-summary-cards {escape(class_name)}">{"".join(cards)}</section>'


def symbols_summary_strip(trades, rows) -> str:
    realized = sum(trade.get("net_pnl") or 0 for trade in trades if trade.get("net_pnl") is not None)
    trade_count = sum(1 for trade in trades if trade.get("net_pnl") is not None)
    winners = sum(1 for trade in trades if trade.get("net_pnl") is not None and (trade.get("net_pnl") or 0) > 0)
    dates = trade_close_dates(trades)
    peak_capital = peak_concurrent_capital(trades, dates[0], dates[-1]) if dates else 0
    total_pl_pct = pl_pct(realized, peak_capital)
    trade_pl_pcts = [trade.get("trade_pl_pct") for trade in trades if trade.get("trade_pl_pct") is not None]
    avg_trade_pl_pct = sum(trade_pl_pcts) / len(trade_pl_pcts) if trade_pl_pcts else None
    best_symbol = max(rows, key=lambda row: row.get("total_pnl") or 0, default=None)
    worst_symbol = min(rows, key=lambda row: row.get("total_pnl") or 0, default=None)
    groups = (
        (
            ("Total P&L", money(realized), "positive" if realized >= 0 else "negative"),
            ("PL %", pct(total_pl_pct), "positive" if total_pl_pct is not None and total_pl_pct >= 0 else "negative"),
        ),
        (
            ("Symbols", f"{len(rows):,}", ""),
            ("Trades", f"{trade_count:,}", ""),
        ),
        (
            ("Win rate", pct(winners / trade_count if trade_count else None), ""),
            ("Avg Trade P/L %", pct(avg_trade_pl_pct), "positive" if avg_trade_pl_pct is not None and avg_trade_pl_pct >= 0 else "negative"),
        ),
        (
            ("Best symbol", f'{escape(best_symbol["ticker"])} {money(best_symbol["total_pnl"])}' if best_symbol else "-", "positive"),
            ("Worst symbol", f'{escape(worst_symbol["ticker"])} {money(worst_symbol["total_pnl"])}' if worst_symbol else "-", "negative" if worst_symbol and (worst_symbol.get("total_pnl") or 0) < 0 else ""),
        ),
    )
    summary_rows = []
    for pair in groups:
        for label, value, css_class in pair:
            summary_rows.append(
                f'<div class="symbols-summary-row"><span>{escape(label)}</span><strong class="{css_class}">{value}</strong></div>'
            )
    return f'<section class="symbols-summary-compact">{"".join(summary_rows)}</section>'


def symbols_rankings_panel(rows) -> str:
    pnl_leaders = sorted(
        rows,
        key=lambda row: (number(row.get("total_pnl"), 0) or 0, row.get("ticker") or ""),
        reverse=True,
    )[:5]
    win_rate_leaders = sorted(
        (row for row in rows if int(row.get("trades") or 0) >= 10),
        key=lambda row: (number(row.get("win_rate"), 0) or 0, int(row.get("trades") or 0)),
        reverse=True,
    )[:5]

    sectors = {}
    for row in rows:
        sector = row.get("sector") or "Unclassified"
        entry = sectors.setdefault(sector, {"sector": sector, "total_pnl": 0.0, "trades": 0, "symbols": 0})
        entry["total_pnl"] += number(row.get("total_pnl"), 0) or 0
        entry["trades"] += int(row.get("trades") or 0)
        entry["symbols"] += 1
    sector_leaders = sorted(
        sectors.values(),
        key=lambda item: (item["total_pnl"], item["trades"]),
        reverse=True,
    )[:5]

    def symbol_ranking(items, kind, metric, detail):
        rendered = []
        for rank, item in enumerate(items, 1):
            rendered.append(f'''<a class="symbols-leader-row" href="/symbol/{quote(item.get("ticker") or "")}">
              <span>{rank}</span>
              <b>{escape(item.get("ticker") or "-")}</b>
              <div>{metric(item)}<small>{detail(item)}</small></div>
            </a>''')
        empty = '<div class="empty">No qualifying symbols.</div>'
        return f'<div class="symbols-leader-list" data-ranking="{kind}">{"".join(rendered) or empty}</div>'

    pnl_rows = symbol_ranking(
        pnl_leaders,
        "pnl",
        lambda item: f'<strong class="{"positive" if (number(item.get("total_pnl"), 0) or 0) >= 0 else "negative"}">{money(item.get("total_pnl"))}</strong>',
        lambda item: pct(item.get("pl_pct")),
    )
    win_rate_rows = symbol_ranking(
        win_rate_leaders,
        "win-rate",
        lambda item: f'<strong class="positive">{pct(item.get("win_rate"))}</strong>',
        lambda item: f'{int(item.get("trades") or 0)} trades',
    )
    sector_rows = []
    for rank, item in enumerate(sector_leaders, 1):
        total_pnl = item["total_pnl"]
        sector_rows.append(f'''<a class="symbols-leader-row sector-leader-row" href="/symbols?sector={quote(item["sector"])}">
          <span>{rank}</span>
          <b>{escape(item["sector"])}</b>
          <div><strong class="{"positive" if total_pnl >= 0 else "negative"}">{money(total_pnl)}</strong><small>{item["symbols"]} symbols · {item["trades"]} trades</small></div>
        </a>''')
    sector_empty = '<div class="empty">No sector performance yet.</div>'
    sector_list = f'<div class="symbols-leader-list" data-ranking="sector">{"".join(sector_rows) or sector_empty}</div>'

    return f'''<section class="panel symbols-leaders-panel symbols-rankings-panel">
      <div class="panel-head"><div><h2>Top 5 Rankings</h2><span>Current filters</span></div></div>
      <section class="symbols-ranking-section"><h3>Total P&L</h3>{pnl_rows}</section>
      <section class="symbols-ranking-section"><h3>Win Rate (10+ trades)</h3>{win_rate_rows}</section>
      <section class="symbols-ranking-section"><h3>Top Sectors</h3>{sector_list}</section>
    </section>'''


def option_trades_switch(active_view: str) -> str:
    return f'''<div class="dashboard-switch">
      <a class="{"active" if active_view == "seller" else ""}" href="/trades">Option Seller</a>
      <a class="{"active" if active_view == "option-buyer" else ""}" href="/trades?view=option-buyer">Option Buyer</a>
      <a class="{"active" if active_view == "day-trades" else ""}" href="/trades?view=day-trades">Day Trades</a>
      <a class="{"active" if active_view == "stock-trades" else ""}" href="/trades?view=stock-trades">Stock Trades</a>
    </div>'''


def filter_date_field(name, value, label):
    return f'''
      <label class="filter-field date-field">
        <span>{escape(label)}</span>
        <input type="date" name="{escape(name)}" value="{escape(value or '')}" aria-label="{escape(label)}">
      </label>
    '''


def trades_page(query) -> bytes:
    view = query.get("view", [""])[0]
    if view == "day-trades":
        return day_trades_page(query, embedded=True)
    if view in {"option-buyer", "other-options"}:
        return other_options_page(query)
    if view in {"stock-trades", "stocks"}:
        return stock_trades_page(query)
    page_size = 30
    filters = {key: query.get(key, [""])[0] for key in ("q", "status", "strategy", "sector", "source", "date_from", "date_to")}
    sort_by = query.get("sort_by", ["open_date"])[0]
    sort_dir = query.get("sort_dir", ["desc"])[0]
    trades = all_trades(filters, sort_by=sort_by, sort_dir=sort_dir)
    total_trades = len(trades)
    total_pages = max(1, math.ceil(total_trades / page_size))
    try:
        page = int(query.get("page", ["1"])[0])
    except ValueError:
        page = 1
    page = min(max(page, 1), total_pages)
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_trades)
    rows = "".join(seller_trade_item(t) for t in trades[start_index:end_index])
    if not rows: rows = '<div class="empty">No trades match these filters.</div>'
    q = escape(filters["q"])

    def page_href(page_number):
        params = dict(filters)
        params.update({"sort_by": sort_by, "sort_dir": sort_dir, "page": str(page_number)})
        return f"/trades?{urlencode({k: v for k, v in params.items() if v})}"

    def sort_link(key, label):
        next_dir = "asc" if sort_by != key or sort_dir == "desc" else "desc"
        params = dict(filters)
        params.update({"sort_by": key, "sort_dir": next_dir, "page": "1"})
        href = f"/trades?{urlencode({k: v for k, v in params.items() if v})}"
        active = "active" if sort_by == key else ""
        arrow = "+" if sort_by == key and sort_dir == "asc" else "-" if sort_by == key else "*"
        return f'<th class="sortable {active}"><a href="{href}">{escape(label)} <span>{arrow}</span></a></th>'

    if total_trades:
        page_numbers = sorted(set([1, total_pages, page - 1, page, page + 1]))
        page_links = []
        previous = 0
        for page_number in page_numbers:
            if page_number < 1 or page_number > total_pages:
                continue
            if previous and page_number - previous > 1:
                page_links.append('<span class="pagination-gap">...</span>')
            page_links.append(
                f'<span class="pagination-current">{page_number}</span>'
                if page_number == page else
                f'<a href="{page_href(page_number)}">{page_number}</a>'
            )
            previous = page_number
        pagination = (
            f'<div class="pagination">'
            f'<span class="pagination-summary">Showing {start_index + 1}-{end_index} of {total_trades}</span>'
            f'<div class="pagination-pages">'
            f'<a class="{"disabled" if page == 1 else ""}" href="{page_href(max(1, page - 1))}">Prev</a>'
            f'{"".join(page_links)}'
            f'<a class="{"disabled" if page == total_pages else ""}" href="{page_href(min(total_pages, page + 1))}">Next</a>'
            f'</div></div>'
        )
    else:
        pagination = '<div class="pagination"><span class="pagination-summary">Showing 0 of 0</span></div>'

    body = f"""<div class="trades-page split-ledger-page"><div class="page-head"><div><p class="eyebrow">Option ledger</p><h1>Option Trades <span class="count">{total_trades}</span></h1>{option_trades_switch("seller")}</div><div class="actions"><a class="button secondary" href="/export.csv">Export CSV</a><a class="button" href="/option-trade/new?book=seller">Record trade</a></div></div>
    <div class="ledger-workspace" data-ledger-layout data-layout-key="trades">
      <aside class="ledger-sidebar">{option_trades_summary_strip(trades)}{trades_rankings_panel(trades)}</aside>
      <div class="ledger-splitter" data-ledger-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="ledger-main">
        <form class="filters date-filters" method="get"><input name="q" value="{q}" placeholder="Search ticker first, or longer text"><select name="status">{select_options(STATUSES,filters['status'],'All statuses')}</select><select name="strategy">{select_options(STRATEGIES,filters['strategy'],'All strategies')}</select><select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select><select name="sector">{select_options(SECTORS,filters['sector'],'All sectors')}</select><input type="date" name="date_from" value="{escape(filters['date_from'])}" aria-label="Open date from"><input type="date" name="date_to" value="{escape(filters['date_to'])}" aria-label="Open date to"><select name="sort_by" aria-label="Sort trades">{compact_sort_options((("open_date","Opened"),("ticker","Ticker"),("strategy","Strategy"),("status","Status"),("expiration","Expiration"),("net_pnl","Net P&L"),("trade_pl","P/L %")), sort_by)}</select><select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select><input type="hidden" name="page" value="1"><button class="button secondary">Filter</button><a class="clear" href="/trades">Clear</a></form>
        <section class="panel compact-transaction-panel"><div class="transaction-grid">{rows}</div>{pagination}</section>
      </div>
    </div></div>"""
    return layout("Option Trades - Option Ledger", body, "trades")


def symbols_page(query) -> bytes:
    page_size = 25
    filters = {key: query.get(key, [""])[0] for key in ("q", "status", "strategy", "sector", "source", "date_from", "date_to")}
    sort_by = query.get("sort_by", ["total_pnl"])[0]
    sort_dir = query.get("sort_dir", ["desc"])[0]
    trades = symbol_trade_records(filters)
    rows = symbol_summary(trades, sort_by=sort_by, sort_dir=sort_dir)
    total_symbols = len(rows)
    total_pages = max(1, math.ceil(total_symbols / page_size))
    try:
        page = int(query.get("page", ["1"])[0])
    except ValueError:
        page = 1
    page = min(max(page, 1), total_pages)
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_symbols)
    page_rows = rows[start_index:end_index]
    q = escape(filters["q"])

    def page_href(page_number):
        params = dict(filters)
        params.update({"sort_by": sort_by, "sort_dir": sort_dir, "page": str(page_number)})
        return f"/symbols?{urlencode({k: v for k, v in params.items() if v})}"

    symbol_items = ''.join(symbol_summary_item(item) for item in page_rows)
    if not symbol_items:
        symbol_items = '<div class="empty">No trades match these filters.</div>'
    if total_symbols:
        page_numbers = sorted(set([1, total_pages, page - 1, page, page + 1]))
        page_links = []
        previous = 0
        for page_number in page_numbers:
            if page_number < 1 or page_number > total_pages:
                continue
            if previous and page_number - previous > 1:
                page_links.append('<span class="pagination-gap">...</span>')
            page_links.append(
                f'<span class="pagination-current">{page_number}</span>'
                if page_number == page else
                f'<a href="{page_href(page_number)}">{page_number}</a>'
            )
            previous = page_number
        pagination = (
            f'<div class="pagination">'
            f'<span class="pagination-summary">Showing {start_index + 1}-{end_index} of {total_symbols}</span>'
            f'<div class="pagination-pages">'
            f'<a class="{"disabled" if page == 1 else ""}" href="{page_href(max(1, page - 1))}">Prev</a>'
            f'{"".join(page_links)}'
            f'<a class="{"disabled" if page == total_pages else ""}" href="{page_href(min(total_pages, page + 1))}">Next</a>'
            f'</div></div>'
        )
    else:
        pagination = '<div class="pagination"><span class="pagination-summary">Showing 0 of 0</span></div>'
    body = f'''<div class="symbols-page"><div class="page-head"><div><p class="eyebrow">Symbol breakdown</p><h1>Per-ticker performance</h1></div><div class="actions"><a class="button secondary" href="/trades">Back to trades</a><a class="button secondary" href="/stock-trade/new">Record stock trade</a><a class="button" href="/option-trade/new">Record trade</a></div></div>
    <div class="symbols-workspace" data-symbols-layout>
      <aside class="symbols-sidebar">{symbols_summary_strip(trades, rows)}{symbols_rankings_panel(rows)}</aside>
      <div class="symbols-splitter" data-symbols-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="symbols-ledger">
        <form class="filters date-filters" method="get"><input name="q" value="{q}" placeholder="Search ticker or sector"><select name="status">{select_options(STATUSES,filters['status'],'All statuses')}</select><select name="strategy">{select_options(SYMBOL_STRATEGY_FILTERS,filters['strategy'],'All option strategies')}</select><select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select><select name="sector">{select_options(SECTORS,filters['sector'],'All sectors')}</select><input type="date" name="date_from" value="{escape(filters['date_from'])}" aria-label="Open date from"><input type="date" name="date_to" value="{escape(filters['date_to'])}" aria-label="Open date to"><select name="sort_by" aria-label="Sort symbols">{compact_sort_options((("total_pnl","Total P&L"),("ticker","Ticker"),("sector","Sector"),("stock_pnl","Stock P&L"),("option_pnl","Option P&L"),("pl_pct","P/L %"),("avg_trade_pl_pct","Avg trade P/L %"),("trades","Trades"),("win_rate","Win rate")), sort_by)}</select><select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select><input type="hidden" name="page" value="1"><button class="button secondary">Filter</button><a class="clear" href="/symbols">Clear</a></form>
        <section class="panel compact-transaction-panel symbols-transaction-panel"><div class="transaction-grid">{symbol_items}</div>{pagination}</section>
      </div>
    </div></div>'''
    return layout("Symbols - Option Ledger", body, "symbols")


def symbol_detail_page(ticker: str, query=None) -> bytes:
    query = query or {}
    ticker = ticker.upper()
    filters = {key: query.get(key, [""])[0] for key in ("q", "status", "strategy", "option_type", "date_from", "date_to")}
    brokers, books = symbol_filter_values(query)
    option_record_href = f"/option-trade/new?{urlencode({'ticker': ticker})}"
    stock_record_href = f"/stock-trade/new?{urlencode({'ticker': ticker})}"
    symbol_actions = (
        f'<div class="actions"><a class="button secondary" href="/symbols">Back to symbols</a>'
        f'<a class="button secondary" href="{stock_record_href}">Record stock trade</a>'
        f'<a class="button" href="{option_record_href}">Record trade</a></div>'
    )
    all_rows = [trade for trade in symbol_trade_records() if trade.get("ticker", "").upper() == ticker]
    if not all_rows:
        body = f'''<div class="page-head"><div><p class="eyebrow">Ticker detail</p><h1>{escape(ticker)}</h1></div>{symbol_actions}</div>
        <section class="panel"><div class="empty">No trades found for {escape(ticker)}.</div></section>'''
        return layout(f"{ticker} - Option Ledger", body, "symbols")

    scoped_rows = filter_dashboard_trades(all_rows, brokers, books)
    perf_range = query.get("perf_range", ["all"])[0]
    perf_metric = query.get("perf_metric", ["pnl"])[0]
    perf_start = query.get("perf_start", [""])[0]
    perf_end = query.get("perf_end", [""])[0]
    range_rows = filter_trades_by_perf_range(scoped_rows, perf_range, perf_start, perf_end)
    filtered_rows = filter_symbol_detail_trades(range_rows, filters)
    closed = [trade for trade in filtered_rows if trade.get("net_pnl") is not None]
    summary = symbol_summary(closed)
    item = summary[0] if summary else {"total_pnl": 0, "pl_pct": None, "trades": 0, "win_rate": None, "capital_used": 0}
    open_count = sum(1 for trade in filtered_rows if trade.get("status") == "Open")
    avg_days = sum(trade.get("days_held") or 0 for trade in closed) / len(closed) if closed else None
    summary_card = dashboard_summary_list((
        ("Sector", escape(item.get("sector") or sector_for_ticker(ticker)), ""),
        ("Total P&L", money(item["total_pnl"]), "positive" if item["total_pnl"] >= 0 else "negative"),
        ("PL %", pct(item["pl_pct"]), "positive" if item.get("pl_pct") is not None and item["pl_pct"] >= 0 else "negative"),
        ("Trades / Win rate", f'{item["trades"]} / {pct(item["win_rate"])}', ""),
        ("Open", str(open_count), ""),
        ("Next earnings", escape(next_earnings_label(ticker)), ""),
    ))
    trade_page_params = {
        key: query.get(key, [""])[0]
        for key in ("perf_range", "perf_metric", "perf_start", "perf_end", "lang", "currency")
        if query.get(key, [""])[0]
    }
    trade_page_params.update(filters)
    trade_page_params.update(
        {
            "symbol_broker_filter": "1",
            "symbol_book_filter": "1",
            "symbol_broker": brokers,
            "symbol_book": books,
        }
    )
    page_rows, pagination = paginate_items(
        filtered_rows,
        query,
        f"/symbol/{quote(ticker)}",
        trade_page_params,
    )
    return_to_params = {key: values[0] for key, values in query.items() if values and values[0]}
    symbol_return_to = f"/symbol/{quote(ticker)}"
    if return_to_params:
        symbol_return_to += f"?{urlencode(return_to_params)}"
    rows = "".join(trade_row(trade, return_to=symbol_return_to, show_broker=True) for trade in page_rows) or '<tr><td colspan="12" class="empty">No trades match these filters.</td></tr>'
    clear_params = {
        key: query.get(key, [""])[0]
        for key in ("perf_range", "perf_metric", "perf_start", "perf_end", "lang", "currency")
        if query.get(key, [""])[0]
    }
    clear_params.update(
        {
            "symbol_broker_filter": "1",
            "symbol_book_filter": "1",
            "symbol_broker": brokers,
            "symbol_book": books,
        }
    )
    clear_href = f"/symbol/{quote(ticker)}"
    if clear_params:
        clear_href += f"?{urlencode(query_param_items(clear_params))}"
    q = escape(filters["q"])
    symbol_filter_hidden = hidden_inputs_from_params(
        [("symbol_broker_filter", "1")]
        + [("symbol_broker", broker) for broker in brokers]
        + [("symbol_book_filter", "1")]
        + [("symbol_book", book) for book in books]
    )
    symbol_extra_params = symbol_filter_params(query, brokers, books, {"perf_range", "perf_metric", "perf_start", "perf_end"})
    body = f'''<div class="symbol-detail-page">
    <div class="symbol-detail-workspace" data-ledger-layout data-layout-key="symbolDetail-{escape(ticker)}">
      <aside class="symbol-detail-sidebar">
        <section class="panel symbol-identity-panel">
          <div class="symbol-identity-heading"><span class="symbol-avatar">{escape(ticker[:1])}</span><div><p class="eyebrow">Ticker detail</p><h1>{escape(ticker)}</h1></div></div>
          <p>{escape(item.get("sector") or sector_for_ticker(ticker))}</p>
        </section>
        {symbol_price_panel(ticker, query)}
        {symbol_2027_valuation_panel(ticker)}
        {summary_card}
        {symbol_intel_panel(ticker, force=query.get("refresh", ["0"])[0] == "1")}
      </aside>
      <div class="ledger-splitter symbol-detail-splitter" data-ledger-splitter role="separator" aria-label="Resize symbol overview" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="symbol-detail-main">
        <div class="symbol-detail-toolbar">{symbol_actions}</div>
        {symbol_filter_panel(query, brokers, books, performance_range_controls(scoped_rows, perf_range, perf_metric, perf_start, perf_end, ticker, extra_params=symbol_extra_params))}
        <section class="dashboard-performance-card">
          <div class="ticker-performance-grid">
            {performance_chart(filtered_rows, perf_range, perf_metric, perf_start, perf_end, ticker, extra_params=symbol_extra_params)}
            {capital_usage_chart(filtered_rows, perf_range, perf_start, perf_end)}
          </div>
        </section>
        {strategy_performance_panel(filtered_rows, perf_range, perf_start, perf_end)}
        <section class="panel symbol-trades-panel">
          <div class="panel-head"><h2>{escape(ticker)} trades</h2><span>{len(filtered_rows)} / {len(range_rows)} records</span></div>
          <form class="filters date-filters" method="get">
            {symbol_filter_hidden}
            <input name="q" value="{q}" placeholder="Search strategy or notes">
            <select name="status">{select_options(STATUSES, filters['status'], 'All statuses')}</select>
            <select name="strategy">{select_options(SYMBOL_STRATEGY_FILTERS, filters['strategy'], 'All strategies')}</select>
            <select name="option_type">{select_options(('Call', 'Put'), filters['option_type'], 'Call / Put')}</select>
            {filter_date_field('date_from', filters['date_from'], 'Opened from')}
            {filter_date_field('date_to', filters['date_to'], 'Opened to')}
            <input type="hidden" name="perf_range" value="{escape(perf_range)}">
            <input type="hidden" name="perf_metric" value="{escape(perf_metric)}">
            <input type="hidden" name="perf_start" value="{escape(perf_start)}">
            <input type="hidden" name="perf_end" value="{escape(perf_end)}">
            <input type="hidden" name="page" value="1">
            <button class="button secondary">Filter</button>
            <a class="clear" href="{escape(clear_href)}">Clear</a>
          </form>
          <div class="table-wrap"><table data-sortable-table><thead><tr><th data-sort-key="ticker">Ticker</th><th data-sort-key="sector">Sector</th><th data-sort-key="strategy">Strategy</th><th data-sort-key="status">Status</th><th data-sort-key="open_date">Opened</th><th data-sort-key="close_date">Close date</th><th data-sort-key="expiration">Expiration</th><th data-sort-key="contracts">Contracts</th><th data-sort-key="strike">Strike</th><th data-sort-key="net_pnl">Net P&L</th><th data-sort-key="trade_pl_pct">Trade P/L %</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>{pagination}</section>
      </div>
    </div>
    </div>'''
    return layout(f"{ticker} - Option Ledger", body, "symbols")


def field(label, name, value="", kind="text", attrs="", help_text=""):
    safe_value = escape("" if value is None else str(value))
    help_html = f"<small>{escape(help_text)}</small>" if help_text else ""
    return f'<label><span>{escape(label)}</span><input type="{kind}" name="{name}" value="{safe_value}" {attrs}>{help_html}</label>'


def default_date_fields(data: dict, *names: str) -> None:
    today = date.today().isoformat()
    for name in names:
        if not data.get(name):
            data[name] = today


def default_new_trade_fields(data: dict, *contract_fields: str) -> None:
    if not data.get("broker_source"):
        data["broker_source"] = "Robinhood"
    for name in contract_fields:
        if data.get(name) in (None, ""):
            data[name] = 1


def holding_form(holding=None, error="") -> bytes:
    h = dict(holding or {})
    editing = bool(h.get("id"))
    title = "Edit stock holding" if editing else "Add stock holding"
    action = f'/holding/{h["id"]}/edit' if editing else "/holding/new"
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/holding/{h["id"]}/delete">Delete holding</button>' if editing else ""
    if not h.get("as_of"):
        h["as_of"] = date.today().isoformat()
    body = f"""<div class="narrow"><div class="page-head"><div><p class="eyebrow">{'Update shares' if editing else 'New shares'}</p><h1>{title}</h1></div><a class="clear" href="/?dashboard=stock-trades">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}">
    <fieldset><legend>Holding</legend><div class="form-grid">
    {field('Ticker','ticker',h.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. AAPL"')}
    {field('Shares','shares',h.get('shares',''),'number','required step="0.0001" min="0"')}
    {field('Average cost / share','avg_cost',h.get('avg_cost',''),'number','step="0.01" min="0"')}
    {field('Current price / share','current_price',h.get('current_price',''),'number','step="0.01" min="0"')}
    {field('As of','as_of',h.get('as_of',''),'date')}
    <label>Broker / Source<select name="broker_source">{broker_source_select('broker_source', h.get('broker_source'), 'Unknown')}</select></label>
    </div></fieldset>
    <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Dividend notes, covered call linkage, thesis...">{escape(h.get('notes') or '')}</textarea></label></fieldset>
    <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add holding'}</button></div></form></div>"""
    return layout(title + " - Option Ledger", body, "holdings")


def validate_holding(form):
    ticker = form.get("ticker", "").strip().upper()
    shares = number(form.get("shares"))
    if not ticker:
        return None, "Ticker is required."
    if shares is None or shares <= 0:
        return None, "Shares must be greater than 0."
    if form.get("as_of") and not parse_date(form["as_of"]):
        return None, "Enter a valid as of date."
    data = {
        "ticker": ticker,
        "sector": sector_for_ticker(ticker),
        "shares": shares,
        "avg_cost": number(form.get("avg_cost")),
        "current_price": number(form.get("current_price")),
        "as_of": form.get("as_of") or None,
        "broker_source": normalize_broker_source(form.get("broker_source")) or None,
        "notes": form.get("notes", "").strip() or None,
    }
    for name in ("avg_cost", "current_price"):
        if data[name] is not None and data[name] < 0:
            return None, f"{name.replace('_', ' ').title()} cannot be negative."
    return data, ""


DAY_TRADE_OPTION_TYPES = ("Call", "Put")
DAY_TRADE_OPEN_SIDES = ("Buy to open", "Sell to open")


def day_trade_pnl(row) -> float:
    contracts = number(row.get("contracts"), 0) or 0
    open_price = number(row.get("open_price"), 0) or 0
    close_price = number(row.get("close_price"), 0) or 0
    fees = number(row.get("fees"), 0) or 0
    if row.get("open_side") == "Sell to open":
        gross = (open_price - close_price) * contracts * 100
    else:
        gross = (close_price - open_price) * contracts * 100
    return gross - fees


def all_day_trades(filters=None) -> list[dict]:
    filters = filters or {}
    where, params = ["user_id = ?"], [current_user_id()]
    if filters.get("q"):
        ticker_term = ticker_search_term(filters["q"])
        if ticker_term:
            where.append("UPPER(ticker) = ?")
            params.append(ticker_term)
        else:
            like = f"%{filters['q'].strip().upper()}%"
            where.append("(UPPER(ticker) LIKE ? OR UPPER(notes) LIKE ?)")
            params.extend([like, like])
    if filters.get("option_type"):
        where.append("option_type = ?")
        params.append(filters["option_type"])
    if filters.get("open_side"):
        where.append("open_side = ?")
        params.append(filters["open_side"])
    apply_source_filter(where, params, filters.get("source"))
    if filters.get("date_from"):
        where.append("COALESCE(open_date, trade_date) >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("COALESCE(open_date, trade_date) <= ?")
        params.append(filters["date_to"])
    if filters.get("expiration_from"):
        where.append("expiration >= ?")
        params.append(filters["expiration_from"])
    if filters.get("expiration_to"):
        where.append("expiration <= ?")
        params.append(filters["expiration_to"])
    with closing(db()) as connection:
        rows = [dict(row) for row in connection.execute(
            f"SELECT * FROM day_trades WHERE {' AND '.join(where)} ORDER BY trade_date DESC, id DESC",
            params,
        ).fetchall()]
    for row in rows:
        row["pnl"] = day_trade_pnl(row)
        basis = (number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100
        row["pl_pct"] = row["pnl"] / basis if basis else None
    return rows


def day_trade_row(row: dict) -> str:
    pnl = row.get("pnl", day_trade_pnl(row))
    option_label = f'{num(row.get("strike"))} {escape(row.get("option_type") or "Option")}'
    if row.get("expiration"):
        option_label += f' <span class="muted-row">{escape(row.get("expiration"))}</span>'
    status = row.get("status") or "Closed"
    return f'''<tr{earnings_row_class(row)}>
      <td><b>{escape(row.get("open_date") or row.get("trade_date") or "-")}</b></td>
      <td>{escape(row.get("close_date") or row.get("trade_date") or "-")}</td>
      <td><span class="pill {escape(status.lower())}">{escape(status)}</span></td>
      <td>{ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row), earnings_marker(row))}</td>
      <td>{option_label}</td>
      <td>{escape(row.get("open_side") or "-")}</td>
      <td>{num(row.get("contracts"))}</td>
      <td>{money(number(row.get("open_price"), 0))}</td>
      <td>{money(number(row.get("close_price"), 0))}</td>
      <td class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</td>
      <td>{pct(row.get("pl_pct"))}</td>
      <td><a class="text-button" href="/day-trade/{row["id"]}/edit">Edit</a></td>
    </tr>'''


def day_trade_item(row: dict) -> str:
    pnl = row.get("pnl", day_trade_pnl(row))
    status = row.get("status") or "Closed"
    option_label = f'{escape(row.get("option_type") or "-")} {num(row.get("strike"))}'
    expiration = row.get("expiration") or "No expiration"
    open_side = row.get("open_side") or "-"
    side_class = "long" if open_side == "Buy to open" else "short"
    earnings_class = " earnings-row" if number(row.get("earnings_bet_id")) else ""
    return f'''<article class="transaction-item{earnings_class}">
      <div class="transaction-primary">
        {ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row))}
        <div class="holding-secondary">{escape(row.get("open_date") or row.get("trade_date") or "-")} · Day trade</div>
      </div>
      <div class="transaction-contract"><strong>{option_label}</strong><small>{escape(expiration)} · {num(row.get("contracts"))} contracts</small></div>
      <div class="transaction-state"><span class="position-side {side_class}">{escape(open_side)}</span><small class="pill {escape(status.lower())}">{escape(status)}</small></div>
      <div class="transaction-result"><strong class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</strong><small class="{"positive" if (row.get("pl_pct") or 0) >= 0 else "negative"}">{pct(row.get("pl_pct"))}</small></div>
      <a class="transaction-edit" href="/day-trade/{row["id"]}/edit">Edit</a>
    </article>'''


EARNINGS_BET_DIRECTIONS = ("Bullish", "Bearish", "Volatility", "Neutral")
EARNINGS_BET_RESULTS = ("Win", "Loss", "Breakeven", "Pending")
EARNINGS_BET_STRATEGY_TYPES = ("Stock", "Single option", "Sell option", "Combo")
EARNINGS_BET_OPTION_TYPES = ("Call", "Put")


def hydrate_earnings_bet_fields(bet: dict) -> dict:
    bet = dict(bet or {})
    strategy = str(bet.get("strategy") or "")
    if not bet.get("strategy_type"):
        if strategy.startswith("Single option"):
            bet["strategy_type"] = "Single option"
        elif strategy.startswith("Sell option"):
            bet["strategy_type"] = "Sell option"
        elif strategy.startswith("Combo"):
            bet["strategy_type"] = "Combo"
        elif strategy.startswith("Stock"):
            bet["strategy_type"] = "Stock"
    strategy_type = bet.get("strategy_type") or "Stock"
    if strategy_type in {"Single option", "Sell option"}:
        if not bet.get("option_type"):
            match = re.search(r"(?:Single option|Sell option):\s*(Call|Put)", strategy, re.I)
            if match:
                bet["option_type"] = match.group(1).title()
        if bet.get("option_contracts") in (None, ""):
            match = re.search(r"x\s*([0-9.]+)", strategy)
            if match:
                bet["option_contracts"] = match.group(1)
        contracts = number(bet.get("option_contracts"))
        cost = number(bet.get("cost_basis"))
        pnl = number(bet.get("realized_pnl"), 0) or 0
        if contracts and contracts > 0:
            if bet.get("option_open_price") in (None, "") and cost is not None:
                bet["option_open_price"] = cost / (contracts * 100)
            if bet.get("option_close_price") in (None, "") and cost is not None:
                if strategy_type == "Sell option":
                    bet["option_close_price"] = (cost - pnl) / (contracts * 100)
                else:
                    bet["option_close_price"] = (cost + pnl) / (contracts * 100)
    elif strategy_type == "Combo":
        if not bet.get("combo_description"):
            bet["combo_description"] = strategy.replace("Combo:", "", 1).strip() if strategy.startswith("Combo:") else strategy
        units = number(bet.get("combo_units"))
        cost = number(bet.get("cost_basis"))
        pnl = number(bet.get("realized_pnl"), 0) or 0
        if units and units > 0:
            if bet.get("combo_open_cost") in (None, "") and cost is not None:
                bet["combo_open_cost"] = cost / (units * 100)
            if bet.get("combo_close_value") in (None, "") and cost is not None:
                bet["combo_close_value"] = (cost + pnl) / (units * 100)
    return bet


def all_earnings_bets(filters=None) -> list[dict]:
    filters = filters or {}
    where, params = ["user_id = ?"], [current_user_id()]
    if filters.get("q"):
        ticker_term = ticker_search_term(filters["q"])
        if ticker_term:
            where.append("UPPER(ticker) = ?")
            params.append(ticker_term)
        else:
            like = f"%{filters['q'].strip().upper()}%"
            where.append("(UPPER(ticker) LIKE ? OR UPPER(strategy) LIKE ? OR UPPER(notes) LIKE ?)")
            params.extend([like, like, like])
    if filters.get("result"):
        where.append("result = ?")
        params.append(filters["result"])
    apply_source_filter(where, params, filters.get("source"))
    if filters.get("date_from"):
        where.append("earnings_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("earnings_date <= ?")
        params.append(filters["date_to"])
    with closing(db()) as connection:
        rows = [dict(row) for row in connection.execute(
            f"SELECT * FROM earnings_bets WHERE {' AND '.join(where)} ORDER BY earnings_date DESC, id DESC",
            params,
        ).fetchall()]
    for row in rows:
        cost = earnings_bet_return_basis(row)
        pnl = number(row.get("realized_pnl"), 0) or 0
        row["pnl_pct"] = pnl / cost if cost else None
    return rows


def earnings_bet_return_basis(row: dict) -> float:
    strategy_type = row.get("strategy_type") or ""
    strategy = row.get("strategy") or ""
    if strategy_type == "Sell option" or strategy.startswith("Sell option"):
        return number(row.get("position_size"), 0) or number(row.get("cost_basis"), 0) or 0
    return number(row.get("cost_basis"), 0) or 0


def earnings_bet_row(row: dict) -> str:
    pnl = number(row.get("realized_pnl"), 0) or 0
    result = row.get("result") or "Pending"
    pnl_class = "positive" if pnl >= 0 else "negative"
    return f'''<tr{earnings_row_class(row)}>
      <td><b>{escape(row.get("earnings_date") or "-")}</b></td>
      <td>{ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row))}</td>
      <td>{escape(row.get("direction") or "-")}</td>
      <td>{escape(row.get("strategy") or "-")}</td>
      <td>{money(number(row.get("position_size"), 0))}</td>
      <td>{money(number(row.get("cost_basis"), 0))}</td>
      <td class="{pnl_class}">{money(pnl)}</td>
      <td class="{pnl_class}">{pct(row.get("pnl_pct"))}</td>
      <td><span class="pill {escape(result.lower())}">{escape(result)}</span></td>
      <td><a class="text-button" href="/earnings-bet/{row["id"]}/edit">Edit</a></td>
    </tr>'''


def earnings_bet_item(row: dict) -> str:
    pnl = number(row.get("realized_pnl"), 0) or 0
    pnl_pct_value = row.get("pnl_pct")
    result = row.get("result") or "Pending"
    direction = row.get("direction") or "-"
    direction_class = "long" if direction == "Bullish" else "short" if direction == "Bearish" else ""
    return f'''<article class="transaction-item">
      <div class="transaction-primary">
        {ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row))}
        <div class="holding-secondary">{escape(row.get("earnings_date") or "-")} · {escape(row.get("strategy") or "-")}</div>
      </div>
      <div class="transaction-state"><span class="position-side {direction_class}">{escape(direction)}</span><small class="pill {escape(result.lower())}">{escape(result)}</small></div>
      <div class="transaction-result"><strong class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</strong><small class="{"positive" if (pnl_pct_value or 0) >= 0 else "negative"}">{pct(pnl_pct_value)}</small></div>
      <a class="transaction-edit" href="/earnings-bet/{row["id"]}/edit">Edit</a>
    </article>'''


def earnings_bets_page(query=None) -> bytes:
    query = query or {}
    filters = {key: query.get(key, [""])[0] for key in ("q", "result", "source", "date_from", "date_to")}
    sort_by = query.get("sort_by", ["earnings_date"])[0]
    sort_dir = query.get("sort_dir", ["desc"])[0]
    rows = all_earnings_bets(filters)
    valid_sort = {
        "earnings_date": lambda row: row.get("earnings_date") or "",
        "ticker": lambda row: row.get("ticker") or "",
        "source": lambda row: broker_source_for_row(row) or "",
        "direction": lambda row: row.get("direction") or "",
        "strategy": lambda row: row.get("strategy") or "",
        "position_size": lambda row: number(row.get("position_size"), 0) or 0,
        "cost_basis": lambda row: number(row.get("cost_basis"), 0) or 0,
        "realized_pnl": lambda row: number(row.get("realized_pnl"), 0) or 0,
        "pnl_pct": lambda row: row.get("pnl_pct") if row.get("pnl_pct") is not None else -999999,
        "result": lambda row: row.get("result") or "",
    }
    sort_key = sort_by if sort_by in valid_sort else "earnings_date"
    sort_dir = "asc" if sort_dir == "asc" else "desc"
    rows.sort(key=valid_sort[sort_key], reverse=sort_dir == "desc")

    def sort_link(key, label):
        next_dir = "asc" if sort_key != key or sort_dir == "desc" else "desc"
        params = {**filters, "sort_by": key, "sort_dir": next_dir, "page": "1"}
        href = f"/earnings-bets?{urlencode({k: v for k, v in params.items() if v})}"
        active = "active" if sort_key == key else ""
        arrow = "+" if sort_key == key and sort_dir == "asc" else "-" if sort_key == key else "*"
        return f'<th class="sortable {active}"><a href="{href}">{escape(label)} <span>{arrow}</span></a></th>'

    total_pnl = sum(number(row.get("realized_pnl"), 0) or 0 for row in rows)
    closed = [row for row in rows if row.get("result") != "Pending"]
    wins = sum(1 for row in closed if (number(row.get("realized_pnl"), 0) or 0) > 0)
    breakeven_count = sum(1 for row in rows if row.get("result") == "Breakeven")
    loss_count = sum(1 for row in rows if row.get("result") == "Loss")
    total_cost = sum(earnings_bet_return_basis(row) for row in rows)
    pnl_pct_values = [row.get("pnl_pct") for row in rows if row.get("pnl_pct") is not None]
    avg_pnl = total_pnl / len(rows) if rows else 0
    avg_pnl_pct = sum(pnl_pct_values) / len(pnl_pct_values) if pnl_pct_values else None
    metrics = (
        ("Total P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Cost basis", money(total_cost), ""),
        ("P&L %", pct(total_pnl / total_cost if total_cost else None), "positive" if total_cost and total_pnl >= 0 else "negative"),
        ("Avg P&L", money(avg_pnl), "positive" if avg_pnl >= 0 else "negative"),
        ("Avg P/L %", pct(avg_pnl_pct), "positive" if avg_pnl_pct is not None and avg_pnl_pct >= 0 else "negative"),
        ("Bets", f"{len(rows):,}", ""),
        ("Win rate", pct(wins / len(closed) if closed else None), ""),
        ("Results", f"{wins:,} / {breakeven_count:,} / {loss_count:,}", ""),
    )
    base_params = {**filters, "sort_by": sort_key, "sort_dir": sort_dir}
    page_rows, pagination = paginate_items(
        rows,
        query,
        "/earnings-bets",
        base_params,
        page_size=30,
    )
    table_rows = "".join(earnings_bet_item(row) for row in page_rows) or '<div class="empty">No earnings bets yet.</div>'
    body = f'''<div class="earnings-bets-page split-ledger-page"><div class="page-head"><div><p class="eyebrow">Earnings results</p><h1>Earnings <span class="count">{len(rows)}</span></h1></div><div class="actions"><a class="button" href="/earnings-bet/new">Record earnings bet</a></div></div>
    <div class="ledger-workspace" data-ledger-layout data-layout-key="earnings">
      <aside class="ledger-sidebar">
        {compact_summary_cards(metrics, "earnings-summary-compact")}
        {trades_rankings_panel(rows, "realized_pnl", "earnings-bet", ("earnings_date",), ("strategy",), True, "Best Earnings", "Worst Earnings")}
      </aside>
      <div class="ledger-splitter" data-ledger-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="ledger-main">
        <section class="panel earnings-reminder-panel is-loading" id="this-week" data-earnings-reminder>
          <div class="panel-head earnings-reminder-head"><div><h2>This Week Earnings</h2><span>Loading this week's reports...</span></div></div>
          <div class="earnings-reminder-grid"><div class="earnings-reminder-loading">Loading...</div></div>
        </section>
        <form class="filters date-filters" method="get">
          <input name="q" value="{escape(filters['q'])}" placeholder="Search ticker, strategy, or notes">
          <select name="result">{select_options(EARNINGS_BET_RESULTS, filters['result'], 'All results')}</select>
          <select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select>
          <input type="date" name="date_from" value="{escape(filters['date_from'])}" aria-label="Earnings date from">
          <input type="date" name="date_to" value="{escape(filters['date_to'])}" aria-label="Earnings date to">
          <select name="sort_by" aria-label="Sort earnings bets">{compact_sort_options((("earnings_date","Earnings date"),("ticker","Ticker"),("direction","Direction"),("strategy","Strategy"),("position_size","Position size"),("cost_basis","Cost"),("realized_pnl","P&L"),("pnl_pct","P/L %"),("result","Result")), sort_key)}</select>
          <select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select>
          <input type="hidden" name="page" value="1">
          <button class="button secondary">Filter</button><a class="clear" href="/earnings-bets">Clear</a>
        </form>
        <section class="panel compact-transaction-panel"><div class="transaction-grid">{table_rows}</div>{pagination}</section>
      </div>
    </div></div>'''
    return layout("Earnings - Option Ledger", body, "earnings-bets")


def earnings_bet_form(row=None, error="") -> bytes:
    bet = hydrate_earnings_bet_fields(dict(row or {}))
    editing = bool(bet.get("id"))
    if not bet.get("earnings_date"):
        bet["earnings_date"] = date.today().isoformat()
    strategy_text = str(bet.get("strategy") or "")
    inferred_type = bet.get("strategy_type") or (
        "Single option" if "Single option" in strategy_text else
        "Sell option" if "Sell option" in strategy_text else
        "Combo" if "Combo" in strategy_text else
        "Stock" if "Stock" in strategy_text else
        "Stock"
    )
    title = "Edit earnings bet" if editing else "Record earnings bet"
    action = f'/earnings-bet/{bet["id"]}/edit' if editing else "/earnings-bet/new"
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/earnings-bet/{bet["id"]}/delete">Delete earnings bet</button>' if editing else ""
    body = f'''<div class="narrow"><div class="page-head"><div><p class="eyebrow">Earnings play</p><h1>{title}</h1></div><a class="clear" href="/earnings-bets">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}" data-earnings-bet-form>
      <fieldset><legend>Setup</legend><div class="form-grid">
        {field('Ticker','ticker',bet.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. NVDA"')}
        {field('Earnings date','earnings_date',bet.get('earnings_date',''),'date','required')}
        <label><span>Direction</span><select name="direction" required>{select_options(EARNINGS_BET_DIRECTIONS, bet.get('direction') or 'Bullish')}</select></label>
        <label><span>Strategy type</span><select name="strategy_type" required data-earnings-strategy-type>{select_options(EARNINGS_BET_STRATEGY_TYPES, inferred_type)}</select></label>
        <label><span>Result</span><select name="result" required>{select_options(EARNINGS_BET_RESULTS, bet.get('result') or 'Pending')}</select></label>
        <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', bet.get('broker_source'))}</select></label>
        <label><span>Linked trade</span><select name="linked_trade_key">{earnings_trade_link_options(bet)}</select></label>
      </div></fieldset>
      <fieldset data-earnings-strategy-section="Stock"><legend>Stock</legend><div class="form-grid">
        {field('Shares','stock_shares',bet.get('stock_shares',''),'number','step="0.0001" min="0"')}
        {field('Buy price','stock_buy_price',bet.get('stock_buy_price',''),'number','step="0.01" min="0"')}
        {field('Sell price','stock_sell_price',bet.get('stock_sell_price',''),'number','step="0.01" min="0"')}
      </div></fieldset>
      <fieldset data-earnings-strategy-section="Single option"><legend>Single Option</legend><div class="form-grid">
        <label><span>Option type</span><select name="option_type">{select_options(EARNINGS_BET_OPTION_TYPES, bet.get('option_type') or 'Call')}</select></label>
        {field('Contracts','option_contracts',bet.get('option_contracts',''),'number','step="1" min="0"')}
        {field('Open price / contract','option_open_price',bet.get('option_open_price',''),'number','step="any" min="0"')}
        {field('Close price / contract','option_close_price',bet.get('option_close_price',''),'number','step="any" min="0"')}
      </div></fieldset>
      <fieldset data-earnings-strategy-section="Sell option"><legend>Sell Option</legend><div class="form-grid">
        <label><span>Option type</span><select name="option_type">{select_options(EARNINGS_BET_OPTION_TYPES, bet.get('option_type') or 'Call')}</select></label>
        {field('Contracts','option_contracts',bet.get('option_contracts',''),'number','step="1" min="0"')}
        {field('Open credit / contract','option_open_price',bet.get('option_open_price',''),'number','step="0.01" min="0"')}
        {field('Close price / contract','option_close_price',bet.get('option_close_price',''),'number','step="any" min="0"')}
      </div></fieldset>
      <fieldset data-earnings-strategy-section="Combo"><legend>Combination</legend><div class="form-grid">
        <label><span>Combo description</span><input name="combo_description" value="{escape(str(bet.get('combo_description') or bet.get('strategy') or ''))}" maxlength="120" placeholder="e.g. Straddle, iron condor, calendar"></label>
        {field('Contracts / units','combo_units',bet.get('combo_units',''),'number','step="1" min="0"')}
        {field('Open debit / risk','combo_open_cost',bet.get('combo_open_cost',''),'number','step="0.01" min="0"')}
        {field('Close value','combo_close_value',bet.get('combo_close_value',''),'number','step="0.01" min="0"')}
      </div></fieldset>
      <fieldset><legend>Outcome</legend><div class="form-grid">
        {field('Position size override','position_size',bet.get('position_size',''),'number','step="0.01" min="0"', 'Optional. Leave blank to auto-calculate.')}
        {field('Cost / risk override','cost_basis',bet.get('cost_basis',''),'number','step="0.01" min="0"', 'Optional. Leave blank to auto-calculate.')}
        {field('Realized P&L override','realized_pnl',bet.get('realized_pnl',''),'number','step="0.01"', 'Optional. Leave blank to auto-calculate.')}
      </div></fieldset>
      <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Expected move, IV crush, entry/exit, what you learned...">{escape(bet.get('notes') or '')}</textarea></label></fieldset>
      <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add earnings bet'}</button></div>
    </form></div>'''
    return layout(title + " - Option Ledger", body, "earnings-bets")


def validate_earnings_bet(form):
    ticker = form.get("ticker", "").strip().upper()
    earnings_date = form.get("earnings_date", "")
    direction = form.get("direction", "")
    result = form.get("result", "")
    strategy_type = form.get("strategy_type", "Stock")
    if not ticker:
        return None, "Ticker is required."
    if not parse_date(earnings_date):
        return None, "Enter a valid earnings date."
    if direction not in EARNINGS_BET_DIRECTIONS:
        return None, "Choose a valid direction."
    if result not in EARNINGS_BET_RESULTS:
        return None, "Choose a valid result."
    if strategy_type not in EARNINGS_BET_STRATEGY_TYPES:
        return None, "Choose a valid strategy type."
    strategy = strategy_type
    position_size = number(form.get("position_size"))
    cost_basis = number(form.get("cost_basis"))
    realized_pnl = number(form.get("realized_pnl"))
    if strategy_type == "Stock":
        shares = number(form.get("stock_shares"))
        buy_price = number(form.get("stock_buy_price"))
        sell_price = number(form.get("stock_sell_price"))
        if shares is not None or buy_price is not None or sell_price is not None:
            if shares is None or shares <= 0:
                return None, "Stock shares must be greater than 0."
            for label, value in (("Stock buy price", buy_price), ("Stock sell price", sell_price)):
                if value is None or value < 0:
                    return None, f"{label} must be zero or greater."
            auto_cost = shares * buy_price
            position_size = position_size if position_size is not None else shares * sell_price
            cost_basis = cost_basis if cost_basis is not None else auto_cost
            realized_pnl = realized_pnl if realized_pnl is not None else (sell_price - buy_price) * shares
            strategy = f"Stock: {num(shares)} shares"
        raw_fields = {
            "stock_shares": shares,
            "stock_buy_price": buy_price,
            "stock_sell_price": sell_price,
            "option_type": None,
            "option_contracts": None,
            "option_open_price": None,
            "option_close_price": None,
            "combo_description": None,
            "combo_units": None,
            "combo_open_cost": None,
            "combo_close_value": None,
        }
    elif strategy_type in {"Single option", "Sell option"}:
        option_type = form.get("option_type", "Call")
        contracts = number(form.get("option_contracts"))
        open_price = number(form.get("option_open_price"))
        close_price = number(form.get("option_close_price"))
        if option_type not in EARNINGS_BET_OPTION_TYPES:
            return None, "Choose Call or Put."
        if contracts is not None or open_price is not None or close_price is not None:
            if contracts is None or contracts <= 0:
                return None, "Option contracts must be greater than 0."
            for label, value in (("Open price", open_price), ("Close price", close_price)):
                if value is None or value < 0:
                    return None, f"{label} must be zero or greater."
            auto_cost = contracts * open_price * 100
            if position_size is None:
                position_size = auto_cost if strategy_type == "Sell option" else contracts * close_price * 100
            cost_basis = cost_basis if cost_basis is not None else auto_cost
            if strategy_type == "Sell option":
                realized_pnl = realized_pnl if realized_pnl is not None else (open_price - close_price) * contracts * 100
                strategy = f"Sell option: {option_type} x{num(contracts)}"
            else:
                realized_pnl = realized_pnl if realized_pnl is not None else (close_price - open_price) * contracts * 100
                strategy = f"Single option: {option_type} x{num(contracts)}"
        raw_fields = {
            "stock_shares": None,
            "stock_buy_price": None,
            "stock_sell_price": None,
            "option_type": option_type,
            "option_contracts": contracts,
            "option_open_price": open_price,
            "option_close_price": close_price,
            "combo_description": None,
            "combo_units": None,
            "combo_open_cost": None,
            "combo_close_value": None,
        }
    else:
        description = form.get("combo_description", "").strip()
        units = number(form.get("combo_units"))
        open_cost = number(form.get("combo_open_cost"))
        close_value = number(form.get("combo_close_value"))
        if units is not None or open_cost is not None or close_value is not None:
            if units is None or units <= 0:
                return None, "Combo units must be greater than 0."
            for label, value in (("Open debit / risk", open_cost), ("Close value", close_value)):
                if value is None or value < 0:
                    return None, f"{label} must be zero or greater."
            auto_cost = units * open_cost * 100
            position_size = position_size if position_size is not None else units * close_value * 100
            cost_basis = cost_basis if cost_basis is not None else auto_cost
            realized_pnl = realized_pnl if realized_pnl is not None else (close_value - open_cost) * units * 100
        strategy = f"Combo: {description or 'custom'}"
        raw_fields = {
            "stock_shares": None,
            "stock_buy_price": None,
            "stock_sell_price": None,
            "option_type": None,
            "option_contracts": None,
            "option_open_price": None,
            "option_close_price": None,
            "combo_description": description or None,
            "combo_units": units,
            "combo_open_cost": open_cost,
            "combo_close_value": close_value,
        }
    data = {
        "ticker": ticker,
        "earnings_date": earnings_date,
        "direction": direction,
        "strategy": strategy,
        "strategy_type": strategy_type,
        "position_size": position_size,
        "cost_basis": cost_basis,
        "realized_pnl": realized_pnl if realized_pnl is not None else 0,
        "result": result,
        "broker_source": normalize_broker_source(form.get("broker_source")),
        "linked_trade_key": form.get("linked_trade_key", ""),
        "notes": form.get("notes", "").strip() or None,
    }
    data.update(raw_fields)
    for name in ("position_size", "cost_basis"):
        if data[name] is not None and data[name] < 0:
            return None, f"{name.replace('_', ' ').title()} cannot be negative."
    return data, ""


STOCK_TRADE_SIDES = ("Buy", "Sell")


def holding_as_stock_trade(row: dict) -> dict:
    ticker = (row.get("ticker") or "").strip().upper()
    shares = number(row.get("shares"), 0) or 0
    avg_cost = number(row.get("avg_cost"), 0) or 0
    current_price = number(row.get("current_price"))
    as_of = row.get("as_of") or row.get("updated_at") or date.today().isoformat()
    return {
        "id": f'holding-{row.get("id")}',
        "is_holding_snapshot": True,
        "edit_href": f'/holding/{row.get("id")}/edit',
        "user_id": row.get("user_id"),
        "ticker": ticker,
        "sector": row.get("sector") or sector_for_ticker(ticker),
        "broker_source": broker_source_for_row(row),
        "status": "Open",
        "side": "Buy",
        "trade_date": as_of,
        "shares": shares,
        "price": avg_cost,
        "buy_price": avg_cost,
        "sell_price": None,
        "current_price": current_price,
        "as_of": as_of,
        "realized_pnl": (current_price - avg_cost) * shares if current_price is not None else None,
        "notes": row.get("notes") or "Current holding snapshot",
        "earnings_bet_id": None,
    }


def all_stock_trades(filters=None) -> list[dict]:
    filters = filters or {}
    where, params = ["user_id = ?"], [current_user_id()]
    if filters.get("q"):
        ticker_term = ticker_search_term(filters["q"])
        if ticker_term:
            where.append("UPPER(ticker) = ?")
            params.append(ticker_term)
        else:
            like = f"%{filters['q'].strip().upper()}%"
            where.append("(UPPER(ticker) LIKE ? OR UPPER(notes) LIKE ?)")
            params.extend([like, like])
    if filters.get("date_from"):
        where.append("trade_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("trade_date <= ?")
        params.append(filters["date_to"])
    if filters.get("status"):
        where.append("COALESCE(status, 'Closed') = ?")
        params.append(filters["status"])
    apply_source_filter(where, params, filters.get("source"))
    with closing(db()) as connection:
        rows = [dict(row) for row in connection.execute(
            f"SELECT * FROM stock_trades WHERE {' AND '.join(where)} ORDER BY trade_date DESC, id DESC",
            params,
        ).fetchall()]
    for row in rows:
        shares = number(row.get("shares"), 0) or 0
        buy_price = number(row.get("buy_price"))
        sell_price = number(row.get("sell_price"))
        current_price = number(row.get("current_price"))
        legacy_price = number(row.get("price"), 0) or 0
        status = row.get("status") or "Closed"
        if buy_price is None:
            buy_price = legacy_price
        if status == "Open":
            row["realized_pnl"] = (current_price - buy_price) * shares if current_price is not None else None
            continue
        if sell_price is None:
            sell_price = legacy_price
        stored_pnl = number(row.get("realized_pnl"))
        row["realized_pnl"] = stored_pnl if stored_pnl is not None else (sell_price - buy_price) * shares
    rows.sort(key=lambda row: (str(row.get("trade_date") or ""), str(row.get("id") or "")), reverse=True)
    return rows


def stock_trade_as_trade(row: dict) -> dict:
    status = row.get("status") or "Closed"
    shares = number(row.get("shares"), 0) or 0
    buy_price = number(row.get("buy_price"))
    sell_price = number(row.get("sell_price"))
    current_price = number(row.get("current_price"))
    legacy_price = number(row.get("price"), 0) or 0
    if buy_price is None:
        buy_price = legacy_price
    if status == "Open":
        exit_price = current_price
        pnl = (current_price - buy_price) * shares if current_price is not None else None
    else:
        if sell_price is None:
            sell_price = legacy_price
        exit_price = sell_price
        pnl = number(row.get("realized_pnl"), 0) or 0
    pnl_value = number(pnl)
    if pnl_value is None:
        pnl_value = None
    if sell_price is None:
        sell_price = legacy_price
    capital = shares * buy_price
    opened = parse_date(row.get("trade_date"))
    held_until = date.today() if status == "Open" else opened
    days_held = max(0, (held_until - opened).days) if opened and held_until else None
    return {
        "id": f'stock-{row.get("id")}',
        "source": "stock_trade",
        "broker_source": broker_source_for_row(row),
        "earnings_bet_id": row.get("earnings_bet_id"),
        "ticker": row.get("ticker"),
        "sector": sector_for_ticker(row.get("ticker")),
        "strategy": "Stock Position" if status == "Open" else "Stock Sell",
        "status": status,
        "open_date": row.get("trade_date"),
        "close_date": None if status == "Open" else row.get("trade_date"),
        "expiration": None,
        "contracts": shares,
        "strike": exit_price,
        "long_put_strike": None,
        "premium_in": buy_price,
        "exit_premium": exit_price,
        "stock_pnl": pnl_value,
        "fees": 0,
        "capital_used": capital,
        "notes": row.get("notes"),
        "premium_pnl": pnl_value,
        "trade_pl_pct": pnl_value / capital if pnl_value is not None and capital else None,
        "net_pnl": pnl_value,
        "days_held": days_held,
        "roc": pnl_value / capital if pnl_value is not None and capital else None,
        "annualized_return": None,
        "outcome": "Open" if status == "Open" else "Win" if (pnl_value or 0) > 0 else "Loss" if (pnl_value or 0) < 0 else "Breakeven",
        "spread_width": None,
        "max_loss": None,
    }


def stock_trade_row(row: dict) -> str:
    status = row.get("status") or "Closed"
    shares = number(row.get("shares"), 0) or 0
    buy_price = number(row.get("buy_price"))
    sell_price = number(row.get("sell_price"))
    current_price = number(row.get("current_price"))
    legacy_price = number(row.get("price"), 0) or 0
    if buy_price is None:
        buy_price = legacy_price
    if status == "Open":
        exit_price = current_price
        pnl = (current_price - buy_price) * shares if current_price is not None else None
    else:
        if sell_price is None:
            sell_price = legacy_price
        exit_price = sell_price
        pnl = number(row.get("realized_pnl"), 0) or 0
    if sell_price is None:
        sell_price = legacy_price
    cost = shares * buy_price
    proceeds = shares * exit_price if exit_price is not None else None
    pl_pct_value = pnl / cost if pnl is not None and cost else None
    edit_href = row.get("edit_href") or f'/stock-trade/{row["id"]}/edit'
    return f'''<tr{earnings_row_class(row)}>
      <td><b>{escape(row.get("trade_date") or "-")}</b></td>
      <td>{ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row), earnings_marker(row))}</td>
      <td>{escape(status)}</td>
      <td>{num(row.get("shares"))}</td>
      <td>{money(buy_price)}</td>
      <td>{money(exit_price)}</td>
      <td>{money(cost)}</td>
      <td>{money(proceeds)}</td>
      <td class="{"positive" if (pnl or 0) >= 0 else "negative"}">{money(pnl)}</td>
      <td class="{"positive" if (pl_pct_value or 0) >= 0 else "negative"}">{pct(pl_pct_value)}</td>
      <td><a class="text-button" href="{escape(edit_href)}">Edit</a></td>
    </tr>'''


def stock_trade_item(row: dict) -> str:
    status = row.get("status") or "Closed"
    shares = number(row.get("shares"), 0) or 0
    buy_price = number(row.get("buy_price"))
    sell_price = number(row.get("sell_price"))
    current_price = number(row.get("current_price"))
    legacy_price = number(row.get("price"), 0) or 0
    if buy_price is None:
        buy_price = legacy_price
    if status == "Open":
        exit_price = current_price
        pnl = (current_price - buy_price) * shares if current_price is not None else None
    else:
        exit_price = sell_price if sell_price is not None else legacy_price
        pnl = number(row.get("realized_pnl"), 0) or 0
    cost = shares * buy_price
    value = shares * exit_price if exit_price is not None else None
    pnl_pct_value = pnl / cost if pnl is not None and cost else None
    edit_href = row.get("edit_href") or f'/stock-trade/{row["id"]}/edit'
    earnings_class = " earnings-row" if number(row.get("earnings_bet_id")) else ""
    return f'''<article class="transaction-item{earnings_class}">
      <div class="transaction-primary">
        {ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row))}
        <div class="holding-secondary">{escape(row.get("trade_date") or "-")} · {num(shares)} shares</div>
      </div>
      <div class="transaction-contract"><strong>{num(shares)} Shares</strong><small>{money(value)} value · {money(buy_price)} avg</small></div>
      <div class="transaction-state"><span class="position-side long">Long</span><small class="pill {escape(status.lower())}">{escape(status)}</small></div>
      <div class="transaction-result"><strong class="{"positive" if (pnl or 0) >= 0 else "negative"}">{money(pnl)}</strong><small class="{"positive" if (pnl_pct_value or 0) >= 0 else "negative"}">{pct(pnl_pct_value)}</small></div>
      <a class="transaction-edit" href="{escape(edit_href)}">Edit</a>
    </article>'''


def stock_trades_page(query=None) -> bytes:
    query = query or {}
    filters = {key: query.get(key, [""])[0] for key in ("q", "status", "source", "date_from", "date_to")}
    rows = all_stock_trades(filters)
    stock_sort_fields = {
        "trade_date": lambda row: row.get("trade_date") or "",
        "ticker": lambda row: row.get("ticker") or "",
        "source": lambda row: broker_source_for_row(row) or "",
        "status": lambda row: row.get("status") or "Closed",
        "shares": lambda row: number(row.get("shares"), 0) or 0,
        "buy_price": lambda row: number(row.get("buy_price"), number(row.get("price"), 0)) or 0,
        "sell_price": lambda row: number(row.get("current_price") if (row.get("status") or "Closed") == "Open" else row.get("sell_price"), number(row.get("price"), 0)) or 0,
        "cost": lambda row: (number(row.get("shares"), 0) or 0) * (number(row.get("buy_price"), number(row.get("price"), 0)) or 0),
        "proceeds": lambda row: (number(row.get("shares"), 0) or 0) * (number(row.get("current_price") if (row.get("status") or "Closed") == "Open" else row.get("sell_price"), number(row.get("price"), 0)) or 0),
        "realized_pnl": lambda row: number(row.get("realized_pnl"), 0) or 0,
        "pl_pct": lambda row: (number(row.get("realized_pnl"), 0) or 0) / ((number(row.get("shares"), 0) or 0) * (number(row.get("buy_price"), number(row.get("price"), 0)) or 0)) if ((number(row.get("shares"), 0) or 0) * (number(row.get("buy_price"), number(row.get("price"), 0)) or 0)) else -999999,
    }
    sort_key, sort_dir = apply_table_sort(rows, query, stock_sort_fields, "trade_date", "desc")
    base_params = {"view": "stock-trades", **filters, "sort_by": sort_key, "sort_dir": sort_dir}
    total_pnl = sum(number(row.get("realized_pnl"), 0) or 0 for row in rows)
    winners = sum(1 for row in rows if (number(row.get("realized_pnl"), 0) or 0) > 0)
    total_cost = sum((number(row.get("shares"), 0) or 0) * (number(row.get("buy_price"), number(row.get("price"), 0)) or 0) for row in rows)
    total_proceeds = sum((number(row.get("shares"), 0) or 0) * (number(row.get("sell_price"), number(row.get("price"), 0)) or 0) for row in rows)
    best, best_class = trade_extreme_value(rows, "realized_pnl", True)
    worst, worst_class = trade_extreme_value(rows, "realized_pnl", False)
    metrics = (
        ("Realized P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Cost basis", money(total_cost), ""),
        ("Proceeds", money(total_proceeds), ""),
        ("Trades", f"{len(rows):,}", ""),
        ("Win rate", pct(winners / len(rows) if rows else None), ""),
        ("Average P&L", money(total_pnl / len(rows) if rows else 0), "positive" if total_pnl >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    )
    page_rows, pagination = paginate_items(
        rows,
        query,
        "/trades",
        base_params,
        page_size=30,
    )
    table_rows = "".join(stock_trade_item(row) for row in page_rows) or '<div class="empty">No stock trades yet.</div>'
    body = f'''<div class="trades-page split-ledger-page"><div class="page-head"><div><p class="eyebrow">Stock transactions</p><h1>Stock Trades <span class="count">{len(rows)}</span></h1>{option_trades_switch("stock-trades")}</div><div class="actions"><a class="button" href="/stock-trade/new">Record stock trade</a></div></div>
    <div class="ledger-workspace" data-ledger-layout data-layout-key="stockTrades">
      <aside class="ledger-sidebar">{compact_summary_cards(metrics, "trades-summary-compact")}{trades_rankings_panel(rows, "realized_pnl", "stock-trade", ("trade_date",), ("status",))}</aside>
      <div class="ledger-splitter" data-ledger-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="ledger-main">
        <form class="filters date-filters" method="get">
          <input type="hidden" name="view" value="stock-trades">
          <input name="q" value="{escape(filters['q'])}" placeholder="Search ticker or notes">
          <select name="status">{select_options(STATUSES, filters['status'], 'All statuses')}</select>
          <select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select>
          <input type="date" name="date_from" value="{escape(filters['date_from'])}" aria-label="Date from">
          <input type="date" name="date_to" value="{escape(filters['date_to'])}" aria-label="Date to">
          <select name="sort_by" aria-label="Sort stock trades">{compact_sort_options((("trade_date","Date"),("ticker","Ticker"),("status","Status"),("shares","Shares"),("buy_price","Buy price"),("sell_price","Current / Sell"),("cost","Cost"),("proceeds","Value / Proceeds"),("realized_pnl","P&L"),("pl_pct","P/L %")), sort_key)}</select>
          <select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select>
          <button class="button secondary">Filter</button><a class="clear" href="/trades?view=stock-trades">Clear</a>
        </form>
        <section class="panel compact-transaction-panel"><div class="transaction-grid">{table_rows}</div>{pagination}</section>
      </div>
    </div></div>'''
    return layout("Stock Trades - Option Ledger", body, "trades")


def stock_trade_form(row=None, error="", return_to: str = "") -> bytes:
    trade = dict(row or {})
    return_to = safe_return_to(return_to or trade.get("return_to"), "/trades?view=stock-trades")
    editing = bool(trade.get("id"))
    if not editing:
        default_date_fields(trade, "trade_date")
        default_new_trade_fields(trade)
    if not trade.get("open_date"):
        trade["open_date"] = trade.get("trade_date") or date.today().isoformat()
    if not trade.get("status"):
        trade["status"] = "Closed"
    if trade.get("buy_price") is None and trade.get("price") is not None:
        trade["buy_price"] = trade.get("price")
    if trade.get("sell_price") is None and trade.get("price") is not None and trade.get("status") != "Open":
        trade["sell_price"] = trade.get("price")
    if trade.get("current_price") is None and trade.get("status") == "Open":
        trade["current_price"] = trade.get("sell_price") or ""
    title = "Edit stock trade" if editing else "Record stock trade"
    action = f'/stock-trade/{trade["id"]}/edit' if editing else "/stock-trade/new"
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/stock-trade/{trade["id"]}/delete?{urlencode({"return_to": return_to})}">Delete stock trade</button>' if editing else ""
    body = f'''<div class="narrow"><div class="page-head"><div><p class="eyebrow">Stock trade</p><h1>{title}</h1></div><a class="clear" href="{escape(return_to)}">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}">
      <input type="hidden" name="return_to" value="{escape(return_to)}">
      <fieldset><legend>Trade</legend><div class="form-grid">
        {field('Trade date','trade_date',trade.get('trade_date',''),'date','required')}
        {field('Ticker','ticker',trade.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. AAPL"')}
        <label><span>Status</span><select name="status" required>{select_options(STATUSES, trade.get('status', 'Closed'))}</select></label>
        <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', trade.get('broker_source'))}</select></label>
        {earnings_bet_toggle(trade)}
        {field('Shares','shares',trade.get('shares',''),'number','required step="0.0001" min="0"')}
        {field('Buy price / share','buy_price',trade.get('buy_price',''),'number','required step="0.01" min="0"')}
        {field('Sell price / share','sell_price',trade.get('sell_price',''),'number','step="0.01" min="0"', 'Required when closed')}
        {field('Current price / share','current_price',trade.get('current_price',''),'number','step="0.01" min="0"', 'Used for open holdings')}
        {field('Price as of','as_of',trade.get('as_of',''),'date')}
      </div></fieldset>
      <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Setup, sell reason, realized lot notes...">{escape(trade.get('notes') or '')}</textarea></label></fieldset>
      <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add stock trade'}</button></div>
    </form></div>'''
    return layout(title + " - Option Ledger", body, "holdings")


def validate_stock_trade(form):
    trade_date = form.get("trade_date", "")
    ticker = form.get("ticker", "").strip().upper()
    status = form.get("status") if form.get("status") in STATUSES else "Closed"
    shares = number(form.get("shares"))
    buy_price = number(form.get("buy_price"))
    sell_price = number(form.get("sell_price"))
    current_price = number(form.get("current_price"))
    as_of = form.get("as_of") or None
    if not parse_date(trade_date):
        return None, "Enter a valid trade date."
    if as_of and not parse_date(as_of):
        return None, "Enter a valid as of date."
    if not ticker:
        return None, "Ticker is required."
    if shares is None or shares <= 0:
        return None, "Shares must be greater than 0."
    if buy_price is None or buy_price < 0:
        return None, "Buy price must be zero or greater."
    if status == "Closed" and (sell_price is None or sell_price < 0):
        return None, "Sell price must be zero or greater for closed stock trades."
    if current_price is not None and current_price < 0:
        return None, "Current price must be zero or greater."
    if status == "Open":
        realized_pnl = (current_price - buy_price) * shares if current_price is not None else 0
        price = current_price if current_price is not None else buy_price
    else:
        current_price = sell_price
        as_of = as_of or trade_date
        realized_pnl = (sell_price - buy_price) * shares
        price = sell_price
    return {
        "trade_date": trade_date,
        "ticker": ticker,
        "side": "Buy" if status == "Open" else "Sell",
        "status": status,
        "shares": shares,
        "price": price,
        "buy_price": buy_price,
        "sell_price": None if status == "Open" else sell_price,
        "current_price": current_price,
        "as_of": as_of,
        "fees": 0,
        "realized_pnl": realized_pnl,
        "broker_source": normalize_broker_source(form.get("broker_source")),
        "notes": form.get("notes", "").strip() or None,
    }, ""


def remove_matching_synced_holding_for_closed_stock_trade(connection, data: dict) -> None:
    """Remove a same-day synced holding when a journal entry closes the full position."""
    if data.get("status") != "Closed" or data.get("broker_source") != "Robinhood":
        return

    ticker = str(data.get("ticker") or "").strip().upper()
    trade_date = parse_date(data.get("trade_date"))
    sold_shares = number(data.get("shares"), 0) or 0
    if not ticker or not trade_date or sold_shares <= 0:
        return

    holding = connection.execute(
        """
        SELECT id, shares, avg_cost, as_of
        FROM stock_holdings
        WHERE user_id=?
          AND UPPER(ticker)=?
          AND notes LIKE 'Synced from Robinhood%'
        ORDER BY id DESC
        LIMIT 1
        """,
        (current_user_id(), ticker),
    ).fetchone()
    if not holding or parse_date(holding["as_of"]) != trade_date:
        return

    held_shares = number(holding["shares"], 0) or 0
    holding_cost = number(holding["avg_cost"])
    trade_cost = number(data.get("buy_price"))
    cost_matches = holding_cost is None or trade_cost is None or math.isclose(holding_cost, trade_cost, abs_tol=0.01)
    if held_shares > 0 and sold_shares + 1e-8 >= held_shares and cost_matches:
        connection.execute(
            "DELETE FROM stock_holdings WHERE id=? AND user_id=?",
            (holding["id"], current_user_id()),
        )


def remove_matching_holding_for_open_stock_trade(connection, data: dict) -> None:
    """Keep an open stock trade as the single source for its current holding."""
    if data.get("status") != "Open":
        return
    ticker = str(data.get("ticker") or "").strip().upper()
    if not ticker:
        return
    connection.execute(
        "DELETE FROM stock_holdings WHERE user_id=? AND UPPER(ticker)=?",
        (current_user_id(), ticker),
    )


OTHER_OPTION_STRATEGY_TYPES = ("Single option", "Call Debit Spread", "Put Debit Spread", "Buy combo")
OTHER_OPTION_TYPES = ("Call", "Put")
OTHER_OPTION_DEBIT_SPREAD_TYPES = {"Call Debit Spread", "Put Debit Spread"}


def other_option_spread_description(strategy_type: str, long_strike, short_strike, description="") -> str:
    description = (description or "").strip()
    if description:
        return description
    if strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES and long_strike is not None and short_strike is not None:
        option_type = "call" if strategy_type == "Call Debit Spread" else "put"
        return f"{num(long_strike)}/{num(short_strike)} {option_type} debit spread"
    return description


def all_other_option_trades(filters=None) -> list[dict]:
    filters = filters or {}
    where, params = ["user_id = ?"], [current_user_id()]
    if filters.get("q"):
        ticker_term = ticker_search_term(filters["q"])
        if ticker_term:
            where.append("UPPER(ticker) = ?")
            params.append(ticker_term)
        else:
            like = f"%{filters['q'].strip().upper()}%"
            where.append("(UPPER(ticker) LIKE ? OR UPPER(description) LIKE ? OR UPPER(notes) LIKE ?)")
            params.extend([like, like, like])
    if filters.get("strategy_type"):
        where.append("strategy_type = ?")
        params.append(filters["strategy_type"])
    if filters.get("option_type"):
        where.append("option_type = ?")
        params.append(filters["option_type"])
    apply_source_filter(where, params, filters.get("source"))
    if filters.get("date_from"):
        where.append("trade_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("trade_date <= ?")
        params.append(filters["date_to"])
    if filters.get("expiration_from"):
        where.append("expiration >= ?")
        params.append(filters["expiration_from"])
    if filters.get("expiration_to"):
        where.append("expiration <= ?")
        params.append(filters["expiration_to"])
    with closing(db()) as connection:
        rows = [dict(row) for row in connection.execute(
            f"SELECT * FROM other_option_trades WHERE {' AND '.join(where)} ORDER BY COALESCE(open_date, trade_date) DESC, id DESC",
            params,
        ).fetchall()]
    for row in rows:
        row["pnl"] = other_option_pnl(row)
        capital = (number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100
        row["pl_pct"] = row["pnl"] / capital if capital else None
    return rows


def other_option_row(row: dict) -> str:
    pnl = number(row.get("pnl"), 0) or 0
    strategy_type = row.get("strategy_type") or "Single option"
    long_strike = number(row.get("long_strike"))
    short_strike = number(row.get("short_strike"))
    option_label = row.get("option_type") or other_option_spread_description(strategy_type, long_strike, short_strike, row.get("description")) or "-"
    strike_label = f'{num(long_strike)} / {num(short_strike)}' if strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES and long_strike is not None and short_strike is not None else money(number(row.get("strike"), 0)) if row.get("strike") not in (None, "") else "-"
    status = row.get("status") or "Closed"
    return f'''<tr>
      <td><b>{escape(row.get("open_date") or row.get("trade_date") or "-")}</b></td>
      <td>{escape(row.get("close_date") or "-" if status == "Open" else row.get("close_date") or row.get("trade_date") or "-")}</td>
      <td><span class="pill {escape(status.lower())}">{escape(status)}</span></td>
      <td>{ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row), earnings_marker(row))}</td>
      <td>{escape(strategy_type)}</td>
      <td>{escape(option_label)}</td>
      <td>{escape(row.get("expiration") or "-")}</td>
      <td>{strike_label}</td>
      <td>{num(row.get("contracts"))}</td>
      <td>{money(number(row.get("open_price"), 0))}</td>
      <td>{money(number(row.get("close_price"), 0))}</td>
      <td class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</td>
      <td class="{"positive" if (row.get("pl_pct") or 0) >= 0 else "negative"}">{pct(row.get("pl_pct"))}</td>
      <td><a class="text-button" href="/other-option/{row["id"]}/edit">Edit</a></td>
    </tr>'''


def other_option_item(row: dict) -> str:
    pnl = number(row.get("pnl"), 0) or 0
    strategy_type = row.get("strategy_type") or "Single option"
    long_strike = number(row.get("long_strike"))
    short_strike = number(row.get("short_strike"))
    option_label = row.get("option_type") or other_option_spread_description(strategy_type, long_strike, short_strike, row.get("description")) or "-"
    strike_label = f'{num(long_strike)} / {num(short_strike)}' if strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES and long_strike is not None and short_strike is not None else money(number(row.get("strike"), 0)) if row.get("strike") not in (None, "") else "-"
    status = row.get("status") or "Closed"
    side_label, side_class = option_position_side({**row, "strategy": strategy_type, "source": "other_option"})
    earnings_class = " earnings-row" if number(row.get("earnings_bet_id")) else ""
    return f'''<article class="transaction-item{earnings_class}">
      <div class="transaction-primary">
        {ticker_broker_display(row.get("ticker") or "-", broker_source_for_row(row))}
        <div class="holding-secondary">{escape(row.get("open_date") or row.get("trade_date") or "-")} · {escape(strategy_type)}</div>
      </div>
      <div class="transaction-contract"><strong>{strike_label} {escape(option_label)}</strong><small>{escape(row.get("expiration") or "No expiration")} · {num(row.get("contracts"))} contracts</small></div>
      <div class="transaction-state"><span class="position-side {side_class}">{side_label}</span><small class="pill {escape(status.lower())}">{escape(status)}</small></div>
      <div class="transaction-result"><strong class="{"positive" if pnl >= 0 else "negative"}">{money(pnl)}</strong><small class="{"positive" if (row.get("pl_pct") or 0) >= 0 else "negative"}">{pct(row.get("pl_pct"))}</small></div>
      <a class="transaction-edit" href="/other-option/{row["id"]}/edit">Edit</a>
    </article>'''


def other_options_page(query=None) -> bytes:
    query = query or {}
    filters = {key: query.get(key, [""])[0] for key in ("q", "strategy_type", "option_type", "source", "date_from", "date_to")}
    rows = all_other_option_trades(filters)
    option_sort_fields = {
        "trade_date": lambda row: row.get("open_date") or row.get("trade_date") or "",
        "close_date": lambda row: row.get("close_date") or row.get("trade_date") or "",
        "status": lambda row: row.get("status") or "Closed",
        "ticker": lambda row: row.get("ticker") or "",
        "strategy_type": lambda row: row.get("strategy_type") or "",
        "source": lambda row: broker_source_for_row(row) or "",
        "contract": lambda row: row.get("option_type") or row.get("description") or "",
        "expiration": lambda row: row.get("expiration") or "",
        "strike": lambda row: number(row.get("strike"), number(row.get("long_strike"), 0)) or 0,
        "contracts": lambda row: number(row.get("contracts"), 0) or 0,
        "open_price": lambda row: number(row.get("open_price"), 0) or 0,
        "close_price": lambda row: number(row.get("close_price"), 0) or 0,
        "fees": lambda row: number(row.get("fees"), 0) or 0,
        "pnl": lambda row: number(row.get("pnl"), 0) or 0,
        "pl_pct": lambda row: row.get("pl_pct") if row.get("pl_pct") is not None else -999999,
    }
    sort_key, sort_dir = apply_table_sort(rows, query, option_sort_fields, "trade_date", "desc")
    base_params = {"view": "option-buyer", **filters, "sort_by": sort_key, "sort_dir": sort_dir}
    total_pnl = sum(number(row.get("pnl"), 0) or 0 for row in rows)
    winners = sum(1 for row in rows if (number(row.get("pnl"), 0) or 0) > 0)
    total_contracts = option_contract_total(rows)
    total_cost = sum((number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100 for row in rows)
    pl_pcts = [row.get("pl_pct") for row in rows if row.get("pl_pct") is not None]
    avg_pl_pct = sum(pl_pcts) / len(pl_pcts) if pl_pcts else None
    best, best_class = trade_extreme_value(rows, "pnl", True)
    worst, worst_class = trade_extreme_value(rows, "pnl", False)
    metrics = (
        ("Total P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Cost basis", money(total_cost), ""),
        ("Avg P/L %", pct(avg_pl_pct), "positive" if avg_pl_pct is not None and avg_pl_pct >= 0 else "negative"),
        ("Trades / Contracts", f"{len(rows):,} / {num(total_contracts)}", ""),
        ("Win rate", pct(winners / len(rows) if rows else None), ""),
        ("Avg P&L", money(total_pnl / len(rows) if rows else 0), "positive" if total_pnl >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    )
    page_rows, pagination = paginate_items(
        rows,
        query,
        "/trades",
        base_params,
        page_size=30,
    )
    table_rows = "".join(other_option_item(row) for row in page_rows) or '<div class="empty">No option buyer trades yet.</div>'
    body = f'''<div class="trades-page split-ledger-page"><div class="page-head"><div><p class="eyebrow">Option ledger</p><h1>Option Trades <span class="count">{len(rows)}</span></h1>{option_trades_switch("option-buyer")}</div><div class="actions"><a class="button" href="/option-trade/new?book=buyer">Record trade</a></div></div>
    <div class="ledger-workspace" data-ledger-layout data-layout-key="optionBuyer">
      <aside class="ledger-sidebar">{compact_summary_cards(metrics, "trades-summary-compact")}{trades_rankings_panel(rows, "pnl", "other-option", ("close_date", "open_date", "trade_date"), ("strategy_type", "option_type"))}</aside>
      <div class="ledger-splitter" data-ledger-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="ledger-main">
    <form class="filters date-filters" method="get">
      <input type="hidden" name="view" value="option-buyer">
      <input name="q" value="{escape(filters['q'])}" placeholder="Search ticker, combo, or notes">
      <select name="strategy_type">{select_options(OTHER_OPTION_STRATEGY_TYPES, filters['strategy_type'], 'All types')}</select>
      <select name="option_type">{select_options(OTHER_OPTION_TYPES, filters['option_type'], 'Call / Put')}</select>
      <select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select>
      {filter_date_field('date_from', filters['date_from'], 'Opened from')}
      {filter_date_field('date_to', filters['date_to'], 'Opened to')}
      <select name="sort_by" aria-label="Sort option trades">{compact_sort_options((("trade_date","Opened"),("ticker","Ticker"),("strategy_type","Type"),("expiration","Expiration"),("strike","Strike"),("contracts","Contracts"),("pnl","P&L"),("pl_pct","P/L %")), sort_key)}</select>
      <select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select>
      <button class="button secondary">Filter</button><a class="clear" href="/trades?view=option-buyer">Clear</a>
    </form>
    <section class="panel compact-transaction-panel"><div class="transaction-grid">{table_rows}</div>{pagination}</section>
      </div>
    </div></div>'''
    return layout("Option Trades - Option Ledger", body, "trades")


def other_option_form(row=None, error="", return_to: str = "") -> bytes:
    trade = dict(row or {})
    return_to = safe_return_to(return_to or trade.get("return_to"), "/trades?view=option-buyer")
    editing = bool(trade.get("id"))
    option_book = trade.get("option_book") or "buyer"
    if not editing:
        default_date_fields(trade, "trade_date", "open_date", "close_date", "expiration")
        default_new_trade_fields(trade, "contracts")
    elif not trade.get("trade_date"):
        trade["trade_date"] = date.today().isoformat()
    title = "Edit option buyer trade" if editing else "Record option buyer trade"
    action = f'/other-option/{trade["id"]}/edit' if editing else "/other-option/new"
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/other-option/{trade["id"]}/delete?{urlencode({"return_to": return_to})}">Delete option buyer trade</button>' if editing else ""
    body = f'''<div class="narrow"><div class="page-head"><div><p class="eyebrow">Option buyer</p><h1>{title}</h1></div><a class="clear" href="{escape(return_to)}">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}" data-other-option-form>
      <input type="hidden" name="return_to" value="{escape(return_to)}">
      <fieldset><legend>Setup</legend><div class="form-grid">
        <label><span>Book</span><select name="option_book" required>
          <option value="buyer" {"selected" if option_book == "buyer" else ""}>Option Buyer</option>
          <option value="seller" {"selected" if option_book == "seller" else ""}>Option Seller</option>
        </select></label>
        <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', trade.get('broker_source'))}</select></label>
        {earnings_bet_toggle(trade)}
        {field('Open date','open_date',trade.get('open_date',''),'date','required')}
        <label><span>Status</span><select name="status" required>{select_options(("Open", "Closed"), trade.get('status') or 'Closed')}</select></label>
        {field('Close date','close_date',trade.get('close_date') or trade.get('trade_date') or '','date')}
        {field('Ticker','ticker',trade.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. NVDA"')}
        <label><span>Type</span><select name="strategy_type" required data-other-option-type>{select_options(OTHER_OPTION_STRATEGY_TYPES, trade.get('strategy_type') or 'Single option')}</select></label>
        <label data-other-option-section="Single option"><span>Option type</span><select name="option_type">{select_options(OTHER_OPTION_TYPES, trade.get('option_type') or 'Call')}</select></label>
        <label data-other-option-section="Buy combo|Call Debit Spread|Put Debit Spread"><span>Combo description</span><input name="description" value="{escape(str(trade.get('description') or ''))}" maxlength="120" placeholder="e.g. 100/105 call debit spread"></label>
        {field('Expiration','expiration',trade.get('expiration',''),'date')}
        <label data-other-option-section="Single option"><span>Strike</span><input type="number" name="strike" value="{escape('' if trade.get('strike') is None else str(trade.get('strike')))}" step="0.01" min="0"></label>
        <label data-other-option-section="Call Debit Spread|Put Debit Spread"><span>Long strike</span><input type="number" name="long_strike" value="{escape('' if trade.get('long_strike') is None else str(trade.get('long_strike')))}" step="0.01" min="0"></label>
        <label data-other-option-section="Call Debit Spread|Put Debit Spread"><span>Short strike</span><input type="number" name="short_strike" value="{escape('' if trade.get('short_strike') is None else str(trade.get('short_strike')))}" step="0.01" min="0"></label>
      </div></fieldset>
      <fieldset><legend>Execution</legend><div class="form-grid">
        {field('Contracts / units','contracts',trade.get('contracts',''),'number','required step="1" min="1"')}
        <label data-other-option-section="Single option|Buy combo|Call Debit Spread|Put Debit Spread"><span>Buy price / contract</span><input type="number" name="open_price" value="{escape('' if trade.get('open_price') is None else str(trade.get('open_price')))}" required step="0.01" min="0"></label>
        <label data-other-option-section="Single option|Buy combo|Call Debit Spread|Put Debit Spread"><span>Close price / contract</span><input type="number" name="close_price" value="{escape('' if trade.get('close_price') is None else str(trade.get('close_price')))}" step="any" min="0"><small>Leave blank while open.</small></label>
        {field('Fees','fees',trade.get('fees',0),'number','step="0.01" min="0"')}
      </div></fieldset>
      <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Thesis, catalyst, exit reason...">{escape(trade.get('notes') or '')}</textarea></label></fieldset>
      <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add option buyer trade'}</button></div>
    </form></div>'''
    return layout(title + " - Option Ledger", body, "trades")


def validate_other_option(form):
    open_date = form.get("open_date") or form.get("trade_date", "")
    status = form.get("status") or "Closed"
    close_date = form.get("close_date") or ""
    ticker = form.get("ticker", "").strip().upper()
    strategy_type = form.get("strategy_type", "")
    option_type = form.get("option_type", "")
    contracts = number(form.get("contracts"))
    fees = number(form.get("fees"), 0) or 0
    if status not in {"Open", "Closed"}:
        return None, "Choose Open or Closed."
    if not parse_date(open_date):
        return None, "Enter a valid open date."
    if status == "Closed" and not parse_date(close_date):
        return None, "Enter a valid close date for a closed trade."
    if close_date and not parse_date(close_date):
        return None, "Enter a valid close date."
    if status == "Open":
        close_date = ""
    if not ticker:
        return None, "Ticker is required."
    if strategy_type not in OTHER_OPTION_STRATEGY_TYPES:
        return None, "Choose a valid option type."
    if strategy_type == "Single option" and option_type not in OTHER_OPTION_TYPES:
        return None, "Choose Call or Put."
    if contracts is None or contracts <= 0:
        return None, "Contracts must be greater than 0."
    if fees < 0:
        return None, "Fees cannot be negative."
    strike = number(form.get("strike"))
    if strike is not None and strike < 0:
        return None, "Strike cannot be negative."
    is_debit_spread = strategy_type in OTHER_OPTION_DEBIT_SPREAD_TYPES
    long_strike = short_strike = long_open_price = short_open_price = long_close_price = short_close_price = None
    if is_debit_spread:
        long_strike = number(form.get("long_strike"))
        short_strike = number(form.get("short_strike"))
        open_price = number(form.get("open_price"))
        close_price = number(form.get("close_price"))
        for label, value in (
            ("Long strike", long_strike),
            ("Short strike", short_strike),
            ("Buy price / contract", open_price),
        ):
            if value is None or value < 0:
                return None, f"{label} must be zero or greater."
        if status == "Closed" and (close_price is None or close_price < 0):
            return None, "Close price / contract must be zero or greater for a closed trade."
        if status == "Open" and close_price is None:
            close_price = 0
        elif close_price is not None and close_price < 0:
            return None, "Close price / contract must be zero or greater."
    else:
        open_price = number(form.get("open_price"))
        close_price = number(form.get("close_price"))
        if open_price is None or open_price < 0:
            return None, "Open debit / contract must be zero or greater."
        if status == "Closed" and (close_price is None or close_price < 0):
            return None, "Close value / contract must be zero or greater for a closed trade."
        if status == "Open" and close_price is None:
            close_price = 0
        elif close_price is not None and close_price < 0:
            return None, "Close value / contract must be zero or greater."
    description = other_option_spread_description(
        strategy_type,
        long_strike,
        short_strike,
        form.get("description", ""),
    )
    data = {
        "trade_date": close_date or open_date,
        "open_date": open_date,
        "close_date": close_date or None,
        "status": status,
        "ticker": ticker,
        "strategy_type": strategy_type,
        "option_type": option_type if strategy_type == "Single option" else "Call" if strategy_type == "Call Debit Spread" else "Put" if strategy_type == "Put Debit Spread" else None,
        "expiration": form.get("expiration") or None,
        "strike": strike if strategy_type == "Single option" else None,
        "contracts": contracts,
        "open_price": open_price,
        "close_price": close_price,
        "long_strike": long_strike,
        "short_strike": short_strike,
        "long_open_price": long_open_price,
        "short_open_price": short_open_price,
        "long_close_price": long_close_price,
        "short_close_price": short_close_price,
        "fees": fees,
        "description": description if strategy_type != "Single option" else None,
        "broker_source": normalize_broker_source(form.get("broker_source")),
        "notes": form.get("notes", "").strip() or None,
    }
    if data["expiration"] and not parse_date(data["expiration"]):
        return None, "Enter a valid expiration date."
    return data, ""


def unified_option_trade_form(mode="seller", form_data=None, error="") -> bytes:
    mode = "buyer" if mode == "buyer" else "seller"
    form_data = dict(form_data or {})
    default_new_trade_fields(form_data, "contracts", "buyer_contracts")
    default_date_fields(
        form_data,
        "open_date",
        "expiration",
        "close_date",
        "buyer_open_date",
        "buyer_close_date",
        "buyer_expiration",
        "trade_date",
    )
    if not form_data.get("buyer_open_date"):
        form_data["buyer_open_date"] = form_data.get("open_date") or form_data.get("trade_date") or date.today().isoformat()
    if not form_data.get("buyer_status"):
        form_data["buyer_status"] = form_data.get("status") or "Closed"
    if not form_data.get("trade_date"):
        form_data["trade_date"] = form_data.get("buyer_open_date") or date.today().isoformat()
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    body = f'''<div class="narrow"><div class="page-head"><div><p class="eyebrow">Option ledger</p><h1>Record trade</h1></div><a class="clear" href="/trades{'?view=option-buyer' if mode == 'buyer' else ''}">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="/option-trade/new" data-unified-option-form data-option-mode="{mode}">
      <fieldset><legend>Trade Type</legend><div class="form-grid">
        <label><span>Book</span><select name="option_book" required data-option-book>
          <option value="seller" {"selected" if mode == "seller" else ""}>Option Seller</option>
          <option value="buyer" {"selected" if mode == "buyer" else ""}>Option Buyer</option>
        </select></label>
      </div></fieldset>
      <div data-option-book-section="seller">
        <fieldset><legend>Seller Setup</legend><div class="form-grid">
          {field('Ticker','ticker',form_data.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. AMD"')}
          <label><span>Strategy</span><select name="strategy" data-seller-strategy>{select_options(STRATEGIES, form_data.get('strategy') or 'Put Credit Spread')}</select></label>
          <label><span>Status</span><select name="status">{select_options(STATUSES, form_data.get('status') or 'Open')}</select></label>
          <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', form_data.get('broker_source'))}</select></label>
          {earnings_bet_toggle(form_data)}
          {field('Open date','open_date',form_data.get('open_date',''),'date','required')}
          {field('Expiration','expiration',form_data.get('expiration',''),'date','required')}
          {field('Close date','close_date',form_data.get('close_date',''),'date')}
          {field('Contracts','contracts',form_data.get('contracts',''),'number','required step="1" min="1"')}
          <label><span data-seller-strike-label>Short strike</span><input type="number" name="strike" value="{escape(str(form_data.get('strike') or ''))}" required step="0.01" min="0"></label>
          <label data-seller-spread-field><span data-seller-long-label>Long strike</span><input type="number" name="long_put_strike" value="{escape(str(form_data.get('long_put_strike') or ''))}" step="0.01" min="0"><small data-seller-long-help>For credit spreads only.</small></label>
          <label data-seller-condor-field><span>Short call strike</span><input type="number" name="short_call_strike" value="{escape(str(form_data.get('short_call_strike') or ''))}" step="0.01" min="0"></label>
          <label data-seller-condor-field><span>Long call strike</span><input type="number" name="long_call_strike" value="{escape(str(form_data.get('long_call_strike') or ''))}" step="0.01" min="0"></label>
          {field('Premium in','premium_in',form_data.get('premium_in',''),'number','required step="any" min="0"')}
          {field('Exit / current premium','exit_premium',form_data.get('exit_premium',''),'number','step="any"')}
          {field('Stock / assignment P&L','stock_pnl',form_data.get('stock_pnl',0),'number','step="any"')}
          {field('Capital used','capital_used',form_data.get('capital_used',''),'number','step="any" min="0"')}
          {field('Fees','fees',form_data.get('fees',0),'number','step="any" min="0"')}
        </div></fieldset>
      </div>
      <div data-option-book-section="buyer">
        <fieldset><legend>Buyer Setup</legend><div class="form-grid">
          {field('Open date','buyer_open_date',form_data.get('buyer_open_date',''),'date','required')}
          <label><span>Status</span><select name="buyer_status" required>{select_options(("Open", "Closed"), form_data.get('buyer_status') or 'Closed')}</select></label>
          {field('Close date','buyer_close_date',form_data.get('buyer_close_date') or form_data.get('close_date') or '','date')}
          {field('Ticker','buyer_ticker',form_data.get('buyer_ticker') or form_data.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. NVDA"')}
          <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', form_data.get('broker_source'))}</select></label>
          {earnings_bet_toggle(form_data)}
          <label><span>Type</span><select name="strategy_type" required data-other-option-type>{select_options(OTHER_OPTION_STRATEGY_TYPES, form_data.get('strategy_type') or 'Single option')}</select></label>
          <label data-other-option-section="Single option"><span>Option type</span><select name="option_type">{select_options(OTHER_OPTION_TYPES, form_data.get('option_type') or 'Call')}</select></label>
          <label data-other-option-section="Buy combo|Call Debit Spread|Put Debit Spread"><span>Combo description</span><input name="description" value="{escape(str(form_data.get('description') or ''))}" maxlength="120" placeholder="e.g. 100/105 call debit spread"></label>
          {field('Expiration','buyer_expiration',form_data.get('buyer_expiration') or form_data.get('expiration',''),'date')}
          <label data-other-option-section="Single option"><span>Strike</span><input type="number" name="buyer_strike" value="{escape(str(form_data.get('buyer_strike') or form_data.get('strike') or ''))}" step="0.01" min="0"></label>
          <label data-other-option-section="Call Debit Spread|Put Debit Spread"><span>Long strike</span><input type="number" name="long_strike" value="{escape(str(form_data.get('long_strike') or ''))}" step="0.01" min="0"></label>
          <label data-other-option-section="Call Debit Spread|Put Debit Spread"><span>Short strike</span><input type="number" name="short_strike" value="{escape(str(form_data.get('short_strike') or ''))}" step="0.01" min="0"></label>
          {field('Contracts / units','buyer_contracts',form_data.get('buyer_contracts') or form_data.get('contracts',''),'number','required step="1" min="1"')}
          <label data-other-option-section="Single option|Buy combo|Call Debit Spread|Put Debit Spread"><span>Buy price / contract</span><input type="number" name="open_price" value="{escape(str(form_data.get('open_price') or ''))}" required step="0.01" min="0"></label>
          <label data-other-option-section="Single option|Buy combo|Call Debit Spread|Put Debit Spread"><span>Close price / contract</span><input type="number" name="close_price" value="{escape(str(form_data.get('close_price') or ''))}" step="any" min="0"><small>Leave blank while open.</small></label>
          {field('Buyer fees','buyer_fees',form_data.get('buyer_fees') or form_data.get('fees',0),'number','step="0.01" min="0"')}
        </div></fieldset>
      </div>
      <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Setup, thesis, exit note...">{escape(form_data.get('notes') or '')}</textarea></label></fieldset>
      <div class="form-actions"><button class="button" type="submit">Add option trade</button></div>
    </form></div>'''
    return layout("Record trade - Option Ledger", body, "trades")


def save_unified_option_trade(form):
    mode = form.get("option_book", "seller")
    if mode == "buyer":
        buyer_form = dict(form)
        buyer_form["ticker"] = form.get("buyer_ticker", "")
        buyer_form["open_date"] = form.get("buyer_open_date", "")
        buyer_form["close_date"] = form.get("buyer_close_date", "")
        buyer_form["status"] = form.get("buyer_status", "Closed")
        buyer_form["expiration"] = form.get("buyer_expiration", "")
        buyer_form["strike"] = form.get("buyer_strike", "")
        buyer_form["contracts"] = form.get("buyer_contracts", "")
        buyer_form["fees"] = form.get("buyer_fees", form.get("fees", "0"))
        data, error = validate_other_option(buyer_form)
        if error:
            return None, error, "buyer"
        data["user_id"] = current_user_id()
        with closing(db()) as connection:
            if other_option_should_live_in_day(data):
                cursor = insert_row(connection, "day_trades", other_option_data_to_day(data))
                sync_trade_earnings_bet(connection, "day_trades", cursor.lastrowid, earnings_checked(form))
                redirect = symbol_page_href(data.get("ticker"), "/trades?view=day-trades")
            else:
                cursor = insert_row(connection, "other_option_trades", data)
                sync_trade_earnings_bet(connection, "other_option_trades", cursor.lastrowid, earnings_checked(form))
                redirect = symbol_page_href(data.get("ticker"), "/trades?view=option-buyer")
            connection.commit()
        return redirect, "", "buyer"
    data, error = validate(form)
    if error:
        return None, error, "seller"
    data["user_id"] = current_user_id()
    fields = tuple(data.keys())
    with closing(db()) as connection:
        cursor = connection.execute(f"INSERT INTO trades ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [data[x] for x in fields])
        sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
        connection.commit()
    return symbol_page_href(data.get("ticker"), "/trades"), "", "seller"


def day_trades_page(query=None, embedded=False) -> bytes:
    query = query or {}
    filters = {key: query.get(key, [""])[0] for key in ("q", "option_type", "open_side", "source", "date_from", "date_to")}
    rows = all_day_trades(filters)
    day_sort_fields = {
        "trade_date": lambda row: row.get("open_date") or row.get("trade_date") or "",
        "close_date": lambda row: row.get("close_date") or row.get("trade_date") or "",
        "status": lambda row: row.get("status") or "Closed",
        "ticker": lambda row: row.get("ticker") or "",
        "source": lambda row: broker_source_for_row(row) or "",
        "contract": lambda row: f'{row.get("option_type") or ""} {number(row.get("strike"), 0) or 0}',
        "open_side": lambda row: row.get("open_side") or "",
        "contracts": lambda row: number(row.get("contracts"), 0) or 0,
        "open_price": lambda row: number(row.get("open_price"), 0) or 0,
        "close_price": lambda row: number(row.get("close_price"), 0) or 0,
        "fees": lambda row: number(row.get("fees"), 0) or 0,
        "pnl": lambda row: number(row.get("pnl"), 0) or 0,
        "pl_pct": lambda row: row.get("pl_pct") if row.get("pl_pct") is not None else -999999,
    }
    sort_key, sort_dir = apply_table_sort(rows, query, day_sort_fields, "trade_date", "desc")
    base_params = {"view": "day-trades", **filters, "sort_by": sort_key, "sort_dir": sort_dir}
    total_pnl = sum(row.get("pnl") or 0 for row in rows)
    winners = sum(1 for row in rows if (row.get("pnl") or 0) > 0)
    total_contracts = option_contract_total(rows)
    total_cost = sum((number(row.get("open_price"), 0) or 0) * (number(row.get("contracts"), 0) or 0) * 100 for row in rows)
    avg_pnl = total_pnl / len(rows) if rows else 0
    pl_pcts = [row.get("pl_pct") for row in rows if row.get("pl_pct") is not None]
    avg_pl_pct = sum(pl_pcts) / len(pl_pcts) if pl_pcts else None
    best, best_class = trade_extreme_value(rows, "pnl", True)
    worst, worst_class = trade_extreme_value(rows, "pnl", False)
    metrics = (
        ("Total P&L", money(total_pnl), "positive" if total_pnl >= 0 else "negative"),
        ("Cost basis", money(total_cost), ""),
        ("Avg P/L %", pct(avg_pl_pct), "positive" if avg_pl_pct is not None and avg_pl_pct >= 0 else "negative"),
        ("Trades / Contracts", f"{len(rows):,} / {num(total_contracts)}", ""),
        ("Win rate", pct(winners / len(rows) if rows else None), ""),
        ("Avg P&L", money(avg_pnl), "positive" if avg_pnl >= 0 else "negative"),
        ("Best trade", best, best_class),
        ("Worst trade", worst, worst_class),
    )
    page_rows, pagination = paginate_items(
        rows,
        query,
        "/trades",
        base_params,
        page_size=30,
    )
    table_rows = "".join(day_trade_item(row) for row in page_rows)
    if not table_rows:
        table_rows = '<div class="empty">No intraday single-leg trades yet.</div>'
    body = f'''<div class="trades-page split-ledger-page"><div class="page-head"><div><p class="eyebrow">Option ledger</p><h1>Option Trades <span class="count">{len(rows)}</span></h1>{option_trades_switch("day-trades")}</div><div class="actions"><a class="button" href="/day-trade/new">Record day trade</a></div></div>
    <div class="ledger-workspace" data-ledger-layout data-layout-key="dayTrades">
      <aside class="ledger-sidebar">{compact_summary_cards(metrics, "trades-summary-compact")}{trades_rankings_panel(rows, "pnl", "day-trade", ("close_date", "open_date", "trade_date"), ("option_type", "open_side"))}</aside>
      <div class="ledger-splitter" data-ledger-splitter role="separator" aria-label="Resize overview sidebar" aria-orientation="vertical" title="Drag to resize"></div>
      <div class="ledger-main">
    <form class="filters date-filters" method="get">
      <input type="hidden" name="view" value="day-trades">
      <input name="q" value="{escape(filters['q'])}" placeholder="Search ticker or notes">
      <select name="option_type">{select_options(DAY_TRADE_OPTION_TYPES, filters['option_type'], 'Call / Put')}</select>
      <select name="open_side">{select_options(DAY_TRADE_OPEN_SIDES, filters['open_side'], 'All sides')}</select>
      <select name="source">{broker_source_select('source', filters['source'], 'All sources', True)}</select>
      {filter_date_field('date_from', filters['date_from'], 'Opened from')}
      {filter_date_field('date_to', filters['date_to'], 'Opened to')}
      <select name="sort_by" aria-label="Sort day trades">{compact_sort_options((("trade_date","Opened"),("ticker","Ticker"),("contract","Contract"),("open_side","Open side"),("contracts","Contracts"),("pnl","P&L"),("pl_pct","P/L %")), sort_key)}</select>
      <select name="sort_dir" aria-label="Sort direction">{compact_sort_options((("desc","Descending"),("asc","Ascending")), sort_dir)}</select>
      <button class="button secondary">Filter</button><a class="clear" href="/trades?view=day-trades">Clear</a>
    </form>
    <section class="panel compact-transaction-panel"><div class="transaction-grid">{table_rows}</div>{pagination}</section>
      </div>
    </div></div>'''
    return layout("Option Trades - Option Ledger", body, "trades")


def day_trade_form(row=None, error="", return_to: str = "") -> bytes:
    trade = dict(row or {})
    return_to = safe_return_to(return_to or trade.get("return_to"), "/trades?view=day-trades")
    editing = bool(trade.get("id"))
    if not editing:
        default_date_fields(trade, "trade_date", "open_date", "close_date", "expiration")
        default_new_trade_fields(trade, "contracts")
    else:
        if not trade.get("trade_date"):
            trade["trade_date"] = date.today().isoformat()
        if not trade.get("open_date"):
            trade["open_date"] = trade.get("trade_date")
        if not trade.get("close_date"):
            trade["close_date"] = trade.get("trade_date")
    title = "Edit day trade" if editing else "Record day trade"
    action = f'/day-trade/{trade["id"]}/edit' if editing else "/day-trade/new"
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/day-trade/{trade["id"]}/delete?{urlencode({"return_to": return_to})}">Delete day trade</button>' if editing else ""
    body = f'''<div class="narrow"><div class="page-head"><div><p class="eyebrow">Single-leg intraday</p><h1>{title}</h1></div><a class="clear" href="{escape(return_to)}">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}">
      <input type="hidden" name="return_to" value="{escape(return_to)}">
      <fieldset><legend>Contract</legend><div class="form-grid">
        {field('Open date','open_date',trade.get('open_date',''),'date','required')}
        <label><span>Status</span><select name="status" required>{select_options(("Closed",), trade.get('status') or 'Closed')}</select></label>
        {field('Close date','close_date',trade.get('close_date') or trade.get('trade_date') or '','date','required')}
        {field('Ticker','ticker',trade.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. SPY"')}
        <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', trade.get('broker_source'))}</select></label>
        {earnings_bet_toggle(trade)}
        <label><span>Option type</span><select name="option_type" required>{select_options(DAY_TRADE_OPTION_TYPES, trade.get('option_type') or 'Call')}</select></label>
        {field('Expiration','expiration',trade.get('expiration',''),'date')}
        {field('Strike','strike',trade.get('strike',''),'number','step="0.01" min="0"')}
        <label><span>Open side</span><select name="open_side" required>{select_options(DAY_TRADE_OPEN_SIDES, trade.get('open_side') or 'Buy to open')}</select></label>
      </div></fieldset>
      <fieldset><legend>Execution</legend><div class="form-grid">
        {field('Contracts','contracts',trade.get('contracts',''),'number','required step="1" min="1"')}
        {field('Open price / contract','open_price',trade.get('open_price',''),'number','required step="any" min="0"')}
        {field('Close price / contract','close_price',trade.get('close_price',''),'number','required step="any"')}
        {field('Fees','fees',trade.get('fees',0),'number','step="0.01" min="0"')}
      </div></fieldset>
      <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Setup, entry reason, mistake, exit note...">{escape(trade.get('notes') or '')}</textarea></label></fieldset>
      <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add day trade'}</button></div>
    </form></div>'''
    return layout(title + " - Option Ledger", body, "day-trades")


def validate_day_trade(form):
    ticker = form.get("ticker", "").strip().upper()
    open_date = form.get("open_date") or form.get("trade_date", "")
    close_date = form.get("close_date") or form.get("trade_date", "")
    status = form.get("status") or "Closed"
    option_type = form.get("option_type", "")
    open_side = form.get("open_side", "")
    if status != "Closed":
        return None, "Day trades must be closed."
    if not parse_date(open_date):
        return None, "Enter a valid open date."
    if not parse_date(close_date):
        return None, "Enter a valid close date."
    if not ticker:
        return None, "Ticker is required."
    if option_type not in DAY_TRADE_OPTION_TYPES:
        return None, "Choose Call or Put."
    if open_side not in DAY_TRADE_OPEN_SIDES:
        return None, "Choose a valid open side."
    if form.get("expiration") and not parse_date(form["expiration"]):
        return None, "Enter a valid expiration date."
    contracts = number(form.get("contracts"))
    open_price = number(form.get("open_price"))
    close_price = number(form.get("close_price"))
    fees = number(form.get("fees"), 0) or 0
    if contracts is None or contracts <= 0:
        return None, "Contracts must be greater than 0."
    if open_price is None or open_price < 0:
        return None, "Open price must be zero or greater."
    if close_price is None:
        return None, "Close price must be zero or greater."
    if close_price < 0 and open_side != "Sell to open":
        return None, "Close price can only be negative for Sell to open day trades."
    if fees < 0:
        return None, "Fees cannot be negative."
    data = {
        "trade_date": close_date,
        "open_date": open_date,
        "close_date": close_date,
        "status": status,
        "ticker": ticker,
        "option_type": option_type,
        "expiration": form.get("expiration") or None,
        "strike": number(form.get("strike")),
        "open_side": open_side,
        "contracts": contracts,
        "open_price": open_price,
        "close_price": close_price,
        "fees": fees,
        "broker_source": normalize_broker_source(form.get("broker_source")),
        "notes": form.get("notes", "").strip() or None,
    }
    if data["strike"] is not None and data["strike"] < 0:
        return None, "Strike cannot be negative."
    return data, ""


def day_trade_should_live_in_buyer(data: dict) -> bool:
    return (
        data.get("open_side") == "Buy to open"
        and (data.get("open_date") or data.get("trade_date")) != (data.get("close_date") or data.get("trade_date"))
    )


def day_trade_should_live_in_seller(data: dict) -> bool:
    return (
        data.get("open_side") == "Sell to open"
        and (data.get("open_date") or data.get("trade_date")) != (data.get("close_date") or data.get("trade_date"))
    )


def other_option_should_live_in_day(data: dict) -> bool:
    return (
        data.get("strategy_type") == "Single option"
        and data.get("status") == "Closed"
        and data.get("open_date")
        and data.get("close_date")
        and data.get("open_date") == data.get("close_date")
    )


def day_data_to_other_option(data: dict) -> dict:
    return {
        "user_id": data.get("user_id", current_user_id()),
        "trade_date": data.get("close_date") or data.get("trade_date"),
        "open_date": data.get("open_date") or data.get("trade_date"),
        "close_date": data.get("close_date") or data.get("trade_date"),
        "status": "Closed",
        "ticker": data.get("ticker"),
        "strategy_type": "Single option",
        "option_type": data.get("option_type"),
        "expiration": data.get("expiration"),
        "strike": data.get("strike"),
        "contracts": data.get("contracts"),
        "open_price": data.get("open_price"),
        "close_price": data.get("close_price"),
        "long_strike": None,
        "short_strike": None,
        "long_open_price": None,
        "short_open_price": None,
        "long_close_price": None,
        "short_close_price": None,
        "fees": data.get("fees", 0) or 0,
        "description": None,
        "broker_source": data.get("broker_source"),
        "earnings_bet_id": data.get("earnings_bet_id"),
        "notes": data.get("notes"),
    }


def day_data_to_seller_trade(data: dict) -> dict:
    option_type = data.get("option_type") or "Put"
    strike = number(data.get("strike"), 0) or 0
    contracts = number(data.get("contracts"), 0) or 0
    return {
        "user_id": data.get("user_id", current_user_id()),
        "ticker": data.get("ticker"),
        "sector": sector_for_ticker(data.get("ticker")),
        "strategy": "Covered Call" if option_type == "Call" else "Sell Put",
        "status": data.get("status") or "Closed",
        "open_date": data.get("open_date") or data.get("trade_date"),
        "expiration": data.get("expiration"),
        "close_date": data.get("close_date") or data.get("trade_date"),
        "contracts": contracts,
        "strike": strike,
        "long_put_strike": None,
        "premium_in": data.get("open_price"),
        "exit_premium": data.get("close_price"),
        "stock_pnl": 0,
        "fees": data.get("fees", 0) or 0,
        "capital_used": strike * contracts * 100 if option_type == "Put" else 0,
        "broker_source": data.get("broker_source"),
        "earnings_bet_id": data.get("earnings_bet_id"),
        "notes": data.get("notes"),
    }


def other_option_data_to_day(data: dict) -> dict:
    return {
        "user_id": data.get("user_id", current_user_id()),
        "trade_date": data.get("close_date") or data.get("open_date") or data.get("trade_date"),
        "open_date": data.get("open_date") or data.get("trade_date"),
        "close_date": data.get("close_date") or data.get("trade_date"),
        "status": "Closed",
        "ticker": data.get("ticker"),
        "option_type": data.get("option_type"),
        "expiration": data.get("expiration"),
        "strike": data.get("strike"),
        "open_side": "Buy to open",
        "contracts": data.get("contracts"),
        "open_price": data.get("open_price"),
        "close_price": data.get("close_price"),
        "fees": data.get("fees", 0) or 0,
        "broker_source": data.get("broker_source"),
        "earnings_bet_id": data.get("earnings_bet_id"),
        "notes": data.get("notes"),
    }


def other_option_should_live_in_seller(form: dict, data: dict) -> bool:
    return (
        (form.get("option_book") or "buyer") == "seller"
        and data.get("strategy_type") == "Single option"
        and data.get("option_type") in OTHER_OPTION_TYPES
    )


def other_option_data_to_seller_trade(data: dict) -> dict:
    option_type = data.get("option_type") or "Put"
    strike = number(data.get("strike"), 0) or 0
    contracts = number(data.get("contracts"), 0) or 0
    open_price = number(data.get("open_price"), 0) or 0
    close_price = number(data.get("close_price"), 0) or 0
    if not open_price and close_price:
        premium_in = close_price
        exit_premium = 0
    else:
        premium_in = open_price
        exit_premium = close_price
    return {
        "user_id": data.get("user_id", current_user_id()),
        "ticker": data.get("ticker"),
        "sector": sector_for_ticker(data.get("ticker")),
        "strategy": "Covered Call" if option_type == "Call" else "Sell Put",
        "status": data.get("status") or "Closed",
        "open_date": data.get("open_date") or data.get("trade_date"),
        "expiration": data.get("expiration"),
        "close_date": data.get("close_date") or data.get("trade_date"),
        "contracts": contracts,
        "strike": strike,
        "long_put_strike": None,
        "premium_in": premium_in,
        "exit_premium": exit_premium,
        "stock_pnl": 0,
        "fees": data.get("fees", 0) or 0,
        "capital_used": strike * contracts * 100 if option_type == "Put" else 0,
        "broker_source": data.get("broker_source"),
        "earnings_bet_id": data.get("earnings_bet_id"),
        "notes": data.get("notes"),
    }


def insert_row(connection, table: str, data: dict):
    fields = tuple(data.keys())
    return connection.execute(
        f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
        [data[x] for x in fields],
    )


def trade_form(trade=None, error="", return_to: str = "") -> bytes:
    t = dict(trade or {})
    return_to = safe_return_to(return_to or t.get("return_to"), "/trades")
    editing = bool(t.get("id"))
    if not editing:
        default_date_fields(t, "open_date", "expiration", "close_date")
        default_new_trade_fields(t, "contracts")
    title = "Edit trade" if editing else "Record a trade"
    action = f'/trade/{t["id"]}/edit' if editing else "/trade/new"
    strategy = t.get("strategy", "Sell Put")
    status = t.get("status", "Open")
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    delete_html = f'<button type="button" class="danger-link" data-delete="/trade/{t["id"]}/delete?{urlencode({"return_to": return_to})}">Delete trade</button>' if editing else ""
    body = f"""<div class="narrow"><div class="page-head"><div><p class="eyebrow">{'Update position' if editing else 'New position'}</p><h1>{title}</h1></div><a class="clear" href="{escape(return_to)}">Cancel</a></div>{error_html}
    <form class="trade-form panel" method="post" action="{action}">
    <input type="hidden" name="return_to" value="{escape(return_to)}">
    <fieldset><legend>Position</legend><div class="form-grid">
    {field('Ticker','ticker',t.get('ticker',''),attrs='required maxlength="12" placeholder="e.g. SOXL"')}
    <label><span>Strategy</span><select name="strategy" id="strategy" required>{select_options(STRATEGIES,strategy)}</select></label>
    <label><span>Status</span><select name="status" required>{select_options(STATUSES,status)}</select></label>
    <label><span>Broker source</span><select name="broker_source">{broker_source_select('broker_source', t.get('broker_source'))}</select></label>
    {earnings_bet_toggle(t)}
    {field('Contracts','contracts',t.get('contracts',''),'number','step="0.01" min="0"')}
    <label><span data-seller-strike-label>Short strike</span><input type="number" name="strike" value="{escape(str(t.get('strike') or ''))}" step="0.01" min="0"></label>
    <label class="spread-field"><span data-seller-long-label>Long strike</span><input type="number" name="long_put_strike" value="{escape(str(t.get('long_put_strike') or ''))}" step="0.01" min="0"><small data-seller-long-help>Only for credit spreads</small></label>
    <label class="condor-field"><span>Short call strike</span><input type="number" name="short_call_strike" value="{escape(str(t.get('short_call_strike') or ''))}" step="0.01" min="0"></label>
    <label class="condor-field"><span>Long call strike</span><input type="number" name="long_call_strike" value="{escape(str(t.get('long_call_strike') or ''))}" step="0.01" min="0"></label>
    </div></fieldset>
    <fieldset><legend>Dates</legend><div class="form-grid">
    {field('Open date','open_date',t.get('open_date',''),'date','required')}{field('Expiration','expiration',t.get('expiration',''),'date')}{field('Close date','close_date',t.get('close_date',''),'date')}
    </div></fieldset>
    <fieldset><legend>Cash flow & capital</legend><div class="form-grid">
    {field('Premium received / share','premium_in',t.get('premium_in',''),'number','step="any"')}
    {field('Exit or current premium / share','exit_premium',t.get('exit_premium',''),'number','step="any"','Leave blank for expired options')}
    {field('Stock / assignment P&L','stock_pnl',t.get('stock_pnl',0),'number','step="any"')}
    {field('Fees','fees',t.get('fees',0),'number','step="any" min="0"')}
    {field('Capital used','capital_used',t.get('capital_used',''),'number','step="any" min="0"','Use max loss for credit spreads if preferred')}
    </div></fieldset>
    <fieldset><legend>Notes</legend><label><textarea name="notes" rows="4" placeholder="Roll linkage, assignment details, thesis...">{escape(t.get('notes') or '')}</textarea></label></fieldset>
    <div class="form-actions">{delete_html}<button class="button" type="submit">{'Save changes' if editing else 'Add trade'}</button></div></form></div>"""
    return layout(title + " - Option Ledger", body, "new" if not editing else "trades")


def account_page(error="", message="") -> bytes:
    user = current_user()
    username = user["username"] if user else "root"
    message_html = f'<div class="notice">{escape(message)}</div>' if message else ""
    error_html = f'<div class="alert">{escape(error)}</div>' if error else ""
    body = f'''<div class="page-head"><div><p class="eyebrow">Local account</p><h1>Account</h1></div><a class="button secondary" href="/">Dashboard</a></div>
    <div class="grid two account-grid">
      <section class="panel">
        <div class="panel-head"><h2>Current user</h2><span>data is isolated per account</span></div>
        <div class="panel-kpi"><span>Signed in as</span><strong>{escape(username)}</strong></div>
        <form class="form-actions" method="post" action="/logout"><button class="button secondary" type="submit">Use root account</button></form>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Switch user</h2><span>root uses a blank password</span></div>
        {message_html}{error_html}
        <form class="account-form" method="post" action="/login">
          {field('Username', 'username', '', attrs='required autocomplete="username"')}
          {field('Password', 'password', '', 'password', 'autocomplete="current-password" placeholder="blank for root"')}
          <div class="form-actions"><button class="button" type="submit">Sign in</button></div>
        </form>
      </section>
    </div>
    <section class="panel">
      <div class="panel-head"><h2>Create user</h2><span>new account starts with empty trades and holdings</span></div>
      <form class="account-form account-create-form" method="post" action="/users/new">
        {field('Username', 'username', '', attrs='required maxlength="32" autocomplete="username"')}
        {field('Display name', 'display_name', '', attrs='maxlength="60"')}
        {field('Password', 'password', '', 'password', 'required autocomplete="new-password"')}
        <div class="form-actions"><button class="button" type="submit">Create and sign in</button></div>
      </form>
    </section>'''
    return layout("Account - Option Ledger", body, "account")


def validate(form):
    ticker = form.get("ticker", "").strip().upper()
    strategy = form.get("strategy", "")
    status = form.get("status", "")
    open_date = form.get("open_date", "")
    if not ticker: return None, "Ticker is required."
    if strategy not in STRATEGIES: return None, "Choose a valid strategy."
    if status not in STATUSES: return None, "Choose a valid status."
    if not parse_date(open_date): return None, "Enter a valid open date."
    for name in ("expiration", "close_date"):
        if form.get(name) and not parse_date(form[name]): return None, f"Enter a valid {name.replace('_',' ')}."
    close_date = None if status == "Open" else form.get("close_date") or None
    if status != "Open" and not close_date:
        close_date = date.today().isoformat()
    data = {"ticker": ticker, "sector": sector_for_ticker(ticker), "strategy": strategy, "status": status, "open_date": open_date,
            "expiration": form.get("expiration") or None, "close_date": close_date,
            "broker_source": normalize_broker_source(form.get("broker_source")),
            "notes": form.get("notes", "").strip() or None}
    for name in ("contracts", "strike", "long_put_strike", "short_call_strike", "long_call_strike", "premium_in", "exit_premium", "stock_pnl", "fees", "capital_used"):
        data[name] = number(form.get(name))
    data["stock_pnl"] = data["stock_pnl"] or 0
    data["fees"] = data["fees"] or 0
    if strategy == "Iron Condor":
        strikes = (data["long_put_strike"], data["strike"], data["short_call_strike"], data["long_call_strike"])
        if any(value is None or value <= 0 for value in strikes):
            return None, "Enter all four Iron Condor strikes."
        if not all(left < right for left, right in zip(strikes, strikes[1:])):
            return None, "Iron Condor strikes must be ordered: long put < short put < short call < long call."
    elif strategy not in {"Put Credit Spread", "Call Credit Spread"}:
        data["long_put_strike"] = None
    elif data["strike"] is not None and data["long_put_strike"] is not None:
        short_strike = data["strike"]
        long_strike = data["long_put_strike"]
        if strategy == "Put Credit Spread":
            data["strike"], data["long_put_strike"] = max(short_strike, long_strike), min(short_strike, long_strike)
        else:
            data["strike"], data["long_put_strike"] = min(short_strike, long_strike), max(short_strike, long_strike)
    if strategy != "Iron Condor":
        data["short_call_strike"] = None
        data["long_call_strike"] = None
    return data, ""


def watch_snapshot() -> dict[Path, int]:
    snapshot = {}
    for path in BASE_DIR.rglob("*"):
        if any(part in IGNORED_WATCH_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in WATCHED_EXTENSIONS:
            try:
                snapshot[path] = path.stat().st_mtime_ns
            except OSError:
                pass
    return snapshot


def wait_for_change(snapshot: dict[Path, int]) -> dict[Path, int]:
    while True:
        time.sleep(RELOAD_INTERVAL)
        current = watch_snapshot()
        if current != snapshot:
            changed = sorted(set(current) ^ set(snapshot) or {
                path for path, mtime in current.items() if snapshot.get(path) != mtime
            })
            if changed:
                rel = changed[0].relative_to(BASE_DIR)
                print(f"Detected change in {rel}; reloading...")
            return current


def run_with_reloader() -> None:
    print(f"Hot reload is watching {BASE_DIR}")
    snapshot = watch_snapshot()
    child = None
    try:
        while True:
            env = os.environ.copy()
            env["OPTIONS_TRACKER_RELOAD"] = "0"
            env.setdefault("PYTHONUNBUFFERED", "1")
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve())], env=env)
            snapshot = wait_for_change(snapshot)
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def cookie_value(self, name):
        cookies = self.headers.get("Cookie", "")
        for item in cookies.split(";"):
            if "=" not in item:
                continue
            key, value = item.strip().split("=", 1)
            if key == name:
                return value
        return None

    def set_current_user(self):
        user_id = verify_user_cookie(self.cookie_value("options_user"))
        if not user_id or not user_by_id(user_id):
            user_id = 1
        USER_CONTEXT.id = user_id

    def send_bytes(self, content, status=200, content_type="text/html; charset=utf-8", headers=None):
        self.send_response(status); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(content)

    def redirect(self, path, headers=None):
        self.send_response(303); self.send_header("Location", path)
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers()

    def form_data(self):
        length = int(self.headers.get("Content-Length", "0"))
        return {key: values[0] for key, values in parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True).items()}

    def do_GET(self):
        self.set_current_user()
        parsed = urlparse(self.path); path = parsed.path
        query = parse_qs(parsed.query)
        CURRENCY_CONTEXT.value = "rmb" if query.get("currency", ["usd"])[0] == "rmb" else "usd"
        if path == "/__reload_id": return self.send_bytes(RELOAD_ID.encode("utf-8"), content_type="text/plain; charset=utf-8", headers={"Cache-Control": "no-store"})
        if path == "/performance":
            trades, ticker = performance_records_for_query(query)
            if not ticker and query.get("dashboard", [""])[0] not in {"option-buyer", "day-trades", "stock-trades"}:
                dash_brokers, dash_books = dashboard_filter_values(query)
                perf_extra = dashboard_filter_params(query, dash_brokers, dash_books, {"perf_metric", "perf_range", "perf_start", "perf_end"})
            else:
                perf_brokers = broker_filter_values(query, "perf_broker")
                perf_extra = broker_filter_query_params(query, "perf_broker", perf_brokers, {"perf_metric", "perf_range", "perf_start", "perf_end"})
            return self.send_bytes(
                performance_chart(
                    trades,
                    query.get("perf_range", ["all"])[0],
                    query.get("perf_metric", ["pnl"])[0],
                    query.get("perf_start", [""])[0],
                    query.get("perf_end", [""])[0],
                    ticker,
                    perf_extra,
                ).encode("utf-8")
            )
        if path == "/strategy-performance":
            trades, _ticker = performance_records_for_query(query)
            return self.send_bytes(
                strategy_performance_panel(
                    trades,
                    query.get("perf_range", ["all"])[0],
                    query.get("perf_start", [""])[0],
                    query.get("perf_end", [""])[0],
                ).encode("utf-8")
            )
        if path == "/capital-usage":
            trades, _ticker = performance_records_for_query(query)
            return self.send_bytes(
                capital_usage_chart(
                    trades,
                    query.get("perf_range", ["all"])[0],
                    query.get("perf_start", [""])[0],
                    query.get("perf_end", [""])[0],
                ).encode("utf-8")
            )
        if path == "/performance-controls":
            trades, ticker = performance_records_for_query(query)
            if not ticker and query.get("dashboard", [""])[0] not in {"option-buyer", "day-trades", "stock-trades"}:
                dash_brokers, dash_books = dashboard_filter_values(query)
                perf_extra = dashboard_filter_params(query, dash_brokers, dash_books, {"perf_metric", "perf_range", "perf_start", "perf_end"})
            else:
                perf_brokers = broker_filter_values(query, "perf_broker")
                perf_extra = broker_filter_query_params(query, "perf_broker", perf_brokers, {"perf_metric", "perf_range", "perf_start", "perf_end"})
            return self.send_bytes(
                performance_range_controls(
                    trades,
                    query.get("perf_range", ["all"])[0],
                    query.get("perf_metric", ["pnl"])[0],
                    query.get("perf_start", [""])[0],
                    query.get("perf_end", [""])[0],
                    ticker,
                    perf_extra,
                ).encode("utf-8")
            )
        if path == "/calendar":
            dashboard_mode = query.get("dashboard", [""])[0]
            is_option_buyer_dashboard = dashboard_mode == "option-buyer"
            is_day_trade_dashboard = dashboard_mode == "day-trades"
            is_stock_trade_dashboard = dashboard_mode == "stock-trades"
            if is_option_buyer_dashboard:
                trades = [other_option_as_trade(row) for row in all_other_option_trades()]
            elif is_day_trade_dashboard:
                trades = [day_trade_as_trade(row) for row in all_day_trades()]
            elif is_stock_trade_dashboard:
                trades = [stock_trade_as_trade(row) for row in all_stock_trades()]
            else:
                trades = symbol_trade_records()
            if dashboard_mode in {"option-buyer", "day-trades", "stock-trades"}:
                cal_brokers = broker_filter_values(query, "cal_broker")
                trades = filter_trades_by_brokers(trades, cal_brokers)
                extra = broker_filter_query_params(query, "cal_broker", cal_brokers, {"cal_year", "cal_month", "cal_view"})
            else:
                dash_brokers, dash_books = dashboard_filter_values(query)
                trades = filter_dashboard_trades(trades, dash_brokers, dash_books)
                extra = dashboard_filter_params(query, dash_brokers, dash_books, {"cal_year", "cal_month", "cal_view"})
            try:
                calendar_year = int(query.get("cal_year", [""])[0])
            except ValueError:
                calendar_year = None
            try:
                calendar_month = int(query.get("cal_month", [""])[0])
            except ValueError:
                calendar_month = None
            return self.send_bytes(
                close_date_calendar(
                    trades,
                    calendar_year,
                    calendar_month,
                    query.get("cal_view", ["month"])[0],
                    extra,
                ).encode("utf-8")
            )
        if path == "/market-news/data":
            items, error = fetch_jin10_flash_items(force=query.get("refresh", ["0"])[0] == "1")
            return self.send_bytes(
                jin10_feed_html(items, error).encode("utf-8"),
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/sentiment/data":
            cards, error = fetch_greedyfear_cards(force=query.get("refresh", ["0"])[0] == "1")
            return self.send_bytes(
                greedyfear_cards_html(cards, error).encode("utf-8"),
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/earnings-reminder":
            reminder = current_week_earnings_reminder_html(force=query.get("refresh", ["0"])[0] == "1")
            return self.send_bytes(
                reminder.encode("utf-8"),
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/holdings/data":
            payload = holdings_live_payload(query, refresh=True)
            return self.send_bytes(
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                content_type="application/json; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/ticker-tape":
            return self.send_bytes(
                ticker_tape_html().encode("utf-8"),
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/brokerage/robinhood/status":
            return self.send_bytes(
                json.dumps(robinhood_snapshot_status()).encode("utf-8"),
                content_type="application/json; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/market-news": return self.send_bytes(market_news_page(query))
        if path == "/sentiment": return self.send_bytes(sentiment_page(query))
        if path == "/earnings-calendar": return self.redirect("/earnings-bets#next-week")
        if path == "/trade-journal-review": return self.send_bytes(trade_journal_review_page(query))
        if path == "/brokerage": return self.send_bytes(brokerage_page(query=query))
        if path == "/portfolio-deposit/new": return self.send_bytes(portfolio_deposit_form())
        if path == "/options-calculator": return self.send_bytes(option_calculator_page(query))
        if path in {"/account", "/login"}: return self.send_bytes(account_page())
        if path == "/welcome": return self.send_bytes(welcome_page(query))
        if path == "/": return self.send_bytes(dashboard_page(query))
        if path == "/symbols": return self.send_bytes(symbols_page(query))
        if path == "/analytics": return self.redirect("/")
        if path == "/assistant": return self.send_bytes(assistant_page())
        if path == "/trades": return self.send_bytes(trades_page(query))
        if path == "/day-trades": return self.redirect("/trades?view=day-trades")
        if path == "/earnings-bets": return self.send_bytes(earnings_bets_page(query))
        if path == "/holdings": return self.send_bytes(holdings_page(query))
        if path == "/favicon.ico":
            return self.send_bytes((STATIC_DIR / "dandan-avatar.png").read_bytes(), content_type="image/png")
        if path.startswith("/symbol/") and path.endswith("/price"):
            ticker = unquote(path.split("/", 3)[2]).strip()
            return self.send_bytes(
                symbol_price_panel(ticker).encode("utf-8"),
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path.startswith("/symbol/"):
            ticker = unquote(path.split("/", 2)[2]).strip()
            return self.send_bytes(symbol_detail_page(ticker, query))
        if path == "/option-trade/new":
            requested_book = query.get("book", [""])[0]
            mode = "seller" if requested_book == "seller" else "buyer"
            form_data = {"ticker": query.get("ticker", [""])[0].strip().upper()}
            return self.send_bytes(unified_option_trade_form(mode, form_data))
        if path == "/trade/new": return self.send_bytes(unified_option_trade_form("seller"))
        if path == "/day-trade/new": return self.send_bytes(day_trade_form())
        if path == "/other-option/new": return self.send_bytes(unified_option_trade_form("buyer"))
        if path == "/earnings-bet/new": return self.send_bytes(earnings_bet_form())
        if path == "/stock-trade/new":
            return self.send_bytes(stock_trade_form({
                "ticker": query.get("ticker", [""])[0].strip().upper(),
                "status": query.get("status", [""])[0],
            }))
        if path == "/holding/new": return self.send_bytes(holding_form())
        if path.startswith("/trade/") and path.endswith("/edit"):
            try: trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: trade = connection.execute("SELECT * FROM trades WHERE id=? AND user_id=?", (trade_id, current_user_id())).fetchone()
            return self.send_bytes(trade_form(trade, return_to=safe_return_to(query.get("return_to", [""])[0]))) if trade else self.send_error(404)
        if path.startswith("/day-trade/") and path.endswith("/edit"):
            try: day_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: day_trade = connection.execute("SELECT * FROM day_trades WHERE id=? AND user_id=?", (day_trade_id, current_user_id())).fetchone()
            return self.send_bytes(day_trade_form(day_trade, return_to=safe_return_to(query.get("return_to", [""])[0]))) if day_trade else self.send_error(404)
        if path.startswith("/other-option/") and path.endswith("/edit"):
            try: other_option_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: other_option = connection.execute("SELECT * FROM other_option_trades WHERE id=? AND user_id=?", (other_option_id, current_user_id())).fetchone()
            return self.send_bytes(other_option_form(other_option, return_to=safe_return_to(query.get("return_to", [""])[0]))) if other_option else self.send_error(404)
        if path.startswith("/earnings-bet/") and path.endswith("/edit"):
            try: earnings_bet_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: earnings_bet = connection.execute("SELECT * FROM earnings_bets WHERE id=? AND user_id=?", (earnings_bet_id, current_user_id())).fetchone()
            return self.send_bytes(earnings_bet_form(earnings_bet)) if earnings_bet else self.send_error(404)
        if path.startswith("/stock-trade/") and path.endswith("/edit"):
            try: stock_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: stock_trade = connection.execute("SELECT * FROM stock_trades WHERE id=? AND user_id=?", (stock_trade_id, current_user_id())).fetchone()
            return self.send_bytes(stock_trade_form(stock_trade, return_to=safe_return_to(query.get("return_to", [""])[0]))) if stock_trade else self.send_error(404)
        if path.startswith("/holding/") and path.endswith("/edit"):
            try: holding_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: holding = connection.execute("SELECT * FROM stock_holdings WHERE id=? AND user_id=?", (holding_id, current_user_id())).fetchone()
            return self.send_bytes(holding_form(holding)) if holding else self.send_error(404)
        if path == "/export.csv": return self.export_csv()
        if path.startswith("/static/"):
            name = Path(path).name
            if name not in {
                "style.css", "app.js", "ragdoll-cat-logo.png", "dandan-avatar.png", "dandan-mascot.png",
                "dandan-pet.png", "dandan-sleep.png", "dandan-stretch.png", "dandan-wave.png",
                "dandan-sleep-sprite.png", "dandan-wake-sprite.png",
            }: return self.send_error(404)
            file = STATIC_DIR / name
            if name.endswith(".css"):
                kind = "text/css; charset=utf-8"
            elif name.endswith(".js"):
                kind = "application/javascript; charset=utf-8"
            else:
                kind = "image/png"
            headers = {"Cache-Control": "no-store"} if name in {"style.css", "app.js"} else None
            return self.send_bytes(file.read_bytes(), content_type=kind, headers=headers)
        self.send_error(404)

    def do_POST(self):
        self.set_current_user()
        parsed_request = urlparse(self.path)
        path = parsed_request.path
        query = parse_qs(parsed_request.query)
        form = self.form_data()
        if path == "/login":
            username = form.get("username", "").strip()
            user = user_by_name(username)
            if not user or not check_password(form.get("password", ""), user["password_hash"]):
                return self.send_bytes(account_page("Invalid username or password."), status=422)
            return self.redirect("/account", {"Set-Cookie": f"options_user={signed_user_cookie(user['id'])}; Path=/; HttpOnly; SameSite=Lax"})
        if path == "/logout":
            return self.redirect("/account", {"Set-Cookie": "options_user=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
        if path == "/users/new":
            username = form.get("username", "").strip()
            display_name = form.get("display_name", "").strip() or username
            password = form.get("password", "")
            if not username or not username.replace("_", "").replace("-", "").isalnum():
                return self.send_bytes(account_page("Use letters, numbers, hyphen, or underscore for username."), status=422)
            if len(username) > 32:
                return self.send_bytes(account_page("Username is too long."), status=422)
            if len(password) < 4:
                return self.send_bytes(account_page("Password must be at least 4 characters."), status=422)
            try:
                with closing(db()) as connection:
                    cursor = connection.execute(
                        "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
                        (username, display_name, password_hash(password)),
                    )
                    connection.commit()
                    user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                return self.send_bytes(account_page("That username already exists."), status=422)
            return self.redirect("/account", {"Set-Cookie": f"options_user={signed_user_cookie(user_id)}; Path=/; HttpOnly; SameSite=Lax"})
        if path == "/assistant":
            focus = form.get("focus", "")
            prompt = assistant_prompt(focus)
            result, error = call_ai_assistant(prompt)
            return self.send_bytes(assistant_page(result, error, focus))
        if path == "/holdings/refresh-prices":
            updated, errors = refresh_holding_prices()
            fallback = f"/?dashboard=stock-trades&{urlencode({'prices': updated, 'price_errors': len(errors)})}"
            return_to = safe_return_to(form.get("return_to"), fallback)
            separator = "&" if "?" in return_to else "?"
            return self.redirect(f"{return_to}{separator}{urlencode({'prices': updated, 'price_errors': len(errors)})}")
        if path == "/brokerage/save":
            save_brokerage_account(form)
            return self.send_bytes(brokerage_page("Robinhood account snapshot saved."))
        if path == "/brokerage/external/save":
            save_external_account(form)
            total = current_portfolio_total()
            if total:
                save_portfolio_snapshot(total)
            return self.send_bytes(brokerage_page("External account snapshot saved."))
        if path == "/portfolio-deposit/new":
            flow_date = form.get("flow_date", "").strip()
            amount = number(form.get("amount"))
            if not parse_date(flow_date):
                return self.send_bytes(portfolio_deposit_form(form, "Enter a valid deposit date."), status=422)
            if amount is None or amount <= 0:
                return self.send_bytes(portfolio_deposit_form(form, "Deposit amount must be greater than 0."), status=422)
            save_portfolio_deposit(flow_date, amount, form.get("account", ""), form.get("notes", ""))
            return self.redirect("/brokerage?range=all&method=simple")
        if path.startswith("/portfolio-deposit/") and path.endswith("/delete"):
            try:
                flow_id = int(path.split("/")[2])
            except (ValueError, IndexError):
                return self.send_error(404)
            with closing(db()) as connection:
                connection.execute(
                    "DELETE FROM portfolio_cash_flows WHERE id=? AND user_id=?",
                    (flow_id, current_user_id()),
                )
                connection.commit()
            return self.redirect("/brokerage?range=all&method=simple")
        if path == "/brokerage/robinhood/sync":
            if not ROBINHOOD_SNAPSHOT_PATH.exists():
                return self.send_bytes(
                    brokerage_page("", "No Robinhood MCP snapshot found. Ask Codex to read Robinhood first, then sync again."),
                    status=422,
                )
            try:
                snapshot = json.loads(ROBINHOOD_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                synced_accounts, synced_holdings = import_robinhood_snapshot(snapshot)
            except Exception as exc:
                return self.send_bytes(brokerage_page("", f"Robinhood snapshot import failed: {exc}"), status=422)
            return self.send_bytes(
                brokerage_page(f"Synced {synced_accounts} Robinhood accounts and {synced_holdings} stock holdings.")
            )
        if path == "/brokerage/plaid/link-token":
            payload, error = create_plaid_link_token()
            status = 422 if error else 200
            body = {"error": error} if error else {"link_token": payload.get("link_token")}
            return self.send_bytes(
                json.dumps(body).encode("utf-8"),
                status=status,
                content_type="application/json; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/brokerage/plaid/exchange":
            public_token = form.get("public_token", "")
            institution = form.get("institution", "")
            message, error = exchange_plaid_public_token(public_token, institution)
            if not error:
                synced, sync_errors = sync_plaid_accounts()
                total = current_portfolio_total()
                if total:
                    save_portfolio_snapshot(total)
                message = f"{message} Synced {synced} accounts."
                error = "; ".join(sync_errors) if sync_errors else None
            status = 422 if error else 200
            return self.send_bytes(
                json.dumps({"message": message, "error": error}).encode("utf-8"),
                status=status,
                content_type="application/json; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        if path == "/brokerage/sync":
            synced, errors = sync_plaid_accounts()
            total = current_portfolio_total()
            if total:
                save_portfolio_snapshot(total)
            if errors:
                return self.send_bytes(brokerage_page(f"Synced {synced} Plaid accounts.", "; ".join(errors)), status=422)
            return self.send_bytes(brokerage_page(f"Synced {synced} Plaid accounts."))
        if path.startswith("/symbol/") and path.endswith("/refresh-price"):
            ticker = unquote(path.split("/", 3)[2]).strip().upper()
            price, updated, error = refresh_symbol_price(ticker)
            params = {"updated": updated}
            if price is not None:
                params["price"] = f"{price:.4f}"
            if error:
                params["price_error"] = error[:180]
            return self.redirect(f"/symbol/{quote(ticker)}?{urlencode(params)}")
        if path == "/holding/new":
            data, error = validate_holding(form)
            if error: return self.send_bytes(holding_form(form, error), status=422)
            data["user_id"] = current_user_id()
            fields = tuple(data.keys())
            with closing(db()) as connection:
                connection.execute(f"INSERT INTO stock_holdings ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [data[x] for x in fields]); connection.commit()
            return self.redirect("/?dashboard=stock-trades")
        if path.startswith("/holding/") and path.endswith("/edit"):
            try: holding_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate_holding(form); form["id"] = holding_id
            if error: return self.send_bytes(holding_form(form, error), status=422)
            fields = tuple(data.keys())
            with closing(db()) as connection:
                connection.execute(f"UPDATE stock_holdings SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [data[x] for x in fields] + [holding_id, current_user_id()]); connection.commit()
            return self.redirect("/?dashboard=stock-trades")
        if path.startswith("/holding/") and path.endswith("/delete"):
            try: holding_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection: connection.execute("DELETE FROM stock_holdings WHERE id=? AND user_id=?", (holding_id, current_user_id())); connection.commit()
            return self.redirect("/?dashboard=stock-trades")
        if path == "/option-trade/new":
            redirect_to, error, mode = save_unified_option_trade(form)
            if error:
                return self.send_bytes(unified_option_trade_form(mode, form, error), status=422)
            return self.redirect(redirect_to)
        if path == "/trade/new":
            data, error = validate(form)
            if error: return self.send_bytes(trade_form(form, error), status=422)
            data["user_id"] = current_user_id()
            fields = tuple(data.keys())
            with closing(db()) as connection:
                cursor = connection.execute(f"INSERT INTO trades ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [data[x] for x in fields])
                sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
                connection.commit()
            return self.redirect(symbol_page_href(data.get("ticker"), "/trades"))
        if path == "/day-trade/new":
            data, error = validate_day_trade(form)
            if error: return self.send_bytes(day_trade_form(form, error), status=422)
            data["user_id"] = current_user_id()
            with closing(db()) as connection:
                if day_trade_should_live_in_buyer(data):
                    cursor = insert_row(connection, "other_option_trades", day_data_to_other_option(data))
                    sync_trade_earnings_bet(connection, "other_option_trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades?view=option-buyer")
                elif day_trade_should_live_in_seller(data):
                    cursor = insert_row(connection, "trades", day_data_to_seller_trade(data))
                    sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades")
                else:
                    cursor = insert_row(connection, "day_trades", data)
                    sync_trade_earnings_bet(connection, "day_trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades?view=day-trades")
                connection.commit()
            return self.redirect(redirect)
        if path == "/other-option/new":
            data, error = validate_other_option(form)
            if error: return self.send_bytes(other_option_form(form, error), status=422)
            data["user_id"] = current_user_id()
            with closing(db()) as connection:
                if other_option_should_live_in_seller(form, data):
                    cursor = insert_row(connection, "trades", other_option_data_to_seller_trade(data))
                    sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades")
                elif other_option_should_live_in_day(data):
                    cursor = insert_row(connection, "day_trades", other_option_data_to_day(data))
                    sync_trade_earnings_bet(connection, "day_trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades?view=day-trades")
                else:
                    cursor = insert_row(connection, "other_option_trades", data)
                    sync_trade_earnings_bet(connection, "other_option_trades", cursor.lastrowid, earnings_checked(form))
                    redirect = symbol_page_href(data.get("ticker"), "/trades?view=option-buyer")
                connection.commit()
            return self.redirect(redirect)
        if path == "/earnings-bet/new":
            data, error = validate_earnings_bet(form)
            if error: return self.send_bytes(earnings_bet_form(form, error), status=422)
            linked_trade_key = data.pop("linked_trade_key", "")
            data["user_id"] = current_user_id()
            fields = tuple(data.keys())
            with closing(db()) as connection:
                cursor = connection.execute(f"INSERT INTO earnings_bets ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [data[x] for x in fields])
                apply_earnings_trade_link(connection, cursor.lastrowid, linked_trade_key)
                connection.commit()
            return self.redirect("/earnings-bets")
        if path.startswith("/earnings-bet/") and path.endswith("/edit"):
            try: earnings_bet_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate_earnings_bet(form); form["id"] = earnings_bet_id
            if error: return self.send_bytes(earnings_bet_form(form, error), status=422)
            linked_trade_key = data.pop("linked_trade_key", "")
            fields = tuple(data.keys())
            with closing(db()) as connection:
                connection.execute(f"UPDATE earnings_bets SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [data[x] for x in fields] + [earnings_bet_id, current_user_id()])
                apply_earnings_trade_link(connection, earnings_bet_id, linked_trade_key)
                connection.commit()
            return self.redirect("/earnings-bets")
        if path.startswith("/earnings-bet/") and path.endswith("/delete"):
            try: earnings_bet_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection:
                apply_earnings_trade_link(connection, earnings_bet_id, "")
                connection.execute("DELETE FROM earnings_bets WHERE id=? AND user_id=?", (earnings_bet_id, current_user_id()))
                connection.commit()
            return self.redirect("/earnings-bets")
        if path == "/stock-trade/new":
            data, error = validate_stock_trade(form)
            if error: return self.send_bytes(stock_trade_form(form, error, return_to=form_return_to(form, "/trades?view=stock-trades")), status=422)
            data["user_id"] = current_user_id()
            fields = tuple(data.keys())
            with closing(db()) as connection:
                cursor = connection.execute(f"INSERT INTO stock_trades ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [data[x] for x in fields])
                sync_trade_earnings_bet(connection, "stock_trades", cursor.lastrowid, earnings_checked(form))
                remove_matching_holding_for_open_stock_trade(connection, data)
                remove_matching_synced_holding_for_closed_stock_trade(connection, data)
                connection.commit()
            return self.redirect(symbol_page_href(data.get("ticker"), "/trades?view=stock-trades"))
        if path.startswith("/stock-trade/") and path.endswith("/edit"):
            try: stock_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate_stock_trade(form); form["id"] = stock_trade_id
            if error: return self.send_bytes(stock_trade_form(form, error, return_to=form_return_to(form, "/trades?view=stock-trades")), status=422)
            fields = tuple(data.keys())
            with closing(db()) as connection:
                previous = connection.execute(
                    "SELECT status FROM stock_trades WHERE id=? AND user_id=?",
                    (stock_trade_id, current_user_id()),
                ).fetchone()
                connection.execute(f"UPDATE stock_trades SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [data[x] for x in fields] + [stock_trade_id, current_user_id()])
                sync_trade_earnings_bet(connection, "stock_trades", stock_trade_id, earnings_checked(form))
                remove_matching_holding_for_open_stock_trade(connection, data)
                if previous and previous["status"] != "Closed":
                    remove_matching_synced_holding_for_closed_stock_trade(connection, data)
                connection.commit()
            return self.redirect(form_return_to(form, "/trades?view=stock-trades"))
        if path.startswith("/stock-trade/") and path.endswith("/delete"):
            try: stock_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection:
                sync_trade_earnings_bet(connection, "stock_trades", stock_trade_id, False)
                connection.execute("DELETE FROM stock_trades WHERE id=? AND user_id=?", (stock_trade_id, current_user_id()))
                connection.commit()
            return self.redirect(safe_return_to(query.get("return_to", [""])[0], "/trades?view=stock-trades"))
        if path.startswith("/day-trade/") and path.endswith("/edit"):
            try: day_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate_day_trade(form); form["id"] = day_trade_id
            if error: return self.send_bytes(day_trade_form(form, error, return_to=form_return_to(form, "/trades?view=day-trades")), status=422)
            data["user_id"] = current_user_id()
            with closing(db()) as connection:
                if day_trade_should_live_in_buyer(data):
                    sync_trade_earnings_bet(connection, "day_trades", day_trade_id, False)
                    cursor = insert_row(connection, "other_option_trades", day_data_to_other_option(data))
                    sync_trade_earnings_bet(connection, "other_option_trades", cursor.lastrowid, earnings_checked(form))
                    connection.execute("DELETE FROM day_trades WHERE id=? AND user_id=?", (day_trade_id, current_user_id()))
                    redirect = "/trades?view=option-buyer"
                elif day_trade_should_live_in_seller(data):
                    sync_trade_earnings_bet(connection, "day_trades", day_trade_id, False)
                    cursor = insert_row(connection, "trades", day_data_to_seller_trade(data))
                    sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
                    connection.execute("DELETE FROM day_trades WHERE id=? AND user_id=?", (day_trade_id, current_user_id()))
                    redirect = "/trades"
                else:
                    update_data = {key: value for key, value in data.items() if key != "user_id"}
                    fields = tuple(update_data.keys())
                    connection.execute(f"UPDATE day_trades SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [update_data[x] for x in fields] + [day_trade_id, current_user_id()])
                    sync_trade_earnings_bet(connection, "day_trades", day_trade_id, earnings_checked(form))
                    redirect = "/trades?view=day-trades"
                connection.commit()
            return self.redirect(form_return_to(form, redirect))
        if path.startswith("/day-trade/") and path.endswith("/delete"):
            try: day_trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection:
                sync_trade_earnings_bet(connection, "day_trades", day_trade_id, False)
                connection.execute("DELETE FROM day_trades WHERE id=? AND user_id=?", (day_trade_id, current_user_id()))
                connection.commit()
            return self.redirect(safe_return_to(query.get("return_to", [""])[0], "/trades?view=day-trades"))
        if path.startswith("/other-option/") and path.endswith("/edit"):
            try: other_option_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate_other_option(form); form["id"] = other_option_id
            if error: return self.send_bytes(other_option_form(form, error, return_to=form_return_to(form, "/trades?view=option-buyer")), status=422)
            data["user_id"] = current_user_id()
            with closing(db()) as connection:
                if other_option_should_live_in_seller(form, data):
                    sync_trade_earnings_bet(connection, "other_option_trades", other_option_id, False)
                    cursor = insert_row(connection, "trades", other_option_data_to_seller_trade(data))
                    sync_trade_earnings_bet(connection, "trades", cursor.lastrowid, earnings_checked(form))
                    connection.execute("DELETE FROM other_option_trades WHERE id=? AND user_id=?", (other_option_id, current_user_id()))
                    redirect = "/trades"
                elif other_option_should_live_in_day(data):
                    sync_trade_earnings_bet(connection, "other_option_trades", other_option_id, False)
                    cursor = insert_row(connection, "day_trades", other_option_data_to_day(data))
                    sync_trade_earnings_bet(connection, "day_trades", cursor.lastrowid, earnings_checked(form))
                    connection.execute("DELETE FROM other_option_trades WHERE id=? AND user_id=?", (other_option_id, current_user_id()))
                    redirect = "/trades?view=day-trades"
                else:
                    update_data = {key: value for key, value in data.items() if key != "user_id"}
                    fields = tuple(update_data.keys())
                    connection.execute(f"UPDATE other_option_trades SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [update_data[x] for x in fields] + [other_option_id, current_user_id()])
                    sync_trade_earnings_bet(connection, "other_option_trades", other_option_id, earnings_checked(form))
                    redirect = "/trades?view=option-buyer"
                connection.commit()
            return_target = form_return_to(form, redirect)
            if redirect == "/trades" and return_target == "/trades?view=option-buyer":
                return_target = redirect
            return self.redirect(return_target)
        if path.startswith("/other-option/") and path.endswith("/delete"):
            try: other_option_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection:
                sync_trade_earnings_bet(connection, "other_option_trades", other_option_id, False)
                connection.execute("DELETE FROM other_option_trades WHERE id=? AND user_id=?", (other_option_id, current_user_id()))
                connection.commit()
            return self.redirect(safe_return_to(query.get("return_to", [""])[0], "/trades?view=option-buyer"))
        if path.startswith("/trade/") and path.endswith("/edit"):
            try: trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            data, error = validate(form); form["id"] = trade_id
            if error: return self.send_bytes(trade_form(form, error, return_to=form_return_to(form, "/trades")), status=422)
            fields = tuple(data.keys())
            with closing(db()) as connection:
                connection.execute(f"UPDATE trades SET {','.join(x+'=?' for x in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", [data[x] for x in fields] + [trade_id, current_user_id()])
                sync_trade_earnings_bet(connection, "trades", trade_id, earnings_checked(form))
                connection.commit()
            return self.redirect(form_return_to(form, "/trades"))
        if path.startswith("/trade/") and path.endswith("/delete"):
            try: trade_id = int(path.split("/")[2])
            except ValueError: return self.send_error(404)
            with closing(db()) as connection:
                sync_trade_earnings_bet(connection, "trades", trade_id, False)
                connection.execute("DELETE FROM trades WHERE id=? AND user_id=?", (trade_id, current_user_id()))
                connection.commit()
            return self.redirect(safe_return_to(query.get("return_to", [""])[0], "/trades"))
        self.send_error(404)

    def export_csv(self):
        trades = all_trades()
        output = io.StringIO(); writer = csv.writer(output)
        headers = ("ID","Ticker","Sector","Strategy","Open Date","Expiration","Close Date","Status","Contracts","Short Put / Short Strike","Long Put Strike","Short Call Strike","Long Call Strike","Premium In","Exit/Current Premium","Stock/Assignment P&L","Fees","Capital Used","Days Held","Premium P&L","Net P&L","ROC","Annualized Return","Outcome","Notes")
        writer.writerow(headers)
        for t in trades:
            writer.writerow([t.get(x) for x in ("id","ticker","sector","strategy","open_date","expiration","close_date","status","contracts","strike","long_put_strike","short_call_strike","long_call_strike","premium_in","exit_premium","stock_pnl","fees","capital_used","days_held","premium_pnl","net_pnl","roc","annualized_return","outcome","notes")])
        payload = ('\ufeff' + output.getvalue()).encode('utf-8')
        self.send_bytes(payload, content_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="options-trades-{date.today().isoformat()}.csv"'})


def run(reload: bool = RELOAD) -> None:
    if reload:
        return run_with_reloader()
    init_db()
    start_auto_refresh_prices()
    start_auto_refresh_portfolio()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Option Ledger is running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__":
    run()
