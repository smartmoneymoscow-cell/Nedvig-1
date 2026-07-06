"""Proxy manager — rotation, Tor fallback, health checks."""

import random
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("realty")

# Tor SOCKS5 proxy (local Tor daemon)
TOR_PROXY = "socks5://127.0.0.1:9050"


class ProxyManager:
    """
    Manages proxy rotation for scrapers.
    
    Priority:
    1. Residential proxies (if configured)
    2. Tor SOCKS5 (free fallback, slower, some sites block)
    """

    def __init__(self, proxies: Optional[list[str]] = None, use_tor: bool = True):
        self.proxies = proxies or []
        self.use_tor = use_tor
        self._blocked: dict[str, datetime] = {}
        self._index = 0

    def get(self, source: str = "") -> Optional[str]:
        """Get next available proxy. Returns None for direct connection."""
        now = datetime.utcnow()

        # Try residential proxies first
        available = [
            p for p in self.proxies
            if p not in self._blocked or self._blocked[p] < now
        ]

        if available:
            proxy = available[self._index % len(available)]
            self._index += 1
            return proxy

        # Fallback to Tor (if enabled and not blocked for this source)
        if self.use_tor and not self._is_tor_blocked(source):
            return TOR_PROXY

        # No proxy — direct connection (will likely fail for CIAN/Avito)
        return None

    def mark_blocked(self, proxy: str, cooldown_minutes: int = 30):
        """Mark proxy as blocked for a cooldown period."""
        self._blocked[proxy] = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
        log.warning(f"[proxy] Blocked for {cooldown_minutes}min: {proxy[:40]}...")

    def mark_tor_blocked(self, source: str):
        """Mark Tor as blocked for a specific source."""
        key = f"tor:{source}"
        self._blocked[key] = datetime.utcnow() + timedelta(hours=1)
        log.warning(f"[proxy] Tor blocked for {source}")

    def _is_tor_blocked(self, source: str) -> bool:
        key = f"tor:{source}"
        if key in self._blocked:
            if datetime.utcnow() < self._blocked[key]:
                return True
            del self._blocked[key]
        return False

    @property
    def has_proxies(self) -> bool:
        return len(self.proxies) > 0

    @property
    def has_tor(self) -> bool:
        return self.use_tor

    def status(self) -> dict:
        """Get proxy pool status."""
        now = datetime.utcnow()
        active_proxies = [
            p for p in self.proxies
            if p not in self._blocked or self._blocked[p] < now
        ]
        return {
            "residential_proxies": len(self.proxies),
            "active_residential": len(active_proxies),
            "tor_enabled": self.use_tor,
            "blocked_until": {
                k: v.isoformat() for k, v in self._blocked.items()
                if v > now
            },
        }
