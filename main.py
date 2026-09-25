"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json.
"""
import json
import os

from semrush import discover, domains, keywords

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a domain or any link to the site: ranks, traffic, sources, AI traffic, keywords, backlinks, competitors
    save("domain_openai.com.json", domains.overview("openai.com"))

    # the ~100 most visited websites in the US
    save("top_websites_us.json", discover.top_websites("us", "all"))

    # volume, difficulty, CPC, intent, the live SERP and related keywords (opens a browser for the captcha)
    save("keyword_email_marketing.json", keywords.overview("email marketing", "US"))
