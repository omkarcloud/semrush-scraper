# 📈 Semrush Scraper

Semrush Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Semrush data for free.

## ✨ What Can I Get?

- 🌐 **Traffic, rank & Authority Score for 200K+ websites** — visits, bounce rate, top countries, traffic sources & competitors
- 🔑 **Volume, difficulty & CPC for any keyword** — intent, the live top-10 SERP & 25 keyword ideas per seed
- 🤖 **AI traffic from ChatGPT, Gemini & Claude** — AI visits, citations, AI visibility score & AI Overviews
- 🏆 **Top 100 websites in 240 countries × 111 categories** — plus backlinks, SEO audits & the most-searched names

## 🎥 Example: A Full Semrush Domain Overview

```json
{
  "domain": "openai.com",
  "link": "https://www.semrush.com/website/openai.com/overview/",
  "rank": {
    "global": { "value": 57, "change": 1 },
    "country": { "value": 114, "change": -1, "country": "US", "name": "United States" }
  },
  "authority_score": 96,
  "visits": 565585964,
  "traffic": {
    "pages_per_visit": { "value": 1.93, "change_percent": null },
    "average_visit_duration_seconds": { "value": 384, "change_percent": null },
    "bounce_rate_percent": { "value": 70.42, "change_percent": null }
  },
  "traffic_by_country": { "countries": [{ "country": "US", "name": "United States", "visits": 75070370, "share_percent": 13.27 }] },
  "traffic_sources": { "incoming": [{ "source": "chatgpt.com", "channel": "referral", "share_percent": 29.1, "visits": 94599695 }] },
  "ai_traffic": { "platforms": [{ "domain": "chatgpt.com", "name": "ChatGPT", "visits": 138690978, "share_percent": 24.68 }] },
  "top_keywords": { "keywords": [{ "keyword": "chatgpt", "position": 3, "search_volume": 68000000, "cpc": 0.08, "currency": "USD", "intents": ["navigational"] }] },
  "backlinks": {
    "backlinks": { "value": 68590939, "change_percent": 1.62 },
    "referring_domains": { "value": 463522, "change_percent": 5.03 },
    "google_penalty_risk": "low"
  },
  "competitors": { "competitors": [{ "domain": "chatgpt.com", "relevance_percent": 46.0, "visits": 6579641823 }] }
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Semrush Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/semrush-scraper
cd semrush-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/domains/overview?domain=openai.com"
```

```json
{
  "domain": "openai.com",
  "link": "https://www.semrush.com/website/openai.com/overview/",
  "country": "US",
  "rank": {
    "global": { "value": 57, "change": 1 },
    "country": { "value": 114, "change": -1, "country": "US", "name": "United States" }
  },
  "authority_score": 96,
  "visits": 565585964,
  "traffic": {
    "visits": { "value": 565585964, "change_percent": 4.22 },
    "bounce_rate_percent": { "value": 70.42, "change_percent": null }
  },
  "backlinks": {
    "backlinks": { "value": 68590939, "change_percent": 1.62 },
    "referring_domains": { "value": 463522, "change_percent": 5.03 },
    "google_penalty_risk": "low"
  }
}
```

All 28 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

28 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Domain Overview | `/domains/overview` | Everything Semrush knows about a website in one call |
| Keyword Overview | `/keywords/overview` | Volume, difficulty, CPC, intent, live SERP and related keywords |
| Autocomplete | `/keywords/autocomplete` | Semrush search-bar suggestions for keywords or domains |
| Keyword Volume | `/keywords/volume` | Monthly search volume, difficulty, CPC and volume by country |
| Keyword Ideas | `/keywords/ideas` | Keyword Magic ideas with volume, difficulty and CPC |
| Keyword SERP | `/keywords/serp` | Google's top results by SERP feature, plus 30-day volatility |
| Keyword Rank | `/keywords/rank` | Where a domain ranks for a keyword, and its top keywords |
| Domain Rank | `/domains/rank` | Global, country and category rank, Authority Score, visits |
| Domain Traffic | `/domains/traffic` | Visits, engagement and 6 months of desktop vs mobile |
| Traffic by Country | `/domains/traffic-by-country` | Top countries with visit share and device split |
| Traffic Sources | `/domains/traffic-sources` | Where visitors come from and where they go next |
| Search Traffic | `/domains/search-traffic` | Organic vs paid search traffic with 6-month history |
| Domain Top Keywords | `/domains/top-keywords` | Organic keywords driving the most traffic |
| AI Traffic | `/domains/ai-traffic` | Visits from ChatGPT, Gemini, Claude and Perplexity |
| AI Traffic Report | `/domains/ai-traffic-report` | AI share, citations, AI Overviews and top AI-visited pages |
| AI Visibility | `/domains/ai-visibility` | AI visibility score, mentions, citations and best topics |
| Backlinks Overview | `/domains/backlinks-overview` | Backlinks, referring domains and penalty risk with history |
| Top Backlinks | `/domains/backlinks` | Top backlinks with anchor, page score and follow status |
| Authority Score | `/domains/authority` | Authority Score, 12-month history and score breakdown |
| Domain Competitors | `/domains/competitors` | Closest competitors with ranks, traffic and market share |
| Organic Competitors | `/domains/competitor-finder` | Search competitors with common keywords and organic traffic |
| Related Domains | `/domains/related` | Headline stats plus the domains Semrush links to it |
| Bulk Domain Rank | `/domains/batch` | Ranks, Authority Score and visits for 10 domains at once |
| SEO Audit | `/pages/seo-audit` | Page SEO scores, issues and every on-page and technical check |
| Top Websites | `/top-websites` | The 100 most visited sites per country and category |
| Top Website Categories / Countries | `/top-websites/categories`, `/top-websites/countries` | Every filter value Top Websites accepts |
| Popular Keywords | `/popular` | The most-searched people, books, foods and brands worldwide |

The keyword, backlink, authority, AI report and SEO audit endpoints are limited by Semrush to a few calls per IP per day. For more, set `SEMRUSH_PROXY` to a rotating residential proxy.

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-semrush-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-semrush-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-semrush-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/domains/overview",
    params={"domain": "openai.com"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Semrush Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Semrush%20Scraper%20API.)

[![Ask Us by Email about Semrush Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Semrush%20Scraper%20API&body=I%20need%20help%20using%20the%20Semrush%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/semrush-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/semrush-scraper)
