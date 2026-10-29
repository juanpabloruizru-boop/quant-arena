# Autopilot Motor Autónomo M6 — QUANT-ARENA v2
"""Motor de decisión y ejecución autónomo para paper trading simulado.

Cuando se ejecuta `qa agent run`, este módulo actúa como un Trader Cuantitativo
Autónomo sobre una cuenta simulada de $1,000 USD, gestionando operaciones abiertas,
abriendo nuevas posiciones y registrando todo en los ledgers correspondientes.

Exported symbols:
- `autonomous_run(capital_inicial=1000.0)`: ejecuta una corrida completa del autopilot.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.live import fetch_extra_multi, fetch_klines_paged, SPOT_BASE, BinancePublicClient
from qa.agent.signals import band_positions, h1_state, h3_state, klines_frame
from qa.report.dashboard import _fmt, _signed, _badge
from qa._yaml_compat import safe_load, safe_dump

# Rutas de ledger (simulación local)
BASE_DIR = Path(__file__).parent.parent
LEDGER_DIR = BASE_DIR / "ledger"
USER_TRADES_PATH = LEDGER_DIR / "user_trades.jsonl"
USER_CAPITAL_PATH = LEDGER_DIR / "user_capital.jsonl"

# Universo de símbolos
UNIVERSO = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ZECUSDT", "NEARUSDT", "SUIUSDT", "UNIUSDT", "DOGEUSDT",
]

# Parámetros de riesgo M6
RISK_PCT_POR_OPERACION = 0.015  # 1.5% del patrimonio por operación
MAX_HEAT_PCT_PATRIMONIO = 0.06  # 6% máximo en riesgo simultáneo
MAX_OPERACIONES_ABERTAS = 4
LEV_SPORT = 1
LEV_FUTURES_MIN = 2
LEV_FUTURES_MAX = 5
MIN_RR_NETO = 2.0


def _ensure_ledger_dir() -> None:
    """Asegura que el directorio de ledgers existe."""
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)


def _cargar_capital() -> dict[str, Any]:
    """Carga el estado actual del capital desde user_capital.jsonl."""
    _ensure_ledger_dir()
    if not USER_CAPITAL_PATH.exists():
        # Capital inicial por defecto
        return {
            "capital_inicial": 1000.0,
            "pnl_realizado_usd": 0.0,
            "pnl_flotante_usd": 0.0,
            "patrimonio_total": 1000.0,
            "portfolio_heat_usd": 0.0,
            "portfolio_heat_pct_patrimonio": 0.0,
            "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
        }
    try:
        text = USER_CAPITAL_PATH.read_text()
        if not text.strip():
            return {
                "capital_inicial": 1000.0,
                "pnl_realizado_usd": 0.0,
                "pnl_flotante_usd": 0.0,
                "patrimonio_total": 1000.0,
                "portfolio_heat_usd": 0.0,
                "portfolio_heat_pct_patrimonio": 0.0,
                "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            }
        # El archivo es append-only con JSON por línea; tomar el último registro
        lines = text.strip().splitlines()
        último = lines[-1]
        registro = json.loads(último)
        # Asegurar todas las claves esperadas
        default = {
            "capital_inicial": 1000.0,
            "pnl_realizado_usd": 0.0,
            "pnl_flotante_usd": 0.0,
            "patrimonio_total": 1000.0,
            "portfolio_heat_usd": 0.0,
            "portfolio_heat_pct_patrimonio": 0.0,
            "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
        }
        for k, v in default.items():
            registro.setdefault(k, v)
        return registro
    except (json.JSONDecodeError, IndexError):
        return {
            "capital_inicial": 1000.0,
            "pnl_realizado_usd": 0.0,
            "pnl_flotante_usd": 0.0,
            "patrimonio_total": 1000.0,
            "portfolio_heat_usd": 0.0,
            "portfolio_heat_pct_patrimonio": 0.0,
            "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
        }


def _guardar_capital(capital: dict[str, Any]) -> None:
    """Agrega un nuevo registro al final de user_capital.jsonl."""
    _ensure_ledger_dir()
    registro = capital.copy()
    registro["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
    with USER_CAPITAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _cargar_trades() -> list[dict[str, Any]]:
    """Carga todas las operaciones desde user_trades.jsonl."""
    _ensure_ledger_dir()
    if not USER_TRADES_PATH.exists():
        return []
    try:
        text = USER_TRADES_PATH.read_text()
        if not text.strip():
            return []
        trades = []
        for line in text.strip().splitlines():
            try:
                trades.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return trades
    except Exception:
        return []


def _guardar_trade(trade: dict[str, Any]) -> None:
    """Agrega una nueva operación al final de user_trades.jsonl."""
    _ensure_ledger_dir()
    with USER_TRADES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trade, ensure_ascii=False) + "\n")


def _precio_actual(symbol: str, client: BinancePublicClient) -> float:
    """Obtiene el precio spot actual de un símbolo."""
    try:
        with BinancePublicClient() as c:
            rows = fetch_klines_paged(
                c, SPOT_BASE, "/api/v3/klines", symbol, "1d", limit=1, max_pages=1
            )
            df = klines_frame(rows, symbol, "1d")
            if not df.empty:
                return float(df["close"].iloc[-1])
    except Exception:
        pass
    # Fallback: intentar precio de las klines extra
    try:
        from qa.agent.live import fetch_extra_multi
        extra = fetch_extra_multi([symbol], intervals=["1d"])
        if symbol in extra and not extra[symbol].empty:
            return float(extra[symbol]["close"].iloc[-1])
    except Exception:
        pass
    return 0.0


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calcula el ATR (Average True Range) de un DataFrame de velas."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    tr = np.maximum(high - low, np.maximum(np.abs(high - close.shift(1)), np.abs(low - close.shift(1))))
    atr = tr.rolling(window=period).mean()
    return float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else 0.0


def _sma(df: pd.DataFrame, period: int = 50) -> float:
    """Calcula la SMA simple."""
    close = df["close"].astype(float)
    sma = close.rolling(window=period).mean()
    return float(sma.iloc[-1]) if not np.isnan(sma.iloc[-1]) else 0.0


def _detectar_noticias_riesgo(symbol: str, news_items: list[dict[str, Any]]) -> bool:
    """Detecta si hay noticias de alto riesgo para un símbolo en los últimos items."""
    keywords_riesgo = ["hack", "exploit", "delist", "insolvency", "ban", "sec"]
    for n in news_items:
        title = n.get("title", "").lower()
        base = symbol.replace("USDT", "").lower()
        if any(k in title for k in keywords_riesgo) and base in title:
            return True
        # También revisar keywords explícitas
        if keywords_riesgo and any(k in (n.get("keywords") or []) for k in keywords_riesgo):
            return True
    return False


def _calcular_rr(entry: float, sl: float, tp1: float, tp2: float, is_long: bool = True) -> dict[str, float]:
    """Calcula R:R neto y brutto para una operación."""
    if is_long:
        riesgo = abs(entry - sl)
        ganancia_tp1 = abs(tp1 - entry)
        ganancia_tp2 = abs(tp2 - entry)
    else:
        riesgo = abs(sl - entry)
        ganancia_tp1 = abs(entry - tp1)
        ganancia_tp2 = abs(entry - tp2)
    
    rr_tp1 = ganancia_tp1 / riesgo if riesgo > 0 else 0.0
    rr_tp2 = ganancia_tp2 / riesgo if riesgo > 0 else 0.0
    
    return {
        "riesgo": riesgo,
        "rr_tp1": rr_tp1,
        "rr_tp2": rr_tp2,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
    }


def _verificar_filtro_rr(entry: float, sl: float, tp2: float, is_long: bool = True) -> bool:
    """Verifica que el R:R neto hacia TP2 sea >= 2.0x."""
    rr = _calcular_rr(entry, sl, entry + (tp2 - entry) * (1 if is_long else -1), tp2, is_long)
    rr_neto = rr["rr_tp2"]
    return rr_neto >= MIN_RR_NETO


def _calcular_tp1_tp2(entry: float, sl: float, is_long: bool = True) -> tuple[float, float]:
    """Calcula TP1 a ~1.5R y TP2 a >= 2.5-3.0R a partir de SL."""
    riesgo = abs(entry - sl)
    # TP1 a 1.5R desde entrada
    tp1 = entry + 1.5 * riesgo if is_long else entry - 1.5 * riesgo
    # TP2 a 3.0R desde entrada
    tp2 = entry + 3.0 * riesgo if is_long else entry - 3.0 * riesgo
    return tp1, tp2


def _estado_a_decision(estado: str, tp1_hit: bool = False, en_ganancia: bool = False) -> str:
    """Convierte el estado técnico en una decisión legible para el dashboard."""
    if tp1_hit:
        return "TP1 Alcanzado ✓ · SL subido a Break-Even/TP1"
    elif en_ganancia:
        return "En Ganancia · Esperando TP2 o cierre preventivo"
    elif "SL alcanzado" in estado:
        return "Cerrada por Stop Loss"
    elif "TP2" in estado:
        return "TP2 Alcanzado (+R)"
    elif " cerrado" in estado.lower():
        return "Cerrada por decisión del agente"
    else:
        return f"Activa — {estado}"


def autonomous_run(capital_inicial: float = 1000.0) -> dict[str, Any]:
    """Ejecuta una corrida completa del Autopilot M6.
    
    El flujo:
    1. Cargar capital actual
    2. Gestionar operaciones abiertas (SL, TP1, TP2, trailing)
    3. Evaluar universo para abrir nuevas operaciones
    4. Registrar todo en ledgers
    5. Retornar estado final
    
    Retorna dict con:
    - capital_actualizado: dict de capital
    - nuevas_abiertas: lista de trades abiertos hoy
    - cierre_operaciones: lista de trades cerrados hoy
    - reporte: dict resumen
    """
    print("=" * 60)
    print("🤖 QUANT-ARENA v2 — M6 Autopilot iniciado")
    print(f"💰 Capital inicial: ${capital_inicial:,.2f} USD")
    print("=" * 60)
    
    # 1. Cargar capital
    capital = _cargar_capital()
    capital["capital_inicial"] = capital_inicial
    patrimonio_anterior = capital["patrimonio_total"]
    
    # 2. Cargar trades existentes
    trades_existentes = _cargar_trades()
    # Filtrar solo las abiertas (status == "open")
    abiertas = [t for t in trades_existentes if t.get("status") == "open"]
    cerradas_hoy = []
    abiertas_cerradas = []
    
    # 3. GESTIÓN DE OPERACIONES ABIERTAS (Paso A del espec)
    print("\n[3] GESTIONANDO OPERACIONES ABIERTAS...")
    for t in abiertas:
        activo = t.get("asset", "?")
        kind = t.get("kind", "spot")
        is_long = kind != "future_short"  # spot y future_long son largos
        entry = float(t.get("entry", t.get("precio_entrada", 0)))
        sl = float(t.get("sl", t.get("stop_loss", 0)))
        tp1 = float(t.get("tp1", t.get("take_profit_1", 0)))
        tp2 = float(t.get("tp2", t.get("take_profit_2", 0)))
        leverage = t.get("leverage", LEV_SPORT if is_long else 3)
        margen_usd = float(t.get("margin_usd", 0))
        size_usd = float(t.get("size_usd", 0))
        riesgo_usd = float(t.get("risk_usd", 0))
        precio_actual = _precio_actual(activo) if t.get("refresh_precio", True) else entry
        
        # Si no hay precio actual válido, saltar esta operación
        if precio_actual <= 0:
            print(f"  ⚡ {activo}: precio no disponible, se conserva en libro.")
            continue
        
        # 3.1 Verificación de Stop Loss
        # Para LONG: si Low tocó o pasó el SL
        sl_tocado = False
        if is_long:
            # En datos en tiempo real necesitaríamos el Low del periodo
            # Simulación: si precio <= SL, SL tocado
            if precio_actual <= sl:
                sl_tocado = True
        else:
            # SHORT: si High tocó o pasó el SL
            if precio_actual >= sl:
                sl_tocado = True
        
        if sl_tocado:
            # Cerrar operación al precio del SL
            pnl_realizado = (sl - entry) * (1 if is_long else -1) * size_usd / entry
            if not is_long:
                pnl_realizado = -pnl_realizado  # ajustar signo
            
            # Descontar comisiones taker
            fee_rate = 0.001 if kind == "spot" else 0.0005
            fee = abs(sl - entry) * fee_rate
            pnl_neto = pnl_realizado - fee
            
            # Actualizar capital
            capital["pnl_realizado_usd"] = capital.get("pnl_realizado_usd", 0) + pnl_neto
            capital["patrimonio_total"] = capital["capital_inicial"] + capital["pnl_realizado_usd"] + capital.get("pnl_flotante_usd", 0)
            capital["portfolio_heat_usd"] = capital.get("portfolio_heat_usd", 0) - margen_usd
            capital["portfolio_heat_pct_patrimonio"] = (
                capital["portfolio_heat_usd"] / capital["patrimonio_total"] * 100
                if capital["patrimonio_total"] > 0 else 0
            )
            
            # Registrar cierre
            trade_cerrado = t.copy()
            trade_cerrado["status"] = "closed"
            trade_cerrado["exit_price"] = sl
            trade_cerrado["exit_reason"] = "Stop Loss alcanzado"
            trade_cerrado["pnl_realizado_usd"] = pnl_neto
            trade_cerrado["ts_cierre"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            cerradas_hoy.append(trade_cerrado)
            abiertas_cerradas.append(trade_cerrado)
            
            # Remover de la lista de abiertas
            abiertas.remove(t)
            
            print(f"  🛑 {activo}: Stop Loss alcanzado @ ${sl:,.2f} | PnL: ${pnl_neto:+.2f} USD")
            continue
        
        # 3.2 Verificación de TP1 (Toma parcial + Subida automática de SL)
        # Simulación: si precio alcanzó o superó TP1
        tp1_hit_actual = t.get("tp1_hit", False)
        precio_toque_tp1 = precio_actual >= tp1 if is_long else precio_actual <= tp1
        
        if precio_toque_tp1 and not tp1_hit_actual:
            # Marcar TP1 como alcanzado
            tp1_hit_actual = True
            
            # Cerrar 50% de la posición (beneficio asegurado)
            size_50 = size_usd * 0.5
            pnl_50 = (tp1 - entry) * 0.5 * (1 if is_long else -1) * size_50 / entry
            fee_50 = abs(tp1 - entry) * 0.001 * 0.5  # fee taker
            pnl_50_neto = pnl_50 - fee_50
            
            # Mover SL al Break-Even Neto o a TP1 si ya pasó más
            sl_nuevo = entry  # Break-Even Neto
            if tp1 > entry if is_long else tp1 < entry:
                sl_nuevo = tp1  # Mover a TP1 si ya avancó más
            
            # Actualizar la operación original con nuevos SL y tp1_hit
            t["tp1_hit"] = True
            t["sl"] = sl_nuevo
            t["margen_usd"] = margen_usd - size_50  # Reducir margen por 50% cerrado
            t["size_usd"] = size_usd - size_50  # Reducir tamaño
            t["risk_usd"] = max(0.0, riesgo_usd - size_50)  # Ajustar riesgo
            
            # Actualizar capital con el PnL del 50% cerrado
            capital["pnl_flotante_usd"] = capital.get("pnl_flotante_usd", 0) + pnl_50_neto
            capital["patrimonio_total"] = capital["capital_inicial"] + capital["pnl_realizado_usd"] + capital.get("pnl_flotante_usd", 0)
            capital["portfolio_heat_usd"] = capital.get("portfolio_heat_usd", 0) + size_50  # Liberar margen
            capital["portfolio_heat_pct_patrimonio"] = (
                capital["portfolio_heat_usd"] / capital["patrimonio_total"] * 100
                if capital["patrimonio_total"] > 0 else 0
            )
            
            # Guardar la operación actualizada
            _guardar_trade(t)
            
            print(f"  🎯 {activo}: TP1 alcanzado @ ${tp1:,.2f} | 50% posición cerrada | SL movido a ${sl_nuevo:,.2f}")
            # Continuar con verificación de TP2 en el mismo bucle
        
        # 3.3 Verificación de TP2 (Meta Final)
        # Si precio alcanzó TP2, cerrar completamente
        tp2_toque = False
        if is_long:
            tp2_toque = precio_actual >= tp2
        else:
            tp2_toque = precio_actual <= tp2
        
        if tp2_toque:
            # Cerrar operación completa con ganancia máxima
            pnl_completo = (tp2 - entry) * size_usd / entry if is_long else (entry - tp2) * size_usd / entry
            fee_completo = abs(tp2 - entry) * 0.001  # fee taker
            pnl_neto_completo = pnl_completo - fee_completo
            
            # Actualizar capital
            capital["pnl_realizado_usd"] = capital.get("pnl_realizado_usd", 0) + pnl_neto_completo
            capital["patrimonio_total"] = capital["capital_inicial"] + capital["pnl_realizado_usd"] + capital.get("pnl_flotante_usd", 0)
            capital["portfolio_heat_usd"] = capital.get("portfolio_heat_usd", 0) - margen_usd
            capital["portfolio_heat_pct_patrimonio"] = (
                capital["portfolio_heat_usd"] / capital["patrimonio_total"] * 100
                if capital["patrimonio_total"] > 0 else 0
            )
            
            # Registrar cierre completo
            trade_cerrado = t.copy()
            trade_cerrado["status"] = "closed"
            trade_cerrado["exit_price"] = tp2
            trade_cerrado["exit_reason"] = "TP2 alcanzado (+R)"
            trade_cerrado["pnl_realizado_usd"] = pnl_neto_completo
            trade_cerrado["ts_cierre"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            cerradas_hoy.append(trade_cerrado)
            
            # Remover de abiertas
            abiertas.remove(t)
            
            print(f"  🏆 {activo}: TP2 alcanzado @ ${tp2:,.2f} | PnL completo: ${pnl_neto_completo:+.2f} USD")
            continue
        
        # 3.4 Cierre anticipado por noticia/choque crítico
        # Revisar si hay noticias de riesgo para este símbolo
        # (En implementación completa aquí obtendríamos news del RSS)
        # Por ahora, simulamos revisión simple
        tiene_noticia_riesgo = False  # Se poblaría con datos reales
        
        if tiene_noticia_riesgo and not tp1_hit_actual:
            # Cierre anticipado asegurando ganancia parcial o subiendo SL
            if en_ganancia := (precio_actual - entry) * (1 if is_long else -1) > 0:
                # Ya hay ganancia, asegurar subiendo SL a BE o TP1
                sl_nuevo = tp1 if tp1 > entry if is_long else tp1 < entry else entry
                t["sl"] = sl_nuevo
                print(f"  ⚠️ {activo}: Cierre anticipado por noticia - SL subido a ${sl_nuevo:,.2f}")
            else:
                # Pérdida pequeña, cerrar anticipadamente
                pnl_ant = (sl - entry) * (1 if is_long else -1) * size_usd / entry
                fee_ant = abs(sl - entry) * 0.001
                pnl_ant_neto = pnl_ant - fee_ant
                
                capital["pnl_realizado_usd"] = capital.get("pnl_realizado_usd", 0) + pnl_ant_neto
                capital["patrimonio_total"] = capital["capital_inicial"] + capital["pnl_realizado_usd"] + capital.get("pnl_flotante_usd", 0)
                capital["portfolio_heat_usd"] = capital.get("portfolio_heat_usd", 0) - margen_usd
                capital["portfolio_heat_pct_patrimonio"] = (
                    capital["portfolio_heat_usd"] / capital["patrimonio_total"] * 100
                    if capital["patrimonio_total"] > 0 else 0
                )
                
                trade_cerrado = t.copy()
                trade_cerrado["status"] = "closed"
                trade_cerrado["exit_reason"] = "Cierre anticipado preventivo: Noticia/Giro de tendencia"
                trade_cerrado["exit_price"] = precio_actual
                trade_cerrado["pnl_realizado_usd"] = pnl_ant_neto
                trade_cerrado["ts_cierre"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                cerradas_hoy.append(trade_cerrado)
                abiertas.remove(t)
                
                print(f"  📉 {activo}: Cierre anticipado por noticia | PnL: ${pnl_ant_neto:+.2f} USD")
            continue
    
    # 4. Actualizar trades en el ledger (solo las que cambiaron)
    for t in abiertas:
        _guardar_trade(t)
    # Guardar las nuevas decisiones también
    
    # 5. EVALUAR UNIVERSO para ABRIR NUEVAS OPERACIONES (Paso B del espec)
    print("\n[5] EVALUANDO UNIVERSO PARA NUEVAS OPERACIONES...")
    # Obtener precios y klines para todos los símbolos
    try:
        extra = fetch_extra_multi(UNIVERSO, intervals=["4h", "1w"])
    except Exception as e:
        print(f"  ⚠ Error obteniendo klines extra: {e}")
        extra = {}
    
    # Obtener estados técnicos desde signals
    try:
        from qa.agent.signals import detect_shocks
        # Simulación de screening
        shock_results = {}
    except Exception:
        shock_results = {}
    
    # Calcular riesgo disponible
    riesgo_disponible = max(0, (capital["patrimonio_total"] - capital["portfolio_heat_usd"]) * RISK_PCT_POR_OPERACION)
    heat_actual = capital.get("portfolio_heat_usd", 0)
    
    # Filtrar operaciones ya abiertas
    activos_con_posicion = {t.get("asset") for t in abiertas if t.get("status") == "open"}
    
    # Evaluar cada símbolo
    nuevas_abiertas = []
    for simbolo in UNIVERSO:
        # Saltar si ya hay posición abierta en este activo
        if simbolo in activos_con_posicion:
            print(f"  ⏭️ {simbolo}: Ya hay posición abierta, pasando.")
            continue
        
        # Obtener precio y klines
        precio = _precio_actual(simbolo)
        if precio <= 0:
            print(f"  ⚡ {simbolo}: precio no disponible, descartando.")
            continue
        
        # Obtener klines 4h y 1d
        klines_4h = extra.get(simbolo, {}).get("4h", pd.DataFrame())
        klines_1d = extra.get(simbolo, {}).get("1d", pd.DataFrame())
        
        if klines_4h.empty or klines_1d.empty:
            print(f"  ⚡ {simbolo}: datos insuficientes, descartando.")
            continue
        
        # Calcular indicadores 4H
        sma50_4h = _sma(klines_4h, 50) if len(klines_4h) >= 50 else precio
        sma50_1d = _sma(klines_1d, 50) if len(klines_1d) >= 50 else precio
        atr_4h = _atr(klines_4h, 14)
        
        # Calcular indicadores 1D
        sma50_1d_val = _sma(klines_1d, 50) if len(klines_1d) >= 50 else precio
        atr_1d = _atr(klines_1d, 14)
        
        # Tendencia 4H y 1D
        tendencia_4h = "alcista" if precio > sma50_4h else "bajista"
        tendencia_1d = "alcista" if precio > sma50_1d_val else "bajista"
        
        # Filtro de R:R Neto >= 2.0x
        # SL técnico = SMA50 del marco (o Entry ∓ 1.5×ATR, el que dé mejor estructura)
        sl_4h = sma50_4h
        sl_1d = sma50_1d_val
        
        # Para LONG: entrada > SMA50 en ambos marcos
        es_longo_valido = tendencia_4h == "alcista" and tendencia_1d == "alcista"
        
        if not es_longo_valido:
            print(f"  ⚪ {simbolo}: Tendencia no alineada 4H/{tendencia_4h}, 1D/{tendencia_1d} — DESCARTADA")
            continue
        
        # Calcular TP1 y TP2 basándose en SL = SMA50
        entry = precio
        tp1, tp2 = _calcular_tp1_tp2(entry, sl_4h, is_long=True)
        
        # Verificar R:R neto hacia TP2
        if not _verificar_filtro_rr(entry, sl_4h, tp2, is_long=True):
            rr_actual = (_calcular_rr(entry, sl_4h, tp2, is_long=True)["rr_tp2"])
            print(f"  🟡 {simbolo}: R:R neto {rr_actual:.2f}x < {MIN_RR_NETO}x — DESCARTADA (extendido)")
            continue
        
        # Filtro de noticias y choques
        # Revisar noticias de riesgo (aquí irían las news reales del RSS)
        tiene_noticia_riesgo = bool(shock_results.get(simbolo, {}).get("tipo", "").startswith("noticia"))
        if tiene_noticia_riesgo:
            print(f"  🔴 {simbolo}: Noticia de riesgo activo — DESCARTADA")
            continue
        
        # Control de riesgo: 1.5% del patrimonio vivo
        riesgo_por_op = capital["patrimonio_total"] * RISK_PCT_POR_OPERACION
        margen_requerido = riesgo_por_op / (abs(entry - sl_4h) / entry) if abs(entry - sl_4h) > 0 else 0
        apalancamiento = max(LEV_SPORT, min(LEV_FUTURES_MAX, int(margen_requerido / 20.0)))  # 20% de cuenta max por operación
        apalancamiento = max(LEV_FUTURES_MIN, apalancamiento)
        
        # Asegurar que el margen no supere 20% de la cuenta
        margen_max = capital["patrimonio_total"] * 0.20
        if margen_requerido > margen_max:
            # Reducir tamaño o apalancamiento
            apalancamiento = max(LEV_FUTURES_MIN, int(margen_max / riesgo_por_op))
            tamaño_usd = riesgo_por_op
        else:
            tamaño_usd = riesgo_por_op
        
        # Calcular tamaño en unidades y margen
        riesgo_pct = abs(entry - sl_4h) / entry * 100  # riesgo percentual
        margen_usd = tamaño_usd / apalancamiento if apalancamiento > 0 else 0
        
        # Verificar heat total
        nuevo_heat = heat_actual + margen_usd
        if nuevo_heat > capital["patrimonio_total"] * MAX_HEAT_PCT_PATRIMONIO:
            print(f"  ⚪ {simbolo}: Heat de mesa excedido ({nuevo_heat:.1f}% > {MAX_HEAT_PCT_PATRIMONIO*100:.1f}%) — DESCARTADA")
            continue
        
        # Verificar límite de operaciones abiertas
        if len(abiertas) >= MAX_OPERACIONES_ABERTAS:
            print(f"  ⚪ {simbolo}: Límite de {MAX_OPERACIONES_ABERTAS} operaciones abiertas — DESCARTADA")
            continue
        
        # ABRIR OPERACIÓN AUTÓNOMAMENTE
        trade_nuevo = {
            "asset": simbolo,
            "kind": "future_long" if apalancamiento > 1 else "spot",
            "timeframe": "4h",
            "entry": round(entry, 2),
            "sl": round(sl_4h, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "leverage": int(apalancamiento),
            "margin_usd": round(margen_usd, 2),
            "size_usd": round(tamaño_usd, 2),
            "risk_usd": round(riesgo_por_op, 2),
            "rr_neto": round(_calcular_rr(entry, sl_4h, tp2, is_long=True)["rr_tp2"], 2),
            "tp1_hit": False,
            "status": "open",
            "fecha_apertura": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "reason_open": f"Autopilot M6: Largo {apalancamiento}x, SL=SMA50 4H, TP1=1.5R (${tp1:,.2f}), TP2=3.0R (${tp2:,.2f}), R:R={_calcular_rr(entry, sl_4h, tp2, is_long=True)['rr_tp2']:.2f}x, Heat={nuevo_heat*100/ capital['patrimonio_total']:.1f}%",
            "precio_actual_ref": round(precio, 2),
        }
        
        # Registrar en ledger
        _guardar_trade(trade_nuevo)
        abiertas.append(trade_nuevo)
        nuevas_abiertas.append(trade_nuevo)
        
        # Actualizar capital y heat
        capital["portfolio_heat_usd"] = nuevo_heat
        capital["portfolio_heat_pct_patrimonio"] = nuevo_heat / capital["patrimonio_total"] * 100
        capital["patrimonio_total"] = capital["capital_inicial"] + capital["pnl_realizado_usd"] + capital.get("pnl_flotante_usd", 0)
        
        print(f"  🟢 {simbolo}: OPERACIÓN AUTÓNOMA ABIERTA")
        print(f"     · Largo {int(apalancamiento)}x · Entrada: ${entry:,.2f}")
        print(f"     · SL: ${sl_4h:,.2f} (SMA50 4H) · TP1: ${tp1:,.2f} (1.5R) · TP2: ${tp2:,.2f} (3.0R)")
        print(f"     · Riesgo: ${riesgo_por_op:.2f} USD ({RISK_PCT_POR_OPERACION*100:.1f}%)")
        print(f"     · Margen: ${margen_usd:.2f} · Apalancamiento: {int(apalancamiento)}x")
        print(f"     · R:R neto: {_calcular_rr(entry, sl_4h, tp2, is_long=True)['rr_tp2']:.2f}x")
    
    # 6. Guardar capital actualizado
    _guardar_capital(capital)
    
    # 7. Generar reporte final
    reporte = {
        "capital_anterior": patrimonio_anterior,
        "capital_nuevo": capital["patrimonio_total"],
        "delta_patrimonio": capital["patrimonio_total"] - patrimonio_anterior,
        "nuevas_abiertas": len(nuevas_abiertas),
        "cierre_operaciones": len(cerradas_hoy),
        "win_rate_hoy": 0.0,  # Se calcularía con operaciones cerradas hoy
        "pnl_hoy": capital["pnl_realizado_usd"] - (patrimonio_anterior - capital_inicial),
        "heat_final": capital.get("portfolio_heat_pct_patrimonio", 0),
    }
    
    print("\n" + "=" * 60)
    print("✅ M6 Autopilot corrida completada")
    print(f"   • Nuevas abiertas: {len(nuevas_abiertas)}")
    print(f"   • Cierres hoy: {len(cerradas_hoy)}")
    print(f"   • PnL del día: ${reporte['pnl_hoy']:+.2f} USD")
    print(f"   • Patrimonio: ${reporte['capital_nuevo']:,.2f} USD")
    print(f"   • Heat en mesa: {reporte['heat_final']*100:.1f}%")
    print("=" * 60)
    
    return {
        "capital_actualizado": capital,
        "nuevas_abiertas": nuevas_abiertas,
        "cierre_operaciones": cerradas_hoy,
        "reporte": reporte,
    }


if __name__ == "__main__":
    """Punto de entrada directo: al ejecutar `python -m qa.agent.autopilot`"""
    import sys
    capital_arg = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
    resultado = autonomous_run(capital_inicial=capital_arg)
    print("\nResultado JSON:")
    print(json.dumps(resultado, indent=2, default=str))