from datetime import datetime, timezone

from agents.dca_agent import DcaAgent
from agents.pattern_agent import PatternAgent
from cloud_sync import sync
from execution import router
from market import atr
import database as db


WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
POSITION_RISK = 0.08
ATR_SL_MULT = 1.6
ATR_TP_MULT = 2.8
MAX_ATR_PCT = 3.5


class MasterOrchestrator:
    def __init__(self, market):
        self.market = market
        self.pattern = PatternAgent()
        self.dca = DcaAgent()
        self.running = True
        self.last_cycle = None
        self.last_signals = []

    def cycle(self):
        config = db.get_config()
        secrets = db.get_secrets()
        account = self._roll_daily_equity()

        if secrets.get("cloud_sync_enabled"):
            sync.pull_config()
            config = db.get_config()

        kill = bool(config["global_kill_switch"])
        mode = config["execution_mode"]
        max_dd = float(config["max_daily_drawdown"])

        self.market.tick(secrets.get("exchange_id"), WATCHLIST)
        self._mark_to_market()
        account = db.get_account()
        daily_pnl_pct = self._daily_pnl_pct(account)

        if daily_pnl_pct <= -max_dd and not kill:
            db.update_config(global_kill_switch=True)
            kill = True
            db.insert_agent_log(
                "RISK",
                f"Daily drawdown {daily_pnl_pct:.2f}% hit max {max_dd}%. Kill switch LOCKED.",
                "WARN",
            )
            db.insert_trade_log(
                "PORTFOLIO",
                "STANDBY",
                f"Global kill switch engaged. Daily drawdown {daily_pnl_pct:.2f}%.",
                mode,
                profit_loss=daily_pnl_pct,
                agent="RISK",
                score=0,
            )
            if secrets.get("cloud_sync_enabled"):
                sync.push_config()

        positions = {p["asset_pair"]: p for p in db.open_positions()}
        signals = []

        for pair in WATCHLIST:
            candles = self.market.ohlcv(pair)
            pattern = self.pattern.analyze(pair, candles)
            atr_v = pattern.get("atr") or atr(candles)
            dca = self.dca.analyze(pair, candles, positions.get(pair), atr_v)
            decision = self._synthesize(pair, pattern, dca, atr_v, kill, mode, account, positions.get(pair), secrets)
            signals.append({"pattern": pattern, "dca": dca, "decision": decision})

        self.last_cycle = datetime.now(timezone.utc).isoformat()
        self.last_signals = signals
        self._mark_to_market()
        account = db.get_account()
        daily_pnl = self._daily_pnl_pct(account)
        drawdown = self._drawdown(account)
        db.insert_equity(account["equity"], daily_pnl, drawdown)

        if secrets.get("cloud_sync_enabled"):
            self._sync_cycle(daily_pnl, drawdown)
        return signals

    def _sync_cycle(self, daily_pnl, drawdown):
        account = db.get_account()
        sync.push_config()
        sync.push_equity({"equity": account["equity"], "daily_pnl": daily_pnl, "drawdown": drawdown, "mode": db.get_config()["execution_mode"]})
        trades = db.list_trade_logs(5)
        if trades:
            sync.push_batch(trades)
        logs = db.list_agent_logs(10)
        if logs:
            sync.push_agent_logs(logs)

    def _synthesize(self, pair, pattern, dca, atr_v, kill, mode, account, position, secrets):
        price = pattern["price"]
        atr_pct = (atr_v / price * 100) if atr_v and price else 99
        score = pattern["score"]

        if kill:
            reason = "Kill switch LOCKED. New orders rejected."
            db.insert_agent_log("ORCHESTRATOR", f"{pair}: {reason}", "WARN")
            return self._log_standby(pair, reason, mode, score)

        if dca["dca_ready"] and position:
            return self._execute_dca(pair, dca, atr_v, mode, account, position, secrets)

        if position:
            reason = f"Position already open on {pair}. Pattern score {score:.1f}."
            db.insert_agent_log("ORCHESTRATOR", f"{pair}: {reason}")
            return self._log_standby(pair, reason, mode, score)

        if score < 80:
            reason = f"Score {score:.1f} < 80. Standby. {pattern['reason']}"
            db.insert_agent_log("PATTERN", f"{pair}: {reason}")
            return self._log_standby(pair, reason, mode, score)

        if atr_pct > MAX_ATR_PCT:
            reason = f"ATR {atr_pct:.2f}% exceeds safety cap {MAX_ATR_PCT}%."
            db.insert_agent_log("RISK", f"{pair}: {reason}", "WARN")
            return self._log_standby(pair, reason, mode, score)

        return self._execute_buy(pair, pattern, atr_v, mode, account, secrets)

    def _execute_buy(self, pair, pattern, atr_v, mode, account, secrets):
        price = pattern["price"]
        sl = price - atr_v * ATR_SL_MULT
        tp = price + atr_v * ATR_TP_MULT
        budget = account["cash"] * POSITION_RISK
        qty = round(budget / price, 6) if price else 0
        if qty <= 0 or budget < 10:
            reason = "Insufficient cash for new allocation."
            return self._log_standby(pair, reason, mode, pattern["score"])

        order_id = sl_order_id = tp_order_id = ""
        if mode == "LIVE":
            result = router.place_bracket_buy(pair, budget, sl, tp)
            if result["status"] != "FILLED":
                reason = (
                    f"Live order DITOLAK: {result['reason']} "
                    f"(exchange={secrets.get('exchange_id')}). Tidak ada order palsu yang dibuat."
                )
                db.insert_agent_log("RISK", f"{pair}: {reason}", "ERROR")
                db.insert_trade_log(pair, "STANDBY", reason, mode, agent="RISK", score=pattern["score"])
                return {"action": "STANDBY", "pair": pair, "score": pattern["score"], "reason": reason}
            order_id = result.get("order_id", "")
            qty = round(result.get("amount", qty), 8)
            price = result.get("price", price)

        notional = qty * price
        db.update_account(cash=account["cash"] - notional)
        db.insert_position(pair, "BUY", price, qty, sl, tp, exchange_order_id=order_id, sl_order_id=sl_order_id, tp_order_id=tp_order_id)
        reason = (
            f"Master allocated {POSITION_RISK*100:.0f}% budget [{mode}]. "
            f"Score {pattern['score']:.1f}. Bracket SL {sl:.4f} / TP {tp:.4f}. "
            f"{pattern['reason']}"
        )
        db.insert_agent_log("ORCHESTRATOR", f"{pair} BUY @ {price:.4f} qty {qty} [{mode}] order={order_id or 'PAPER'}")
        db.insert_trade_log(
            pair, "BUY", reason, mode, profit_loss=0, price=price, quantity=qty, agent="ORCHESTRATOR", score=pattern["score"]
        )
        return {"action": "BUY", "pair": pair, "score": pattern["score"], "reason": reason, "price": price, "quantity": qty}

    def _execute_dca(self, pair, dca, atr_v, mode, account, position, secrets):
        price = dca["price"]
        add_qty = round(position["quantity"] * 0.6, 6)
        cost = add_qty * price
        if cost > account["cash"]:
            reason = "DCA skipped: not enough cash."
            return self._log_standby(pair, reason, mode, dca["score"])

        if mode == "LIVE":
            result = router.place_bracket_buy(pair, cost, position["stop_loss"], position["take_profit"])
            if result["status"] != "FILLED":
                reason = f"DCA Live DITOLAK: {result['reason']}. Tidak ada order palsu."
                db.insert_agent_log("RISK", f"{pair}: {reason}", "ERROR")
                return self._log_standby(pair, reason, mode, dca["score"])
            add_qty = round(result.get("amount", add_qty), 8)
            price = result.get("price", price)
            cost = add_qty * price

        new_qty = position["quantity"] + add_qty
        new_avg = (position["avg_price"] * position["quantity"] + price * add_qty) / new_qty
        sl = new_avg - (atr_v or new_avg * 0.01) * ATR_SL_MULT
        tp = new_avg + (atr_v or new_avg * 0.01) * ATR_TP_MULT
        db.update_account(cash=account["cash"] - cost)
        db.update_position(
            position["id"],
            quantity=new_qty,
            avg_price=new_avg,
            dca_levels=position["dca_levels"] + 1,
            stop_loss=sl,
            take_profit=tp,
        )
        reason = f"{dca['reason']} New avg {new_avg:.4f}. Bracket reset SL {sl:.4f} / TP {tp:.4f}."
        db.insert_agent_log("DCA", f"{pair} AVERAGE_DOWN @ {price:.4f} level {position['dca_levels'] + 1} [{mode}]")
        db.insert_trade_log(
            pair, "AVERAGE_DOWN", reason, mode, profit_loss=dca.get("drawdown", 0), price=price, quantity=add_qty, agent="DCA", score=dca["score"]
        )
        return {"action": "AVERAGE_DOWN", "pair": pair, "score": dca["score"], "reason": reason, "price": price, "quantity": add_qty}

    def _log_standby(self, pair, reason, mode, score):
        if score >= 70 or "Kill" in reason:
            db.insert_trade_log(pair, "STANDBY", reason, mode, agent="ORCHESTRATOR", score=score)
        return {"action": "STANDBY", "pair": pair, "score": score, "reason": reason}

    def _mark_to_market(self):
        positions = db.open_positions()
        account = db.get_account()
        cash = account["cash"]
        unrealized = 0.0
        config = db.get_config()
        mode = config["execution_mode"]

        for pos in positions:
            candles = self.market.ohlcv(pos["asset_pair"])
            price = candles[-1]["close"] if candles else pos["avg_price"]
            pnl = (price - pos["avg_price"]) * pos["quantity"]
            pnl_pct = ((price - pos["avg_price"]) / pos["avg_price"]) * 100 if pos["avg_price"] else 0
            db.update_position(pos["id"], unrealized_pnl=pnl)

            hit_sl = price <= pos["stop_loss"]
            hit_tp = price >= pos["take_profit"]
            if hit_sl or hit_tp:
                proceeds = price * pos["quantity"]
                cash += proceeds
                action = "TAKE_PROFIT" if hit_tp else "STOP_LOSS"
                reason = (
                    f"Broker-side bracket filled. {action} at {price:.4f}. "
                    f"Entry avg {pos['avg_price']:.4f}. Realized PnL {pnl_pct:.2f}%."
                )
                db.update_position(pos["id"], status="CLOSED", closed_at=db.utcnow(), unrealized_pnl=pnl)
                db.insert_trade_log(
                    pos["asset_pair"], action, reason, mode, profit_loss=pnl_pct, price=price, quantity=pos["quantity"], agent="RISK", score=100 if hit_tp else 0
                )
                db.insert_agent_log("RISK", f"{pos['asset_pair']} {action} @ {price:.4f} PnL {pnl_pct:.2f}%")
            else:
                unrealized += pnl

        equity = cash + self._open_notional()
        db.update_account(cash=cash, equity=round(equity, 4))

    def _open_notional(self):
        total = 0.0
        for pos in db.open_positions():
            candles = self.market.ohlcv(pos["asset_pair"])
            price = candles[-1]["close"] if candles else pos["avg_price"]
            total += price * pos["quantity"]
        return total

    def _roll_daily_equity(self):
        account = db.get_account()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if account["daily_date"] != today:
            db.update_account(daily_date=today, daily_start_equity=account["equity"])
            account = db.get_account()
        return account

    def _daily_pnl_pct(self, account):
        start = account["daily_start_equity"] or account["starting_balance"]
        if not start:
            return 0.0
        return ((account["equity"] - start) / start) * 100

    def _drawdown(self, account):
        start = account["starting_balance"] or 10000
        return ((account["equity"] - start) / start) * 100
