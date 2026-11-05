"""
Cross-Sectional Matchup Filtering Engine for NBA In-Game Volatility Arbitrage.
"""

from typing import List, Tuple, Dict, Optional
from config.default_config import FilterConfig
from src.engine.models import MatchupMetrics, FilterEvaluation, GameMetadata
from src.metadata.team_metrics import TeamMetricsRegistry


class GameFilterPipeline:
    """
    Evaluates pre-game team metadata against volatility thresholds.
    Filters out one-sided mismatches and slow-paced games to avoid single-leg stop-losses.
    """

    def __init__(self, config: Optional[FilterConfig] = None, registry: Optional[TeamMetricsRegistry] = None):
        self.config = config or FilterConfig()
        self.registry = registry or TeamMetricsRegistry()

    def evaluate_matchup(self, team_a: str, team_b: str) -> FilterEvaluation:
        """Evaluates whether two teams satisfy the quantitative volatility conditions."""
        matchup = self.registry.compute_matchup_metrics(team_a, team_b)
        if not matchup:
            return FilterEvaluation(
                passed=False,
                rejection_reasons=[f"Missing metrics for teams {team_a} or {team_b}"],
                matchup=None
            )

        return self.evaluate_metrics(matchup)

    def evaluate_metrics(self, matchup: MatchupMetrics) -> FilterEvaluation:
        """Applies filter rules directly to a MatchupMetrics object."""
        reasons: List[str] = []

        # 1. Combined Pace Check
        if matchup.combined_pace < self.config.min_combined_pace:
            reasons.append(
                f"Low Pace: Combined pace {matchup.combined_pace:.1f} < threshold {self.config.min_combined_pace:.1f}"
            )

        # 2. Net Rating Parity Check (Avoid blowouts)
        if matchup.net_rating_diff > self.config.max_net_rating_diff:
            reasons.append(
                f"Mismatch / Blowout Risk: Net Rating diff {matchup.net_rating_diff:.1f} > max allowed {self.config.max_net_rating_diff:.1f}"
            )

        # 3. 3-Point Attempt Volume Check (High 3PA drives scoring runs)
        if matchup.combined_3pa < self.config.min_combined_3pa:
            reasons.append(
                f"Low 3PA Volume: Combined 3PA {matchup.combined_3pa:.1f} < threshold {self.config.min_combined_3pa:.1f}"
            )

        # 4. Composite Volatility Score Check
        if matchup.volatility_score < self.config.min_volatility_score:
            reasons.append(
                f"Low Volatility Score: Score {matchup.volatility_score:.1f} < required {self.config.min_volatility_score:.1f}"
            )

        passed = len(reasons) == 0
        return FilterEvaluation(
            passed=passed,
            rejection_reasons=reasons,
            matchup=matchup
        )

    def filter_game_slate(self, slate: List[Tuple[str, str]]) -> Dict[str, List[Dict]]:
        """
        Filters a list of game matchups scheduled for a date.
        Returns accepted games and rejected games with detailed rationales.
        """
        accepted = []
        rejected = []

        for team_a, team_b in slate:
            res = self.evaluate_matchup(team_a, team_b)
            summary = {
                "matchup": f"{team_a} vs {team_b}",
                "passed": res.passed,
                "volatility_score": res.matchup.volatility_score if res.matchup else 0.0,
                "combined_pace": res.matchup.combined_pace if res.matchup else 0.0,
                "net_rating_diff": res.matchup.net_rating_diff if res.matchup else 0.0,
                "combined_3pa": res.matchup.combined_3pa if res.matchup else 0.0,
                "reasons": res.rejection_reasons
            }
            if res.passed:
                accepted.append(summary)
            else:
                rejected.append(summary)

        # Sort accepted by highest volatility score
        accepted = sorted(accepted, key=lambda x: x["volatility_score"], reverse=True)
        return {"accepted": accepted, "rejected": rejected}
