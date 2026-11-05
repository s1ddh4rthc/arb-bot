"""
Domain models and dataclasses for the NBA Prediction Market Engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import pandas as pd


class TradeStatus(str, Enum):
    ARBITRAGE_LOCKED = "ARBITRAGE_LOCKED"
    STOP_LOSS_EXIT = "STOP_LOSS_EXIT"
    UNHEDGED_HOLD = "UNHEDGED_HOLD"
    NO_FILL = "NO_FILL"
    INVALID_DATA = "INVALID_DATA"


@dataclass
class TeamStats:
    """Advanced team metrics for volatility modeling and cross-sectional filtering."""
    team_id: str
    team_name: str
    abbreviation: str
    pace: float               # Possessions per 48 mins (e.g., 96.0 - 104.0)
    offensive_rating: float   # Points scored per 100 possessions
    defensive_rating: float   # Points allowed per 100 possessions
    net_rating: float         # OffRtg - DefRtg
    three_point_att: float    # 3-point field goal attempts per game (e.g., 30.0 - 45.0)
    three_point_pct: float    # 3-point percentage (e.g., 0.34 - 0.39)
    turnover_pct: float       # Turnover percentage (e.g., 11.5 - 16.0)
    assist_ratio: float       # Assist percentage / ratio
    conference: str = "East"
    division: str = "Atlantic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "abbreviation": self.abbreviation,
            "pace": self.pace,
            "offensive_rating": self.offensive_rating,
            "defensive_rating": self.defensive_rating,
            "net_rating": self.net_rating,
            "three_point_att": self.three_point_att,
            "three_point_pct": self.three_point_pct,
            "turnover_pct": self.turnover_pct,
            "assist_ratio": self.assist_ratio,
        }


@dataclass
class MatchupMetrics:
    """Derived matchup features used by pre-game filter rules."""
    combined_pace: float
    net_rating_diff: float        # Absolute difference |NetRtg_A - NetRtg_B|
    net_rating_spread: float      # NetRtg_A - NetRtg_B (directional)
    combined_3pa: float
    combined_tov_pct: float
    pace_percentile: float = 0.0
    volatility_score: float = 0.0 # Composite score 0.0 to 100.0


@dataclass
class FilterEvaluation:
    """Result of passing a game matchup through the Cross-Sectional Filter Pipeline."""
    passed: bool
    rejection_reasons: List[str] = field(default_factory=list)
    matchup: Optional[MatchupMetrics] = None


@dataclass
class GameMetadata:
    """Metadata attached to a specific game."""
    game_id: str
    date: str
    team_a: str                  # Abbreviation of Team A (e.g., "IND")
    team_b: str                  # Abbreviation of Team B (e.g., "GSW")
    home_team: str
    stats_a: Optional[TeamStats] = None
    stats_b: Optional[TeamStats] = None
    matchup: Optional[MatchupMetrics] = None
    filter_result: Optional[FilterEvaluation] = None


@dataclass
class GameBacktestResult:
    """Execution output from simulating a game's order lifecycle."""
    game_id: str
    status: TradeStatus
    pnl: float
    roi: float
    legs_filled: int
    allocated_capital: float
    contracts: float
    fill_price_a: Optional[float] = None
    fill_price_b: Optional[float] = None
    exit_price: Optional[float] = None
    first_leg: Optional[str] = None    # "A" or "B"
    stop_loss_triggered: bool = False
    metadata: Optional[GameMetadata] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "game_id": self.game_id,
            "status": self.status.value,
            "pnl": round(self.pnl, 2),
            "roi": round(self.roi * 100, 2),
            "legs_filled": self.legs_filled,
            "allocated_capital": round(self.allocated_capital, 2),
            "contracts": round(self.contracts, 2),
            "fill_price_a": self.fill_price_a,
            "fill_price_b": self.fill_price_b,
            "exit_price": self.exit_price,
            "first_leg": self.first_leg,
            "stop_loss_triggered": self.stop_loss_triggered,
        }
        if self.metadata and self.metadata.matchup:
            data.update({
                "team_a": self.metadata.team_a,
                "team_b": self.metadata.team_b,
                "combined_pace": self.metadata.matchup.combined_pace,
                "net_rating_diff": self.metadata.matchup.net_rating_diff,
                "combined_3pa": self.metadata.matchup.combined_3pa,
                "volatility_score": self.metadata.matchup.volatility_score,
                "passed_filter": self.metadata.filter_result.passed if self.metadata.filter_result else None
            })
        return data
