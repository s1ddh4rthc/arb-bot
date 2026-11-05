"""
NBA Play-by-Play to Win-Probability Curve Reconstruction Engine.
Converts real historical play-by-play score flows into continuous minute-by-minute
prediction market price curves ($0.00 - $1.00) using empirical basketball win probability models.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import norm


class PlayByPlayPriceModel:
    """
    Transforms second-by-second game scores and clock state into binary market prices.
    Calibrated against historical NBA in-game win distributions.
    """

    def __init__(self, variance_per_minute: float = 14.5):
        # In NBA basketball, variance of score margin grows roughly ~14.5 points^2 per elapsed minute
        self.sigma_per_minute = np.sqrt(variance_per_minute)

    def calculate_win_probability(
        self,
        margin_team_a: float,
        seconds_remaining: float,
        pregame_spread_a: float = 0.0
    ) -> float:
        """
        Computes win probability P(Team A wins) given current margin and clock.
        Uses normal CDF approximation of Brownian motion score diffusion.
        """
        if seconds_remaining <= 0:
            if margin_team_a > 0:
                return 1.00
            elif margin_team_a < 0:
                return 0.00
            else:
                return 0.50  # Overtime / tie

        minutes_remaining = max(0.1, seconds_remaining / 60.0)
        # Expected drift based on pregame quality differential decaying to 0 at game end
        decay_weight = seconds_remaining / 2880.0  # 2880 seconds in standard 48-minute regulation
        expected_margin = margin_team_a + (pregame_spread_a * decay_weight)

        # Standard deviation of remaining score margin
        sd_margin = self.sigma_per_minute * np.sqrt(minutes_remaining)

        # Win probability via standard normal CDF
        z_score = expected_margin / sd_margin
        prob = float(norm.cdf(z_score))
        return float(np.clip(prob, 0.01, 0.99))

    def convert_pbp_dataframe_to_candles(
        self,
        pbp_df: pd.DataFrame,
        game_id: str,
        team_a: str,
        team_b: str,
        pregame_spread_a: float = 0.0
    ) -> pd.DataFrame:
        """
        Takes raw play-by-play events with ['seconds_remaining', 'team_a_score', 'team_b_score']
        and generates resampled 1-minute price series for backtesting.
        """
        pbp_df = pbp_df.copy()
        pbp_df['margin'] = pbp_df['team_a_score'] - pbp_df['team_b_score']
        
        # Calculate win prob for each event
        probs = [
            self.calculate_win_probability(
                row.margin,
                row.seconds_remaining,
                pregame_spread_a=pregame_spread_a
            )
            for row in pbp_df.itertuples()
        ]
        pbp_df['team_a_price'] = probs
        pbp_df['team_b_price'] = 1.00 - pbp_df['team_a_price']

        # Downsample to 1-minute intervals (48 minutes -> 48 ticks)
        pbp_df['minute_bucket'] = (2880 - pbp_df['seconds_remaining']) // 60
        minute_df = pbp_df.groupby('minute_bucket').last().reset_index()

        minute_df['game_id'] = game_id
        minute_df['timestamp'] = pd.date_range(start="2026-01-01", periods=len(minute_df), freq="min")
        minute_df['team_a'] = team_a
        minute_df['team_b'] = team_b

        # Final settlement row
        final_winner = 1.00 if minute_df['margin'].iloc[-1] > 0 else 0.00
        minute_df.loc[len(minute_df) - 1, 'team_a_price'] = final_winner
        minute_df.loc[len(minute_df) - 1, 'team_b_price'] = 1.00 - final_winner

        return minute_df[['game_id', 'timestamp', 'team_a', 'team_b', 'team_a_price', 'team_b_price']]
