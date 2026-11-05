"""
Quantitative Performance Analytics and Visualization for Prediction Market Strategies.
"""

from typing import List, Dict, Any, Optional
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from src.engine.models import GameBacktestResult, TradeStatus

warnings.filterwarnings('ignore')



class StrategyAnalytics:
    """Calculates comprehensive quantitative performance and risk metrics."""

    @staticmethod
    def calculate_metrics(
        results: List[GameBacktestResult],
        initial_capital: float = 10000.0
    ) -> Dict[str, Any]:
        """Calculates risk, return, drawdown, and win-rate statistics from trade logs."""
        if not results:
            return {
                "total_games": 0,
                "initial_capital": initial_capital,
                "ending_capital": initial_capital,
                "total_pnl": 0.0,
                "roi_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "arb_locked_pct": 0.0,
                "stop_loss_pct": 0.0,
                "unhedged_pct": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
            }

        df = pd.DataFrame([r.to_dict() for r in results])
        total_games = len(df)

        running_capital = initial_capital
        capital_curve = [initial_capital]

        for pnl in df['pnl']:
            running_capital += pnl
            capital_curve.append(running_capital)

        equity_series = pd.Series(capital_curve)
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        max_drawdown_pct = float(drawdown.min() * 100)

        total_pnl = float(df['pnl'].sum())
        roi_pct = float((total_pnl / initial_capital) * 100)

        # Categorical counts
        arb_count = int((df['status'] == TradeStatus.ARBITRAGE_LOCKED.value).sum())
        stop_count = int((df['status'] == TradeStatus.STOP_LOSS_EXIT.value).sum())
        unhedged_count = int((df['status'] == TradeStatus.UNHEDGED_HOLD.value).sum())
        no_fill_count = int((df['status'] == TradeStatus.NO_FILL.value).sum())

        active_games = total_games - no_fill_count
        arb_locked_pct = (arb_count / total_games * 100) if total_games else 0.0
        stop_loss_pct = (stop_count / total_games * 100) if total_games else 0.0
        unhedged_pct = (unhedged_count / total_games * 100) if total_games else 0.0

        wins = df[df['pnl'] > 0]['pnl']
        losses = df[df['pnl'] < 0]['pnl']
        gross_profit = float(wins.sum())
        gross_loss = float(abs(losses.sum()))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Sharpe calculation (per-trade basis)
        mean_pnl = df['pnl'].mean()
        std_pnl = df['pnl'].std()
        sharpe = float((mean_pnl / std_pnl) * np.sqrt(total_games)) if std_pnl > 0 else 0.0

        return {
            "total_games": total_games,
            "active_games": active_games,
            "initial_capital": initial_capital,
            "ending_capital": float(running_capital),
            "total_pnl": total_pnl,
            "roi_pct": roi_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "arb_count": arb_count,
            "arb_locked_pct": arb_locked_pct,
            "stop_count": stop_count,
            "stop_loss_pct": stop_loss_pct,
            "unhedged_count": unhedged_count,
            "unhedged_pct": unhedged_pct,
            "no_fill_count": no_fill_count,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "equity_curve": capital_curve,
            "drawdown_curve": (drawdown * 100).tolist()
        }

    @staticmethod
    def print_comparison_table(unfiltered_stats: Dict[str, Any], filtered_stats: Dict[str, Any]):
        """Prints a clean side-by-side terminal comparison between Unfiltered and Filtered runs."""
        print("\n" + "=" * 76)
        print(f"{'STRATEGY PERFORMANCE COMPARISON: UNFILTERED VS FILTERED':^76}")
        print("=" * 76)
        print(f"{'Metric':<32} | {'Unfiltered (All)':<18} | {'Filtered (Alpha)':<18}")
        print("-" * 76)
        print(f"{'Total Games Evaluated':<32} | {unfiltered_stats['total_games']:<18} | {filtered_stats['total_games']:<18}")
        print(f"{'Trades Executed':<32} | {unfiltered_stats['active_games']:<18} | {filtered_stats['active_games']:<18}")
        print(f"{'Starting Capital':<32} | ${unfiltered_stats['initial_capital']:<17,.2f} | ${filtered_stats['initial_capital']:<17,.2f}")
        print(f"{'Ending Portfolio Value':<32} | ${unfiltered_stats['ending_capital']:<17,.2f} | ${filtered_stats['ending_capital']:<17,.2f}")
        
        # Color or format PnL
        uf_pnl = f"${unfiltered_stats['total_pnl']:+,.2f} ({unfiltered_stats['roi_pct']:+.2f}%)"
        f_pnl = f"${filtered_stats['total_pnl']:+,.2f} ({filtered_stats['roi_pct']:+.2f}%)"
        print(f"{'Total Return (PnL / ROI)':<32} | {uf_pnl:<18} | {f_pnl:<18}")
        
        print(f"{'Max Drawdown':<32} | {unfiltered_stats['max_drawdown_pct']:.2f}%{'':<12} | {filtered_stats['max_drawdown_pct']:.2f}%{'':<12}")
        print(f"{'Profit Factor':<32} | {unfiltered_stats['profit_factor']:.2f}{'':<14} | {filtered_stats['profit_factor']:.2f}{'':<14}")
        print(f"{'Sharpe Ratio':<32} | {unfiltered_stats['sharpe_ratio']:.2f}{'':<14} | {filtered_stats['sharpe_ratio']:.2f}{'':<14}")
        print("-" * 76)
        print(f"{'Dual-Leg Arb Locked Rate':<32} | {unfiltered_stats['arb_locked_pct']:.1f}% ({unfiltered_stats['arb_count']}){'':<6} | {filtered_stats['arb_locked_pct']:.1f}% ({filtered_stats['arb_count']}){'':<6}")
        print(f"{'Stop-Loss Exit Rate':<32} | {unfiltered_stats['stop_loss_pct']:.1f}% ({unfiltered_stats['stop_count']}){'':<6} | {filtered_stats['stop_loss_pct']:.1f}% ({filtered_stats['stop_count']}){'':<6}")
        print(f"{'Unhedged Hold Rate':<32} | {unfiltered_stats['unhedged_pct']:.1f}% ({unfiltered_stats['unhedged_count']}){'':<6} | {filtered_stats['unhedged_pct']:.1f}% ({filtered_stats['unhedged_count']}){'':<6}")
        print("=" * 76 + "\n")

    @staticmethod
    def plot_comparative_performance(
        unfiltered_stats: Dict[str, Any],
        filtered_stats: Dict[str, Any],
        save_path: Optional[str] = None
    ):
        """Generates visual comparison charts for equity growth and drawdowns."""
        plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]})

        # Equity Curves
        ax1.plot(unfiltered_stats['equity_curve'], color='#e74c3c', linestyle='--', linewidth=2, label=f"Unfiltered (ROI: {unfiltered_stats['roi_pct']:.2f}%)")
        ax1.plot(filtered_stats['equity_curve'], color='#2ecc71', linewidth=2.5, label=f"Filtered Alpha Engine (ROI: {filtered_stats['roi_pct']:.2f}%)")
        ax1.axhline(unfiltered_stats['initial_capital'], color='#7f8c8d', linestyle=':', label='Starting Balance ($10,000)')
        ax1.set_title("Equity Curve Comparison: Unfiltered Baseline vs Feature-Filtered Pipeline", fontsize=14, fontweight='bold')
        ax1.set_ylabel("Portfolio Value ($)", fontsize=11)
        ax1.legend(loc='upper left', frameon=True)

        # Drawdown comparison
        ax2.plot(unfiltered_stats['drawdown_curve'], color='#c0392b', linestyle='--', linewidth=1.5, label=f"Unfiltered Max DD: {unfiltered_stats['max_drawdown_pct']:.2f}%")
        ax2.plot(filtered_stats['drawdown_curve'], color='#27ae60', linewidth=1.8, label=f"Filtered Max DD: {filtered_stats['max_drawdown_pct']:.2f}%")
        ax2.set_title("Drawdown Profile (%)", fontsize=12, fontweight='bold')
        ax2.set_xlabel("Game Trade Index", fontsize=11)
        ax2.set_ylabel("Drawdown %", fontsize=11)
        ax2.legend(loc='lower left', frameon=True)

        plt.tight_layout()
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            fig.savefig(save_path)
            print(f"[Success] Saved comparative chart to: {save_path}")
        else:
            plt.show()
        plt.close(fig)
