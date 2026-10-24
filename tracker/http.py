"""HTTP helper that records per-source health (status codes, retries, failures).

Every collector reports through a SourceLog so each run leaves a record of
whether the source actually worked — the core question of this PoC.
"""
import time
import urllib.error
import urllib.request

UA = "ai-science-tracker/0.1 (+https://github.com/flytothejy/ai-science-tracker)"


class SourceLog:
    def __init__(self, name):
        self.name = name
        self.requests = 0
        self.status_counts = {}
        self.retries = 0
        self.failures = []
        self.items_seen = 0
        self.candidates = 0
        self.notes = []

    def record(self, status):
        self.status_counts[str(status)] = self.status_counts.get(str(status), 0) + 1

    def ok(self):
        return self.requests > 0 and not self.failures

    def to_dict(self):
        return {
            "source": self.name,
            "ok": self.ok(),
            "requests": self.requests,
            "status_counts": self.status_counts,
            "retries": self.retries,
            "failures": self.failures[:10],
            "items_seen": self.items_seen,
            "candidates": self.candidates,
            "notes": self.notes,
        }


def fetch(url, log, *, retries=4, backoff=5.0, timeout=60, headers=None):
    """GET url, retrying on 429/5xx with backoff. Returns bytes or None."""
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries + 1):
        log.requests += 1
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                log.record(resp.status)
                return resp.read()
        except urllib.error.HTTPError as e:
            log.record(e.code)
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = backoff * (attempt + 1)
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra and ra.isdigit():
                    wait = max(wait, int(ra))
                log.retries += 1
                time.sleep(min(wait, 120))
                continue
            log.failures.append(f"HTTP {e.code} {url[:160]}")
            return None
        except Exception as e:  # network errors, timeouts
            log.record("error")
            if attempt < retries:
                log.retries += 1
                time.sleep(backoff * (attempt + 1))
                continue
            log.failures.append(f"{type(e).__name__}: {e} {url[:160]}")
            return None
    return None
