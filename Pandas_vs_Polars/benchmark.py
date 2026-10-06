"""
Compara pandas y polars en 5 operaciones tipicas sobre series de precios diarios.

Tres tamanos:
- real: precios_diarios.csv (50 acciones, 10 anios, descargado con descargar_datos.py)
- 1M y 10M filas: series sinteticas (caminata aleatoria, semilla fija) con las mismas
  fechas que los datos reales. Solo cambia el numero de tickers.

Cada operacion se repite varias veces y se reporta la mediana. Antes de medir, se
verifica que pandas y polars den el mismo resultado numerico.
"""

import gc
import os
import statistics
import tempfile
import time

import numpy as np
import pandas as pd
import polars as pl

VENTANA = 20
SEMILLA = 42
TAMANOS_SINTETICOS = {"1M": 400, "10M": 4000}


def generar_sintetico(n_tickers, fechas, ruta):
    """Caminatas aleatorias por ticker; mismo esquema de columnas que los datos reales."""
    rng = np.random.default_rng(SEMILLA)
    n_dias = len(fechas)
    retornos = rng.normal(0.0004, 0.02, size=(n_tickers, n_dias))
    cierre = 100 * np.cumprod(1 + retornos, axis=1)
    volumen = rng.lognormal(mean=15, sigma=0.5, size=(n_tickers, n_dias)).astype("int64")
    tickers = np.repeat([f"T{i:04d}" for i in range(n_tickers)], n_dias)
    df = pl.DataFrame({
        "fecha": np.tile(fechas, n_tickers),
        "ticker": tickers,
        "cierre": cierre.ravel(),
        "volumen": volumen.ravel(),
    })
    df.write_csv(ruta)


# ---- operaciones en pandas ----

def pd_retornos(df):
    return df.groupby("ticker")["cierre"].pct_change()


def pd_rolling(df):
    g = df.groupby("ticker")["cierre"]
    media = g.rolling(VENTANA).mean().reset_index(level=0, drop=True)
    desv = g.rolling(VENTANA).std().reset_index(level=0, drop=True)
    return media, desv


def pd_mensual(df):
    return df.groupby(["ticker", pd.Grouper(key="fecha", freq="MS")]).agg(
        cierre_medio=("cierre", "mean"), volumen=("volumen", "sum")
    ).reset_index()


def pd_join(df):
    indice = df.groupby("fecha")["cierre"].mean().rename("indice").reset_index()
    out = df.merge(indice, on="fecha")
    out["relativo"] = out["cierre"] / out["indice"]
    return out


# ---- operaciones en polars ----

def pl_retornos(df):
    return df.select(pl.col("cierre").pct_change().over("ticker"))["cierre"]


def pl_rolling(df):
    return df.select(
        pl.col("cierre").rolling_mean(VENTANA).over("ticker").alias("media"),
        pl.col("cierre").rolling_std(VENTANA).over("ticker").alias("desv"),
    )


def pl_mensual(df):
    return df.group_by(["ticker", pl.col("fecha").dt.truncate("1mo")]).agg(
        pl.col("cierre").mean().alias("cierre_medio"),
        pl.col("volumen").sum().alias("volumen"),
    )


def pl_join(df):
    indice = df.group_by("fecha").agg(pl.col("cierre").mean().alias("indice"))
    return df.join(indice, on="fecha").with_columns(
        (pl.col("cierre") / pl.col("indice")).alias("relativo")
    )


def verificar(dfp, dfl):
    """Mismo resultado numerico en ambas librerias (tolerancia 1e-9)."""
    r_p = np.nansum(pd_retornos(dfp).to_numpy())
    r_l = np.nansum(pl_retornos(dfl).to_numpy())
    m_p, d_p = pd_rolling(dfp)
    rl = pl_rolling(dfl)
    m_ok = np.isclose(np.nansum(m_p.to_numpy()), rl["media"].drop_nulls().sum(), rtol=1e-9)
    d_ok = np.isclose(np.nansum(d_p.to_numpy()), rl["desv"].drop_nulls().sum(), rtol=1e-9)
    mens_ok = len(pd_mensual(dfp)) == pl_mensual(dfl).height
    rel_ok = np.isclose(pd_join(dfp)["relativo"].sum(), pl_join(dfl)["relativo"].sum(), rtol=1e-9)
    ret_ok = np.isclose(r_p, r_l, rtol=1e-9)
    assert all([m_ok, d_ok, mens_ok, rel_ok, ret_ok]), "pandas y polars no coinciden"


def medir(fn, repeticiones):
    fn()  # calentamiento descartado (cache de disco, imports perezosos)
    tiempos = []
    for _ in range(repeticiones):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        tiempos.append(time.perf_counter() - t0)
    return statistics.median(tiempos)


def correr_tamano(nombre, ruta, repeticiones, filas_out):
    filas = []

    t_pd = medir(lambda: pd.read_csv(ruta, parse_dates=["fecha"]), repeticiones)
    t_pl = medir(lambda: pl.read_csv(ruta, try_parse_dates=True), repeticiones)
    filas.append((nombre, "leer_csv", t_pd, t_pl))

    dfp = pd.read_csv(ruta, parse_dates=["fecha"])
    dfl = pl.read_csv(ruta, try_parse_dates=True)
    filas_out[nombre] = len(dfp)
    mem_pd = dfp.memory_usage(deep=True).sum() / 1e6
    mem_pl = dfl.estimated_size() / 1e6
    verificar(dfp, dfl)

    ops = [
        ("retornos_por_ticker", pd_retornos, pl_retornos),
        ("rolling_20_media_y_desv", pd_rolling, pl_rolling),
        ("agregado_mensual", pd_mensual, pl_mensual),
        ("join_con_indice", pd_join, pl_join),
    ]
    for op, f_pd, f_pl in ops:
        filas.append((nombre, op, medir(lambda: f_pd(dfp), repeticiones),
                      medir(lambda: f_pl(dfl), repeticiones)))

    filas.append((nombre, "memoria_MB", mem_pd, mem_pl))
    return filas


def main():
    real = pd.read_csv("precios_diarios.csv", parse_dates=["fecha"])
    fechas = np.sort(real["fecha"].unique())
    print(f"pandas {pd.__version__} | polars {pl.__version__} | numpy {np.__version__}")

    resultados, filas_por_tamano = [], {}
    resultados += correr_tamano("real", "precios_diarios.csv", 7, filas_por_tamano)

    with tempfile.TemporaryDirectory() as tmp:
        for nombre, n_tickers in TAMANOS_SINTETICOS.items():
            ruta = os.path.join(tmp, f"sintetico_{nombre}.csv")
            generar_sintetico(n_tickers, fechas, ruta)
            reps = 5 if nombre == "1M" else 3
            resultados += correr_tamano(nombre, ruta, reps, filas_por_tamano)

    out = pd.DataFrame(resultados, columns=["tamano", "operacion", "pandas", "polars"])
    out["filas"] = out["tamano"].map(filas_por_tamano)
    out["veces_mas_rapido_polars"] = (out["pandas"] / out["polars"]).round(1)
    out["pandas"] = out["pandas"].round(4)
    out["polars"] = out["polars"].round(4)
    out = out[["tamano", "filas", "operacion", "pandas", "polars", "veces_mas_rapido_polars"]]
    out.to_csv("resultados_benchmark.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
