"""
NBA Team Statistics and Matchup Feature Engineering.
Provides baseline team metrics for all 30 NBA teams and computes matchup volatility profiles.
"""

from typing import Dict, Optional, List
import json
import os
from src.engine.models import TeamStats, MatchupMetrics


# Pre-compiled multi-season calibrated baseline metrics for all 30 NBA teams.
# Reflects realistic ranges: Pace (96-104), NetRtg (-12.0 to +11.5), 3PA (29 to 44), TOV% (11.5 to 15.5)
NBA_TEAMS_DATA: Dict[str, Dict] = {
    "BOS": {"team_name": "Boston Celtics", "pace": 98.2, "offensive_rating": 122.2, "defensive_rating": 110.6, "net_rating": 11.6, "three_point_att": 42.5, "three_point_pct": 0.388, "turnover_pct": 11.9, "assist_ratio": 19.8, "conference": "East"},
    "IND": {"team_name": "Indiana Pacers", "pace": 103.5, "offensive_rating": 120.5, "defensive_rating": 117.6, "net_rating": 2.9, "three_point_att": 37.8, "three_point_pct": 0.375, "turnover_pct": 12.9, "assist_ratio": 21.6, "conference": "East"},
    "OKC": {"team_name": "Oklahoma City Thunder", "pace": 101.1, "offensive_rating": 118.3, "defensive_rating": 111.0, "net_rating": 7.3, "three_point_att": 36.2, "three_point_pct": 0.389, "turnover_pct": 12.4, "assist_ratio": 19.1, "conference": "West"},
    "DEN": {"team_name": "Denver Nuggets", "pace": 97.4, "offensive_rating": 117.8, "defensive_rating": 112.3, "net_rating": 5.5, "three_point_att": 31.2, "three_point_pct": 0.374, "turnover_pct": 12.3, "assist_ratio": 21.2, "conference": "West"},
    "MIN": {"team_name": "Minnesota Timberwolves", "pace": 98.1, "offensive_rating": 114.6, "defensive_rating": 108.4, "net_rating": 6.2, "three_point_att": 33.7, "three_point_pct": 0.387, "turnover_pct": 14.1, "assist_ratio": 18.9, "conference": "West"},
    "LAC": {"team_name": "LA Clippers", "pace": 97.8, "offensive_rating": 117.9, "defensive_rating": 114.5, "net_rating": 3.4, "three_point_att": 33.2, "three_point_pct": 0.381, "turnover_pct": 13.0, "assist_ratio": 18.6, "conference": "West"},
    "DAL": {"team_name": "Dallas Mavericks", "pace": 100.8, "offensive_rating": 117.0, "defensive_rating": 114.9, "net_rating": 2.1, "three_point_att": 39.5, "three_point_pct": 0.369, "turnover_pct": 12.5, "assist_ratio": 18.2, "conference": "West"},
    "NYK": {"team_name": "New York Knicks", "pace": 96.0, "offensive_rating": 117.3, "defensive_rating": 112.4, "net_rating": 4.9, "three_point_att": 36.9, "three_point_pct": 0.369, "turnover_pct": 12.9, "assist_ratio": 17.8, "conference": "East"},
    "MIL": {"team_name": "Milwaukee Bucks", "pace": 100.4, "offensive_rating": 117.6, "defensive_rating": 115.0, "net_rating": 2.6, "three_point_att": 37.1, "three_point_pct": 0.373, "turnover_pct": 12.8, "assist_ratio": 18.9, "conference": "East"},
    "PHX": {"team_name": "Phoenix Suns", "pace": 98.7, "offensive_rating": 116.8, "defensive_rating": 113.7, "net_rating": 3.1, "three_point_att": 32.6, "three_point_pct": 0.382, "turnover_pct": 14.9, "assist_ratio": 19.1, "conference": "West"},
    "NOP": {"team_name": "New Orleans Pelicans", "pace": 98.4, "offensive_rating": 116.5, "defensive_rating": 111.9, "net_rating": 4.6, "three_point_att": 32.6, "three_point_pct": 0.378, "turnover_pct": 13.2, "assist_ratio": 19.3, "conference": "West"},
    "ORL": {"team_name": "Orlando Magic", "pace": 97.2, "offensive_rating": 112.9, "defensive_rating": 110.8, "net_rating": 2.1, "three_point_att": 31.3, "three_point_pct": 0.352, "turnover_pct": 14.7, "assist_ratio": 17.5, "conference": "East"},
    "CLE": {"team_name": "Cleveland Cavaliers", "pace": 97.6, "offensive_rating": 115.2, "defensive_rating": 112.7, "net_rating": 2.5, "three_point_att": 36.8, "three_point_pct": 0.367, "turnover_pct": 13.6, "assist_ratio": 19.5, "conference": "East"},
    "GSW": {"team_name": "Golden State Warriors", "pace": 100.3, "offensive_rating": 116.9, "defensive_rating": 114.5, "net_rating": 2.4, "three_point_att": 38.9, "three_point_pct": 0.380, "turnover_pct": 14.1, "assist_ratio": 20.8, "conference": "West"},
    "SAC": {"team_name": "Sacramento Kings", "pace": 100.1, "offensive_rating": 116.2, "defensive_rating": 114.4, "net_rating": 1.8, "three_point_att": 39.3, "three_point_pct": 0.366, "turnover_pct": 13.2, "assist_ratio": 20.1, "conference": "West"},
    "MIA": {"team_name": "Miami Heat", "pace": 96.9, "offensive_rating": 113.3, "defensive_rating": 111.5, "net_rating": 1.8, "three_point_att": 33.7, "three_point_pct": 0.370, "turnover_pct": 12.8, "assist_ratio": 18.5, "conference": "East"},
    "PHI": {"team_name": "Philadelphia 76ers", "pace": 98.5, "offensive_rating": 116.2, "defensive_rating": 113.0, "net_rating": 3.2, "three_point_att": 33.5, "three_point_pct": 0.363, "turnover_pct": 12.0, "assist_ratio": 18.0, "conference": "East"},
    "LAL": {"team_name": "Los Angeles Lakers", "pace": 101.4, "offensive_rating": 115.4, "defensive_rating": 114.8, "net_rating": 0.6, "three_point_att": 31.4, "three_point_pct": 0.377, "turnover_pct": 13.4, "assist_ratio": 20.2, "conference": "West"},
    "HOU": {"team_name": "Houston Rockets", "pace": 99.3, "offensive_rating": 113.7, "defensive_rating": 112.8, "net_rating": 0.9, "three_point_att": 35.2, "three_point_pct": 0.352, "turnover_pct": 12.7, "assist_ratio": 17.6, "conference": "West"},
    "CHI": {"team_name": "Chicago Bulls", "pace": 97.4, "offensive_rating": 114.0, "defensive_rating": 115.7, "net_rating": -1.7, "three_point_att": 32.1, "three_point_pct": 0.358, "turnover_pct": 12.2, "assist_ratio": 17.8, "conference": "East"},
    "ATL": {"team_name": "Atlanta Hawks", "pace": 101.5, "offensive_rating": 116.4, "defensive_rating": 118.4, "net_rating": -2.0, "three_point_att": 37.7, "three_point_pct": 0.364, "turnover_pct": 13.4, "assist_ratio": 18.7, "conference": "East"},
    "BKN": {"team_name": "Brooklyn Nets", "pace": 97.8, "offensive_rating": 112.4, "defensive_rating": 115.4, "net_rating": -3.0, "three_point_att": 36.8, "three_point_pct": 0.362, "turnover_pct": 13.0, "assist_ratio": 18.4, "conference": "East"},
    "UTA": {"team_name": "Utah Jazz", "pace": 100.9, "offensive_rating": 114.4, "defensive_rating": 119.6, "net_rating": -5.2, "three_point_att": 36.5, "three_point_pct": 0.354, "turnover_pct": 15.7, "assist_ratio": 19.8, "conference": "West"},
    "MEM": {"team_name": "Memphis Grizzlies", "pace": 98.7, "offensive_rating": 106.8, "defensive_rating": 113.7, "net_rating": -6.9, "three_point_att": 38.4, "three_point_pct": 0.349, "turnover_pct": 15.1, "assist_ratio": 18.0, "conference": "West"},
    "TOR": {"team_name": "Toronto Raptors", "pace": 99.8, "offensive_rating": 111.8, "defensive_rating": 118.1, "net_rating": -6.3, "three_point_att": 34.1, "three_point_pct": 0.347, "turnover_pct": 14.1, "assist_ratio": 20.3, "conference": "East"},
    "SAS": {"team_name": "San Antonio Spurs", "pace": 101.8, "offensive_rating": 109.3, "defensive_rating": 115.6, "net_rating": -6.3, "three_point_att": 36.1, "three_point_pct": 0.347, "turnover_pct": 15.1, "assist_ratio": 21.3, "conference": "West"},
    "POR": {"team_name": "Portland Trail Blazers", "pace": 98.1, "offensive_rating": 107.6, "defensive_rating": 116.6, "net_rating": -9.0, "three_point_att": 31.7, "three_point_pct": 0.345, "turnover_pct": 15.2, "assist_ratio": 16.7, "conference": "West"},
    "CHA": {"team_name": "Charlotte Hornets", "pace": 97.9, "offensive_rating": 108.6, "defensive_rating": 119.2, "net_rating": -10.6, "three_point_att": 35.5, "three_point_pct": 0.355, "turnover_pct": 13.8, "assist_ratio": 17.6, "conference": "East"},
    "WAS": {"team_name": "Washington Wizards", "pace": 103.1, "offensive_rating": 110.2, "defensive_rating": 118.9, "net_rating": -8.7, "three_point_att": 34.0, "three_point_pct": 0.348, "turnover_pct": 14.0, "assist_ratio": 19.5, "conference": "East"},
    "DET": {"team_name": "Detroit Pistons", "pace": 99.7, "offensive_rating": 109.0, "defensive_rating": 118.0, "net_rating": -9.0, "three_point_att": 31.7, "three_point_pct": 0.348, "turnover_pct": 15.3, "assist_ratio": 18.3, "conference": "East"}
}


class TeamMetricsRegistry:
    """Registry maintaining active team metrics and computing matchup characteristics."""

    def __init__(self, custom_data: Optional[Dict[str, Dict]] = None):
        raw_dict = custom_data or NBA_TEAMS_DATA
        self.teams: Dict[str, TeamStats] = {}
        for abbr, stats in raw_dict.items():
            self.teams[abbr] = TeamStats(
                team_id=abbr,
                team_name=stats.get("team_name", abbr),
                abbreviation=abbr,
                pace=stats["pace"],
                offensive_rating=stats["offensive_rating"],
                defensive_rating=stats["defensive_rating"],
                net_rating=stats["net_rating"],
                three_point_att=stats["three_point_att"],
                three_point_pct=stats["three_point_pct"],
                turnover_pct=stats["turnover_pct"],
                assist_ratio=stats["assist_ratio"],
                conference=stats.get("conference", "Unknown"),
            )

    def get_team(self, abbreviation: str) -> Optional[TeamStats]:
        return self.teams.get(abbreviation.upper())

    def list_teams(self) -> List[str]:
        return sorted(list(self.teams.keys()))

    def compute_matchup_metrics(self, team_a_abbr: str, team_b_abbr: str) -> Optional[MatchupMetrics]:
        stats_a = self.get_team(team_a_abbr)
        stats_b = self.get_team(team_b_abbr)

        if not stats_a or not stats_b:
            return None

        combined_pace = stats_a.pace + stats_b.pace
        net_rating_spread = stats_a.net_rating - stats_b.net_rating
        net_rating_diff = abs(net_rating_spread)
        combined_3pa = stats_a.three_point_att + stats_b.three_point_att
        combined_tov_pct = stats_a.turnover_pct + stats_b.turnover_pct

        # Composite Volatility Score (0.0 to 100.0)
        # Weights:
        # 1. Pace Component: Target > 200 (Score 0-35)
        # 2. Parity Component: Target small diff <= 5 (Score 0-35)
        # 3. 3PA Component: Target > 72 (Score 0-20)
        # 4. Turnover Component: High turnover -> unpredictability (Score 0-10)

        pace_score = min(35.0, max(0.0, (combined_pace - 192.0) / (208.0 - 192.0) * 35.0))
        parity_score = min(35.0, max(0.0, (18.0 - net_rating_diff) / 18.0 * 35.0))
        three_pt_score = min(20.0, max(0.0, (combined_3pa - 62.0) / (85.0 - 62.0) * 20.0))
        tov_score = min(10.0, max(0.0, (combined_tov_pct - 24.0) / (31.0 - 24.0) * 10.0))

        volatility_score = round(pace_score + parity_score + three_pt_score + tov_score, 1)

        return MatchupMetrics(
            combined_pace=round(combined_pace, 2),
            net_rating_diff=round(net_rating_diff, 2),
            net_rating_spread=round(net_rating_spread, 2),
            combined_3pa=round(combined_3pa, 2),
            combined_tov_pct=round(combined_tov_pct, 2),
            volatility_score=volatility_score
        )

    def export_to_json(self, file_path: str):
        payload = {k: v.to_dict() for k, v in self.teams.items()}
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load_from_json(cls, file_path: str) -> "TeamMetricsRegistry":
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls(custom_data=data)
