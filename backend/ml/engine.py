"""
AI/ML Engine for Water Quality Monitoring.
Two core tasks:
  1. Anomaly Detection — Isolation Forest (flags abnormal readings in real-time)
  2. Pollution Forecasting — Random Forest (predicts WQI and parameter values)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

FEATURES = ["ph", "turbidity", "dissolved_oxygen", "temperature", "tds"]


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector.
    Flags readings that deviate significantly from normal patterns.
    """

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self._load_model()

    def _model_path(self):
        return os.path.join(MODEL_DIR, "anomaly_detector.pkl")

    def _scaler_path(self):
        return os.path.join(MODEL_DIR, "anomaly_scaler.pkl")

    def _load_model(self):
        try:
            if os.path.exists(self._model_path()):
                self.model = joblib.load(self._model_path())
                self.scaler = joblib.load(self._scaler_path())
                self.is_trained = True
                logger.info("Loaded anomaly detection model from disk")
        except Exception as e:
            logger.warning(f"Could not load anomaly model: {e}")
            self.is_trained = False

    def train(self, readings_df: pd.DataFrame):
        """
        Train the Isolation Forest on historical sensor readings.
        Expects a DataFrame with columns: ph, turbidity, dissolved_oxygen, temperature, tds
        """
        if len(readings_df) < 30:
            logger.warning("Not enough data to train anomaly detector (need ≥ 30 rows)")
            return False

        # Fill missing values with column medians
        df = readings_df[FEATURES].copy()
        df = df.fillna(df.median())

        # Scale features
        X = self.scaler.fit_transform(df)

        # Train Isolation Forest
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.1,  # expect ~10% anomalies
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X)
        self.is_trained = True

        # Save model
        joblib.dump(self.model, self._model_path())
        joblib.dump(self.scaler, self._scaler_path())
        logger.info(f"Anomaly detector trained on {len(df)} samples")
        return True

    def predict(self, ph=None, turbidity=None, dissolved_oxygen=None,
                temperature=None, tds=None) -> tuple:
        """
        Check if a single reading is anomalous.
        Returns (is_anomaly: bool, anomaly_score: float)
        """
        if not self.is_trained:
            # Fallback: simple threshold-based detection
            return self._threshold_fallback(ph, turbidity, dissolved_oxygen, temperature, tds)

        values = [
            ph if ph is not None else 7.0,
            turbidity if turbidity is not None else 5.0,
            dissolved_oxygen if dissolved_oxygen is not None else 8.0,
            temperature if temperature is not None else 25.0,
            tds if tds is not None else 300.0,
        ]

        X = self.scaler.transform([values])
        prediction = self.model.predict(X)[0]   # -1 = anomaly, 1 = normal
        score = self.model.decision_function(X)[0]

        return bool(prediction == -1), round(float(score), 4)

    def _threshold_fallback(self, ph, turbidity, dissolved_oxygen, temperature, tds):
        """Simple threshold-based anomaly detection when ML model isn't trained yet."""
        anomaly = False
        if ph is not None and (ph < 4.0 or ph > 10.0):
            anomaly = True
        if turbidity is not None and turbidity > 100:
            anomaly = True
        if dissolved_oxygen is not None and dissolved_oxygen < 3.0:
            anomaly = True
        if temperature is not None and (temperature < 2.0 or temperature > 45.0):
            anomaly = True
        if tds is not None and tds > 1500:
            anomaly = True
        return anomaly, -0.5 if anomaly else 0.5


class PollutionForecaster:
    """
    Random Forest-based pollution forecaster.
    Predicts future WQI and individual parameter values.
    """

    def __init__(self):
        self.models = {}  # one model per target
        self.scaler = StandardScaler()
        self.is_trained = False
        self._load_models()

    def _model_path(self, target):
        return os.path.join(MODEL_DIR, f"forecast_{target}.pkl")

    def _scaler_path(self):
        return os.path.join(MODEL_DIR, "forecast_scaler.pkl")

    def _load_models(self):
        try:
            if os.path.exists(self._scaler_path()):
                self.scaler = joblib.load(self._scaler_path())
                for target in FEATURES + ["wqi"]:
                    path = self._model_path(target)
                    if os.path.exists(path):
                        self.models[target] = joblib.load(path)
                if self.models:
                    self.is_trained = True
                    logger.info("Loaded forecasting models from disk")
        except Exception as e:
            logger.warning(f"Could not load forecast models: {e}")
            self.is_trained = False

    def _create_lag_features(self, df: pd.DataFrame, n_lags: int = 6) -> pd.DataFrame:
        """
        Create time-lagged features for time-series forecasting.
        Uses rolling windows and lag values.
        """
        result = pd.DataFrame()

        for col in FEATURES:
            if col in df.columns:
                for lag in range(1, n_lags + 1):
                    result[f"{col}_lag{lag}"] = df[col].shift(lag)
                # Rolling statistics
                result[f"{col}_roll_mean_3"] = df[col].rolling(3).mean()
                result[f"{col}_roll_std_3"] = df[col].rolling(3).std()
                result[f"{col}_roll_mean_6"] = df[col].rolling(6).mean()

        # Time features
        if "timestamp" in df.columns:
            result["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
            result["day_of_week"] = pd.to_datetime(df["timestamp"]).dt.dayofweek

        return result

    def train(self, readings_df: pd.DataFrame):
        """
        Train forecasting models on historical data.
        Expects DataFrame with: ph, turbidity, dissolved_oxygen, temperature, tds, wqi, timestamp
        """
        if len(readings_df) < 50:
            logger.warning("Not enough data to train forecaster (need ≥ 50 rows)")
            return False

        df = readings_df.sort_values("timestamp").reset_index(drop=True)
        df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())

        # Create features
        X_df = self._create_lag_features(df)
        X_df = X_df.dropna()

        # Align target with features
        valid_idx = X_df.index

        if len(valid_idx) < 20:
            logger.warning("Not enough valid lag data for training")
            return False

        X = X_df.values
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)

        # Train a model for each target variable
        targets = FEATURES + ["wqi"]
        for target in targets:
            if target not in df.columns:
                continue
            y = df.loc[valid_idx, target].values

            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )

            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)
            train_score = model.score(X_train, y_train)
            test_score = model.score(X_test, y_test)

            self.models[target] = model
            joblib.dump(model, self._model_path(target))
            logger.info(f"Forecast model for '{target}': train R²={train_score:.3f}, test R²={test_score:.3f}")

        joblib.dump(self.scaler, self._scaler_path())
        self.is_trained = True
        return True

    def predict(self, recent_readings: pd.DataFrame) -> dict:
        """
        Predict future values given recent readings (at least 6 rows).
        Returns dict with predicted values for each parameter.
        """
        if not self.is_trained or len(recent_readings) < 6:
            return self._simple_forecast(recent_readings)

        df = recent_readings.sort_values("timestamp").reset_index(drop=True)
        df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())

        X_df = self._create_lag_features(df)
        X_df = X_df.dropna()

        if len(X_df) == 0:
            return self._simple_forecast(recent_readings)

        # Use the last row of features for prediction
        X = self.scaler.transform(X_df.values[-1:])

        predictions = {}
        for target, model in self.models.items():
            pred = model.predict(X)[0]
            # Clamp to reasonable ranges
            if target == "ph":
                pred = np.clip(pred, 0, 14)
            elif target in ("turbidity", "tds", "wqi"):
                pred = max(0, pred)
            elif target == "dissolved_oxygen":
                pred = np.clip(pred, 0, 20)
            elif target == "temperature":
                pred = np.clip(pred, -5, 50)
            predictions[target] = round(float(pred), 2)

        # Compute confidence from R² score (simplified)
        predictions["confidence"] = 0.75  # placeholder, would be model.score() on test set

        return predictions

    def _simple_forecast(self, readings_df: pd.DataFrame) -> dict:
        """Simple moving-average fallback when ML model isn't trained."""
        predictions = {}
        for col in FEATURES:
            if col in readings_df.columns:
                vals = readings_df[col].dropna()
                if len(vals) >= 2:
                    # Weighted average: recent values weighted more
                    weights = np.linspace(0.5, 1.0, len(vals[-10:]))
                    predictions[col] = round(float(np.average(vals.iloc[-10:], weights=weights)), 2)
                elif len(vals) == 1:
                    predictions[col] = round(float(vals.iloc[0]), 2)
        predictions["confidence"] = 0.3
        return predictions


# ── Singleton instances ──────────────────────────────────────────
anomaly_detector = AnomalyDetector()
pollution_forecaster = PollutionForecaster()
