"""
Descarga precios diarios reales de 50 acciones y los guarda en formato largo
(fecha, ticker, cierre, volumen) en precios_diarios.csv.

Fuente: Yahoo Finance via yfinance, precios ajustados, ultimos 10 anios.
"""

import yfinance as yf
import pandas as pd

TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "ORCL", "ADBE",
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "BRK-B", "AXP", "C",
    "KO", "PEP", "WMT", "COST", "PG", "MCD", "NKE", "HD", "DIS", "SBUX",
    "XOM", "CVX", "COP", "NEE", "DUK", "CAT", "BA", "GE", "UPS", "HON",
    "JNJ", "PFE", "MRK", "UNH", "LLY", "ABBV", "T", "VZ", "INTC", "AMD",
]
PERIODO = "10y"


def main():
    datos = yf.download(TICKERS, period=PERIODO, auto_adjust=True, progress=False)
    cierre = datos["Close"].stack().rename("cierre")
    volumen = datos["Volume"].stack().rename("volumen")
    largo = pd.concat([cierre, volumen], axis=1).reset_index()
    largo.columns = ["fecha", "ticker", "cierre", "volumen"]
    largo = largo.sort_values(["ticker", "fecha"]).reset_index(drop=True)
    largo.to_csv("precios_diarios.csv", index=False)
    print(f"{len(largo):,} filas, {largo['ticker'].nunique()} tickers, "
          f"{largo['fecha'].min().date()} a {largo['fecha'].max().date()}")


if __name__ == "__main__":
    main()
