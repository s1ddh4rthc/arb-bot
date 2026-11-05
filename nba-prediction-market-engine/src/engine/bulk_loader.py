"""
Bulk Dataset Ingestion and Historical Simulation Engine.
Supports Parquet/CSV loading and realistic metadata-conditioned stochastic price simulation.
"""

from typing import Dict, List, Optional, Tuple
import io
import requests
import numpy as np
import pandas as pd
from src.engine.models import GameMetadata
from src.metadata.team_metrics import TeamMetricsRegistry
from src.metadata.game_filter import GameFilterPipeline


class BulkDataLoader:
    """
    Handles bulk ingestion of multi-game prediction market datasets and
    generates metadata-conditioned game simulations for backtesting.
    """

    @staticmethod
    def load_from_csv_or_parquet(
        file_path_or_url: str,
        registry: Optional[TeamMetricsRegistry] = None,
        filter_pipeline: Optional[GameFilterPipeline] = None
    ) -> Dict[str, Tuple[pd.DataFrame, Optional[GameMetadata]]]:
        """
        Loads a bulk multi-game dataset from a local Parquet/CSV file or HTTP endpoint.
        Returns a dictionary mapping game_id -> (game_df, metadata).
        """
        print(f"Loading bulk dataset from: {file_path_or_url}...")
        if file_path_or_url.endswith('.parquet'):
            df = pd.read_parquet(file_path_or_url)
        elif file_path_or_url.startswith('http'):
            res = requests.get(file_path_or_url, timeout=30)
            df = pd.read_csv(io.StringIO(res.text))
        else:
            df = pd.read_csv(file_path_or_url)

        df.columns = [c.lower() for c in df.columns]

        if 'team_a_price' not in df.columns and 'price' in df.columns:
            df['team_a_price'] = df['price']

        if df['team_a_price'].max() > 1.0:
            df['team_a_price'] /= 100.0

        if 'team_b_price' not in df.columns:
            df['team_b_price'] = np.clip(1.00 - df['team_a_price'], 0.00, 1.00)

        registry = registry or TeamMetricsRegistry()
        filter_pipeline = filter_pipeline or GameFilterPipeline(registry=registry)

        game_dict = {}
        for gid, group in df.groupby('game_id'):
            g_df = group.sort_values('timestamp').reset_index(drop=True)
            gid_str = str(gid)
            meta = None
            if 'team_a' in g_df.columns and 'team_b' in g_df.columns:
                team_a = str(g_df['team_a'].iloc[0])
                team_b = str(g_df['team_b'].iloc[0])
                matchup = registry.compute_matchup_metrics(team_a, team_b)
                filter_res = filter_pipeline.evaluate_metrics(matchup) if matchup else None
                meta = GameMetadata(
                    game_id=gid_str,
                    date=str(g_df['timestamp'].iloc[0])[:10] if 'timestamp' in g_df.columns else "2026-01-01",
                    team_a=team_a,
                    team_b=team_b,
                    home_team=team_b,
                    stats_a=registry.get_team(team_a),
                    stats_b=registry.get_team(team_b),
                    matchup=matchup,
                    filter_result=filter_res
                )
            game_dict[gid_str] = (g_df, meta)

        print(f"[Success] Loaded {len(game_dict)} unique games.")
        return game_dict

    @staticmethod
    def generate_metadata_driven_season(
        num_games: int = 300,
        seed: int = 101,
        registry: Optional[TeamMetricsRegistry] = None,
        filter_pipeline: Optional[GameFilterPipeline] = None
    ) -> Dict[str, Tuple[pd.DataFrame, GameMetadata]]:
        """
        Generates a realistic multi-game season dataset where each game's in-game
        win probability path is conditioned directly on cross-sectional team metrics:
        - Diffusion volatility is driven by Pace + 3PA volume.
        - Drift / initial bias is driven by Net Rating differential.
        """
        np.random.seed(seed)
        registry = registry or TeamMetricsRegistry()
        filter_pipeline = filter_pipeline or GameFilterPipeline(registry=registry)
        team_list = registry.list_teams()

        print(f"Synthesizing {num_games}-game season conditioned on NBA team metadata...")
        games = {}

        for g_id in range(1, num_games + 1):
            # Select two distinct teams
            team_a, team_b = np.random.choice(team_list, size=2, replace=False)
            matchup = registry.compute_matchup_metrics(team_a, team_b)
            filter_res = filter_pipeline.evaluate_metrics(matchup)

            # Volatility calculation based on Pace (norm ~200) and 3PA (norm ~72)
            # Baseline sigma ~ 0.035, adjusted by pace factor and 3PA factor
            pace_factor = (matchup.combined_pace - 192.0) / 16.0  # ~0.0 to 1.0
            three_factor = (matchup.combined_3pa - 62.0) / 23.0    # ~0.0 to 1.0
            vol_scale = 0.020 + (0.015 * pace_factor) + (0.015 * three_factor)
            vol_scale = np.clip(vol_scale, 0.018, 0.055)

            # Drift calculation based on Net Rating differential
            # Strong favorite pulls probability toward their side
            drift_per_step = (matchup.net_rating_spread / 100.0) * 0.0015

            # Game duration in minutes (standard NBA regulation 48 min game translates to ~100-140 mins elapsed time)
            length = np.random.randint(95, 145)

            # Initial pre-game opening price based on Net Rating spread
            # E.g., +10 Net Rating favorite opens around 0.65-0.70; evenly matched opens at ~0.50
            opening_prob = 1.0 / (1.0 + np.exp(-0.08 * matchup.net_rating_spread))
            opening_prob = np.clip(opening_prob, 0.20, 0.80)

            # In-game probability path simulation with mean-reverting momentum swings
            shocks = np.random.normal(loc=drift_per_step, scale=vol_scale, size=length)
            raw_path = np.zeros(length)
            raw_path[0] = opening_prob
            for t in range(1, length):
                # Small mean-reversion pull toward opening price + shock
                pull = 0.02 * (opening_prob - raw_path[t - 1])
                raw_path[t] = np.clip(raw_path[t - 1] + pull + shocks[t], 0.02, 0.98)

            # Final resolution at expiration (1.00 or 0.00)
            final_winner = 1.00 if raw_path[-2] >= 0.50 else 0.00
            raw_path[-1] = final_winner

            game_id_str = f"GAME_{g_id:03d}_{team_a}_vs_{team_b}"
            g_df = pd.DataFrame({
                'game_id': game_id_str,
                'timestamp': pd.date_range(start="2026-01-01", periods=length, freq="min"),
                'team_a': team_a,
                'team_b': team_b,
                'team_a_price': raw_path,
                'team_b_price': np.clip(1.00 - raw_path, 0.00, 1.00)
            })

            meta = GameMetadata(
                game_id=game_id_str,
                date="2026-01-01",
                team_a=team_a,
                team_b=team_b,
                home_team=team_b,
                stats_a=registry.get_team(team_a),
                stats_b=registry.get_team(team_b),
                matchup=matchup,
                filter_result=filter_res
            )

            games[game_id_str] = (g_df, meta)

        print(f"[Success] Generated {len(games)} metadata-conditioned games.")
        return games

    @staticmethod
    def generate_full_season_archive(num_games: int = 300) -> Dict[str, pd.DataFrame]:
        """Backwards compatible version returning dictionary of DataFrames."""
        dataset = BulkDataLoader.generate_metadata_driven_season(num_games=num_games)
        return {gid: df for gid, (df, _) in dataset.items()}
