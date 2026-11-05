"""
Default configuration parameters for NBA Prediction Market Trading & Backtesting Engine.
"""

from dataclasses import dataclass, field


@dataclass
class ExecutionConfig:
    """Trading and exchange execution parameters."""
    initial_capital: float = 10000.0
    risk_per_trade: float = 0.02          # 2% portfolio allocation per game
    fee_rate: float = 0.015               # 1.5% taker fee per side (e.g., Kalshi/Polymarket)
    slippage: float = 0.01                # $0.01 expected slippage on fill / exit
    max_portfolio_exposure: float = 0.20  # Max 20% active exposure across simultaneous games


@dataclass
class StrategyConfig:
    """Dual-Limit Legging Strategy parameters."""
    target_a: float = 0.40                # Target buy price for Team A (40¢)
    target_b: float = 0.40                # Target buy price for Team B (40¢)
    stop_loss_pct: float = 0.20           # Drop from fill price that triggers hard stop (e.g. 0.40 -> 0.20)
    enable_trailing_scalp: bool = False   # Optional trailing profit scalp before resolution
    trailing_scalp_gain: float = 0.15     # If single leg rises by 15¢, exit early if second leg fails to fill
    time_stop_quarter: int = 4            # Optional time-based stop enforcement


@dataclass
class FilterConfig:
    """
    Cross-Sectional Team Metadata Filters for In-Game Volatility Arbitrage.
    Goal: Filter out low-volatility blowouts; select high-variance, fast-paced, balanced matchups.
    """
    # Combined Pace: Pace is estimated possessions per 48 min.
    # League avg ~98-100 per team, so combined pace avg ~198-200. High-pace >= 202.0.
    min_combined_pace: float = 200.0
    
    # Net Rating spread: |NetRtg_A - NetRtg_B|.
    # Lower spread = closer matchup = more lead changes and price swings.
    max_net_rating_diff: float = 6.0
    
    # Combined 3-Point Attempt volume: High 3PA produces high scoring variance and sudden runs.
    min_combined_3pa: float = 70.0
    
    # Minimum combined Turnover Rate: Turnover swings create transition runs.
    min_combined_tov_pct: float = 25.0
    
    # Minimum composite volatility score (0 - 100)
    min_volatility_score: float = 55.0


@dataclass
class EngineConfig:
    """Master configuration bundling execution, strategy, and filter settings."""
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
