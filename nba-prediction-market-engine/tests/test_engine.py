"""
Unit tests for NBA Prediction Market Trading & Backtesting Engine.
"""

import unittest
import pandas as pd
import numpy as np
from config.default_config import FilterConfig, ExecutionConfig, StrategyConfig
from src.metadata.team_metrics import TeamMetricsRegistry
from src.metadata.game_filter import GameFilterPipeline
from src.engine.backtest_engine import BulkPMEngine
from src.engine.models import TradeStatus


class TestPredictionMarketEngine(unittest.TestCase):

    def setUp(self):
        self.registry = TeamMetricsRegistry()
        self.pipeline = GameFilterPipeline(config=FilterConfig(), registry=self.registry)
        self.engine = BulkPMEngine(
            execution_config=ExecutionConfig(initial_capital=10000.0, risk_per_trade=0.02, fee_rate=0.015, slippage=0.01),
            strategy_config=StrategyConfig(target_a=0.40, target_b=0.40, stop_loss_pct=0.20)
        )

    def test_team_metrics_registry(self):
        self.assertIn("IND", self.registry.list_teams())
        self.assertIn("BOS", self.registry.list_teams())

        matchup = self.registry.compute_matchup_metrics("IND", "SAC")
        self.assertIsNotNone(matchup)
        # IND (103.5) + SAC (100.1) = 203.6 combined pace
        self.assertGreater(matchup.combined_pace, 200.0)
        # Net rating diff |2.9 - 1.8| = 1.1
        self.assertLess(matchup.net_rating_diff, 2.0)
        # Volatility score should be high for two fast, evenly matched teams
        self.assertGreater(matchup.volatility_score, 60.0)

    def test_game_filter_pipeline(self):
        # 1. High-volatility candidate: IND vs SAC (fast pace, close net rating)
        res_good = self.pipeline.evaluate_matchup("IND", "SAC")
        self.assertTrue(res_good.passed)
        self.assertEqual(len(res_good.rejection_reasons), 0)

        # 2. Blowout risk candidate: BOS (+11.6) vs DET (-9.0) -> net rating diff = 20.6
        res_blowout = self.pipeline.evaluate_matchup("BOS", "DET")
        self.assertFalse(res_blowout.passed)
        self.assertTrue(any("Mismatch" in r or "Blowout" in r for r in res_blowout.rejection_reasons))

        # 3. Slow defensive grind: NYK (96.0) vs MIA (96.9) -> combined pace ~192.9 < 200.0
        res_slow = self.pipeline.evaluate_matchup("NYK", "MIA")
        self.assertFalse(res_slow.passed)
        self.assertTrue(any("Low Pace" in r for r in res_slow.rejection_reasons))

    def test_engine_symmetric_arbitrage_locked_leg_a_first(self):
        df = pd.DataFrame({
            "team_a_price": [0.50, 0.45, 0.38, 0.45, 0.60, 0.70],
            "team_b_price": [0.50, 0.55, 0.62, 0.55, 0.40, 0.30]
        })
        res = self.engine.evaluate_game("TEST_GAME_1", df)

        self.assertEqual(res.status, TradeStatus.ARBITRAGE_LOCKED)
        self.assertEqual(res.legs_filled, 2)
        self.assertEqual(res.first_leg, "A")
        self.assertGreater(res.pnl, 0)

    def test_engine_symmetric_arbitrage_locked_leg_b_first(self):
        df = pd.DataFrame({
            "team_a_price": [0.50, 0.55, 0.65, 0.55, 0.39, 0.45],
            "team_b_price": [0.50, 0.45, 0.35, 0.45, 0.61, 0.55]
        })
        res = self.engine.evaluate_game("TEST_GAME_2", df)

        self.assertEqual(res.status, TradeStatus.ARBITRAGE_LOCKED)
        self.assertEqual(res.legs_filled, 2)
        self.assertEqual(res.first_leg, "B")
        self.assertGreater(res.pnl, 0)

    def test_engine_stop_loss_leg_a(self):
        df = pd.DataFrame({
            "team_a_price": [0.50, 0.40, 0.30, 0.25, 0.18, 0.10],
            "team_b_price": [0.50, 0.60, 0.70, 0.75, 0.82, 0.90]
        })
        res = self.engine.evaluate_game("TEST_GAME_STOP_A", df)

        self.assertEqual(res.status, TradeStatus.STOP_LOSS_EXIT)
        self.assertEqual(res.first_leg, "A")
        self.assertEqual(res.legs_filled, 1)
        self.assertLess(res.pnl, 0)

    def test_engine_stop_loss_leg_b(self):
        df = pd.DataFrame({
            "team_a_price": [0.50, 0.60, 0.70, 0.75, 0.82, 0.90],
            "team_b_price": [0.50, 0.40, 0.30, 0.25, 0.18, 0.10]
        })
        res = self.engine.evaluate_game("TEST_GAME_STOP_B", df)

        self.assertEqual(res.status, TradeStatus.STOP_LOSS_EXIT)
        self.assertEqual(res.first_leg, "B")
        self.assertEqual(res.legs_filled, 1)
        self.assertLess(res.pnl, 0)


if __name__ == "__main__":
    unittest.main()

