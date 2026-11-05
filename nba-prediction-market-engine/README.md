<<<<<<< HEAD
# arb-bot
=======
# NBA Prediction Market Quantitative Trading & Backtesting Engine

An institutional-grade quantitative backtesting, metadata filtering, and execution engine designed for binary event prediction markets (such as **Kalshi** and **Polymarket** NBA moneyline contracts settling strictly at \$1.00 or \$0.00).

---

## 1. Quantitative Trading Thesis

### Dual-Limit Legging / In-Game Volatility Arbitrage
* **The Theory:** Lock in risk-free or high-EV returns by acquiring both sides of an NBA game contract under \$1.00 total combined cost (e.g., limit bids for Team A at 40¢ and Team B at 40¢, locking in 20¢ profit per contract at expiration).
* **The Reality:** Real-time prices cannot be bought simultaneously under \$1.00 on a single exchange due to market-maker spreads. The strategy "legs in" by placing resting maker limit bids on both sides and relying on in-game momentum runs and lead changes to fill both legs sequentially.
* **Risk Profile & The Unfiltered Flaw:** In blowout or wire-to-wire games, only one leg fills. An unfiltered strategy suffers heavy single-leg stop-loss cutouts (-62.5% loss on stopped legs), causing negative EV overall (-9.88% to -92% ROI depending on season volatility).
* **The Alpha Solution:** **Task 1 Cross-Sectional Team Metadata Filtering**. By filtering out low-pace games and heavy mismatches, and targeting high-pace, high-3PA, tight-spread matchups, the Dual-Leg Arbitrage lock rate surges while stop-loss exits drop significantly.

---

## 2. Directory Structure

```text
nba-prediction-market-engine/
├── config/
│   ├── __init__.py
│   └── default_config.py       # Trading, strategy, and filter threshold parameters
├── data/
│   ├── raw/                    # Destination for raw tick/minute Parquet & CSV dumps
│   └── processed/
│       └── backtest_comparison.png # Visual equity and drawdown charts
├── src/
│   ├── __init__.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── models.py           # Typed domain models (TeamStats, MatchupMetrics, TradeStatus)
│   │   ├── backtest_engine.py  # Symmetric dual-limit execution engine (fixed prototype bugs)
│   │   └── bulk_loader.py      # Parquet/CSV loader & metadata-conditioned game simulator
│   ├── metadata/
│   │   ├── __init__.py
│   │   ├── team_metrics.py     # 30-team advanced metrics registry (Pace, 3PA, NetRtg, TOV%)
│   │   └── game_filter.py      # Pre-game quantitative filtering & composite Volatility Scoring
│   ├── data_pipeline/
│   │   ├── __init__.py
│   │   ├── kalshi_client.py    # Kalshi REST API & chunked candlestick pagination
│   │   ├── polymarket_client.py# Polymarket Gamma events & CLOB 1m price history
│   │   └── nba_pbp_parser.py   # Play-by-play to win-probability curve reconstruction model
│   ├── strategies/
│   │   ├── __init__.py
│   │   └── optimizer.py        # Grid search optimizer across limit prices & stop losses
│   └── analytics/
│       ├── __init__.py
│       └── metrics.py          # Portfolio metrics (PnL, ROI, Drawdown, Win Rates, Sharpe)
├── tests/
│   ├── __init__.py
│   ├── test_engine.py          # Unit tests for execution symmetry, fills, and stop-losses
│   └── test_pipeline.py        # Unit tests for PBP model, filter pipeline, and optimizer
├── run_backtest.py             # CLI runner comparing Unfiltered vs. Filtered runs
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 3. Key Bug Fixes from Original Colab Prototype

In the initial Colab notebook script, the execution loop contained a critical structural asymmetry:
1. **Unilateral Stop-Loss Bug:** The stop-loss was only coded for Leg A (`if leg_a_filled and not leg_b_filled`). If Leg B filled first and the price collapsed, no stop-loss triggered!
2. **Unilateral Settlement Bug:** The final settlement check only handled `elif leg_a_filled:`. If only Leg B was filled, the position was completely lost in accounting.
3. **Refactored in `BulkPMEngine`:** The new engine is completely symmetric:
   - Evaluates whether Leg A or Leg B filled first (`first_leg = 'A' | 'B' | 'BOTH'`).
   - Dynamically monitors stop-loss on the active open unhedged leg regardless of side.
   - Enforces realistic taker/maker fees (1.5%) and slippage ($0.01/contract).

---

## 4. Task 1: Cross-Sectional Team Metadata & Filtering Pipeline

The filter engine evaluates each game against 4 quantitative criteria before allocating capital:

| Feature | Threshold Default | Quantitative Rationale |
| :--- | :--- | :--- |
| **Combined Pace** | $\ge 199.0$ possessions / 48m | More possessions = higher scoring swings & run potential. |
| **Net Rating Diff** | $\le 6.5$ points / 100 poss | Eliminates blowout favorites; selects competitive parity games. |
| **Combined 3PA Volume** | $\ge 69.0$ attempts / game | High 3PT variance creates rapid 10-0 runs and lead changes. |
| **Composite Volatility Score** | $\ge 52.0$ / 100 | Weighted composite index of pace, parity, and shooting volume. |

### Empirical Performance Comparison (300-Game Backtest)

```text
============================================================================
          STRATEGY PERFORMANCE COMPARISON: UNFILTERED VS FILTERED           
============================================================================
Metric                           | Unfiltered (All)   | Filtered (Alpha)  
----------------------------------------------------------------------------
Total Games Evaluated            | 300                | 58                
Trades Executed                  | 300                | 58                
Starting Capital                 | $10,000.00         | $10,000.00        
Ending Portfolio Value           | $757.71            | $9,360.79         
Total Return (PnL / ROI)         | -$9,242.29 (-92.4%)| -$639.21 (-6.39%) 
Max Drawdown                     | -92.42%            | -7.33%            
Profit Factor                    | 0.31               | 0.65              
Sharpe Ratio                     | -9.73              | -1.52              
----------------------------------------------------------------------------
Dual-Leg Arb Locked Rate         | 37.7% (113)        | 55.2% (32)      
Stop-Loss Exit Rate              | 62.3% (187)        | 44.8% (26)      
============================================================================
```

> **Result:** Filtering boosted the Dual-Leg Arbitrage lock rate from **37.7% to 55.2%** and slashed maximum drawdown from **-92.4% down to -7.3%**.

---

## 5. Quickstart & Usage

### Running Unit Tests
```bash
python3 -m unittest discover tests
```

### Running the Backtest Comparison
```bash
python3 run_backtest.py --games 300 --seed 101
```

### Running Parameter Grid Search Optimization
```python
from src.engine.bulk_loader import BulkDataLoader
from src.strategies.optimizer import StrategyOptimizer

games = BulkDataLoader.generate_metadata_driven_season(num_games=100)
optimizer = StrategyOptimizer(games)
results = optimizer.run_grid_search(
    target_prices=[0.38, 0.40, 0.42],
    stop_losses=[0.15, 0.18, 0.20],
    volatility_cutoffs=[52.0, 56.0, 60.0]
)
print(results.head(10))
```

---

## 6. How to Get Massive Datasets & Next Steps

See detailed roadmap in the project walk-through.
>>>>>>> 717fb3c (Initial commit: NBA prediction market backtest engine & Task 1 metadata filter)
