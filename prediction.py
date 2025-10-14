from typing import Tuple
import numpy as np
from sklearn.linear_model import LinearRegression


def simulate_crowd_series(n: int = 60, base_density: float = 2.5, noise: float = 0.6) -> np.ndarray:
    t = np.arange(n)
    trend = 0.01 * t
    series = base_density + trend + np.random.normal(0, noise, size=n)
    series = np.clip(series, 0.2, 5.0)
    return series


def forecast_next(series: np.ndarray, steps: int = 15) -> np.ndarray:
    X = np.arange(len(series)).reshape(-1, 1)
    y = series
    model = LinearRegression()
    model.fit(X, y)
    X_future = np.arange(len(series), len(series) + steps).reshape(-1, 1)
    y_pred = model.predict(X_future)
    y_pred = np.clip(y_pred, 0.2, 5.0)
    return y_pred


def bottleneck_probability(pred_density: np.ndarray, threshold: float = 4.0) -> float:
    exceed = (pred_density >= threshold).mean()
    return float(np.round(exceed, 2))
