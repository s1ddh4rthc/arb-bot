"""
Main Execution Script: Comparative Backtest of Dual-Limit Legging Strategy
Evaluates Unfiltered Baseline vs. Cross-Sectional Team Metadata Filtered Pipeline.
"""

import time
import os
import argparse
from config.default_config import EngineConfig, FilterConfig, StrategyConfig, ExecutionConfig
from src.metadata.team_metrics import TeamMetricsRegistry
from src.metadata.game_filter import GameFilterPipeline
from src.engine.bulk_loader import BulkDataLoader
from src.engine.backtest_engine import BulkPMEngine
from src.analytics.metrics import StrategyAnalytics


def run_comparative_backtest(
    num_games: int = 300,
    seed: int = 101,
    custom_dataset_path: str = None,
    save_chart: bool = True
):
    print("\n" + "=" * 76)
    print("    NBA PREDICTION MARKET DUAL-LIMIT LEGGING ENGINE - TASK 1 EVALUATION")
    print("=" * 76)

    # 1. Initialize Configuration and Modules
    config = EngineConfig(
        execution=ExecutionConfig(initial_capital=10000.0, risk_per_trade=0.02, fee_rate=0.015, slippage=0.01),
        strategy=StrategyConfig(target_a=0.40, target_b=0.40, stop_loss_pct=0.20),
        filters=FilterConfig(
            min_combined_pace=199.0,
            max_net_rating_diff=6.5,
            min_combined_3pa=69.0,
            min_volatility_score=52.0
        )
    )

    registry = TeamMetricsRegistry()
    filter_pipeline = GameFilterPipeline(config=config.filters, registry=registry)
    engine = BulkPMEngine(execution_config=config.execution, strategy_config=config.strategy)

    # 2. Ingest or Generate Data
    if custom_dataset_path and os.path.exists(custom_dataset_path):
        games_dict = BulkDataLoader.load_from_csv_or_parquet(
            custom_dataset_path,
            registry=registry,
            filter_pipeline=filter_pipeline
        )
    else:
        games_dict = BulkDataLoader.generate_metadata_driven_season(
            num_games=num_games,
            seed=seed,
            registry=registry,
            filter_pipeline=filter_pipeline
        )

    print(f"\n[Step 1] Running Unfiltered Baseline across all {len(games_dict)} games...")
    start_t = time.time()
    unfiltered_results = []
    for game_id, (g_df, meta) in games_dict.items():
        res = engine.evaluate_game(game_id, g_df, metadata=meta)
        unfiltered_results.append(res)
    t_unfiltered = time.time() - start_t
    print(f"-> Unfiltered run complete in {t_unfiltered:.2f}s.")

    print(f"\n[Step 2] Applying Cross-Sectional Metadata Filters...")
    filtered_results = []
    filtered_out_count = 0
    filter_breakdown = {}

    for game_id, (g_df, meta) in games_dict.items():
        if meta and meta.filter_result and meta.filter_result.passed:
            res = engine.evaluate_game(game_id, g_df, metadata=meta)
            filtered_results.append(res)
        else:
            filtered_out_count += 1
            if meta and meta.filter_result:
                for r in meta.filter_result.rejection_reasons:
                    category = r.split(":")[0]
                    filter_breakdown[category] = filter_breakdown.get(category, 0) + 1

    print(f"-> Filter Pipeline Accepted: {len(filtered_results)} games | Filtered Out: {filtered_out_count} games.")
    print("\nPre-Game Rejection Factors Breakdown:")
    for cat, count in sorted(filter_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat:<30}: {count} games rejected")

    # 3. Compute Analytics
    unfiltered_stats = StrategyAnalytics.calculate_metrics(unfiltered_results, initial_capital=config.execution.initial_capital)
    filtered_stats = StrategyAnalytics.calculate_metrics(filtered_results, initial_capital=config.execution.initial_capital)

    # 4. Display Results
    StrategyAnalytics.print_comparison_table(unfiltered_stats, filtered_stats)

    # 5. Save Equity & Drawdown Chart
    if save_chart:
        chart_dir = os.path.join(os.path.dirname(__file__), "data", "processed")
        chart_path = os.path.join(chart_dir, "backtest_comparison.png")
        # Ensure directory has write permission
        try:
            StrategyAnalytics.plot_comparative_performance(unfiltered_stats, filtered_stats, save_path=chart_path)
        except Exception as e:
            print(f"Notice: Plot save skipped ({e})")

    return unfiltered_stats, filtered_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Prediction Market Backtest Runner")
    parser.add_argument("--games", type=int, default=300, help="Number of games to simulate")
    parser.add_argument("--seed", type=int, default=101, help="Random seed for simulation")
    parser.add_argument("--data", type=str, default=None, help="Path to Parquet or CSV file")
    args = parser.parse_args()

    run_comparative_backtest(num_games=args.games, seed=args.seed, custom_dataset_path=args.data)
