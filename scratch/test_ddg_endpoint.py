import requests
import json
import urllib.parse
import re

query = "python programming"

queries = ["Python lenguaje", "Lionel Messi", "Dolar en Argentina", "Inteligencia artificial"]

for q in queries:
    print(f"\n--- Probando: {q} ---")
    # 1. DDG API
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(q)}&format=json&no_html=1"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=4)
        data = r.json()
        abstract = data.get("AbstractText") or data.get("Abstract")
        heading = data.get("Heading", "")
        related = [t.get("Text") for t in data.get("RelatedTopics", []) if isinstance(t, dict) and t.get("Text")]
        print(f"  DDG Abstract: {abstract[:100] if abstract else 'Sin abstract'}")
        print(f"  DDG Relacionados: {len(related)}")
        if related:
            print(f"    Muestra: {related[0][:80]}")
    except Exception as e:
        print("  DDG Error:", e)

    # 2. Wikipedia API REST en español
    try:
        wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}&utf8=&format=json"
        rw = requests.get(wiki_url, headers={"User-Agent": "F3NIX_AI_Agent/1.0"}, timeout=4)
        w_data = rw.json()
        search_res = w_data.get("query", {}).get("search", [])
        print(f"  Wiki items: {len(search_res)}")
        if search_res:
            snippet = re.sub(r'<[^>]+>', '', search_res[0].get("snippet", ""))
            print(f"    Wiki muestra: [{search_res[0].get('title')}] {snippet[:100]}")
    except Exception as e:
        print("  Wiki Error:", e)

# Test 2: DDG Lite HTML
try:
    url = "https://lite.duckduckgo.com/lite/"
    data = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lite.duckduckgo.com/"
    }
    r = requests.post(url, data=data, headers=headers, timeout=5)
    print("Lite HTML Status:", r.status_code)
    snippets = re.findall(r'<td class="result-snippet">(.*?)</td>', r.text, re.DOTALL)
    print("Lite snippets count:", len(snippets))
    if snippets:
        print("Sample snippet:", re.sub(r'<[^>]+>', '', snippets[0]).strip()[:150])
except Exception as e:
    print("Lite Error:", e)

# Test 3: duckduckgo_search text method options
try:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        res = list(ddgs.text(query, max_results=3))
        print("DDGS count:", len(res))
        if res:
            print("DDGS sample:", res[0])
except Exception as e:
    print("DDGS Error:", e)
