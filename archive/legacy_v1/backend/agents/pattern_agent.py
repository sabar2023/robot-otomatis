from market import atr, macd, rsi, support_resistance


class PatternAgent:
    name = "PATTERN"

    def analyze(self, pair, candles):
        closes = [c["close"] for c in candles]
        last = closes[-1] if closes else 0
        rsi_v = rsi(closes, 14)
        macd_line, signal_line, hist = macd(closes)
        atr_v = atr(candles, 14)
        support, resistance = support_resistance(candles)

        score = 50.0
        reasons = []

        if rsi_v is not None:
            if rsi_v < 32:
                score += 18
                reasons.append(f"RSI oversold {rsi_v:.1f}")
            elif rsi_v < 45:
                score += 8
                reasons.append(f"RSI recovering {rsi_v:.1f}")
            elif rsi_v > 72:
                score -= 16
                reasons.append(f"RSI overbought {rsi_v:.1f}")
            else:
                reasons.append(f"RSI neutral {rsi_v:.1f}")

        if hist is not None:
            if hist > 0 and macd_line is not None and signal_line is not None and macd_line > signal_line:
                score += 16
                reasons.append("MACD bullish crossover")
            elif hist < 0:
                score -= 10
                reasons.append("MACD bearish histogram")

        if resistance and last >= resistance * 0.998:
            score += 14
            reasons.append("Price breaking resistance")
        elif support and last <= support * 1.004:
            score += 10
            reasons.append("Price holding support")

        momentum = 0
        if len(closes) >= 8:
            momentum = (closes[-1] - closes[-8]) / closes[-8] * 100
            if momentum > 0.6:
                score += 10
                reasons.append(f"Short momentum +{momentum:.2f}%")
            elif momentum < -0.8:
                score -= 8
                reasons.append(f"Short momentum {momentum:.2f}%")

        score = max(0, min(100, score))
        action = "BUY" if score >= 80 else "STANDBY"
        return {
            "agent": self.name,
            "pair": pair,
            "score": round(score, 2),
            "action": action,
            "rsi": round(rsi_v, 2) if rsi_v is not None else None,
            "macd": round(macd_line, 6) if macd_line is not None else None,
            "macd_signal": round(signal_line, 6) if signal_line is not None else None,
            "macd_hist": round(hist, 6) if hist is not None else None,
            "atr": round(atr_v, 4) if atr_v is not None else None,
            "support": round(support, 4) if support else None,
            "resistance": round(resistance, 4) if resistance else None,
            "price": last,
            "reason": "; ".join(reasons) if reasons else "Insufficient data",
        }
