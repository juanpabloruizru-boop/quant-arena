# Informe de calidad de datos — M1

- Freeze de datos (ultimo dia UTC completo): **2026-10-25 23:59:59.999000+00:00**
- Holdout sellado: **2025-10-26 00:00:00+00:00 → 2026-10-25 23:59:59.999000+00:00** (365 dias, ficheros `*_holdout.parquet` fisicamente separados)
- Duplicados (symbol, ts) eliminados en curacion: {'funding': 0, 'futures_daily': 0, 'spot_daily': 0}
- Fallos de manifiestos SHA256: 0

## Spot diario (in-sample)
- Simbolos: **427** · filas: 479954 (holdout: SELLADO (AES256; sha256 en ledger/holdout_seal.log))
- Rango: 2017-08-17 00:00:00+00:00 → 2025-10-25 00:00:00+00:00 · tz UTC: True
- Grupos duplicados residuales: 0 · filas con precios imposibles (close<=0 o high<low): 0
- Simbolos sin ningun hueco: 415 (detalle completo: `reports/M1_coverage_by_symbol.csv`)
- Peores coberturas: [{'symbol': 'VENUSDT', 'missing_pct': 72.5, 'max_gap_days': 88}, {'symbol': 'FTTUSDT', 'missing_pct': 14.506, 'max_gap_days': 311}, {'symbol': 'CVCUSDT', 'missing_pct': 6.794, 'max_gap_days': 154}, {'symbol': 'KEYUSDT', 'missing_pct': 1.446, 'max_gap_days': 28}, {'symbol': 'BCCUSDT', 'missing_pct': 1.067, 'max_gap_days': 5}]

## Outliers (z robusto sobre log-retornos, |z|>8 — QA de datos, no metrica de estrategia)
- Filas marcadas: 1672
- Top 10: [{'symbol': 'LUNAUSDT', 'open_time': '2022-05-31 00:00:00+00:00', 'lr': 12.086162348857615, 'z': 268.50272577228077}, {'symbol': 'SUNUSDT', 'open_time': '2021-06-18 00:00:00+00:00', 'lr': -6.7265344777078475, 'z': -230.63448367093838}, {'symbol': 'LUNAUSDT', 'open_time': '2022-05-12 00:00:00+00:00', 'lr': -8.121276105523199, 'z': -180.3720641617547}, {'symbol': 'VENUSDT', 'open_time': '2018-10-19 00:00:00+00:00', 'lr': -9.815694051585458, 'z': -168.4732871774236}, {'symbol': 'COCOSUSDT', 'open_time': '2021-01-23 00:00:00+00:00', 'lr': 7.166571474531776, 'z': 162.0878181890555}]

## Funding (perp USDT-M, historico real)
- **BTCUSDT**: 6713 registros (2019-09-10 08:00:00+00:00 → 2025-10-25 16:00:00.001000+00:00), esperados@8h 6713, faltan 0, huecos>8.5h: 0 (max 8.0h), rate medio 0.000117 [min -0.0030, max 0.0030]
- **ETHUSDT**: 6479 registros (2019-11-27 08:00:00+00:00 → 2025-10-25 16:00:00.001000+00:00), esperados@8h 6479, faltan 0, huecos>8.5h: 0 (max 8.0h), rate medio 0.000142 [min -0.0036, max 0.0037]
- Cross-check API vs dump mensual vision (BTCUSDT 2020-01): 93 registros comunes, **0 discrepancias** (sha256 del zip: 7f81b2f3694d1377…)

## Universo PIT (top-N mensual)
- Meses: 97 (2017-11-01 00:00:00+00:00 → 2025-11-01 00:00:00+00:00)
- Candidatos por mes: min 2, mediana 40.0
- Primer mes con >=20 candidatos: 2019-04-01 00:00:00+00:00
- Primer mes con >=40 candidatos: 2019-07-01 00:00:00+00:00
- Simbolos distintos que alguna vez estuvieron en top-20: 150

## Pool de ingesta y deslistados
- Pool (union top-60 mensual + BTC/ETH): 485 simbolos (universo mensual: 689)
- Deslistados/ausentes del exchangeInfo actual incluidos: 135 → ['AGIXUSDT', 'AIONUSDT', 'AKROUSDT', 'ALPACAUSDT', 'ALPHAUSDT', 'AMBUSDT', 'ANCUSDT', 'ANTUSDT', 'ATAUSDT', 'AUDUSDT', 'BAKEUSDT', 'BCCUSDT']

## Futures diario (perp USDT-M)
- ['BTCUSDT', 'ETHUSDT'] · filas in-sample: 4400 · desde 2019-09-08 00:00:00+00:00

## Limitaciones y sesgos declarados
1. **Supervivencia del venue:** solo existe lo que Binance listo. Los dumps conservan deslistados (incluidos en el pool cuando fueron top-60 mensual), pero monedas muertas que nunca cotizaron en Binance son invisibles.
2. **Pool top-60 mensual como filtro de ingesta:** el ranking diario top-20 se reconstruye dentro del pool. Riesgo residual: un simbolo top-20 diario que nunca fuese top-60 mensual quedaria fuera (margen 3x; auditado mes a mes en el JSON).
3. **Regimen 2017-18:** liquidez y spreads de la microestructura temprana; los costes verificados en 2026 la subestiman (protegido por stress x2, PRERREGISTRO s3).
4. **PIT fino pre-2019:** meses con <20 candidatos existen; H2 arranca cuando first_month_with_20 lo permita (reportado arriba).
5. **NBTUSDT** (unico simbolo USDT con dumps y sin entrada en exchangeInfo actual) se ingirio via vision monthly si sus dumps existen; en otro caso queda documentado.
6. El funding anterior a 2019-09 no existe (perps USD-M lanzados en 2019): H3 empieza ahi. ETHUSDT puede empezar despues que BTCUSDT: aplicar regla P4 (MDE por activo; ETH INCONTRASTABLE si MDE_ETH > 2x MDE_BTC).

**Ninguna metrica de estrategia (retorno/Sharpe/drawdown de reglas) fue calculada en M1**, segun la prohibicion del gate M0b.

