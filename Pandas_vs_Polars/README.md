# Pandas vs Polars para series financieras

Compara pandas y polars en 4 operaciones típicas sobre precios diarios de acciones, más lectura de CSV y memoria, a tres tamaños de datos.

## Metodología
- **Datos reales:** 50 acciones de EE. UU., 10 años de precios diarios ajustados (125,600 filas), descargados con `descargar_datos.py` (Yahoo Finance vía `yfinance`) y guardados en `precios_diarios.csv`.
- **Datos sintéticos:** 1M y 10M de filas. Son caminatas aleatorias con semilla fija (42), con las mismas fechas que los datos reales. Solo cambia el número de series (400 y 4,000 tickers).
- **Operaciones medidas** (las mismas en las dos librerías):
  1. Retornos diarios por ticker.
  2. Media y desviación estándar móvil de 20 días por ticker.
  3. Agregado mensual por ticker (media del cierre, suma del volumen).
  4. Join contra un índice (promedio del universo por fecha) y precio relativo.
- **Tiempos:** se descarta una corrida de calentamiento y se reporta la mediana de 7 repeticiones (datos reales), 5 (1M) o 3 (10M). El tiempo es de reloj (`time.perf_counter`).
- **Verificación:** antes de medir, el script comprueba que pandas y polars dan el mismo resultado numérico en las 4 operaciones (tolerancia relativa 1e-9).
- **Versiones:** pandas 2.3.3, polars 1.44.2, numpy 2.2.6, Python 3.13, Windows 11, 8 hilos.

## Resultados (segundos, mediana)

| Operación | Datos reales (125,600) pandas | polars | 1M pandas | polars | 10M pandas | polars |
|---|---|---|---|---|---|---|
| Retornos por ticker | 0.019 | 0.005 | 0.189 | 0.026 | 1.138 | 0.227 |
| Media y desv. móvil 20 días | 0.132 | 0.010 | 0.720 | 0.050 | 5.741 | 0.436 |
| Agregado mensual | 0.069 | 0.011 | 0.413 | 0.073 | 4.694 | 0.686 |
| Join con índice | 0.021 | 0.007 | 0.123 | 0.037 | 1.128 | 0.450 |
| **Suma de las 4** | **0.241** | **0.033** | **1.445** | **0.187** | **12.701** | **1.798** |
| Veces más rápido polars | 7.3 | | 7.7 | | 7.1 | |

Polars fue más rápido en las 4 operaciones y en los 3 tamaños, de 2.5 a 14.6 veces. En memoria, el DataFrame de polars ocupó entre 2.7 y 3.3 veces menos (783.7 MB en pandas contra 291.4 MB en polars con 10M de filas).

La salida completa, incluida la lectura de CSV y la memoria, está en `resultados_benchmark.csv`.

## Limitaciones
- Es una máquina, un sistema operativo y una versión de cada librería. Los tiempos absolutos cambian con el equipo; las proporciones son más estables.
- Los 10M de filas son sintéticos. Reproducen el tamaño y la estructura, no el comportamiento real de los precios.
- El código de pandas usa los modismos más comunes (`groupby().rolling()`, `pd.Grouper`, `merge`). Hay formas más rápidas de escribir algunas operaciones en pandas, y los resultados dependen de ello.
- Polars usa los 8 hilos del equipo por defecto; pandas ejecuta estas operaciones en un solo hilo.
- Con datos reales (50 acciones) las diferencias son de milisegundos y quedan dentro del ruido de una corrida a otra. Por eso no se reporta la lectura de CSV a ese tamaño como conclusión.
- No se mide el costo de aprender una librería nueva ni la compatibilidad con el resto del ecosistema (statsmodels, scikit-learn, etc.), que acompaña a pandas de forma más directa.

## Archivos
- `descargar_datos.py`: descarga los precios reales y genera `precios_diarios.csv`.
- `benchmark.py`: corre la comparación y genera `resultados_benchmark.csv`.
- `precios_diarios.csv`: datos reales usados.
- `resultados_benchmark.csv`: salida del benchmark.
- `requirements.txt`: dependencias.

## Cómo replicar
```
pip install -r requirements.txt
python descargar_datos.py   # opcional: el CSV ya viene incluido
python benchmark.py         # tarda varios minutos por los 10M de filas
```
