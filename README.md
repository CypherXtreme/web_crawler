# Site Crawler

Enter a website address. Crawl4AI renders the page, Groq extracts the services, contact details and a design verdict, and the result appears in the browser.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
crawl4ai-setup                                       # one-time browser install
cp .env.example .env                                 # then add your GROQ_API_KEY
uvicorn app:app --reload
```

Open http://localhost:8000. Each analysis is also saved to `reports/` as JSON.

Never commit your `.env` file or put API keys in source code.

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, create a new Blueprint/Web Service from the repository.
3. If using the included `render.yaml`, Render will use `crawl4ai-setup` during the build and Uvicorn for the web server.
4. Add `GROQ_API_KEY` in the Render Environment settings. Never commit `.env` or the API key.
5. After deployment, test `/health`, `/docs`, and the homepage.

The `reports/` directory is suitable for local development, but files written to a typical hosted service filesystem may not persist across redeploys/restarts. For permanent report storage, use object storage or a database later.
