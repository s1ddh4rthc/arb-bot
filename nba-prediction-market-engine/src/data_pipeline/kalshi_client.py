"""
Kalshi Exchange REST API Client.
Fetches historical market tickers, chunked 1-minute candlestick data, and trade logs for NBA games.
"""

from typing import List, Dict, Optional, Generator
import time
import requests
import pandas as pd


class KalshiDataIngestion:
    """Ingestion pipeline for Kalshi binary event markets."""

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def get_nba_markets(self, series_ticker: str = "KXNBAGAME", status: str = "settled", limit: int = 100) -> List[Dict]:
        """
        Discovers NBA game market contracts on Kalshi.
        """
        url = f"{self.BASE_URL}/markets"
        params = {"series_ticker": series_ticker, "status": status, "limit": limit}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("markets", [])
            else:
                print(f"[Warning] Kalshi API returned HTTP {resp.status_code}: {resp.text[:200]}")
                return []
        except Exception as e:
            print(f"[Error] Failed to connect to Kalshi: {e}")
            return []

    def fetch_candlesticks_chunked(
        self,
        ticker: str,
        start_ts: int,
        end_ts: int,
        series_ticker: str = "KXNBAGAME",
        interval_minutes: int = 1
    ) -> pd.DataFrame:
        """
        Fetches minute-by-minute candlesticks for a specific market ticker.
        Handles Kalshi's 5,000 candle query cap via time-window pagination.
        """
        all_candles = []
        chunk_window = 5000 * interval_minutes * 60  # seconds
        current_start = start_ts

        while current_start < end_ts:
            current_end = min(current_start + chunk_window, end_ts)
            url = f"{self.BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks"
            params = {
                "start_ts": current_start,
                "end_ts": current_end,
                "period_interval": interval_minutes
            }

            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    candles = resp.json().get("candlesticks", [])
                    if candles:
                        all_candles.extend(candles)
                else:
                    break
            except Exception as e:
                print(f"Error fetching candles for {ticker}: {e}")
                break

            current_start = current_end + 1
            time.sleep(0.1)  # Respect rate limits

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles)
        # Kalshi prices are in cents (1-99), normalize to 0.00-1.00
        if 'price' in df.columns:
            df['team_a_price'] = df['price'] / 100.0
        elif 'close' in df.columns:
            df['team_a_price'] = df['close'] / 100.0
        else:
            return pd.DataFrame()

        df['team_b_price'] = (1.00 - df['team_a_price']).clip(0.0, 1.0)
        df['game_id'] = ticker
        if 'end_period_ts' in df.columns:
            df['timestamp'] = pd.to_datetime(df['end_period_ts'], unit='s')
        else:
            df['timestamp'] = pd.date_range(start="2026-01-01", periods=len(df), freq="min")

        return df[['game_id', 'timestamp', 'team_a_price', 'team_b_price']]
