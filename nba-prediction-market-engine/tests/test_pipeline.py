"""
Unit tests for data pipeline and optimizer modules.
"""

import unittest
import pandas as pd
from src.data_pipeline.nba_pbp_parser import PlayByPlayPriceModel
from src.strategies.optimizer import StrategyOptimizer
from src.engine.bulk_loader import BulkDataLoader


class TestDataPipelineAndOptimizer(unittest.TestCase):

    def test_pbp_win_probability_model(self):
        model = PlayByPlayPriceModel()

        # At start of game (2880s remaining), 0-0 margin -> ~50%
        p_start = model.calculate_win_probability(margin_team_a=0, seconds_remaining=2880)
        self.assertAlmostEqual(p_start, 0.50, delta=0.05)

        # Team A ahead by 15 points with 120s remaining -> >98%
        p_late_lead = model.calculate_win_probability(margin_team_a=15, seconds_remaining=120)
        self.assertGreater(p_late_lead, 0.95)

        # Team A down by 15 points with 120s remaining -> <5%
        p_late_trail = model.calculate_win_probability(margin_team_a=-15, seconds_remaining=120)
        self.assertLess(p_late_trail, 0.05)

    def test_pbp_to_candles_conversion(self):
        model = PlayByPlayPriceModel()
        # Mock play-by-play events
        mock_pbp = pd.DataFrame({
            "seconds_remaining": [2800, 2000, 1000, 200, 0],
            "team_a_score": [2, 35, 70, 105, 110],
            "team_b_score": [0, 30, 68, 102, 104]
        })
        candles = model.convert_pbp_dataframe_to_candles(mock_pbp, "GAME_TEST_PBP", "BOS", "MIA")
        self.assertFalse(candles.empty)
        self.assertIn("team_a_price", candles.columns)
        self.assertIn("team_b_price", candles.columns)
        self.assertEqual(candles['team_a_price'].iloc[-1], 1.00)  # BOS won 110-104

    def test_grid_search_optimizer(self):
        games = BulkDataLoader.generate_metadata_driven_season(num_games=10, seed=42)
        optimizer = StrategyOptimizer(games_dict=games, initial_capital=10000.0)
        res_df = optimizer.run_grid_search(
            target_prices=[0.38, 0.40],
            stop_losses=[0.18, 0.20],
            volatility_cutoffs=[50.0]
        )
        self.assertEqual(len(res_df), 4)
        self.assertIn("roi_pct", res_df.columns)


if __name__ == "__main__":
    unittest.main()
