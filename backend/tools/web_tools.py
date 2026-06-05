import httpx
from bs4 import BeautifulSoup
from tavily import TavilyClient
from config import TAVILY_API_KEY

_tavily = TavilyClient(api_key=TAVILY_API_KEY)

# Tool schemas for the Anthropic API
TOOLS = [
    {
        "name": "search_web",
        "description": (
            "Search the web for up-to-date information on any topic. "
            "Returns titles, URLs, and content summaries from top results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page",
        "description": (
            "Fetch the full readable text content of a specific webpage URL. "
            "Use when you need more detail than the search snippet provides."
            # Playwright could replace httpx here for JavaScript-heavy pages.
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"],
        },
    },
]


def search_web(query: str) -> str:
    results = _tavily.search(query=query, max_results=5)
    items = []
    for r in results.get("results", []):
        items.append(f"**{r['title']}**\nURL: {r['url']}\n{r['content']}")
    return "\n\n---\n\n".join(items) if items else "No results found."


def fetch_page(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Axolotl/1.0)"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:5000]
    except Exception as exc:
        return f"Error fetching page: {exc}"


def dispatch(name: str, inputs: dict) -> str:
    if name == "search_web":
        return search_web(**inputs)
    if name == "fetch_page":
        return fetch_page(**inputs)
    return f"Unknown tool: {name}"
