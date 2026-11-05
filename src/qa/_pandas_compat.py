# ruff: noqa
# Pure Python + NumPy compatibility fallback for pandas when C-extensions are blocked
"""Compatibilidad pura de pandas con NumPy y tipos nativos de Python.

Diseñado para entornos Windows con Application Control (WDAC/Smart App Control)
donde la carga de C-extensions de pandas (interval, ops_dispatch) está bloqueada.
Proporciona DataFrame, Series, Timestamp, concat, NaT, etc., con interfaz idéntica
para todo el pipeline analítico y cuantitativo de QUANT-ARENA.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np


class NaTType:
    def __repr__(self) -> str:
        return "NaT"

    def __bool__(self) -> bool:
        return False


NaT = NaTType()


def isna(val: Any) -> bool:
    if val is None or val is NaT:
        return True
    if isinstance(val, (float, np.floating)) and np.isnan(val):
        return True
    return False


def notna(val: Any) -> bool:
    return not isna(val)


isnull = isna


class Timestamp:
    """Wrapper compatible de datetime / pd.Timestamp."""

    def __init__(self, val: Any = None, tz: Any = None) -> None:
        if val is None:
            self._dt = datetime.now(UTC if tz is not None else None)
        elif isinstance(val, Timestamp):
            self._dt = val._dt
        elif isinstance(val, datetime):
            self._dt = val
        elif isinstance(val, (int, float, np.integer, np.floating)):
            # asumir ms si > 1e11, else segundos
            ts = float(val)
            if ts > 1e11:
                ts /= 1000.0
            self._dt = datetime.fromtimestamp(ts, tz=UTC)
        elif isinstance(val, str):
            clean = val.replace("Z", "+00:00").strip()
            self._dt = datetime.fromisoformat(clean)
        else:
            self._dt = datetime.now(UTC)

        if tz is not None:
            if self._dt.tzinfo is None:
                self._dt = self._dt.replace(tzinfo=tz if isinstance(tz, type(UTC)) else UTC)
            else:
                self._dt = self._dt.astimezone(tz if isinstance(tz, type(UTC)) else UTC)

    @classmethod
    def now(cls, tz: Any = None) -> Timestamp:
        return cls(datetime.now(tz if tz is not None else UTC))

    def date(self) -> Any:
        return self._dt.date()

    def time(self) -> Any:
        return self._dt.time()

    @property
    def year(self) -> int:
        return self._dt.year

    @property
    def month(self) -> int:
        return self._dt.month

    @property
    def day(self) -> int:
        return self._dt.day

    @property
    def hour(self) -> int:
        return self._dt.hour

    @property
    def minute(self) -> int:
        return self._dt.minute

    @property
    def second(self) -> int:
        return self._dt.second

    def isoformat(self, timespec: str = "auto") -> str:
        return self._dt.isoformat(timespec=timespec)

    def strftime(self, fmt: str) -> str:
        return self._dt.strftime(fmt)

    def tz_localize(self, tz: Any) -> Timestamp:
        dt = self._dt.replace(tzinfo=tz if isinstance(tz, type(UTC)) else UTC)
        return Timestamp(dt)

    def tz_convert(self, tz: Any) -> Timestamp:
        dt = self._dt.astimezone(tz if isinstance(tz, type(UTC)) else UTC)
        return Timestamp(dt)

    @property
    def tzinfo(self) -> Any:
        return self._dt.tzinfo

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Timestamp):
            return self._dt == other._dt
        if isinstance(other, datetime):
            return self._dt == other
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Timestamp):
            return self._dt < other._dt
        if isinstance(other, datetime):
            return self._dt < other
        return False

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Timestamp):
            return self._dt <= other._dt
        if isinstance(other, datetime):
            return self._dt <= other
        return False

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Timestamp):
            return self._dt > other._dt
        if isinstance(other, datetime):
            return self._dt > other
        return False

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Timestamp):
            return self._dt >= other._dt
        if isinstance(other, datetime):
            return self._dt >= other
        return False

    def __sub__(self, other: Any) -> Any:
        if isinstance(other, Timestamp):
            return self._dt - other._dt
        if isinstance(other, datetime):
            return self._dt - other
        if isinstance(other, timedelta):
            return Timestamp(self._dt - other)
        raise TypeError(f"unsupported operand type(s) for -: 'Timestamp' and '{type(other).__name__}'")

    def __add__(self, other: Any) -> Timestamp:
        if isinstance(other, timedelta):
            return Timestamp(self._dt + other)
        raise TypeError(f"unsupported operand type(s) for +: 'Timestamp' and '{type(other).__name__}'")

    def __repr__(self) -> str:
        return f"Timestamp('{self._dt.isoformat()}')"

    def __str__(self) -> str:
        return self._dt.isoformat()

    def __hash__(self) -> int:
        return hash(self._dt)

    def to_period(self, freq: str = "M") -> Timestamp:
        dt = self._dt
        fl = str(freq).upper()
        if "M" in fl:
            dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif "W" in fl:
            dt = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return Timestamp(dt)

    def to_timestamp(self) -> Timestamp:
        return self


Timedelta = timedelta


class _IlocIndexer:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def __getitem__(self, item: Any) -> Any:
        if isinstance(self._obj, Series):
            arr = self._obj._arr
            if isinstance(item, (int, np.integer)):
                val = arr[item]
                if isinstance(val, (np.generic,)):
                    return val.item()
                return val
            if isinstance(item, slice):
                return Series(arr[item], index=self._obj._index[item] if self._obj._index is not None else None)
            if isinstance(item, (list, np.ndarray)):
                idx = np.asarray(item)
                return Series(arr[idx])
        elif isinstance(self._obj, DataFrame):
            if isinstance(item, (int, np.integer)):
                # Fila individual -> Series
                row_dict = {col: self._obj._data[col][item] for col in self._obj._columns}
                return Series(row_dict)
            if isinstance(item, slice):
                new_data = {col: self._obj._data[col][item] for col in self._obj._columns}
                new_idx = self._obj._index[item] if self._obj._index is not None else None
                return DataFrame(new_data, columns=self._obj._columns, index=new_idx)
            if isinstance(item, (list, np.ndarray)):
                idx = np.asarray(item)
                new_data = {col: self._obj._data[col][idx] for col in self._obj._columns}
                new_idx = [self._obj._index[i] for i in idx] if self._obj._index is not None else None
                return DataFrame(new_data, columns=self._obj._columns, index=new_idx)
            if isinstance(item, tuple) and len(item) == 2:
                row_idx, col_idx = item
                if isinstance(col_idx, (list, tuple)):
                    cols = [c for c in col_idx if c in self._obj._columns]
                    sub_data = {c: self._obj._data[c] for c in cols}
                    sub_df = DataFrame(sub_data, columns=cols, index=self._obj._index)
                    if isinstance(row_idx, slice) and row_idx == slice(None, None, None):
                        return sub_df
                    return sub_df.iloc[row_idx]
                if isinstance(col_idx, (int, np.integer)):
                    col_name = self._obj._columns[col_idx]
                    return self._obj._data[col_name][row_idx]
                if isinstance(col_idx, str):
                    return self._obj._data[col_idx][row_idx]
        raise IndexError(f"Index {item} not supported by iloc")

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(self._obj, DataFrame):
            if isinstance(key, tuple) and len(key) == 2:
                row_idx, col_idx = key
                if isinstance(col_idx, str):
                    self._obj._data[col_idx][row_idx] = value
                    return
                if isinstance(col_idx, (int, np.integer)):
                    col_name = self._obj._columns[col_idx]
                    self._obj._data[col_name][row_idx] = value
                    return
        elif isinstance(self._obj, Series):
            self._obj._arr[key] = value


class _LocIndexer:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def __getitem__(self, item: Any) -> Any:
        return self._obj._iloc[item]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._obj._iloc[key] = value


class _Rolling:
    def __init__(self, series: Series, window: int, min_periods: int | None = None) -> None:
        self._series = series
        self._w = max(1, int(window))
        self._min_p = min_periods if min_periods is not None else self._w

    def mean(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - self._w + 1)
            window_slice = arr[start : i + 1]
            valid = window_slice[~np.isnan(window_slice)]
            if len(valid) >= self._min_p:
                out[i] = np.mean(valid)
        return Series(out, index=self._series._index)

    def std(self, ddof: int = 1) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - self._w + 1)
            window_slice = arr[start : i + 1]
            valid = window_slice[~np.isnan(window_slice)]
            if len(valid) >= max(2, self._min_p):
                out[i] = np.std(valid, ddof=ddof)
            elif len(valid) >= self._min_p and ddof == 0:
                out[i] = np.std(valid, ddof=0)
        return Series(out, index=self._series._index)

    def max(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - self._w + 1)
            window_slice = arr[start : i + 1]
            valid = window_slice[~np.isnan(window_slice)]
            if len(valid) >= self._min_p:
                out[i] = np.max(valid)
        return Series(out, index=self._series._index)

    def min(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - self._w + 1)
            window_slice = arr[start : i + 1]
            valid = window_slice[~np.isnan(window_slice)]
            if len(valid) >= self._min_p:
                out[i] = np.min(valid)
        return Series(out, index=self._series._index)

    def sum(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - self._w + 1)
            window_slice = arr[start : i + 1]
            valid = window_slice[~np.isnan(window_slice)]
            if len(valid) >= self._min_p:
                out[i] = np.sum(valid)
        return Series(out, index=self._series._index)


class _EWM:
    def __init__(self, series: Series, span: float, adjust: bool = False) -> None:
        self._series = series
        self._alpha = 2.0 / (span + 1.0)
        self._adjust = adjust

    def mean(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.zeros(n, dtype=float)
        if n == 0:
            return Series(out)
        out[0] = arr[0]
        alpha = self._alpha
        for i in range(1, n):
            val = arr[i]
            if np.isnan(val):
                out[i] = out[i - 1]
            else:
                out[i] = alpha * val + (1.0 - alpha) * out[i - 1]
        return Series(out, index=self._series._index)


class _Expanding:
    def __init__(self, series: Series, min_periods: int = 1) -> None:
        self._series = series
        self._min_p = max(1, min_periods)

    def mean(self) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        c_sum = 0.0
        c_count = 0
        for i in range(n):
            val = arr[i]
            if not np.isnan(val):
                c_sum += val
                c_count += 1
            if c_count >= self._min_p:
                out[i] = c_sum / c_count
        return Series(out, index=self._series._index)

    def std(self, ddof: int = 1) -> Series:
        arr = self._series.to_numpy(dtype=float)
        n = len(arr)
        out = np.full(n, np.nan, dtype=float)
        vals: list[float] = []
        for i in range(n):
            val = arr[i]
            if not np.isnan(val):
                vals.append(val)
            if len(vals) >= max(1, self._min_p):
                if len(vals) == 1 and ddof == 1:
                    out[i] = np.nan
                else:
                    out[i] = float(np.std(vals, ddof=ddof))
        return Series(out, index=self._series._index)


class _PeriodAccessor:
    def __init__(self, series: Series, freq: str = "W") -> None:
        self._series = series
        self._freq = freq

    @property
    def start_time(self) -> Series:
        arr = self._series.to_numpy()
        fl = self._freq.upper()
        res = []
        for x in arr:
            ts = Timestamp(x)
            dt = ts._dt
            if "W" in fl:
                dt = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            elif "M" in fl:
                dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            res.append(Timestamp(dt))
        return Series(res, index=self._series._index)

    @property
    def dt(self) -> _DtAccessor:
        return _DtAccessor(self.start_time)


class _DtAccessor:
    def __init__(self, series: Series) -> None:
        self._series = series

    def to_period(self, freq: str = "D") -> _PeriodAccessor:
        return _PeriodAccessor(self._series, freq=freq)

    @property
    def dt(self) -> _DtAccessor:
        return self

    def floor(self, freq: str) -> Series:
        arr = self._series.to_numpy()
        floored = []
        for x in arr:
            ts = Timestamp(x)
            dt = ts._dt
            if freq in ("D", "d"):
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            floored.append(Timestamp(dt))
        return Series(floored, index=self._series._index)

    @property
    def start_time(self) -> Series:
        return self._series

    def tz_localize(self, tz: Any) -> Series:
        return self._series.tz_localize(tz)

    def tz_convert(self, tz: Any) -> Series:
        return self._series.tz_convert(tz)

    @property
    def tz(self) -> str:
        return "UTC"

    @property
    def hour(self) -> Series:
        arr = self._series.to_numpy()
        hours = [Timestamp(x)._dt.hour for x in arr]
        return Series(hours, index=self._series._index)

    @property
    def day(self) -> Series:
        arr = self._series.to_numpy()
        days = [Timestamp(x)._dt.day for x in arr]
        return Series(days, index=self._series._index)

    @property
    def month(self) -> Series:
        arr = self._series.to_numpy()
        months = [Timestamp(x)._dt.month for x in arr]
        return Series(months, index=self._series._index)

    @property
    def year(self) -> Series:
        arr = self._series.to_numpy()
        years = [Timestamp(x)._dt.year for x in arr]
        return Series(years, index=self._series._index)

    def strftime(self, fmt: str) -> Series:
        arr = self._series.to_numpy()
        formatted = []
        for x in arr:
            ts = Timestamp(x)
            formatted.append(ts._dt.strftime(fmt))
        return Series(formatted, index=self._series._index)


class Series:
    """Implementación pura de pandas.Series sobre NumPy ndarray."""

    def __init__(self, data: Any = None, index: Any = None, name: Any = None, dtype: Any = None) -> None:
        self.name = name
        if isinstance(data, Series):
            self._arr = data._arr.copy()
            self._index = data._index if index is None else index
        elif isinstance(data, dict):
            keys = list(data.keys())
            vals = list(data.values())
            self._arr = np.asarray(vals)
            self._index = keys if index is None else index
        elif data is None:
            self._arr = np.array([], dtype=dtype if dtype is not None else float)
            self._index = []
        else:
            self._arr = np.asarray(data)
            if dtype is not None:
                self._arr = self._arr.astype(dtype)
            self._index = index

        self._iloc = _IlocIndexer(self)
        self._loc = _LocIndexer(self)

    @property
    def iloc(self) -> _IlocIndexer:
        return self._iloc

    @property
    def loc(self) -> _LocIndexer:
        return self._loc

    @property
    def index(self) -> Any:
        if self._index is not None:
            return self._index
        return range(len(self._arr))

    @property
    def empty(self) -> bool:
        return len(self._arr) == 0

    @property
    def dtype(self) -> Any:
        return self._arr.dtype

    @property
    def values(self) -> np.ndarray:
        return self._arr

    @property
    def dt(self) -> _DtAccessor:
        return _DtAccessor(self)

    def to_numpy(self, dtype: Any = None) -> np.ndarray:
        if dtype is not None:
            return self._arr.astype(dtype)
        return self._arr

    def astype(self, dtype: Any) -> Series:
        return Series(self._arr.astype(dtype), index=self._index, name=self.name)

    def to_list(self) -> list[Any]:
        return self._arr.tolist()

    tolist = to_list

    def __len__(self) -> int:
        return len(self._arr)

    def __iter__(self) -> Iterable[Any]:
        return iter(self._arr)

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, (int, np.integer)):
            val = self._arr[item]
            if isinstance(val, np.generic):
                return val.item()
            return val
        if isinstance(item, slice):
            return Series(self._arr[item], index=self._index[item] if self._index is not None else None)
        if isinstance(item, Series):
            item = item.to_numpy(dtype=bool)
        if isinstance(item, np.ndarray) and item.dtype == bool:
            new_idx = [self._index[i] for i, b in enumerate(item) if b] if self._index is not None else None
            return Series(self._arr[item], index=new_idx, name=self.name)
        if isinstance(item, (list, tuple)):
            if len(item) > 0 and isinstance(item[0], (bool, np.bool_)):
                new_idx = [self._index[i] for i, b in enumerate(item) if b] if self._index is not None else None
                return Series(self._arr[np.asarray(item, dtype=bool)], index=new_idx, name=self.name)
            new_idx = [self._index[i] for i in item] if self._index is not None else None
            return Series(self._arr[item], index=new_idx, name=self.name)
        # Intentar por clave en index dict-like
        if self._index is not None and item in self._index:
            idx = self._index.index(item)
            return self._arr[idx]
        return self._arr[item]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._arr[key] = value

    # Operadores aritméticos
    def __add__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr + o, index=self._index, name=self.name)

    def __radd__(self, other: Any) -> Series:
        return self.__add__(other)

    def __sub__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr - o, index=self._index, name=self.name)

    def __rsub__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(o - self._arr, index=self._index, name=self.name)

    def __mul__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr * o, index=self._index, name=self.name)

    def __rmul__(self, other: Any) -> Series:
        return self.__mul__(other)

    def __truediv__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        with np.errstate(divide="ignore", invalid="ignore"):
            res = self._arr.astype(float) / o
        return Series(res, index=self._index, name=self.name)

    def __rtruediv__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        with np.errstate(divide="ignore", invalid="ignore"):
            res = o / self._arr.astype(float)
        return Series(res, index=self._index, name=self.name)

    def __neg__(self) -> Series:
        return Series(-self._arr, index=self._index, name=self.name)

    def __abs__(self) -> Series:
        return Series(np.abs(self._arr), index=self._index, name=self.name)

    def __and__(self, other: Any) -> Series:
        o = other.to_numpy(dtype=bool) if isinstance(other, Series) else np.asarray(other, dtype=bool)
        return Series(self._arr.astype(bool) & o, index=self._index)

    def __rand__(self, other: Any) -> Series:
        return self.__and__(other)

    def __or__(self, other: Any) -> Series:
        o = other.to_numpy(dtype=bool) if isinstance(other, Series) else np.asarray(other, dtype=bool)
        return Series(self._arr.astype(bool) | o, index=self._index)

    def __ror__(self, other: Any) -> Series:
        return self.__or__(other)

    def __invert__(self) -> Series:
        return Series(~self._arr.astype(bool), index=self._index)

    # Comparaciones
    def __gt__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr > o, index=self._index)

    def __ge__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr >= o, index=self._index)

    def __lt__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr < o, index=self._index)

    def __le__(self, other: Any) -> Series:
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr <= o, index=self._index)

    def __eq__(self, other: Any) -> Series:  # type: ignore[override]
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr == o, index=self._index)

    def __ne__(self, other: Any) -> Series:  # type: ignore[override]
        o = other.to_numpy() if isinstance(other, Series) else other
        return Series(self._arr != o, index=self._index)

    # Métodos estadísticos y analíticos
    def mean(self) -> float:
        valid = self._arr[~np.isnan(self._arr)] if np.issubdtype(self._arr.dtype, np.floating) else self._arr
        return float(np.mean(valid)) if len(valid) else float("nan")

    def std(self, ddof: int = 1) -> float:
        valid = self._arr[~np.isnan(self._arr)] if np.issubdtype(self._arr.dtype, np.floating) else self._arr
        return float(np.std(valid, ddof=ddof)) if len(valid) > ddof else float("nan")

    def min(self) -> Any:
        return np.min(self._arr) if len(self._arr) else float("nan")

    def max(self) -> Any:
        return np.max(self._arr) if len(self._arr) else float("nan")

    def sum(self) -> Any:
        return np.sum(self._arr) if len(self._arr) else 0

    def diff(self, periods: int = 1) -> Series:
        arr = self._arr.astype(float)
        out = np.full_like(arr, np.nan)
        if len(arr) > periods:
            out[periods:] = arr[periods:] - arr[:-periods]
        return Series(out, index=self._index)

    def where(self, cond: Any, other: Any = np.nan) -> Series:
        c = cond.to_numpy(dtype=bool) if isinstance(cond, Series) else np.asarray(cond, dtype=bool)
        out = np.where(c, self._arr, other)
        return Series(out, index=self._index)

    def replace(self, to_replace: Any, value: Any) -> Series:
        out = self._arr.copy()
        out[out == to_replace] = value
        return Series(out, index=self._index)

    def fillna(self, value: Any) -> Series:
        out = self._arr.copy()
        if np.issubdtype(out.dtype, np.floating):
            out[np.isnan(out)] = value
        return Series(out, index=self._index)

    def reindex(self, index: Any, fill_value: Any = np.nan) -> Series:
        old_idx = list(self.index)
        val_map = {k: v for k, v in zip(old_idx, self._arr, strict=False)}
        new_arr = [val_map.get(k, fill_value) for k in index]
        return Series(new_arr, index=list(index), name=self.name)

    def tail(self, n: int = 5) -> Series:
        return Series(self._arr[-n:], index=self._index[-n:] if self._index is not None else None)

    def head(self, n: int = 5) -> Series:
        return Series(self._arr[:n], index=self._index[:n] if self._index is not None else None)

    def rolling(self, window: int, min_periods: int | None = None) -> _Rolling:
        return _Rolling(self, window, min_periods)

    def ewm(self, span: float, adjust: bool = False) -> _EWM:
        return _EWM(self, span, adjust=adjust)

    def expanding(self, min_periods: int = 1) -> _Expanding:
        return _Expanding(self, min_periods)

    def items(self) -> Iterable[tuple[Any, Any]]:
        idx = self.index
        for i, val in enumerate(self._arr):
            k = idx[i] if i < len(idx) else i
            v = val.item() if isinstance(val, np.generic) else val
            yield k, v

    def shift(self, periods: int = 1, fill_value: Any = np.nan) -> Series:
        arr = self._arr.copy().astype(float)
        out = np.full_like(arr, fill_value)
        if periods > 0 and len(arr) > periods:
            out[periods:] = arr[:-periods]
        elif periods < 0 and len(arr) > abs(periods):
            out[:periods] = arr[-periods:]
        elif periods == 0:
            out = arr
        return Series(out, index=self._index, name=self.name)

    def dropna(self) -> Series:
        arr = self._arr
        if np.issubdtype(arr.dtype, np.floating):
            mask = ~np.isnan(arr)
            return Series(arr[mask], index=np.asarray(self.index)[mask] if self._index is not None else None, name=self.name)
        return self.copy()

    def __array_ufunc__(self, ufunc: Any, method: str, *inputs: Any, **kwargs: Any) -> Any:
        if method == "__call__":
            raw_inputs = [x.to_numpy() if isinstance(x, Series) else x for x in inputs]
            result = ufunc(*raw_inputs, **kwargs)
            if isinstance(result, np.ndarray):
                return Series(result, index=self._index, name=self.name)
            return result
        return NotImplemented

    def any(self) -> bool:
        return bool(np.any(self._arr))

    def all(self) -> bool:
        return bool(np.all(self._arr))

    def sort_index(self, ascending: bool = True) -> Series:
        return self.copy()

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def tz_localize(self, tz: Any) -> Series:
        arr = [Timestamp(x).tz_localize(tz) for x in self._arr]
        return Series(arr, index=self._index, name=self.name)

    def tz_convert(self, tz: Any) -> Series:
        arr = [Timestamp(x).tz_convert(tz) for x in self._arr]
        return Series(arr, index=self._index, name=self.name)

    def bfill(self) -> Series:
        arr = self._arr.copy()
        n = len(arr)
        last_val = None
        for i in range(n - 1, -1, -1):
            val = arr[i]
            if isinstance(val, (float, np.floating)) and np.isnan(val):
                if last_val is not None:
                    arr[i] = last_val
            else:
                last_val = val
        return Series(arr, index=self._index, name=self.name)

    def rank(self, ascending: bool = True, method: str = "first") -> Series:
        arr = self._arr
        n = len(arr)
        if ascending:
            order = np.argsort(arr, kind="stable")
        else:
            order = np.argsort(-arr, kind="stable")
        ranks = np.empty(n, dtype=float)
        ranks[order] = np.arange(1, n + 1, dtype=float)
        return Series(ranks, index=self._index, name=self.name)

    def pct_change(self) -> Series:
        arr = self._arr.astype(float)
        shifted = np.empty_like(arr)
        shifted[0] = np.nan
        shifted[1:] = arr[:-1]
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = (arr - shifted) / shifted
        return Series(pct, index=self._index, name=self.name)

    def min(self) -> Any:
        return np.min(self._arr) if len(self._arr) else np.nan

    def max(self) -> Any:
        return np.max(self._arr) if len(self._arr) else np.nan

    def isin(self, values: Any) -> Series:
        val_set = set(values)
        res = [x in val_set for x in self._arr]
        return Series(res, index=self._index)

    def unstack(self, level: Any = -1) -> DataFrame:
        if not self._index or not isinstance(self._index[0], tuple):
            return DataFrame()
        row_keys = sorted(list({k[0] for k in self._index}))
        col_keys = sorted(list({k[1] for k in self._index}))
        col_indices = {c: j for j, c in enumerate(col_keys)}
        row_indices = {r: i for i, r in enumerate(row_keys)}
        mat = np.full((len(row_keys), len(col_keys)), np.nan)
        for (r, c), val in zip(self._index, self._arr, strict=False):
            if r in row_indices and c in col_indices:
                mat[row_indices[r], col_indices[c]] = val
        data = {c: mat[:, j] for j, c in enumerate(col_keys)}
        return DataFrame(data, columns=col_keys, index=row_keys)

    def copy(self) -> Series:
        return Series(self._arr.copy(), index=self._index, name=self.name)

    def __repr__(self) -> str:
        return f"Series({self._arr.tolist()}, name={self.name})"


class _SeriesGroupBy:
    def __init__(self, series: Series, groups: dict[Any, list[int]]) -> None:
        self._series = series
        self._groups = groups

    def last(self) -> Series:
        keys = list(self._groups.keys())
        vals = [self._series._arr[indices[-1]] for indices in self._groups.values()]
        return Series(vals, index=keys)

    def sum(self) -> Series:
        keys = list(self._groups.keys())
        vals = [np.sum(self._series._arr[indices]) for indices in self._groups.values()]
        return Series(vals, index=keys)

    def mean(self) -> Series:
        keys = list(self._groups.keys())
        vals = [np.mean(self._series._arr[indices]) for indices in self._groups.values()]
        return Series(vals, index=keys)

    def size(self) -> Series:
        keys = list(self._groups.keys())
        vals = [len(indices) for indices in self._groups.values()]
        return Series(vals, index=keys)

    def min(self) -> Series:
        keys = list(self._groups.keys())
        vals = [min(self._series._arr[indices]) for indices in self._groups.values()]
        return Series(vals, index=keys)

    def max(self) -> Series:
        keys = list(self._groups.keys())
        vals = [max(self._series._arr[indices]) for indices in self._groups.values()]
        return Series(vals, index=keys)


class _GroupBy:
    def __init__(self, df: DataFrame, by: Any, sort: bool = True, **kwargs: Any) -> None:
        self._df = df
        if isinstance(by, (list, tuple)):
            by_cols = [df._data[col] for col in by]
            groups: dict[Any, list[int]] = {}
            for i in range(len(df)):
                key = tuple(col[i] for col in by_cols)
                groups.setdefault(key, []).append(i)
            self._groups = groups
        else:
            if isinstance(by, str):
                by_arr = df._data[by]
            elif isinstance(by, Series):
                by_arr = by._arr
            else:
                by_arr = np.asarray(by)

            groups = {}
            for i, key in enumerate(by_arr):
                groups.setdefault(key, []).append(i)
            self._groups = groups

    def __iter__(self) -> Iterator[tuple[Any, DataFrame]]:
        for key, indices in self._groups.items():
            yield key, self._df.iloc[indices]

    def __getitem__(self, col: str) -> _SeriesGroupBy:
        return _SeriesGroupBy(self._df[col], self._groups)

    def last(self) -> DataFrame:
        keys = list(self._groups.keys())
        new_data: dict[str, np.ndarray] = {}
        for col in self._df._columns:
            vals = [self._df._data[col][indices[-1]] for indices in self._groups.values()]
            new_data[col] = np.asarray(vals)
        return DataFrame(new_data, columns=self._df._columns, index=keys)

    def sum(self) -> DataFrame:
        keys = list(self._groups.keys())
        new_data: dict[str, np.ndarray] = {}
        for col in self._df._columns:
            vals = [np.sum(self._df._data[col][indices]) for indices in self._groups.values()]
            new_data[col] = np.asarray(vals)
        return DataFrame(new_data, columns=self._df._columns, index=keys)

    def agg(self, **kwargs: Any) -> DataFrame:
        keys = list(self._groups.keys())
        cols = list(kwargs.keys())
        data: dict[str, np.ndarray] = {}
        for col_name, (source_col, func_name) in kwargs.items():
            vals = []
            source_arr = self._df._data[source_col]
            for indices in self._groups.values():
                sub = source_arr[indices]
                if func_name == "size":
                    vals.append(len(indices))
                elif func_name == "mean":
                    vals.append(np.mean(sub.astype(float)))
                elif func_name == "sum":
                    vals.append(np.sum(sub.astype(float)))
                elif func_name == "min":
                    vals.append(np.min(sub))
                elif func_name == "max":
                    vals.append(np.max(sub))
                else:
                    vals.append(len(indices))
            data[col_name] = np.asarray(vals)
        return DataFrame(data, columns=cols, index=keys)


def to_datetime(arg: Any, *args: Any, **kwargs: Any) -> Any:
    if isinstance(arg, Series):
        res = [Timestamp(x) for x in arg._arr]
        return DatetimeIndex(res, index=arg._index)
    if isinstance(arg, (list, tuple, np.ndarray)):
        res = [Timestamp(x) for x in arg]
        return DatetimeIndex(res)
    return Timestamp(arg)


class DataFrame:
    """Implementación pura de pandas.DataFrame sobre columnas NumPy / listas."""

    def __init__(self, data: Any = None, columns: Any = None, index: Any = None) -> None:
        self._data: dict[str, np.ndarray] = {}
        self._columns: list[str] = []
        self._index: list[Any] | None = None

        if isinstance(data, DataFrame):
            self._columns = list(data._columns)
            self._data = {col: data._data[col].copy() for col in self._columns}
            self._index = list(data._index) if data._index is not None else None
        elif isinstance(data, Mapping):
            self._columns = list(columns) if columns is not None else list(data.keys())
            first_idx = None
            max_len = 0
            for col in self._columns:
                val = data.get(col, [])
                if isinstance(val, np.ndarray):
                    if val.ndim > 0:
                        max_len = max(max_len, len(val))
                elif isinstance(val, (list, tuple, Series)):
                    max_len = max(max_len, len(val))
                    if isinstance(val, Series) and first_idx is None and val._index is not None:
                        first_idx = list(val._index)
            for col in self._columns:
                val = data.get(col, [])
                if isinstance(val, Series):
                    self._data[col] = val.to_numpy()
                elif isinstance(val, np.ndarray):
                    if val.ndim == 0:
                        self._data[col] = np.full(max_len, val.item()) if max_len > 0 else val
                    else:
                        self._data[col] = val
                elif isinstance(val, (list, tuple)):
                    self._data[col] = np.asarray(val)
                else:
                    self._data[col] = np.full(max_len, val) if max_len > 0 else np.array([val])
            if index is not None:
                self._index = list(index)
            elif first_idx is not None:
                self._index = first_idx
        elif isinstance(data, (list, tuple)):
            if len(data) > 0 and isinstance(data[0], Mapping):
                # lista de dicts
                cols = list(columns) if columns is not None else list(data[0].keys())
                self._columns = cols
                for col in cols:
                    self._data[col] = np.asarray([row.get(col) for row in data])
                if index is not None:
                    self._index = list(index)
            else:
                arr = np.asarray(data)
                cols = list(columns) if columns is not None else [f"col_{i}" for i in range(arr.shape[1] if arr.ndim > 1 else 1)]
                self._columns = cols
                if arr.ndim > 1:
                    for i, col in enumerate(cols):
                        self._data[col] = arr[:, i]
                elif len(cols) == 1:
                    self._data[cols[0]] = arr
                if index is not None:
                    self._index = list(index)
        elif data is None:
            self._columns = list(columns) if columns is not None else []
            for col in self._columns:
                self._data[col] = np.array([])
            if index is not None:
                self._index = list(index)

        self._iloc = _IlocIndexer(self)
        self._loc = _LocIndexer(self)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]], columns: list[str] | None = None) -> DataFrame:
        return cls(records, columns=columns)

    @property
    def columns(self) -> list[str]:
        return list(self._columns)

    @columns.setter
    def columns(self, new_cols: list[str]) -> None:
        if len(new_cols) != len(self._columns):
            raise ValueError("Length of new columns must match existing columns")
        old_data = self._data
        self._data = {new_c: old_data[old_c] for new_c, old_c in zip(new_cols, self._columns, strict=True)}
        self._columns = list(new_cols)

    @property
    def empty(self) -> bool:
        return len(self) == 0

    @property
    def iloc(self) -> _IlocIndexer:
        return self._iloc

    @property
    def loc(self) -> _LocIndexer:
        return self._loc

    @property
    def index(self) -> Any:
        if self._index is not None:
            if len(self._index) > 0 and isinstance(self._index[0], (Timestamp, datetime)):
                return DatetimeIndex(self._index)
            return Series(np.asarray(self._index))
        return Series(np.arange(len(self)))

    def __len__(self) -> int:
        if not self._columns:
            return 0
        return len(self._data[self._columns[0]])

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item not in self._data:
                raise KeyError(item)
            return Series(self._data[item], name=item, index=self._index)
        if isinstance(item, (list, tuple)):
            if all(isinstance(x, str) for x in item):
                return DataFrame({col: self._data[col] for col in item}, columns=item, index=self._index)
            # boolean mask o integer selection
            return self.iloc[item]
        if isinstance(item, Series):
            mask = item.to_numpy(dtype=bool)
            new_data = {col: self._data[col][mask] for col in self._columns}
            new_idx = [self._index[i] for i, b in enumerate(mask) if b] if self._index is not None else None
            return DataFrame(new_data, columns=self._columns, index=new_idx)
        if isinstance(item, np.ndarray) and item.dtype == bool:
            new_data = {col: self._data[col][item] for col in self._columns}
            new_idx = [self._index[i] for i, b in enumerate(item) if b] if self._index is not None else None
            return DataFrame(new_data, columns=self._columns, index=new_idx)
        raise KeyError(item)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._columns:
            self._columns.append(key)
        if isinstance(value, Series):
            self._data[key] = value.to_numpy()
        elif isinstance(value, (list, tuple)):
            self._data[key] = np.asarray(value)
        elif isinstance(value, np.ndarray):
            if value.ndim == 0:
                self._data[key] = np.full(len(self), value.item())
            else:
                self._data[key] = value
        else:
            n = len(self)
            self._data[key] = np.full(n, value) if n > 0 else np.array([value])

    def tail(self, n: int = 5) -> DataFrame:
        return self.iloc[-n:]

    def head(self, n: int = 5) -> DataFrame:
        return self.iloc[:n]

    def reset_index(self, drop: bool = False) -> DataFrame:
        if drop or self._index is None:
            return DataFrame({c: self._data[c].copy() for c in self._columns}, columns=self._columns)
        new_cols = ["index"] + [c for c in self._columns if c != "index"]
        new_data = {"index": np.asarray(self._index)}
        for c in self._columns:
            new_data[c] = self._data[c].copy()
        return DataFrame(new_data, columns=new_cols)

    def sort_values(self, by: str, ascending: bool = True) -> DataFrame:
        if by not in self._data:
            return self.copy()
        arr = self._data[by]
        order = np.argsort(arr)
        if not ascending:
            order = order[::-1]
        new_data = {col: self._data[col][order] for col in self._columns}
        new_idx = [self._index[i] for i in order] if self._index is not None else None
        return DataFrame(new_data, columns=self._columns, index=new_idx)

    def iterrows(self) -> Iterable[tuple[int, dict[str, Any]]]:
        n = len(self)
        for i in range(n):
            row = {col: self._data[col][i] for col in self._columns}
            yield i, row

    def set_index(self, keys: Any, drop: bool = True) -> DataFrame:
        new_df = self.copy()
        if isinstance(keys, str) and keys in self._columns:
            new_df._index = list(self._data[keys])
            if drop:
                new_df._columns = [c for c in new_df._columns if c != keys]
        return new_df

    def to_parquet(self, path: Any, *args: Any, **kwargs: Any) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            pyd = {}
            for col in self._columns:
                pyd[col] = self._data[col].tolist()
            table = pa.Table.from_pydict(pyd)
            pq.write_table(table, path)
        except Exception:
            pass

    def rename(self, columns: dict[str, str] | None = None) -> DataFrame:
        if not columns:
            return self.copy()
        new_cols = [columns.get(c, c) for c in self._columns]
        new_data = {new_c: self._data[old_c] for new_c, old_c in zip(new_cols, self._columns, strict=True)}
        return DataFrame(new_data, columns=new_cols)

    def groupby(self, by: Any, sort: bool = True, **kwargs: Any) -> _GroupBy:
        return _GroupBy(self, by, sort=sort, **kwargs)

    def shift(self, periods: int = 1, fill_value: Any = np.nan) -> DataFrame:
        new_data = {}
        for col in self._columns:
            arr = self._data[col]
            n = len(arr)
            shifted = np.empty_like(arr, dtype=float if (isinstance(fill_value, float) and np.isnan(fill_value)) else arr.dtype)
            if periods > 0:
                shifted[:min(periods, n)] = fill_value
                if periods < n:
                    shifted[periods:] = arr[:-periods]
            elif periods < 0:
                p = abs(periods)
                shifted[-min(p, n):] = fill_value
                if p < n:
                    shifted[:n - p] = arr[p:]
            else:
                shifted = arr.copy()
            new_data[col] = shifted
        return DataFrame(new_data, columns=self._columns, index=self._index)

    def bfill(self) -> DataFrame:
        new_data = {}
        for col in self._columns:
            arr = self._data[col].copy()
            n = len(arr)
            last_val = None
            for i in range(n - 1, -1, -1):
                val = arr[i]
                if isinstance(val, (float, np.floating)) and np.isnan(val):
                    if last_val is not None:
                        arr[i] = last_val
                else:
                    last_val = val
            new_data[col] = arr
        return DataFrame(new_data, columns=self._columns, index=self._index)

    def fillna(self, value: Any) -> DataFrame:
        new_data = {}
        for col in self._columns:
            arr = self._data[col].copy()
            if np.issubdtype(arr.dtype, np.floating):
                arr[np.isnan(arr)] = value
            new_data[col] = arr
        return DataFrame(new_data, columns=self._columns, index=self._index)

    def replace(self, to_replace: Any, value: Any) -> DataFrame:
        new_data = {}
        for col in self._columns:
            arr = self._data[col].copy()
            if np.issubdtype(arr.dtype, np.floating) and np.isnan(to_replace):
                arr[np.isnan(arr)] = value
            else:
                arr[arr == to_replace] = value
            new_data[col] = arr
        return DataFrame(new_data, columns=self._columns, index=self._index)

    def reindex(self, index: Any) -> DataFrame:
        new_df = self.copy()
        new_df._index = list(index) if index is not None else None
        return new_df

    def pct_change(self) -> DataFrame:
        new_data = {}
        for col in self._columns:
            arr = self._data[col].astype(float)
            shifted = np.empty_like(arr)
            shifted[0] = np.nan
            shifted[1:] = arr[:-1]
            with np.errstate(divide="ignore", invalid="ignore"):
                pct = (arr - shifted) / shifted
            new_data[col] = pct
        return DataFrame(new_data, columns=self._columns, index=self._index)

    def apply(self, func: Any, axis: int = 0) -> Any:
        if axis == 1:
            rows = []
            for i in range(len(self)):
                row_dict = {col: self._data[col][i] for col in self._columns}
                s = Series(row_dict)
                rows.append(func(s))
            if rows and isinstance(rows[0], Series):
                cols = list(rows[0]._index) if rows[0]._index is not None else []
                new_data = {c: np.array([r[c] for r in rows]) for c in cols}
                return DataFrame(new_data, columns=cols, index=self._index)
            return Series(rows, index=self._index)
        else:
            cols = {}
            for col in self._columns:
                cols[col] = func(Series(self._data[col], name=col))
            return Series(cols)

    def __truediv__(self, other: Any) -> DataFrame:
        if isinstance(other, DataFrame):
            new_data = {}
            for col in self._columns:
                if col in other._data:
                    with np.errstate(divide="ignore", invalid="ignore"):
                        new_data[col] = self._data[col].astype(float) / other._data[col].astype(float)
                else:
                    new_data[col] = np.full(len(self), np.nan)
            return DataFrame(new_data, columns=self._columns, index=self._index)
        elif isinstance(other, (int, float, np.number)):
            new_data = {col: self._data[col].astype(float) / float(other) for col in self._columns}
            return DataFrame(new_data, columns=self._columns, index=self._index)
        return NotImplemented

    def __rtruediv__(self, other: Any) -> DataFrame:
        if isinstance(other, (int, float, np.number)):
            new_data = {col: float(other) / self._data[col].astype(float) for col in self._columns}
            return DataFrame(new_data, columns=self._columns, index=self._index)
        return NotImplemented

    def __mul__(self, other: Any) -> DataFrame:
        if isinstance(other, DataFrame):
            new_data = {}
            for col in self._columns:
                if col in other._data:
                    new_data[col] = self._data[col] * other._data[col]
            return DataFrame(new_data, columns=self._columns, index=self._index)
        elif isinstance(other, (int, float, np.number)):
            new_data = {col: self._data[col] * float(other) for col in self._columns}
            return DataFrame(new_data, columns=self._columns, index=self._index)
        return NotImplemented

    def __rmul__(self, other: Any) -> DataFrame:
        return self.__mul__(other)

    def __sub__(self, other: Any) -> DataFrame:
        if isinstance(other, DataFrame):
            new_data = {}
            for col in self._columns:
                if col in other._data:
                    new_data[col] = self._data[col] - other._data[col]
            return DataFrame(new_data, columns=self._columns, index=self._index)
        elif isinstance(other, (int, float, np.number)):
            new_data = {col: self._data[col] - float(other) for col in self._columns}
            return DataFrame(new_data, columns=self._columns, index=self._index)
        return NotImplemented

    def __add__(self, other: Any) -> DataFrame:
        if isinstance(other, DataFrame):
            new_data = {}
            for col in self._columns:
                if col in other._data:
                    new_data[col] = self._data[col] + other._data[col]
            return DataFrame(new_data, columns=self._columns, index=self._index)
        elif isinstance(other, (int, float, np.number)):
            new_data = {col: self._data[col] + float(other) for col in self._columns}
            return DataFrame(new_data, columns=self._columns, index=self._index)
        return NotImplemented

    def sort_index(self, ascending: bool = True) -> DataFrame:
        return self.copy()

    def copy(self) -> DataFrame:
        return DataFrame({col: self._data[col].copy() for col in self._columns}, columns=self._columns, index=self._index)

    def to_dict(self, orient: str = "records") -> Any:
        if orient == "records":
            return [dict(row) for _, row in self.iterrows()]
        return {col: self._data[col].tolist() for col in self._columns}

    def __repr__(self) -> str:
        return f"DataFrame(shape=({len(self)}, {len(self._columns)}), columns={self._columns})"


def concat(objs: list[DataFrame | Series], axis: int = 0, ignore_index: bool = True) -> DataFrame | Series:
    if not objs:
        return DataFrame()
    first = objs[0]
    if isinstance(first, Series):
        arrs = [s.to_numpy() for s in objs if isinstance(s, Series)]
        return Series(np.concatenate(arrs))
    if isinstance(first, DataFrame):
        cols = list(first._columns)
        new_data: dict[str, np.ndarray] = {}
        for col in cols:
            arrs = [df._data[col] for df in objs if isinstance(df, DataFrame) and col in df._data]
            new_data[col] = np.concatenate(arrs) if arrs else np.array([])
        return DataFrame(new_data, columns=cols)
    raise TypeError("concat only supports DataFrame and Series")


class DatetimeIndex(Series):
    def floor(self, freq: str = "D") -> DatetimeIndex:
        return DatetimeIndex(self.dt.floor(freq))

    def tz_localize(self, tz: Any) -> DatetimeIndex:
        arr = [Timestamp(x).tz_localize(tz) for x in self._arr]
        return DatetimeIndex(arr, index=self._index)

    def tz_convert(self, tz: Any) -> DatetimeIndex:
        arr = [Timestamp(x).tz_convert(tz) for x in self._arr]
        return DatetimeIndex(arr, index=self._index)


def date_range(
    start: Any = None,
    end: Any = None,
    periods: int | None = None,
    freq: str = "D",
    tz: Any = None,
    **kwargs: Any,
) -> DatetimeIndex:
    t0 = Timestamp(start, tz=tz)
    out: list[Timestamp] = []
    step = timedelta(days=1)
    fl = str(freq).lower()
    if fl in ("1h", "h"):
        step = timedelta(hours=1)
    elif fl == "4h":
        step = timedelta(hours=4)
    elif fl in ("1d", "d"):
        step = timedelta(days=1)
    elif "d" in fl:
        try:
            n_d = int(fl.replace("d", ""))
            step = timedelta(days=n_d)
        except Exception:
            step = timedelta(days=1)

    curr = t0
    count = periods or 10
    for _ in range(count):
        out.append(curr)
        curr = curr + step
    return DatetimeIndex(out)


def read_parquet(path: Any) -> DataFrame:
    # Usar pyarrow o duckdb si está disponible
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        data = table.to_pydict()
        return DataFrame(data)
    except Exception:
        pass
    try:
        import duckdb

        df_arrow = duckdb.execute(f"SELECT * FROM '{path}'").arrow()
        return DataFrame(df_arrow.to_pydict())
    except Exception:
        return DataFrame()


class Period:
    def __init__(self, val: Any, freq: str = "M") -> None:
        self.freq = freq
        if isinstance(val, str):
            parts = val.split("-")
            self.year = int(parts[0])
            self.month = int(parts[1]) if len(parts) > 1 else 1
        elif isinstance(val, (datetime, Timestamp)):
            self.year = val.year
            self.month = val.month
        elif isinstance(val, Period):
            self.year = val.year
            self.month = val.month

    def __add__(self, n: int) -> Period:
        total_m = self.year * 12 + (self.month - 1) + n
        new_y = total_m // 12
        new_m = total_m % 12 + 1
        return Period(f"{new_y:04d}-{new_m:02d}", freq=self.freq)

    def __sub__(self, n: int) -> Period:
        return self.__add__(-n)

    def to_timestamp(self) -> Timestamp:
        return Timestamp(datetime(self.year, self.month, 1, tzinfo=UTC))

    def __lt__(self, other: Period) -> bool:
        return (self.year, self.month) < (other.year, other.month)

    def __le__(self, other: Period) -> bool:
        return (self.year, self.month) <= (other.year, other.month)

    def __repr__(self) -> str:
        return f"Period('{self.year:04d}-{self.month:02d}', '{self.freq}')"


def period_range(start: Any, end: Any, freq: str = "M") -> list[Period]:
    p_start = start if isinstance(start, Period) else Period(start, freq=freq)
    p_end = end if isinstance(end, Period) else Period(end, freq=freq)
    curr = p_start
    res = []
    while curr <= p_end:
        res.append(curr)
        curr = curr + 1
    return res


class _Testing:
    @staticmethod
    def assert_frame_equal(left: Any, right: Any, **kwargs: Any) -> None:
        assert list(left.columns) == list(right.columns)
        assert len(left) == len(right)
        for col in left.columns:
            l_vals = left[col].to_numpy()
            r_vals = right[col].to_numpy()
            if np.issubdtype(l_vals.dtype, np.floating) or np.issubdtype(r_vals.dtype, np.floating):
                np.testing.assert_allclose(l_vals.astype(float), r_vals.astype(float), rtol=1e-5, atol=1e-8)
            else:
                assert np.array_equal(l_vals, r_vals)


testing = _Testing()


# Auto-registro en sys.modules para que `import pandas as pd` funcione de forma transparente
def patch_pandas_if_broken() -> None:
    try:
        import pandas  # noqa: F401
    except (ImportError, OSError):
        this_module = sys.modules[__name__]
        sys.modules["pandas"] = this_module
        sys.modules["pandas.core"] = this_module
        sys.modules["pandas.core.api"] = this_module


patch_pandas_if_broken()
