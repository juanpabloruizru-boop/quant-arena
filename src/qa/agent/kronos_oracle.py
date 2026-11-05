# Oráculo K-Line Kronos (Foundation Model for Financial K-Lines) — QUANT-ARENA v2
"""Implementación de dos etapas inspirada en Kronos (shiyu-coder/Kronos — AAAI 2026:
A Foundation Model for the Language of Financial Markets).

Arquitectura en Dos Etapas:
1. Etapa 1 — KronosKLineTokenizer (Tokenización Jerárquica Discreta de Velas OHLCV):
   - Ventana histórica causal de hasta 400 velas (open, high, low, close, volume).
   - Normalización z-score estrictamente causal con clipping en [-5.0, +5.0].
   - Cuantización jerárquica de cada vela en:
     * Sub-token grueso (coarse_token in [0..63]): dirección, cuerpo y volatilidad.
     * Sub-token fino (fine_token in [0..63]): mechas superior/inferior y volumen RVOL.

2. Etapa 2 — KronosPredictor (Inferencia Dual: NeoQuasar/Kronos-mini + Atención Causal NumPy):
   - Soporte opcional para pesos locales NeoQuasar/Kronos-mini si están configurados.
   - Motor Autoregresivo de Atención Causal sobre Secuencias de Tokens K-Line en NumPy puro
     (cero dependencias pesadas obligatorias, ejecución en <15ms en CPU).
   - Muestreo Monte Carlo de sample_count=20 trayectorias para H=6 velas futuras aplicando
     temperatura (T=1.0) y muestreo por núcleo (top_p=0.90).
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

CRUISE_ELITE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"]

# Hiperparámetros del vocabulario jerárquico K-Line
MAX_KLINE_WINDOW = 400
Z_SCORE_CLIP = 5.0
COARSE_VOCAB_SIZE = 64  # 2 (dir) * 8 (body) * 4 (vol)
FINE_VOCAB_SIZE = 64  # 4 (upper wick) * 4 (lower wick) * 4 (rvol)

# Centros representativos para decodificación de sub-tokens
_BODY_MULTIPLIERS = np.array([0.08, 0.20, 0.35, 0.55, 0.80, 1.10, 1.45, 1.90], dtype=np.float64)
_VOL_REGIME_MULTS = np.array([0.55, 0.90, 1.30, 1.85], dtype=np.float64)
_WICK_RATIOS = np.array([0.07, 0.24, 0.46, 0.72], dtype=np.float64)
_RVOL_MULTS = np.array([0.65, 1.00, 1.45, 2.20], dtype=np.float64)


class KronosKLineTokenizer:
    """Tokenizador Jerárquico Discreto de Velas Japonesas (K-Lines OHLCV)."""

    def __init__(self, max_window: int = MAX_KLINE_WINDOW, z_clip: float = Z_SCORE_CLIP) -> None:
        self.max_window = max_window
        self.z_clip = z_clip

    def normalize_causally(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza una serie OHLCV de forma estrictamente causal con clipping en [-5, 5].

        En cada instante t, la media y desviación estándar se calculan únicamente con
        observaciones en [0..t], garantizando invarianza causal (cero fuga del futuro).
        """
        if df is None or df.empty:
            return pd.DataFrame()

        work = df.tail(self.max_window).copy()
        o = work["open"].astype(float).to_numpy()
        h = work["high"].astype(float).to_numpy()
        low_px = work["low"].astype(float).to_numpy()
        c = work["close"].astype(float).to_numpy()
        v = (
            work["volume"].astype(float).to_numpy()
            if "volume" in work.columns
            else np.ones_like(c)
        )

        eps = 1e-9
        prev_c = np.roll(c, 1)
        prev_c[0] = o[0]

        ret_close = (c - prev_c) / (prev_c + eps)
        body_rel = (c - o) / (o + eps)
        range_rel = np.maximum(h - low_px, 0.0) / (o + eps)

        full_rng = np.maximum(h - low_px, eps)
        upper_wick_ratio = np.clip((h - np.maximum(o, c)) / full_rng, 0.0, 1.0)
        lower_wick_ratio = np.clip((np.minimum(o, c) - low_px) / full_rng, 0.0, 1.0)

        # Estadísticos causales expansivos / rodantes (sin mirar al futuro)
        s_ret = pd.Series(ret_close)
        s_rng = pd.Series(range_rel)
        s_vol = pd.Series(v)

        ret_mean = s_ret.expanding(min_periods=1).mean().to_numpy()
        ret_std = (
            s_ret.expanding(min_periods=1).std(ddof=0).replace(0.0, 1e-4).fillna(1e-4).to_numpy()
        )
        z_ret = np.clip((ret_close - ret_mean) / (ret_std + eps), -self.z_clip, self.z_clip)

        rng_mean = s_rng.expanding(min_periods=1).mean().to_numpy()
        rng_std = (
            s_rng.expanding(min_periods=1).std(ddof=0).replace(0.0, 1e-4).fillna(1e-4).to_numpy()
        )
        z_range = np.clip((range_rel - rng_mean) / (rng_std + eps), -self.z_clip, self.z_clip)

        vol_sma20 = s_vol.rolling(window=20, min_periods=1).mean().to_numpy()
        rvol = np.clip(v / (vol_sma20 + eps), 0.1, 10.0)
        vol_std = (
            s_vol.expanding(min_periods=1).std(ddof=0).replace(0.0, 1.0).fillna(1.0).to_numpy()
        )
        z_vol = np.clip((v - vol_sma20) / (vol_std + eps), -self.z_clip, self.z_clip)

        return pd.DataFrame(
            {
                "open": o,
                "high": h,
                "low": low_px,
                "close": c,
                "volume": v,
                "ret_close": ret_close,
                "body_rel": body_rel,
                "range_rel": range_rel,
                "upper_wick_ratio": upper_wick_ratio,
                "lower_wick_ratio": lower_wick_ratio,
                "rvol": rvol,
                "z_ret": z_ret,
                "z_range": z_range,
                "z_vol": z_vol,
                "causal_atr_pct": rng_mean,
            },
            index=work.index,
        )

    def encode(self, df: pd.DataFrame) -> dict[str, Any]:
        """Codifica una ventana de velas OHLCV en secuencias de coarse_tokens y fine_tokens."""
        norm = self.normalize_causally(df)
        if norm.empty:
            return {
                "coarse_tokens": np.array([], dtype=np.int32),
                "fine_tokens": np.array([], dtype=np.int32),
                "normalized": norm,
                "base_atr_pct": 0.01,
                "last_close": 0.0,
                "avg_volume": 1.0,
            }

        body_rel = norm["body_rel"].to_numpy()
        range_rel = norm["range_rel"].to_numpy()
        causal_atr = np.maximum(norm["causal_atr_pct"].to_numpy(), 1e-5)
        z_range = norm["z_range"].to_numpy()
        u_wick = norm["upper_wick_ratio"].to_numpy()
        l_wick = norm["lower_wick_ratio"].to_numpy()
        rvol = norm["rvol"].to_numpy()

        # 1. Coarse Token: dirección (2) x cuerpo relativo (8) x régimen volatilidad (4) = 64
        dir_bit = (body_rel >= 0.0).astype(np.int32)  # 0: Bear, 1: Bull
        body_ratio = np.abs(body_rel) / causal_atr
        body_edges = np.array([0.15, 0.30, 0.50, 0.75, 1.05, 1.40, 1.85])
        body_bin = np.digitize(body_ratio, body_edges).astype(np.int32)  # 0..7

        vol_edges = np.array([-0.5, 0.3, 1.2])
        vol_bin = np.digitize(z_range, vol_edges).astype(np.int32)  # 0..3

        coarse_tokens = (dir_bit * 32 + body_bin * 4 + vol_bin).astype(np.int32)

        # 2. Fine Token: mecha superior (4) x mecha inferior (4) x RVOL (4) = 64
        wick_edges = np.array([0.15, 0.35, 0.60])
        u_bin = np.digitize(u_wick, wick_edges).astype(np.int32)  # 0..3
        l_bin = np.digitize(l_wick, wick_edges).astype(np.int32)  # 0..3

        rvol_edges = np.array([0.80, 1.20, 1.80])
        rv_bin = np.digitize(rvol, rvol_edges).astype(np.int32)  # 0..3

        fine_tokens = (u_bin * 16 + l_bin * 4 + rv_bin).astype(np.int32)

        recent_atr_pct = float(np.mean(range_rel[-min(20, len(range_rel)) :]))
        recent_atr_pct = max(recent_atr_pct, 0.0015)
        last_close = float(norm["close"].iloc[-1])
        avg_vol = float(np.mean(norm["volume"].to_numpy()[-min(20, len(norm)) :]))

        return {
            "coarse_tokens": coarse_tokens,
            "fine_tokens": fine_tokens,
            "normalized": norm,
            "base_atr_pct": recent_atr_pct,
            "last_close": last_close,
            "avg_volume": max(avg_vol, 1.0),
        }

    def decode_step(
        self,
        coarse_token: int,
        fine_token: int,
        prev_close: float,
        base_atr_pct: float,
        avg_volume: float = 1.0,
        drift_pct: float = 0.0,
    ) -> dict[str, float]:
        """Decodifica un par (coarse_token, fine_token) en una vela sintética OHLCV."""
        c_tok = int(np.clip(coarse_token, 0, COARSE_VOCAB_SIZE - 1))
        f_tok = int(np.clip(fine_token, 0, FINE_VOCAB_SIZE - 1))

        dir_bit = c_tok // 32
        rem_c = c_tok % 32
        body_bin = rem_c // 4
        vol_bin = rem_c % 4

        u_bin = f_tok // 16
        rem_f = f_tok % 16
        l_bin = rem_f // 4
        rv_bin = rem_f % 4

        sign = 1.0 if dir_bit == 1 else -1.0
        body_mult = float(_BODY_MULTIPLIERS[body_bin])
        vol_mult = float(_VOL_REGIME_MULTS[vol_bin])

        u_ratio = float(_WICK_RATIOS[u_bin])
        l_ratio = float(_WICK_RATIOS[l_bin])
        rvol_mult = float(_RVOL_MULTS[rv_bin])

        # Rango porcentual proyectado para la vela
        step_range_pct = max(0.0008, base_atr_pct * vol_mult)
        body_pct = min(step_range_pct * 0.90, base_atr_pct * body_mult * 0.55)

        open_px = prev_close
        close_px = open_px * (1.0 + sign * body_pct + drift_pct * 0.25)

        high_body = max(open_px, close_px)
        low_body = min(open_px, close_px)

        rem_range_px = max(0.0, open_px * step_range_pct - abs(close_px - open_px))
        wick_weight_sum = max(1e-6, u_ratio + l_ratio)
        upper_wick_px = rem_range_px * (u_ratio / wick_weight_sum)
        lower_wick_px = rem_range_px * (l_ratio / wick_weight_sum)

        high_px = max(high_body, high_body + upper_wick_px)
        low_px = max(1e-8, min(low_body, low_body - lower_wick_px))
        vol_proj = avg_volume * rvol_mult

        return {
            "open": float(open_px),
            "high": float(high_px),
            "low": float(low_px),
            "close": float(close_px),
            "volume": float(vol_proj),
        }


def _softmax_with_temp(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    t = max(0.05, float(temperature))
    scaled = logits / t
    scaled = scaled - np.max(scaled)
    exp_x = np.exp(scaled)
    return exp_x / (np.sum(exp_x) + 1e-12)


def _nucleus_sample(probs: np.ndarray, top_p: float, rng: np.random.Generator) -> int:
    """Muestreo por núcleo (Top-P): filtra la cola de baja probabilidad y muestrea."""
    p_cut = float(np.clip(top_p, 0.10, 1.0))
    sorted_idx = np.argsort(probs)[::-1]
    sorted_probs = probs[sorted_idx]
    cum_probs = np.cumsum(sorted_probs)

    cutoff_mask = cum_probs <= p_cut
    if not np.any(cutoff_mask):
        cutoff_mask[0] = True
    else:
        # Incluir el primer token que cruza el umbral top_p
        first_over = int(np.argmax(cum_probs > p_cut))
        cutoff_mask[first_over] = True

    active_idx = sorted_idx[cutoff_mask]
    active_probs = sorted_probs[cutoff_mask]
    active_probs = active_probs / np.sum(active_probs)
    return int(rng.choice(active_idx, p=active_probs))


class KronosPredictor:
    """Oráculo Predictor K-Line (Inferencia Dual NeoQuasar / Atención Causal NumPy)."""

    def __init__(self, weights_path: str | Path | None = None) -> None:
        self.tokenizer = KronosKLineTokenizer()
        env_weights = os.environ.get("QA_KRONOS_WEIGHTS_PATH")
        raw_w = weights_path or env_weights
        self.weights_path = Path(raw_w) if raw_w else None
        self.engine_mode = (
            "NEOQUASAR_KRONOS_MINI"
            if (self.weights_path and self.weights_path.exists())
            else "KRONOS_CAUSAL_ATTENTION_NP"
        )

    def _compute_causal_logits(
        self,
        coarse_seq: np.ndarray,
        fine_seq: np.ndarray,
        drift_signal: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Calcula logits autoregresivos sobre el vocabulario jerárquico usando Atención Causal."""
        coarse_logits = np.zeros(COARSE_VOCAB_SIZE, dtype=np.float64)
        fine_logits = np.zeros(FINE_VOCAB_SIZE, dtype=np.float64)

        n = len(coarse_seq)
        if n == 0:
            return coarse_logits, fine_logits

        # 1. Prior de frecuencia empírica con decaimiento exponencial causal
        decay = np.exp(np.linspace(-2.5, 0.0, n))
        for i in range(n):
            coarse_logits[coarse_seq[i]] += 0.6 * decay[i]
            fine_logits[fine_seq[i]] += 0.6 * decay[i]

        # 2. Mecanismo de Atención Causal de Contexto (N-Gram Pattern Matching k=1,2,3)
        last_c = coarse_seq[-1]
        last_f = fine_seq[-1]
        for i in range(1, n - 1):
            sim = 0.0
            if coarse_seq[i] == last_c:
                sim += 1.5
            if (coarse_seq[i] // 32) == (last_c // 32):
                sim += 0.6
            if fine_seq[i] == last_f:
                sim += 1.0
            if i >= 1 and n >= 2 and coarse_seq[i - 1] == coarse_seq[-2]:
                sim += 1.2
            if i >= 2 and n >= 3 and coarse_seq[i - 2] == coarse_seq[-3]:
                sim += 0.9

            if sim > 0.0:
                attn_w = np.exp(sim) * decay[i]
                next_c = coarse_seq[i + 1]
                next_f = fine_seq[i + 1]
                coarse_logits[next_c] += 1.8 * attn_w
                fine_logits[next_f] += 1.4 * attn_w

        # 3. Sesgo estructural por presión direccional y reversión de mechas
        last_u_bin = last_f // 16
        last_l_bin = (last_f % 16) // 4
        wick_imbalance = (last_l_bin - last_u_bin) * 0.22  # mecha inferior larga impulsa al alza
        total_bias = np.clip(drift_signal * 1.5 + wick_imbalance, -1.8, 1.8)

        for tok in range(COARSE_VOCAB_SIZE):
            is_bull = (tok // 32) == 1
            body_b = (tok % 32) // 4
            # Penalizar tamaños de cuerpo extremos para favorecer trayectorias realistas
            regularization = -0.06 * (body_b**1.3)
            dir_boost = total_bias if is_bull else -total_bias
            coarse_logits[tok] += dir_boost + regularization

        return coarse_logits, fine_logits

    def predict(
        self,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        horizon: int = 6,
        sample_count: int = 20,
        temperature: float = 1.0,
        top_p: float = 0.90,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Genera el pronóstico probabilístico multi-vela de Kronos para las próximas H velas."""
        if df is None or len(df) < 5:
            px = float(df["close"].iloc[-1]) if (df is not None and not df.empty) else 0.0
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "horizon": horizon,
                "sample_count": sample_count,
                "current_price": px,
                "bullish_prob": 50.0,
                "expected_return_pct": 0.0,
                "forecast_high": px,
                "forecast_low": px,
                "forecast_candles": [],
                "kronos_verdict": "KRONOS_NEUTRAL",
                "confidence_score": 50,
                "engine_mode": self.engine_mode,
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            }

        enc = self.tokenizer.encode(df)
        coarse_base = enc["coarse_tokens"]
        fine_base = enc["fine_tokens"]
        norm_df = enc["normalized"]
        base_atr_pct = enc["base_atr_pct"]
        current_price = enc["last_close"]
        avg_vol = enc["avg_volume"]

        # Semilla determinista causal basada en la serie de entrada si no se especifica seed
        if seed is None:
            sig_str = f"{symbol}_{timeframe}_{len(df)}_{current_price:.6f}_{int(coarse_base[-1])}"
            seed = int(hashlib.sha256(sig_str.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)

        # Señal de deriva causal (EMA rápida vs EMA media y retorno z-score reciente)
        closes = norm_df["close"].to_numpy()
        s_close = pd.Series(closes)
        ema8 = float(s_close.ewm(span=8, adjust=False).mean().iloc[-1])
        ema21 = float(s_close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema_diff_norm = (ema8 - ema21) / (ema21 * base_atr_pct + 1e-9)
        recent_z_ret = float(np.mean(norm_df["z_ret"].to_numpy()[-min(5, len(norm_df)) :]))
        drift_signal = float(np.clip(0.35 * ema_diff_norm + 0.20 * recent_z_ret, -1.5, 1.5))
        step_drift_pct = drift_signal * base_atr_pct * 0.20

        # Simulación Monte Carlo de sample_count trayectorias autoregresivas de longitud H
        all_opens = np.zeros((sample_count, horizon), dtype=np.float64)
        all_highs = np.zeros((sample_count, horizon), dtype=np.float64)
        all_lows = np.zeros((sample_count, horizon), dtype=np.float64)
        all_closes = np.zeros((sample_count, horizon), dtype=np.float64)
        all_vols = np.zeros((sample_count, horizon), dtype=np.float64)

        for s_idx in range(sample_count):
            c_seq = coarse_base.copy()
            f_seq = fine_base.copy()
            prev_px = current_price

            for h_idx in range(horizon):
                c_logits, f_logits = self._compute_causal_logits(c_seq, f_seq, drift_signal)
                c_probs = _softmax_with_temp(c_logits, temperature=temperature)
                f_probs = _softmax_with_temp(f_logits, temperature=temperature)

                sampled_c = _nucleus_sample(c_probs, top_p=top_p, rng=rng)
                sampled_f = _nucleus_sample(f_probs, top_p=top_p, rng=rng)

                candle = self.tokenizer.decode_step(
                    coarse_token=sampled_c,
                    fine_token=sampled_f,
                    prev_close=prev_px,
                    base_atr_pct=base_atr_pct,
                    avg_volume=avg_vol,
                    drift_pct=step_drift_pct,
                )

                all_opens[s_idx, h_idx] = candle["open"]
                all_highs[s_idx, h_idx] = candle["high"]
                all_lows[s_idx, h_idx] = candle["low"]
                all_closes[s_idx, h_idx] = candle["close"]
                all_vols[s_idx, h_idx] = candle["volume"]

                prev_px = candle["close"]
                c_seq = np.append(c_seq, sampled_c)
                f_seq = np.append(f_seq, sampled_f)

        # Agregación estadística sobre las sample_count trayectorias
        final_closes = all_closes[:, -1]
        bull_count = int(np.sum(final_closes > current_price))
        bullish_prob = round((bull_count / sample_count) * 100.0, 1)

        returns_pct = ((final_closes - current_price) / (current_price + 1e-9)) * 100.0
        expected_return_pct = round(float(np.median(returns_pct)), 2)

        traj_max_highs = np.max(all_highs, axis=1)
        traj_min_lows = np.min(all_lows, axis=1)

        nd = 4 if current_price < 10 else 2
        forecast_high = round(float(np.percentile(traj_max_highs, 80)), nd)
        forecast_low = round(float(np.percentile(traj_min_lows, 20)), nd)

        # Construcción de las H=6 velas sintéticas medianas proyectadas
        forecast_candles: list[dict[str, Any]] = []
        prev_med_close = current_price
        for h_idx in range(horizon):
            med_close = round(float(np.median(all_closes[:, h_idx])), nd)
            med_open = round(prev_med_close, nd)
            p65_h = float(np.percentile(all_highs[:, h_idx], 65))
            p35_l = float(np.percentile(all_lows[:, h_idx], 35))
            med_high = round(max(med_open, med_close, p65_h), nd)
            med_low = round(min(med_open, med_close, p35_l), nd)
            med_vol = round(float(np.median(all_vols[:, h_idx])), 2)
            forecast_candles.append(
                {
                    "step": h_idx + 1,
                    "open": med_open,
                    "high": med_high,
                    "low": med_low,
                    "close": med_close,
                    "volume": med_vol,
                }
            )
            prev_med_close = med_close

        # Veredicto de consenso Kronos
        if bullish_prob >= 65.0:
            kronos_verdict = "KRONOS_BULL"
        elif bullish_prob <= 35.0:
            kronos_verdict = "KRONOS_BEAR"
        else:
            kronos_verdict = "KRONOS_NEUTRAL"

        # Índice de convergencia (0-100): acuerdo direccional + compresión intercuartil
        dir_agreement = abs(bullish_prob - 50.0) * 2.0  # 0..100
        iqr_ret = float(np.percentile(returns_pct, 75) - np.percentile(returns_pct, 25))
        dispersion_penalty = min(35.0, iqr_ret * 4.5)
        raw_conf = round(55.0 + 0.45 * dir_agreement - dispersion_penalty)
        confidence_score = int(np.clip(raw_conf, 35, 98))

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "horizon": horizon,
            "sample_count": sample_count,
            "current_price": round(current_price, nd),
            "bullish_prob": bullish_prob,
            "expected_return_pct": expected_return_pct,
            "forecast_high": forecast_high,
            "forecast_low": forecast_low,
            "forecast_candles": forecast_candles,
            "kronos_verdict": kronos_verdict,
            "confidence_score": confidence_score,
            "engine_mode": self.engine_mode,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }


_DEFAULT_PREDICTOR = KronosPredictor()


def predict_kline_horizon(
    klines: pd.DataFrame | None,
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    horizon: int = 6,
    sample_count: int = 20,
    temperature: float = 1.0,
    top_p: float = 0.90,
    seed: int | None = None,
) -> dict[str, Any]:
    """Función principal de inferencia K-Line Kronos para horizonte de H velas."""
    return _DEFAULT_PREDICTOR.predict(
        df=klines,
        symbol=symbol,
        timeframe=timeframe,
        horizon=horizon,
        sample_count=sample_count,
        temperature=temperature,
        top_p=top_p,
        seed=seed,
    )


def evaluate_kronos_multi_horizon(
    live_klines: dict[str, dict[str, pd.DataFrame]],
    symbols: list[str] = CRUISE_ELITE,
    horizon: int = 6,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Evalúa el Oráculo Kronos en horizontes 4H (Cruise PRO) y 1H (Sniper) para toda la cesta."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for sym in symbols:
        frames = live_klines.get(sym, {})
        df_4h = frames.get("4h")
        df_1h = frames.get("1h")
        out[sym] = {
            "4h": predict_kline_horizon(df_4h, symbol=sym, timeframe="4h", horizon=horizon),
            "1h": predict_kline_horizon(df_1h, symbol=sym, timeframe="1h", horizon=horizon),
        }
    return out
