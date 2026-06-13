import os
import re
import html
import requests
import feedparser
import yfinance as yf
from datetime import datetime, timezone

CRITICAL_WEBHOOK = os.getenv("DISCORD_CRITICAL_WEBHOOK")
BRIEF_WEBHOOK = os.getenv("DISCORD_BRIEF_WEBHOOK")
MACRO_WEBHOOK = os.getenv("DISCORD_MACRO_WEBHOOK")
AI_SEMIS_WEBHOOK = os.getenv("DISCORD_AI_SEMIS_WEBHOOK")
EARNINGS_WEBHOOK = os.getenv("DISCORD_EARNINGS_WEBHOOK")
NEWS_WEBHOOK = os.getenv("DISCORD_NEWS_WEBHOOK")
TRUMP_WEBHOOK = os.getenv("DISCORD_TRUMP_WEBHOOK")
MARKET_DATA_WEBHOOK = os.getenv("DISCORD_MARKET_DATA_WEBHOOK")

FEEDS = {
    "CNBC Markets": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC Tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "Nasdaq Markets": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Investing.com News": "https://www.investing.com/rss/news.rss",
    "S&P Global": "https://www.spglobal.com/spdji/en/rss/",
}

TRUMP_FEED = "https://trumpstruth.org/feed"

MARKET_SYMBOLS = {
    "NQ Futures": "NQ=F",
    "QQQ": "QQQ",
    "VIX": "^VIX",
    "US 10Y Yield": "^TNX",
    "DXY": "DX-Y.NYB",
    "NVDA": "NVDA",
    "AMD": "AMD",
    "MSFT": "MSFT",
    "AAPL": "AAPL",
    "META": "META",
}

CRITICAL_KEYWORDS = [
    "cpi", "ppi", "nfp", "nonfarm", "payrolls", "fomc", "powell",
    "fed", "federal reserve", "rate decision", "inflation",
    "treasury yield", "10-year", "2-year", "bond yield",
    "vix", "volatility", "selloff", "crash",
    "war", "attack", "missile", "iran", "israel", "russia",
    "china", "taiwan"
]

MACRO_KEYWORDS = [
    "fed", "federal reserve", "powell", "rates", "rate cut",
    "rate hike", "inflation", "cpi", "ppi", "nfp",
    "jobs report", "treasury", "yield", "10-year", "2-year",
    "bond", "dollar", "dxy"
]

AI_SEMIS_KEYWORDS = [
    "ai", "artificial intelligence", "chip", "semiconductor",
    "nvidia", "nvda", "amd", "broadcom", "avgo", "tsmc",
    "asml", "arm", "micron", "mu", "super micro", "smci",
    "datacenter", "data center", "openai", "anthropic",
    "gemini", "microsoft ai", "google ai", "meta ai"
]

EARNINGS_KEYWORDS = [
    "earnings", "guidance", "revenue", "profit", "eps",
    "quarterly results", "reports results", "beats estimates",
    "misses estimates"
]

GENERAL_KEYWORDS = list(set(
    CRITICAL_KEYWORDS + MACRO_KEYWORDS + AI_SEMIS_KEYWORDS +
    EARNINGS_KEYWORDS + [
        "nasdaq", "qqq", "futures", "wall street",
        "stocks", "technology", "market", "treasury"
    ]
))


def clean_text(text):
    text = html.unescape(text or "")
    text = re.sub("<.*?>", "", text)
    return text.strip()


def send_discord(webhook, title, body):
    if not webhook:
        print(f"Missing webhook for {title}")
        return

    body = body.strip() or "No relevant updates detected."
    payload = {"content": f"**{title}**\n{body[:1900]}"}

    response = requests.post(webhook, json=payload, timeout=10)
    response.raise_for_status()


def matches(text, keywords):
    text = text.lower()
    return any(k.lower() in text for k in keywords)


def collect_news():
    items = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:8]:
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))
                link = entry.get("link", "")
                combined = f"{title} {summary}"

                if matches(combined, GENERAL_KEYWORDS):
                    items.append({
                        "source": source,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "critical": matches(combined, CRITICAL_KEYWORDS),
                        "macro": matches(combined, MACRO_KEYWORDS),
                        "ai_semis": matches(combined, AI_SEMIS_KEYWORDS),
                        "earnings": matches(combined, EARNINGS_KEYWORDS),
                    })

        except Exception as e:
            print(f"Feed error: {source}: {e}")

    return items


def format_news(items, limit=8):
    if not items:
        return "No relevant headlines detected."

    seen = set()
    lines = []

    for item in items:
        key = item["title"].lower()
        if key in seen:
            continue

        seen.add(key)
        lines.append(f"- [{item['source']}] {item['title']}\n{item['link']}")

        if len(lines) >= limit:
            break

    return "\n\n".join(lines)


def get_market_snapshot():
    rows = []

    for name, symbol in MARKET_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1d", timeout=10)

            if hist.empty:
                continue

            last_close = hist["Close"].iloc[-1]

            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                change_pct = ((last_close - prev_close) / prev_close) * 100
            else:
                change_pct = 0

            rows.append({
                "name": name,
                "price": float(last_close),
                "change_pct": float(change_pct),
            })

        except Exception as e:
            print(f"Market data error: {name}: {e}")

    return rows


def format_market_snapshot(rows):
    if not rows:
        return "Market data unavailable."

    lines = []

    for row in rows:
        name = row["name"]
        price = row["price"]
        change = row["change_pct"]

        if "Yield" in name:
            display_price = f"{price / 10:.2f}%"
        else:
            display_price = f"{price:.2f}"

        emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        lines.append(f"{emoji} **{name}**: {display_price} ({change:+.2f}%)")

    return "\n".join(lines)


def run_market_data():
    rows = get_market_snapshot()
    send_discord(
        MARKET_DATA_WEBHOOK or MACRO_WEBHOOK,
        "📊 Market Data Snapshot",
        format_market_snapshot(rows)
    )


def run_brief():
    news = collect_news()
    rows = get_market_snapshot()

    critical = [n for n in news if n["critical"]]
    macro = [n for n in news if n["macro"]]
    ai_semis = [n for n in news if n["ai_semis"]]
    earnings = [n for n in news if n["earnings"]]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body = f"""
📌 **NQ Preparation Brief**
Time: {now}

This is context, not a trade signal.

**1. Market Data**
{format_market_snapshot(rows)}

**2. Critical Market Risks**
{format_news(critical, 5)}

**3. Macro / Rates / Fed**
{format_news(macro, 5)}

**4. AI / Semiconductor Drivers**
{format_news(ai_semis, 5)}

**5. Earnings / Guidance**
{format_news(earnings, 5)}

**Trading checklist**
- Check VIX.
- Check US10Y.
- Check economic calendar.
- Check Mag 7 premarket direction.
- Check semiconductors.
- If tier-1 macro is close to your execution window, treat it as a no-trade risk.
"""

    send_discord(BRIEF_WEBHOOK, "🟦 NQ Main Brief", body)


def run_critical():
    news = collect_news()
    critical = [n for n in news if n["critical"]]

    if critical:
        send_discord(
            CRITICAL_WEBHOOK,
            "🔴 Critical Market Alert",
            format_news(critical, 6)
        )


def run_macro():
    news = collect_news()
    macro = [n for n in news if n["macro"]]
    rows = get_market_snapshot()

    body = f"""
**Market Data**
{format_market_snapshot(rows)}

**Macro Headlines**
{format_news(macro, 8)}
"""

    send_discord(MACRO_WEBHOOK, "🟡 Macro / Rates Update", body)


def run_ai_semis():
    news = collect_news()
    ai_semis = [n for n in news if n["ai_semis"]]

    send_discord(
        AI_SEMIS_WEBHOOK,
        "🟣 AI / Semiconductor Update",
        format_news(ai_semis, 8)
    )


def run_earnings():
    news = collect_news()
    earnings = [n for n in news if n["earnings"]]

    send_discord(
        EARNINGS_WEBHOOK,
        "🟢 Earnings / Guidance Update",
        format_news(earnings, 8)
    )


def run_general():
    news = collect_news()
    send_discord(
        NEWS_WEBHOOK,
        "📰 General Market News",
        format_news(news, 10)
    )


def run_trump():
    try:
        feed = feedparser.parse(TRUMP_FEED)

        if not feed.entries:
            return

        lines = []

        for entry in feed.entries[:5]:
            title = clean_text(entry.get("title", "Trump post"))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")

            lines.append(f"- {title}\n{summary[:300]}\n{link}")

        send_discord(
            TRUMP_WEBHOOK,
            "🇺🇸 Trump Social Posts",
            "\n\n".join(lines)
        )

    except Exception as e:
        print(f"Trump feed error: {e}")


if __name__ == "__main__":
    mode = os.getenv("MODE", "general")

    if mode == "brief":
        run_brief()
    elif mode == "critical":
        run_critical()
    elif mode == "macro":
        run_macro()
    elif mode == "ai_semis":
        run_ai_semis()
    elif mode == "earnings":
        run_earnings()
    elif mode == "market":
        run_market_data()
    elif mode == "trump":
        run_trump()
    else:
        run_general()
