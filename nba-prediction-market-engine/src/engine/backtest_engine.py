"""
Vectorized and Event-Driven Backtesting Engine for Binary Prediction Markets.
Executes symmetric dual-limit legging strategies with transaction fees, slippage, and stop-losses.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from config.default_config import ExecutionConfig, StrategyConfig
from src.engine.models import GameBacktestResult, TradeStatus, GameMetadata


class BulkPMEngine:
    """
    Simulates high-speed execution of Dual-Limit Legging in NBA prediction markets.
    Supports symmetric order evaluation, slippage, taker/maker fee modeling, and risk sizing.
    """

    def __init__(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        strategy_config: Optional[StrategyConfig] = None,
    ):
        self.exec_cfg = execution_config or ExecutionConfig()
        self.strat_cfg = strategy_config or StrategyConfig()

        self.initial_capital = self.exec_cfg.initial_capital
        self.risk_per_trade = self.exec_cfg.risk_per_trade
        self.fee_rate = self.exec_cfg.fee_rate
        self.slippage = self.exec_cfg.slippage

    def evaluate_game(
        self,
        game_id: str,
        game_df: pd.DataFrame,
        target_a: Optional[float] = None,
        target_b: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        metadata: Optional[GameMetadata] = None,
    ) -> GameBacktestResult:
        """
        Evaluates a single game's price history against resting limit orders.
        Guarantees complete symmetry between Team A and Team B fills and stops.
        """
        target_a = target_a if target_a is not None else self.strat_cfg.target_a
        target_b = target_b if target_b is not None else self.strat_cfg.target_b
        stop_loss_pct = stop_loss_pct if stop_loss_pct is not None else self.strat_cfg.stop_loss_pct

        if game_df.empty or len(game_df) < 5:
            return GameBacktestResult(
                game_id=game_id,
                status=TradeStatus.INVALID_DATA,
                pnl=0.0,
                roi=0.0,
                legs_filled=0,
                allocated_capital=0.0,
                contracts=0.0,
                metadata=metadata
            )

        allocated_capital = self.initial_capital * self.risk_per_trade
        target_pair_cost = target_a + target_b
        contracts = allocated_capital / target_pair_cost

        leg_a_filled = False
        leg_b_filled = False
        fill_price_a = 0.0
        fill_price_b = 0.0
        first_leg = None

        for row in game_df.itertuples():
            p_a = row.team_a_price
            p_b = row.team_b_price

            # 1. Neither leg filled yet
            if not leg_a_filled and not leg_b_filled:
                if p_a <= target_a and p_b <= target_b:
                    # Both legs hit limit price in the same minute
                    leg_a_filled = True
                    leg_b_filled = True
                    fill_price_a = target_a + self.slippage
                    fill_price_b = target_b + self.slippage
                    first_leg = "BOTH"
                    break
                elif p_a <= target_a:
                    leg_a_filled = True
                    fill_price_a = target_a + self.slippage
                    first_leg = "A"
                elif p_b <= target_b:
                    leg_b_filled = True
                    fill_price_b = target_b + self.slippage
                    first_leg = "B"

            # 2. Leg A is filled, waiting for Leg B
            elif leg_a_filled and not leg_b_filled:
                if p_b <= target_b:
                    leg_b_filled = True
                    fill_price_b = target_b + self.slippage
                    # Arbitrage is now locked!
                    break

                # Stop loss check on open Leg A position
                if p_a <= (fill_price_a - stop_loss_pct):
                    exit_price_a = max(0.01, p_a - self.slippage)
                    # Cost was fill_price_a + entry fee; exit brings exit_price_a - exit fee
                    net_loss = (fill_price_a - exit_price_a + (2 * self.fee_rate)) * contracts
                    return GameBacktestResult(
                        game_id=game_id,
                        status=TradeStatus.STOP_LOSS_EXIT,
                        pnl=-net_loss,
                        roi=-net_loss / allocated_capital,
                        legs_filled=1,
                        allocated_capital=allocated_capital,
                        contracts=contracts,
                        fill_price_a=fill_price_a,
                        exit_price=exit_price_a,
                        first_leg="A",
                        stop_loss_triggered=True,
                        metadata=metadata
                    )

            # 3. Leg B is filled, waiting for Leg A
            elif leg_b_filled and not leg_a_filled:
                if p_a <= target_a:
                    leg_a_filled = True
                    fill_price_a = target_a + self.slippage
                    # Arbitrage is now locked!
                    break

                # Stop loss check on open Leg B position
                if p_b <= (fill_price_b - stop_loss_pct):
                    exit_price_b = max(0.01, p_b - self.slippage)
                    net_loss = (fill_price_b - exit_price_b + (2 * self.fee_rate)) * contracts
                    return GameBacktestResult(
                        game_id=game_id,
                        status=TradeStatus.STOP_LOSS_EXIT,
                        pnl=-net_loss,
                        roi=-net_loss / allocated_capital,
                        legs_filled=1,
                        allocated_capital=allocated_capital,
                        contracts=contracts,
                        fill_price_b=fill_price_b,
                        exit_price=exit_price_b,
                        first_leg="B",
                        stop_loss_triggered=True,
                        metadata=metadata
                    )

        # -------------------------------------------------------------
        # Resolution & Final PnL Accounting
        # -------------------------------------------------------------

        # Outcome 1: Dual-Leg Arbitrage Locked
        if leg_a_filled and leg_b_filled:
            total_unit_cost = fill_price_a + fill_price_b + (2 * self.fee_rate)
            # Binary contract guarantees payout of $1.00 regardless of who wins
            net_unit_pnl = 1.00 - total_unit_cost
            total_pnl = net_unit_pnl * contracts
            return GameBacktestResult(
                game_id=game_id,
                status=TradeStatus.ARBITRAGE_LOCKED,
                pnl=total_pnl,
                roi=total_pnl / allocated_capital,
                legs_filled=2,
                allocated_capital=allocated_capital,
                contracts=contracts,
                fill_price_a=fill_price_a,
                fill_price_b=fill_price_b,
                first_leg=first_leg,
                stop_loss_triggered=False,
                metadata=metadata
            )

        # Outcome 2: Unhedged Single-Leg Hold on Team A (Never hit stop loss, Leg B never filled)
        elif leg_a_filled:
            winner_a = game_df.iloc[-1]['team_a_price'] >= 0.50
            payout = 1.00 if winner_a else 0.00
            net_unit_pnl = payout - fill_price_a - self.fee_rate
            total_pnl = net_unit_pnl * contracts
            return GameBacktestResult(
                game_id=game_id,
                status=TradeStatus.UNHEDGED_HOLD,
                pnl=total_pnl,
                roi=total_pnl / allocated_capital,
                legs_filled=1,
                allocated_capital=allocated_capital,
                contracts=contracts,
                fill_price_a=fill_price_a,
                first_leg="A",
                stop_loss_triggered=False,
                metadata=metadata
            )

        # Outcome 3: Unhedged Single-Leg Hold on Team B (Never hit stop loss, Leg A never filled)
        elif leg_b_filled:
            winner_b = game_df.iloc[-1]['team_b_price'] >= 0.50
            payout = 1.00 if winner_b else 0.00
            net_unit_pnl = payout - fill_price_b - self.fee_rate
            total_pnl = net_unit_pnl * contracts
            return GameBacktestResult(
                game_id=game_id,
                status=TradeStatus.UNHEDGED_HOLD,
                pnl=total_pnl,
                roi=total_pnl / allocated_capital,
                legs_filled=1,
                allocated_capital=allocated_capital,
                contracts=contracts,
                fill_price_b=fill_price_b,
                first_leg="B",
                stop_loss_triggered=False,
                metadata=metadata
            )

        # Outcome 4: Neither leg reached target buy limits
        return GameBacktestResult(
            game_id=game_id,
            status=TradeStatus.NO_FILL,
            pnl=0.0,
            roi=0.0,
            legs_filled=0,
            allocated_capital=allocated_capital,
            contracts=contracts,
            metadata=metadata
        )
