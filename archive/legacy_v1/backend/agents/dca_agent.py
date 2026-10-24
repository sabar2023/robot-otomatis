class DcaAgent:
    name = "DCA"

    def analyze(self, pair, candles, position, atr_value):
        if not position:
            return {
                "agent": self.name,
                "pair": pair,
                "score": 0,
                "action": "STANDBY",
                "reason": "No open position. DCA idle.",
                "dca_ready": False,
            }

        last = candles[-1]["close"] if candles else position["avg_price"]
        avg = position["avg_price"]
        drawdown = ((last - avg) / avg) * 100 if avg else 0
        levels = position.get("dca_levels", 0)
        atr_pct = (atr_value / last * 100) if atr_value and last else 0.8

        trigger = -1.2 * (levels + 1) - atr_pct * 0.3
        score = 0
        action = "STANDBY"
        ready = False
        reason = f"Floating PnL {drawdown:.2f}%. DCA levels used {levels}/3."

        if drawdown <= trigger and levels < 3:
            score = min(95, 70 + abs(drawdown) * 4)
            action = "AVERAGE_DOWN"
            ready = True
            reason = (
                f"Floating loss {drawdown:.2f}% exceeded trigger {trigger:.2f}%. "
                f"Propose DCA level {levels + 1} at {last:.4f}."
            )
        elif drawdown >= 0:
            reason = f"Position recovering ({drawdown:.2f}%). DCA stands down."
        else:
            reason = f"Loss {drawdown:.2f}% still above DCA trigger {trigger:.2f}%."

        return {
            "agent": self.name,
            "pair": pair,
            "score": round(score, 2),
            "action": action,
            "reason": reason,
            "dca_ready": ready,
            "drawdown": round(drawdown, 3),
            "levels": levels,
            "price": last,
        }
