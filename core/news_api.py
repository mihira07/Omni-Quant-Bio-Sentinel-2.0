from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
import yfinance as yf
from django.http import JsonResponse


CACHE = {}
CACHE_SECONDS = 600


COMPANY_ALIASES = {

    "RELIANCE": [
        "reliance industries",
        "reliance",
        "ril",
    ],

    "HDFCBANK": [
        "hdfc bank",
        "hdfcbank",
    ],

    "ICICIBANK": [
        "icici bank",
        "icicibank",
    ],

    "INFY": [
        "infosys",
        "infy",
    ],

    "TCS": [
        "tata consultancy services",
        "tcs",
    ],

    "SBIN": [
        "state bank of india",
        "sbi",
        "sbin",
    ],

    "ITC": [
        "itc limited",
        "itc",
    ],

    "LT": [
        "larsen & toubro",
        "larsen and toubro",
        "l&t",
        "lt",
    ],

    "BHARTIARTL": [
        "bharti airtel",
        "airtel",
        "bhartiartl",
    ],

    "AXISBANK": [
        "axis bank",
        "axisbank",
    ],

    "KOTAKBANK": [
        "kotak mahindra bank",
        "kotak bank",
        "kotakbank",
    ],

    "HINDUNILVR": [
        "hindustan unilever",
        "hul",
        "hindunilvr",
    ],

    "MARUTI": [
        "maruti suzuki",
        "maruti",
    ],

    "M&M": [
        "mahindra & mahindra",
        "mahindra",
        "m&m",
    ],

    "SUNPHARMA": [
        "sun pharma",
        "sun pharmaceutical",
    ],

    "TITAN": [
        "titan company",
        "titan",
    ],

    "ADANIENT": [
        "adani enterprises",
        "adani",
        "adanient",
    ],

    "NTPC": [
        "ntpc",
        "ntpc limited",
    ],

    "ONGC": [
        "ongc",
        "oil and natural gas corporation",
    ],

    "POWERGRID": [
        "power grid",
        "powergrid",
        "power grid corporation",
    ],

    "TATAMOTORS": [
        "tata motors",
        "tatamotors",
    ],

    "TATASTEEL": [
        "tata steel",
        "tatasteel",
    ],

    "WIPRO": [
        "wipro",
    ],

    "HCLTECH": [
        "hcl technologies",
        "hcl tech",
        "hcltech",
    ],

    "BAJFINANCE": [
        "bajaj finance",
        "bajajfinance",
    ],

    "BAJAJFINSV": [
        "bajaj finserv",
        "bajajfinsv",
    ],

    "ASIANPAINT": [
        "asian paints",
        "asianpaint",
    ],

    "ULTRACEMCO": [
        "ultratech cement",
        "ultracemco",
    ],

    "COALINDIA": [
        "coal india",
        "coalindia",
    ],

    "BEL": [
        "bharat electronics",
        "bel",
    ],

    "AAPL": [
        "apple inc",
        "apple",
        "aapl",
    ],

    "TSLA": [
        "tesla",
        "tsla",
    ],

    "MSFT": [
        "microsoft",
        "msft",
    ],

    "USDINR": [
        "usd/inr",
        "us dollar indian rupee",
        "usd inr",
    ],

    "BTC": [
        "bitcoin",
        "btc",
    ],

    "ETH": [
        "ethereum",
        "eth",
    ],

    "GOLD": [
        "gold",
        "gold price",
    ],

    "SILVER": [
        "silver",
        "silver price",
    ],

    "CRUDE": [
        "crude oil",
        "oil price",
        "wti",
    ],

    "NIFTY": [
        "nifty 50",
        "nifty",
    ],

    "BANKNIFTY": [
        "bank nifty",
        "nifty bank",
    ],

    "FINNIFTY": [
        "fin nifty",
        "nifty financial services",
    ],

    "SENSEX": [
        "sensex",
        "bse sensex",
    ],

    "US10Y": [
        "us 10 year treasury",
        "10 year treasury yield",
        "us10y",
    ],

    "US02Y": [
        "us 2 year treasury",
        "2 year treasury yield",
        "us02y",
    ],

    "IN10Y": [
        "india 10 year bond",
        "india 10 year yield",
        "in10y",
    ],
}


def normalize(text: str) -> str:

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(text).lower(),
    ).strip()


def relevant(
    symbol: str,
    title: str,
) -> bool:

    aliases = COMPANY_ALIASES.get(
        symbol.upper(),
        [symbol],
    )

    normalized_title = normalize(
        title
    )

    return any(
        normalize(alias) in normalized_title
        for alias in aliases
    )


def score_sentiment(
    title: str,
) -> int:

    text = normalize(title)

    positive = [
        "profit",
        "growth",
        "surge",
        "rally",
        "gain",
        "upgrade",
        "strong",
        "beats",
        "positive",
        "record",
        "buy",
        "bullish",
    ]

    negative = [
        "loss",
        "fall",
        "drop",
        "crash",
        "downgrade",
        "weak",
        "negative",
        "miss",
        "sell",
        "bearish",
        "decline",
    ]

    positive_score = sum(
        1 for word in positive
        if word in text
    )

    negative_score = sum(
        1 for word in negative
        if word in text
    )

    if positive_score > negative_score:
        return 1

    if negative_score > positive_score:
        return -1

    return 0


def google_news(
    symbol: str,
) -> list[dict]:

    aliases = COMPANY_ALIASES.get(
        symbol.upper(),
        [symbol],
    )

    query = (
        f'"{aliases[0]}" '
        f'finance markets'
    )

    url = (
        "https://news.google.com/rss/search"
        f"?q={quote(query)}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )

    response = requests.get(
        url,
        timeout=8,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "Trade_My_Dream/1.0"
        },
    )

    response.raise_for_status()

    root = ET.fromstring(
        response.content
    )

    articles = []

    for item in root.findall(
        "./channel/item"
    ):

        title = (
            item.findtext(
                "title"
            )
            or ""
        )

        link = (
            item.findtext(
                "link"
            )
            or "#"
        )

        pub_date = (
            item.findtext(
                "pubDate"
            )
            or ""
        )

        source_node = item.find(
            "source"
        )

        source = (
            source_node.text
            if source_node is not None
            else "Google News"
        )

        if not relevant(
            symbol,
            title,
        ):
            continue

        articles.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published": pub_date,
                "sentiment":
                    score_sentiment(
                        title
                    ),
            }
        )

        if len(articles) >= 5:
            break

    return articles


def yahoo_news(
    symbol: str,
) -> list[dict]:

    yf_map = {
        "RELIANCE": "RELIANCE.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "ICICIBANK": "ICICIBANK.NS",
        "INFY": "INFY.NS",
        "TCS": "TCS.NS",
        "SBIN": "SBIN.NS",
        "ITC": "ITC.NS",
        "BHARTIARTL": "BHARTIARTL.NS",
        "AXISBANK": "AXISBANK.NS",
        "POWERGRID": "POWERGRID.NS",
        "TATASTEEL": "TATASTEEL.NS",
        "BAJFINANCE": "BAJFINANCE.NS",
        "AAPL": "AAPL",
        "TSLA": "TSLA",
        "MSFT": "MSFT",
        "USDINR": "USDINR=X",
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "CRUDE": "CL=F",
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "FINNIFTY": "^CNXFIN",
        "SENSEX": "^BSESN",
        "US10Y": "^TNX",
        "US02Y": "^IRX",
        "IN10Y": "^IN10YT=RR",
    }

    ticker_symbol = yf_map.get(
        symbol.upper()
    )

    if not ticker_symbol:
        return []

    try:

        ticker = yf.Ticker(
            ticker_symbol
        )

        raw = ticker.news or []

        result = []

        for item in raw:

            title = item.get(
                "title",
                "",
            )

            if not relevant(
                symbol,
                title,
            ):
                continue

            result.append(
                {
                    "title": title,
                    "url": item.get(
                        "link",
                        "#",
                    ),
                    "source": item.get(
                        "publisher",
                        "Yahoo Finance",
                    ),
                    "published": "",
                    "sentiment":
                        score_sentiment(
                            title
                        ),
                }
            )

            if len(result) >= 5:
                break

        return result

    except Exception as exc:

        print(
            f"[NEWS] Yahoo failed "
            f"for {symbol}: {exc}"
        )

        return []


def market_news_api(
    request,
):

    symbol = (
        request.GET.get(
            "symbol",
            "RELIANCE",
        )
        .upper()
        .strip()
    )

    now = time.time()

    cached = CACHE.get(
        symbol
    )

    if cached:

        if (
            now -
            cached["timestamp"]
            < CACHE_SECONDS
        ):

            return JsonResponse(
                {
                    "symbol": symbol,
                    "news": cached["news"],
                    "cached": True,
                }
            )

    articles = []

    # Primary: targeted Google News RSS.
    try:

        articles = google_news(
            symbol
        )

    except Exception as exc:

        print(
            f"[NEWS] Google News failed "
            f"for {symbol}: {exc}"
        )

    # Secondary: targeted Yahoo.
    if not articles:

        articles = yahoo_news(
            symbol
        )

    # Never show unrelated market news.
    if not articles:

        articles = [
            {
                "title":
                    f"No targeted intelligence found for {symbol}.",
                "url": "#",
                "source":
                    "OMNI_QUANT",
                "published": "",
                "sentiment": 0,
            }
        ]

    CACHE[symbol] = {
        "timestamp": now,
        "news": articles,
    }

    return JsonResponse(
        {
            "symbol": symbol,
            "news": articles,
            "cached": False,
        }
    )