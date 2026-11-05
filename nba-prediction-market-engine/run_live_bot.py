#!/usr/bin/env python3
"""
Strategy 3: Cross-Platform Arbitrage Bot (24/7 paper-execution daemon).
Polls Kalshi and Polymarket books, records detected vs filled arbs,
persists paper_portfolio.json / paper_trades.csv, and emails fill + 5xx alerts
via Gmail SMTP.
"""
import os
import sys
import csv
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests
from src.notifications.notifier import NotificationEngine, load_env_file
from src.metadata.ticker_resolver import MarketTickerResolver
from src.data_pipeline.cross_platform_arb import CrossPlatformArbDetector, ArbOpportunity
logger = logging.getLogger("LiveArbBot")
PORTFOLIO_PATH = "data/processed/paper_portfolio.json"
TRADES_PATH = "data/processed/paper_trades.csv"
TRADE_FIELDS = [
    "timestamp",
    "matchup",
    "route",
    "combined_cost",
    "net_edge_pct",
    "size",
    "profit",
    "status",
    "kalshi_balance",
    "poly_balance",
    "total_equity",
]
def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
class LiveArbBot:
    def __init__(
        self,
        starting_bankroll: float = 100.0,
        arb_threshold: float = 0.97,
        min_depth: int = 50,
        poll_interval: float = 5.0,
        fill_cooldown_sec: int = 900,
        health_every_n_cycles: int = 12,
    ):
        load_env_file()
        self.starting_bankroll = starting_bankroll
        self.arb_threshold = arb_threshold
        self.min_depth = min_depth
        self.poll_interval = poll_interval
        self.fill_cooldown_sec = fill_cooldown_sec
        self.health_every_n_cycles = health_every_n_cycles
        self.notifier = NotificationEngine()
        self.resolver = MarketTickerResolver()
        self.detector = CrossPlatformArbDetector(
            arb_threshold=arb_threshold,
            min_depth_contracts=min_depth,
        )
        self.session = requests.Session()
        self._recent_fills: Dict[str, float] = {}
        self._last_error_sent: Dict[str, float] = {}
        os.makedirs("data/processed", exist_ok=True)
    def _default_portfolio(self) -> Dict[str, Any]:
        half = round(self.starting_bankroll / 2.0, 2)
        return {
            "starting_bankroll": self.starting_bankroll,
            "current_bankroll": self.starting_bankroll,
            "daily_starting_bankroll": self.starting_bankroll,
            "kalshi_usd_balance": half,
            "poly_usdc_balance": half,
            "total_arbs_detected": 0,
            "successful_fills": 0,
            "rebalances_count": 0,
            "last_updated": utc_now_str(),
        }
    def load_portfolio(self) -> Dict[str, Any]:
        if os.path.exists(PORTFOLIO_PATH):
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("starting_bankroll", self.starting_bankroll)
                data.setdefault("daily_starting_bankroll", data.get("current_bankroll", self.starting_bankroll))
                return data
            except Exception as e:
                logger.warning(f"Could not read portfolio file: {e}")
        return self._default_portfolio()
    def save_portfolio(self, portfolio: Dict[str, Any]) -> None:
        portfolio["last_updated"] = utc_now_str()
        tmp_path = PORTFOLIO_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2)
        os.replace(tmp_path, PORTFOLIO_PATH)
    def append_trade(self, row: Dict[str, Any]) -> None:
        write_header = not os.path.exists(TRADES_PATH) or os.path.getsize(TRADES_PATH) == 0
        with open(TRADES_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_FIELDS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)
    def _alert_5xx(self, context: str, message: str) -> None:
        now = time.time()
        last = self._last_error_sent.get(context, 0.0)
        if now - last < 600:
            return
        self._last_error_sent[context] = now
        logger.error(f"{context}: {message}")
        self.notifier.send_error_alert(message, context=context)
    def check_api_health(self) -> None:
        endpoints = [
            ("Kalshi", "https://api.elections.kalshi.com/trade-api/v2/exchange/status"),
            ("Polymarket", "https://clob.polymarket.com/time"),
        ]
        for name, url in endpoints:
            try:
                resp = self.session.get(url, timeout=8)
                if resp.status_code >= 500:
                    self._alert_5xx(
                        f"{name} API 5xx",
                        f"{name} endpoint {url} returned HTTP {resp.status_code}: {resp.text[:300]}",
                    )
            except requests.RequestException as e:
                self._alert_5xx(
                    f"{name} API Disconnect",
                    f"{name} endpoint {url} disconnected: {e}",
                )
    def _fetch_with_status(self, url: str, params: Optional[dict] = None) -> Tuple[Optional[requests.Response], Optional[str]]:
        try:
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code >= 500:
                return resp, f"{url} returned HTTP {resp.status_code}"
            return resp, None
        except requests.RequestException as e:
            return None, f"{url} disconnected: {e}"
    def paper_fill(self, opp: ArbOpportunity, portfolio: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        route = f"{opp.venue_a}({opp.team_a}) + {opp.venue_b}({opp.team_b})"
        fill_key = f"{opp.matchup}|{route}"
        now = time.time()
        if now - self._recent_fills.get(fill_key, 0.0) < self.fill_cooldown_sec:
            return None
        kalshi_bal = float(portfolio.get("kalshi_usd_balance", 0.0))
        poly_bal = float(portfolio.get("poly_usdc_balance", 0.0))
        if opp.venue_a == "Kalshi":
            cost_k, cost_p = opp.ask_a, opp.ask_b
        else:
            cost_k, cost_p = opp.ask_b, opp.ask_a
        max_by_k = int(kalshi_bal // cost_k) if cost_k > 0 else 0
        max_by_p = int(poly_bal // cost_p) if cost_p > 0 else 0
        size = min(int(opp.max_contracts), max_by_k, max_by_p, 25)
        if size <= 0:
            logger.info(f"Skipping {opp.matchup}: insufficient split-venue capital.")
            return None
        spend_k = cost_k * size
        spend_p = cost_p * size
        profit = (1.0 - opp.combined_cost) * size
        kalshi_bal -= spend_k
        poly_bal -= spend_p
        # Locked arb settles at $1.00; credit payouts to the venue holding each winning ticket.
        kalshi_bal += 0.5 * size
        poly_bal += 0.5 * size
        portfolio["kalshi_usd_balance"] = round(kalshi_bal, 4)
        portfolio["poly_usdc_balance"] = round(poly_bal, 4)
        portfolio["current_bankroll"] = round(kalshi_bal + poly_bal, 4)
        portfolio["successful_fills"] = int(portfolio.get("successful_fills", 0)) + 1
        self._recent_fills[fill_key] = now
        trade = {
"timestamp": utc_now_str(),
            "matchup": opp.matchup,
            "route": route,
            "combined_cost": round(opp.combined_cost, 4),
            "net_edge_pct": round(opp.net_margin_pct, 4),
            "size": size,
            "profit": round(profit, 4),
            "status": "FILLED",
            "kalshi_balance": f"{kalshi_bal:.2f}",
            "poly_balance": f"{poly_bal:.2f}",
            "total_equity": round(portfolio["current_bankroll"], 4),
        }
        return trade
    def scan_once(self, mapped_pairs: List[Any], cycle: int, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        detected_this_cycle = 0
        for pair in mapped_pairs:
            matchup_title = f"{pair.team_a} vs {pair.team_b}"
            _, k_err = self._fetch_with_status(
                f"{self.detector.KALSHI_API}/markets/{pair.kalshi_ticker_a}"
            )
            if k_err:
                self._alert_5xx("Kalshi API Disconnect / 5xx Alert", k_err)
            _, p_err = self._fetch_with_status(
                f"{self.detector.POLY_CLOB_API}/book",
                params={"token_id": pair.poly_token_a} if pair.poly_token_a else None,
            )
            if p_err:
                self._alert_5xx("Polymarket API Disconnect / 5xx Alert", p_err)
            k_ask_a, k_size_a = self.detector.fetch_kalshi_top_ask(pair.kalshi_ticker_a)
            k_ask_b, k_size_b = self.detector.fetch_kalshi_top_ask(pair.kalshi_ticker_b)
            p_ask_a, p_size_a = self.detector.fetch_polymarket_top_ask(pair.poly_token_a)
            p_ask_b, p_size_b = self.detector.fetch_polymarket_top_ask(pair.poly_token_b)
            opps = self.detector.evaluate_order_books(
                matchup=matchup_title,
                team_a=pair.team_a,
                team_b=pair.team_b,
                kalshi_ask_a=k_ask_a,
                kalshi_size_a=k_size_a,
                kalshi_ask_b=k_ask_b,
                kalshi_size_b=k_size_b,
                poly_ask_a=p_ask_a,
                poly_size_a=p_size_a,
                poly_ask_b=p_ask_b,
                poly_size_b=p_size_b,
                only_opportunities=True,
            )
            for opp in opps:
                if not opp.is_alert:
                    continue
                detected_this_cycle += 1
                portfolio["total_arbs_detected"] = int(portfolio.get("total_arbs_detected", 0)) + 1
                logger.info(
                    f"ARB DETECTED: {opp.matchup} | Cost: ${opp.combined_cost:.2f} | "
                    f"Net Edge: {opp.net_margin_pct:+.2f}%"
                )
                trade = self.paper_fill(opp, portfolio)
                if trade:
                    self.append_trade(trade)
                    self.notifier.send_arb_fill_alert(trade)
                    logger.info(
                        f"ARB FILLED: {trade['matchup']} | Cost: ${trade['combined_cost']:.2f} | "
                        f"Net Edge: {trade['net_edge_pct']:+.2f}% | Est. Profit: +${trade['profit']:.2f}"
                    )
        if cycle % self.health_every_n_cycles == 0:
            self.check_api_health()
        self.save_portfolio(portfolio)
        return portfolio
    def run(self) -> None:
        logger.info("Initializing Cross-Platform Arbitrage Bot (Strategy 3)...")
        mapped_pairs = self.resolver.resolve_mapped_pairs()
        logger.info(f"Mapped {len(mapped_pairs)} NBA pairs. SMTP configured: {self.notifier.is_configured}")
        portfolio = self.load_portfolio()
        cycle = 1
        while True:
            try:
                portfolio = self.scan_once(mapped_pairs, cycle, portfolio)
                cycle += 1
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("Bot halted by user.")
                self.save_portfolio(portfolio)
                break
            except Exception as e:
                self._alert_5xx("Bot Runtime Exception", str(e))
                logger.exception("Unhandled error in scan loop")
                time.sleep(max(self.poll_interval, 10))
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="24/7 Cross-Platform Arbitrage Bot")
    parser.add_argument("--threshold", type=float, default=0.97)
    parser.add_argument("--depth", type=int, default=50)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--bankroll", type=float, default=100.0)
    args = parser.parse_args()
    bot = LiveArbBot(
        starting_bankroll=args.bankroll,
        arb_threshold=args.threshold,
        min_depth=args.depth,
        poll_interval=args.interval,
    )
    bot.run()
if __name__ == "__main__":
    main()
