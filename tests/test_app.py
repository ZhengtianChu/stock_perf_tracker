import os
import tempfile
import unittest
from pathlib import Path

import app


class AppTests(unittest.TestCase):
    def test_rmb_money_format_uses_valid_yen_symbol(self):
        previous_currency = getattr(app.CURRENCY_CONTEXT, "value", None)
        try:
            app.CURRENCY_CONTEXT.value = "rmb"
            self.assertEqual(app.money(100), "\u00a5720.00")
            self.assertEqual(app.compact_currency(1000), "\u00a57.20K")
            self.assertNotIn("\u00ef\u00bf\u00a5", app.money(100))
        finally:
            if previous_currency is None:
                if hasattr(app.CURRENCY_CONTEXT, "value"):
                    del app.CURRENCY_CONTEXT.value
            else:
                app.CURRENCY_CONTEXT.value = previous_currency

    def test_portfolio_return_method_does_not_force_full_page_submit(self):
        controls = app.portfolio_return_method_options("time", "all")
        self.assertIn('id="portfolio-return-method"', controls)
        self.assertIn('value="time" selected', controls)
        self.assertNotIn("this.form.submit()", controls)

    def test_sell_put_calculation(self):
        result = app.derived({"contracts": 2, "premium_in": 1.5, "exit_premium": .5,
                              "stock_pnl": 20, "fees": 2, "status": "Closed",
                              "open_date": "2026-08-01", "close_date": "2026-08-11",
                              "capital_used": 5000, "strike": 25, "long_put_strike": None})
        self.assertEqual(result["net_pnl"], 218)
        self.assertAlmostEqual(result["roc"], .0436)
        self.assertEqual(result["days_held"], 10)
        self.assertEqual(result["outcome"], "Win")

    def test_expired_blank_exit_is_zero(self):
        result = app.derived({"contracts": 1, "premium_in": .75, "exit_premium": None,
                              "stock_pnl": 0, "fees": 0, "status": "Expired",
                              "open_date": "2026-08-01", "close_date": "2026-08-08",
                              "capital_used": 4000, "strike": 40, "long_put_strike": None})
        self.assertEqual(result["net_pnl"], 75)

    def test_credit_spread_risk(self):
        result = app.derived({"contracts": 3, "premium_in": 1.2, "exit_premium": .4,
                              "stock_pnl": 0, "fees": 0, "status": "Closed",
                              "open_date": "2026-08-01", "close_date": "2026-08-04",
                              "capital_used": 1140, "strike": 50, "long_put_strike": 45})
        self.assertEqual(result["spread_width"], 5)
        self.assertAlmostEqual(result["max_loss"], 1140)
        self.assertAlmostEqual(result["net_pnl"], 240)

    def test_iron_condor_validation_and_risk(self):
        form = {
            "ticker": "SPY", "strategy": "Iron Condor", "status": "Open",
            "open_date": "2026-10-21", "expiration": "2026-11-20",
            "contracts": "2", "long_put_strike": "560", "strike": "565",
            "short_call_strike": "590", "long_call_strike": "600",
            "premium_in": "2.25", "capital_used": "1550",
        }
        data, error = app.validate(form)
        self.assertEqual(error, "")
        self.assertEqual(
            [data[key] for key in ("long_put_strike", "strike", "short_call_strike", "long_call_strike")],
            [560, 565, 590, 600],
        )
        result = app.derived(data)
        self.assertEqual(result["spread_width"], 10)
        self.assertEqual(result["max_loss"], 1550)

        invalid = dict(form, short_call_strike="564")
        _, error = app.validate(invalid)
        self.assertIn("long put < short put < short call < long call", error)

    def test_portfolio_holdings_pie_groups_smaller_positions(self):
        holdings = [
            {"ticker": ticker, "market_value": value}
            for ticker, value in (
                ("AAPL", 6000), ("MSFT", 5000), ("NVDA", 4000),
                ("GOOGL", 3000), ("META", 2000), ("RKLB", 1000),
            )
        ]
        chart = app.portfolio_holdings_pie(holdings)
        self.assertIn("Cash stock and option holdings by market value", chart)
        self.assertIn("AAPL", chart)
        self.assertIn("Other", chart)
        self.assertNotIn("RKLB", chart)

    def test_dashboard_defaults_exclude_fidelity_and_external_brokers(self):
        brokers, _books = app.dashboard_filter_values({})
        self.assertNotIn("Fidelity", brokers)
        self.assertNotIn("External", brokers)
        self.assertIn("Robinhood", brokers)

        explicit_brokers, _books = app.dashboard_filter_values({
            "dash_broker_filter": ["1"],
            "dash_broker": ["Fidelity"],
        })
        self.assertEqual(explicit_brokers, ["Fidelity"])

        explicit_external, _books = app.dashboard_filter_values({
            "dash_broker_filter": ["1"],
            "dash_broker": ["External"],
        })
        self.assertEqual(explicit_external, ["External"])

    def test_default_holdings_exclude_fidelity(self):
        holdings = [
            {"ticker": "RKLB", "broker_source": "Robinhood", "notes": ""},
            {"ticker": "HPE", "broker_source": "Fidelity", "notes": ""},
            {"ticker": "US LG CAP EQ INDEX", "broker_source": "Fidelity 401k", "notes": "Fidelity HPE 401(k)"},
        ]
        self.assertEqual(
            [holding["ticker"] for holding in app.exclude_fidelity_holdings(holdings)],
            ["RKLB"],
        )
        self.assertEqual(
            [holding["ticker"] for holding in app.filter_holdings_by_brokers(holdings, ["Fidelity"])],
            ["HPE", "US LG CAP EQ INDEX"],
        )
        self.assertEqual(
            [holding["ticker"] for holding in app.filter_holdings_by_brokers(holdings, ["Robinhood"])],
            ["RKLB"],
        )

    def test_weekly_win_rates_group_by_monday(self):
        rates = app.weekly_win_rates([
            (app.date(2026, 10, 26), 100),
            (app.date(2026, 10, 28), -50),
            (app.date(2026, 11, 1), 20),
            (app.date(2026, 11, 2), -10),
        ])
        self.assertEqual(rates[app.date(2026, 10, 26)], 2 / 3)
        self.assertEqual(rates[app.date(2026, 11, 2)], 0)

    def test_portfolio_axis_only_scales_selected_benchmarks(self):
        original_fetch = app.fetch_benchmark_series
        try:
            app.fetch_benchmark_series = lambda _symbol, _start, _end: [
                (app.date(2026, 1, 1), 100),
                (app.date(2026, 1, 2), 200),
            ]
            points = [
                {"date": "2026-01-01", "value": 100},
                {"date": "2026-01-02", "value": 120},
            ]
            portfolio_only = app.portfolio_overview_chart(points)
            with_sp = app.portfolio_overview_chart(points, active_benchmarks={"sp"})
            self.assertIn("$121.60", portfolio_only)
            self.assertNotIn("$208.00", portfolio_only)
            self.assertIn("$208.00", with_sp)
        finally:
            app.fetch_benchmark_series = original_fetch

    def test_portfolio_chart_uses_red_below_profit_baseline(self):
        chart = app.portfolio_overview_chart(
            [
                {"date": "2026-01-01", "value": 100},
                {"date": "2026-01-02", "value": 90},
            ],
            show_benchmarks=False,
        )
        self.assertIn('id="portfolioProfitFill"', chart)
        self.assertIn('id="portfolioLineGradient"', chart)
        self.assertIn('stop-color="#f23645"', chart)
        self.assertIn('class="portfolio-profit-baseline"', chart)
        self.assertIn('class="portfolio-dot negative"', chart)

    def test_symbol_2027_valuation_panel_has_three_scenarios(self):
        original_quote = app.fetch_market_quote
        try:
            app.fetch_market_quote = lambda _ticker, _label=None: {"price": 100}
            panel = app.symbol_2027_valuation_panel("RKLB")
            self.assertIn("2027 Year-End Valuation", panel)
            self.assertIn('data-current-price="100.0"', panel)
            self.assertIn('data-valuation-result="bear"', panel)
            self.assertIn('data-valuation-result="base"', panel)
            self.assertIn('data-valuation-result="bull"', panel)
        finally:
            app.fetch_market_quote = original_quote

    def test_all_trades_sorting_by_net_pnl_desc(self):
        original_db_path = app.DB_PATH
        original_data_dir = app.DATA_DIR
        original_bootstrap_path = app.BOOTSTRAP_PATH
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                app.DATA_DIR = Path(tmpdir)
                app.DB_PATH = app.DATA_DIR / "trades.db"
                app.BOOTSTRAP_PATH = app.DATA_DIR / "missing_bootstrap.json"
                app.init_db()
                rows = [
                    {"ticker": "AAPL", "strategy": "Sell Put", "status": "Closed", "open_date": "2026-08-01", "close_date": "2026-08-11", "contracts": 1, "premium_in": 1.5, "exit_premium": 0.5, "stock_pnl": 0, "fees": 0, "capital_used": 1000},
                    {"ticker": "MSFT", "strategy": "Sell Put", "status": "Closed", "open_date": "2026-08-02", "close_date": "2026-08-12", "contracts": 1, "premium_in": 3.0, "exit_premium": 1.0, "stock_pnl": 0, "fees": 0, "capital_used": 2000},
                    {"ticker": "NVDA", "strategy": "Sell Put", "status": "Closed", "open_date": "2026-08-03", "close_date": "2026-08-13", "contracts": 1, "premium_in": 1.0, "exit_premium": 0.5, "stock_pnl": 0, "fees": 0, "capital_used": 500},
                ]
                with app.closing(app.db()) as connection:
                    connection.executemany(
                        "INSERT INTO trades (ticker, strategy, status, open_date, close_date, contracts, premium_in, exit_premium, stock_pnl, fees, capital_used, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                        [
                            (row["ticker"], row["strategy"], row["status"], row["open_date"], row["close_date"], row["contracts"], row["premium_in"], row["exit_premium"], row["stock_pnl"], row["fees"], row["capital_used"])
                            for row in rows
                        ],
                    )
                    connection.commit()
                trades = app.all_trades(sort_by="net_pnl", sort_dir="desc")
                self.assertEqual([trade["ticker"] for trade in trades[:3]], ["MSFT", "AAPL", "NVDA"])
        finally:
            app.DB_PATH = original_db_path
            app.DATA_DIR = original_data_dir
            app.BOOTSTRAP_PATH = original_bootstrap_path

    def test_symbol_summary_totals_and_pl_percent(self):
        trades = [
            app.derived({"ticker": "MSTR", "strategy": "Sell Put", "status": "Closed", "open_date": "2026-08-01", "close_date": "2026-08-11", "contracts": 1, "premium_in": 2.0, "exit_premium": 0.5, "stock_pnl": 0, "fees": 0, "capital_used": 1000, "net_pnl": 150}),
            app.derived({"ticker": "MSTR", "strategy": "Covered Call", "status": "Closed", "open_date": "2026-08-01", "close_date": "2026-08-13", "contracts": 1, "premium_in": 1.5, "exit_premium": 0.5, "stock_pnl": 0, "fees": 0, "capital_used": 1500, "net_pnl": 100}),
            app.derived({"ticker": "COIN", "strategy": "Sell Put", "status": "Closed", "open_date": "2026-08-01", "close_date": "2026-08-10", "contracts": 1, "premium_in": 1.0, "exit_premium": 0.5, "stock_pnl": 0, "fees": 0, "capital_used": 500, "net_pnl": 50}),
        ]
        summary = app.symbol_summary(trades)
        self.assertEqual(summary[0]["ticker"], "MSTR")
        self.assertEqual(summary[0]["total_pnl"], 250)
        self.assertAlmostEqual(summary[0]["pl_pct"], 0.1)
        self.assertEqual(summary[1]["ticker"], "COIN")
        self.assertEqual(summary[1]["total_pnl"], 50)


if __name__ == "__main__": unittest.main()
