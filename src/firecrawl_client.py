"""Cliente Firecrawl (search + scrape) com timeout e retry."""
import time

import requests

import config


class FirecrawlClient:
    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (base_url or config.FIRECRAWL_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.FIRECRAWL_API_KEY
        self.timeout = timeout or config.REQUEST_TIMEOUT

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, path, payload, retries=2):
        url = f"{self.base_url}{path}"
        last = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001
                last = e
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Firecrawl {path} falhou: {last}")

    def search(self, query, limit=10):
        data = self._post("/v1/search", {"query": query, "limit": limit})
        return data.get("data", []) or []

    def scrape(self, url, formats=None):
        formats = formats or ["rawHtml", "markdown"]
        data = self._post("/v1/scrape", {"url": url, "formats": formats})
        return data.get("data", {}) or {}

    def ping(self):
        """Teste rapido de conectividade."""
        try:
            self.search("teste", limit=1)
            return True, "ok"
        except Exception as e:  # noqa: BLE001
            return False, str(e)
