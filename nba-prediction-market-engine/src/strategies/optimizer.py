"""
Grid Search and Parameter Tuning Engine for Prediction Market Arbitrage Strategies.
"""

from typing import List, Dict, Any, Tuple
import itertools
import pandas as pd
from config.default_config import EngineConfig, StrategyConfig, FilterConfig, ExecutionConfig
from src.metadata.team_metrics import TeamMetricsRegistry
from src.metadata.game_filter import GameFilterPipeline
from src.engine.backtest_engine import BulkPMEngine
from src.analytics.metrics import StrategyAnalytics


class StrategyOptimizer:
    """Runs high-speed grid searches across limit targets, stop-losses, and filter cutoffs."""

    def __init__(self, games_dict: Dict[str, Tuple[pd.DataFrame, Any]], initial_capital: float = 10000.0):
        self.games_dict = games_dict
        self.initial_capital = initial_capital
        self.registry = TeamMetricsRegistry()

    def run_grid_search(
        self,
        target_prices: List[float] = [0.38, 0.40, 0.42],
        stop_losses: List[float] = [0.15, 0.18, 0.20],
        volatility_cutoffs: List[float] = [50.0, 55.0, 60.0]
    ) -> pd.DataFrame:
        """
        Executes grid search over targets, stop losses, and volatility score thresholds.
        """
        results_records = []
        combinations = list(itertools.product(target_prices, stop_losses, volatility_cutoffs))
        print(f"Executing multi-variable parameter search across {len(combinations)} configurations...")

        for target_p, stop_l, vol_cut in combinations:
            filter_cfg = FilterConfig(min_volatility_score=vol_cut)
            pipeline = GameFilterPipeline(config=filter_cfg, registry=self.registry)
            strat_cfg = StrategyConfig(target_a=target_p, target_b=target_p, stop_loss_pct=stop_l)
            engine = BulkPMEngine(
                execution_config=ExecutionConfig(initial_capital=self.initial_capital),
                strategy_config=strat_cfg
            )

            game_results = []
            for gid, (g_df, meta) in self.games_dict.items():
                if meta and meta.matchup:
                    eval_res = pipeline.evaluate_metrics(meta.matchup)
                    if eval_res.passed:
                        res = engine.evaluate_game(
                            gid,
                            g_df,
                            target_a=target_p,
                            target_b=target_p,
                            stop_loss_pct=stop_l,
                            metadata=meta
                        )
                        game_results.append(res)

            metrics = StrategyAnalytics.calculate_metrics(game_results, initial_capital=self.initial_capital)
            results_records.append({
                "target_price": target_p,
                "stop_loss": stop_l,
                "min_vol_score": vol_cut,
                "trades_count": metrics["total_games"],
                "total_pnl": round(metrics["total_pnl"], 2),
                "roi_pct": round(metrics["roi_pct"], 2),
                "max_drawdown_pct": round(metrics["max_drawdown_pct"], 2),
                "arb_rate_pct": round(metrics["arb_locked_pct"], 1),
                "stop_rate_pct": round(metrics["stop_loss_pct"], 1),
                "profit_factor": round(metrics["profit_factor"], 2),
                "sharpe_ratio": round(metrics["sharpe_ratio"], 2)
            })

        df_grid = pd.DataFrame(results_records)
        df_grid = df_grid.sort_values(by="roi_pct", ascending=False).reset_index(drop=True)
        return df_grid
