"""
Polymarket Gamma and CLOB API Client.
Pulls historical 1-minute price history, market discovery, and order book tokens for NBA matchups.
"""

from typing import List, Dict, Optional
import requests
import pandas as pd


class PolymarketDataIngestion:
    """Ingestion pipeline for Polymarket NBA CLOB and Gamma APIs."""

    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

    def __init__(self):
        self.session = requests.Session()

    def discover_nba_markets(self, limit: int = 50, closed: bool = True) -> List[Dict]:
        """
        Discovers NBA games on Polymarket via Gamma API.
        """
        url = f"{self.GAMMA_URL}/events"
        params = {
            "tag": "nba",
            "closed": str(closed).lower(),
            "limit": limit
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                events = resp.json()
                return events
            return []
        except Exception as e:
            print(f"[Error] Failed to fetch Polymarket events: {e}")
            return []

    def fetch_clob_prices_history(
        self,
        token_id: str,
        interval: str = "1m",
        fidelity: int = 60
    ) -> pd.DataFrame:
        """
        Pulls historical prices from Polymarket CLOB price history endpoint.
        """
        url = f"{self.CLOB_URL}/prices-history"
        params = {
            "market": token_id,
            "interval": interval,
            "fidelity": fidelity
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("history", [])
                if not data:
                    return pd.DataFrame()
                df = pd.DataFrame(data)
                df['team_a_price'] = df['p'].astype(float)
                df['team_b_price'] = (1.00 - df['team_a_price']).clip(0.0, 1.0)
                df['timestamp'] = pd.to_datetime(df['t'], unit='s')
                df['game_id'] = token_id
                return df[['game_id', 'timestamp', 'team_a_price', 'team_b_price']]
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching Polymarket price history: {e}")
            return pd.DataFrame()
