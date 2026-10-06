import ipaddress
import socket
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

app = FastAPI(title="Site Crawler")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class AnalyzeRequest(BaseModel):
    url: str


def get_client() -> AsyncOpenAI:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(500, "GROQ_API_KEY is not set. Add it to your .env file.")
    return AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)


def normalize_url(raw: str) -> str:
    raw = raw.strip()

    if not raw:
        raise HTTPException(400, "Enter a website address.")

    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(400, "Enter a valid http or https address.")

    # Block private/local targets
    try:
        for info in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(info[4][0])

            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(
                    400,
                    "That address points to a private network."
                )

    except socket.gaierror:
        raise HTTPException(
            400,
            "Could not find that website. Check the address."
        )

    return raw


PROMPT = """You are a business research AI. Analyze this scraped website markdown.
Respond with ONLY a JSON object in exactly this shape:
{{
  "headlines": ["main headlines on the page"],
  "services": ["key business services or offerings"],
  "contacts": {{
    "emails": [], "phones": [], "calls_to_action": []
  }},
  "design_assessment": {{
    "verdict": "outdated" | "needs work" | "modern",
    "summary": "2-3 sentences on whether the design and copy look outdated",
    "issues": ["specific problems or improvements"]
  }}
}}
Use empty lists when nothing is found. Do not invent contact details.

WEBSITE CONTENT:
{content}
"""


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    url = normalize_url(req.url)
    client = get_client()

    # Step 1: crawl and render the page locally with Crawl4AI
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    if not result.success:
        raise HTTPException(502, f"Crawling failed: {result.error_message}")
    markdown = str(result.markdown)[:12000]
    if not markdown.strip():
        raise HTTPException(422, "The page had no readable content.")

    # Step 2: extract structured data with Groq
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT.format(content=markdown)}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise HTTPException(502, f"AI analysis failed: {exc}")

    text = response.choices[0].message.content or ""
    try:
        analysis = json.loads(text)
    except json.JSONDecodeError:
        analysis = {"raw": text}

    report = {
        "url": url,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis": analysis,
    }
    host = urlparse(url).hostname.replace(".", "_")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (REPORTS_DIR / f"{host}-{stamp}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
