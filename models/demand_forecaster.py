"""
FoodFlow AI — Demand Forecasting Engine
Ensemble of Prophet (seasonality) + XGBoost (feature-rich) for accurate demand prediction.
Falls back to XGBoost-only if Prophet is unavailable.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb
import json

from database.db import get_db
from utils.helpers import get_sales_dataframe, get_weather_dataframe, get_events_dataframe

# Try importing Prophet (optional dependency)
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("⚠️  Prophet not available. Using XGBoost-only mode.")


class DemandForecaster:
    """
    Ensemble demand forecaster combining Prophet + XGBoost.
    
    Features used:
    - Temporal: day_of_week, month, day_of_month, week_of_year, is_weekend
    - Lag features: lag_7, lag_14, lag_30 (previous demand)
    - Rolling stats: rolling_mean_7, rolling_std_7, rolling_mean_30
    - Weather: temperature, precipitation
    - Events: binary event flag, event impact multiplier
    - Product: shelf_life, is_perishable
    """

    def __init__(self):
        self.xgb_model = None
        self.prophet_model = None
        self.feature_columns = []
        self.is_trained = False
        self.metrics = {}
        self.training_info = {}

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer features from raw sales data."""
        df = df.copy()
        df = df.sort_values("date")

        # ── Temporal features ──
        df["day_of_week"] = df["date"].dt.dayofweek
        df["month"] = df["date"].dt.month
        df["day_of_month"] = df["date"].dt.day
        df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
        df["quarter"] = df["date"].dt.quarter
        df["day_of_year"] = df["date"].dt.dayofyear

        # Cyclical encoding for temporal features
        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
        df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
        df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

        # ── Lag features (grouped by store+product) ──
        group_key = ["store_id", "product_id"]
        if all(k in df.columns for k in group_key):
            for lag in [1, 3, 7, 14, 30]:
                df[f"lag_{lag}"] = df.groupby(group_key)["qty_sold"].shift(lag)

            # Rolling statistics
            for window in [7, 14, 30]:
                df[f"rolling_mean_{window}"] = df.groupby(group_key)["qty_sold"].transform(
                    lambda x: x.shift(1).rolling(window, min_periods=1).mean()
                )
                df[f"rolling_std_{window}"] = df.groupby(group_key)["qty_sold"].transform(
                    lambda x: x.shift(1).rolling(window, min_periods=1).std()
                )
                df[f"rolling_max_{window}"] = df.groupby(group_key)["qty_sold"].transform(
                    lambda x: x.shift(1).rolling(window, min_periods=1).max()
                )

            # Demand trend (slope of last 7 days)
            df["demand_trend"] = df.groupby(group_key)["qty_sold"].transform(
                lambda x: x.shift(1).rolling(7, min_periods=2).apply(
                    lambda y: np.polyfit(range(len(y)), y, 1)[0] if len(y) >= 2 else 0
                )
            )

        # ── Weather features ──
        if "weather_temp" in df.columns:
            df["temp_squared"] = df["weather_temp"] ** 2
            df["is_hot"] = (df["weather_temp"] > 30).astype(int)
            df["is_cold"] = (df["weather_temp"] < 5).astype(int)

        # ── Product features ──
        if "shelf_life_days" in df.columns:
            df["log_shelf_life"] = np.log1p(df["shelf_life_days"])

        # Fill NaN from lag features
        df = df.fillna(0)

        return df

    def _get_feature_columns(self, df: pd.DataFrame) -> list:
        """Select feature columns for the model."""
        exclude = [
            "date", "sale_id", "store_id", "product_id", "product_name",
            "store_name", "category", "subcategory", "city", "store_type",
            "qty_sold", "qty_ordered", "qty_wasted", "revenue", "waste_cost",
            "unit_cost", "unit_price", "carbon_footprint_kg",
            "day_of_year"  # already encoded cyclically
        ]
        return [c for c in df.columns if c not in exclude and df[c].dtype in [np.float64, np.int64, np.int32, np.float32]]

    def train(self, store_id: int = None, product_id: int = None,
              days_back: int = 365, verbose: bool = True):
        """
        Train the ensemble model on historical sales data.
        """
        if verbose:
            print("🔮 Training Demand Forecaster...")
            print(f"   Store: {store_id or 'All'} | Product: {product_id or 'All'} | Days: {days_back}")

        # Load data
        df = get_sales_dataframe(store_id=store_id, product_id=product_id, days_back=days_back)
        if len(df) < 30:
            raise ValueError(f"Not enough data to train. Got {len(df)} records, need at least 30.")

        # Engineer features
        df = self._create_features(df)

        # Define features
        self.feature_columns = self._get_feature_columns(df)
        if verbose:
            print(f"   Features: {len(self.feature_columns)}")

        # ── Train/Test split (temporal) ──
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        X_train = train_df[self.feature_columns].values
        y_train = train_df["qty_sold"].values
        X_test = test_df[self.feature_columns].values
        y_test = test_df["qty_sold"].values

        # ── Train XGBoost ──
        if verbose:
            print("   Training XGBoost...")

        self.xgb_model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            verbosity=0
        )
        self.xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # ── Evaluate ──
        xgb_preds = self.xgb_model.predict(X_test)
        xgb_preds = np.maximum(xgb_preds, 0)  # No negative demand

        mae = mean_absolute_error(y_test, xgb_preds)
        mape = mean_absolute_percentage_error(y_test, xgb_preds) * 100

        self.metrics = {
            "mae": round(mae, 2),
            "mape": round(mape, 2),
            "train_size": len(train_df),
            "test_size": len(test_df),
            "features_used": len(self.feature_columns),
            "model": "XGBoost"
        }

        # ── Feature importance ──
        importances = self.xgb_model.feature_importances_
        self.feature_importance = dict(
            sorted(
                zip(self.feature_columns, importances),
                key=lambda x: x[1], reverse=True
            )[:15]
        )

        if verbose:
            print(f"   ✅ XGBoost MAE: {mae:.2f} | MAPE: {mape:.1f}%")
            print(f"   Top features: {list(self.feature_importance.keys())[:5]}")

        # ── Train Prophet (if available) ──
        if PROPHET_AVAILABLE:
            if verbose:
                print("   Training Prophet...")
            try:
                # Prepare Prophet dataframe: daily aggregated sales
                prophet_df = df.groupby("date").agg({"qty_sold": "sum"}).reset_index()
                prophet_df.columns = ["ds", "y"]
                prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

                # Split Prophet data at 80% (same ratio, different granularity)
                prophet_split = int(len(prophet_df) * 0.8)

                self.prophet_model = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                    seasonality_prior_scale=10,
                )
                self.prophet_model.fit(prophet_df.iloc[:prophet_split])

                # Evaluate Prophet on test period
                prophet_test = prophet_df.iloc[prophet_split:]
                prophet_future = self.prophet_model.predict(prophet_test[["ds"]])
                prophet_preds = np.maximum(prophet_future["yhat"].values, 0)
                prophet_mae = mean_absolute_error(prophet_test["y"].values, prophet_preds)
                prophet_mape = mean_absolute_percentage_error(prophet_test["y"].values, prophet_preds) * 100

                # Calculate ensemble weights based on inverse MAE
                total_inv = (1 / mae) + (1 / prophet_mae) if prophet_mae > 0 else 1
                self.xgb_weight = (1 / mae) / total_inv
                self.prophet_weight = (1 / prophet_mae) / total_inv if prophet_mae > 0 else 0

                self.metrics["model"] = "Ensemble (Prophet + XGBoost)"
                self.metrics["prophet_mae"] = round(prophet_mae, 2)
                self.metrics["prophet_mape"] = round(prophet_mape, 2)
                self.metrics["xgb_weight"] = round(self.xgb_weight, 3)
                self.metrics["prophet_weight"] = round(self.prophet_weight, 3)

                if verbose:
                    print(f"   ✅ Prophet MAE: {prophet_mae:.2f} | MAPE: {prophet_mape:.1f}%")
                    print(f"   Ensemble weights — XGBoost: {self.xgb_weight:.1%}, Prophet: {self.prophet_weight:.1%}")
            except Exception as e:
                if verbose:
                    print(f"   ⚠️ Prophet training failed: {e}. Using XGBoost only.")
                self.prophet_model = None
                self.xgb_weight = 1.0
                self.prophet_weight = 0.0
        else:
            self.xgb_weight = 1.0
            self.prophet_weight = 0.0

        self.is_trained = True
        self.training_info = {
            "trained_at": datetime.now().isoformat(),
            "store_id": store_id,
            "product_id": product_id,
            "days_back": days_back
        }

        return self.metrics

    def predict(self, store_id: int, product_id: int,
                days_ahead: int = 7, verbose: bool = True) -> pd.DataFrame:
        """
        Generate demand forecasts for the next N days.
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call .train() first.")

        # Get recent history for feature engineering
        df = get_sales_dataframe(store_id=store_id, product_id=product_id, days_back=90)
        if len(df) == 0:
            raise ValueError(f"No data for store {store_id}, product {product_id}")

        df = self._create_features(df)
        last_row = df.iloc[-1].copy()
        last_date = df["date"].max()

        predictions = []
        for day_offset in range(1, days_ahead + 1):
            forecast_date = last_date + timedelta(days=day_offset)
            row = last_row.copy()

            # Update temporal features
            row["day_of_week"] = forecast_date.dayofweek
            row["month"] = forecast_date.month
            row["day_of_month"] = forecast_date.day
            row["week_of_year"] = forecast_date.isocalendar()[1]
            row["is_weekend"] = int(forecast_date.dayofweek >= 5)
            row["quarter"] = (forecast_date.month - 1) // 3 + 1
            doy = forecast_date.timetuple().tm_yday
            row["dow_sin"] = np.sin(2 * np.pi * row["day_of_week"] / 7)
            row["dow_cos"] = np.cos(2 * np.pi * row["day_of_week"] / 7)
            row["month_sin"] = np.sin(2 * np.pi * row["month"] / 12)
            row["month_cos"] = np.cos(2 * np.pi * row["month"] / 12)
            row["doy_sin"] = np.sin(2 * np.pi * doy / 365)
            row["doy_cos"] = np.cos(2 * np.pi * doy / 365)

            # Use available feature columns
            feature_values = []
            for col in self.feature_columns:
                if col in row.index:
                    feature_values.append(float(row[col]) if pd.notna(row[col]) else 0)
                else:
                    feature_values.append(0)

            X = np.array([feature_values])
            xgb_pred = float(self.xgb_model.predict(X)[0])
            xgb_pred = max(0, xgb_pred)

            # Ensemble with Prophet if available
            model_used = "XGBoost"
            if self.prophet_model is not None and self.prophet_weight > 0:
                try:
                    prophet_future = pd.DataFrame({"ds": [pd.Timestamp(forecast_date)]})
                    prophet_result = self.prophet_model.predict(prophet_future)
                    prophet_pred = max(0, float(prophet_result["yhat"].iloc[0]))
                    pred = self.xgb_weight * xgb_pred + self.prophet_weight * prophet_pred
                    model_used = "Ensemble"
                except Exception:
                    pred = xgb_pred
            else:
                pred = xgb_pred

            # Confidence intervals (using training error distribution)
            std_err = self.metrics.get("mae", pred * 0.1)
            lower = max(0, pred - 1.96 * std_err)
            upper = pred + 1.96 * std_err

            predictions.append({
                "forecast_date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_demand": round(pred, 1),
                "lower_bound": round(lower, 1),
                "upper_bound": round(upper, 1),
                "confidence": round(max(0, 100 - self.metrics.get("mape", 15)), 1),
                "model_used": model_used
            })

        result_df = pd.DataFrame(predictions)

        if verbose:
            print(f"\n📊 Forecast for Store {store_id}, Product {product_id}")
            print(f"   Next {days_ahead} days:")
            for _, row in result_df.iterrows():
                print(f"   {row['forecast_date']}: {row['predicted_demand']:.1f} "
                      f"[{row['lower_bound']:.1f} - {row['upper_bound']:.1f}]")

        return result_df

    def save_forecasts(self, store_id: int, product_id: int, forecasts: pd.DataFrame):
        """Save forecasts to the database."""
        now = datetime.now().isoformat()
        with get_db() as conn:
            for _, row in forecasts.iterrows():
                conn.execute("""
                    INSERT INTO forecasts (created_at, store_id, product_id,
                        forecast_date, predicted_demand, lower_bound, upper_bound,
                        model_used, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [now, store_id, product_id, row["forecast_date"],
                      row["predicted_demand"], row["lower_bound"], row["upper_bound"],
                      row["model_used"], row["confidence"]])

    def batch_forecast(self, days_ahead: int = 7, top_n_products: int = 20,
                       store_ids: list = None) -> dict:
        """
        Generate forecasts for multiple store-product combinations.
        Focuses on top-selling perishable products.
        """
        with get_db(read_only=True) as conn:
            # Get top perishable products by sales volume
            top_products = conn.execute(f"""
                SELECT product_id, SUM(qty_sold) as total_sold
                FROM sales
                WHERE product_id IN (SELECT product_id FROM products WHERE is_perishable = 1)
                GROUP BY product_id
                ORDER BY total_sold DESC
                LIMIT {top_n_products}
            """).fetchdf()

            if store_ids is None:
                stores = conn.execute(
                    "SELECT store_id FROM stores WHERE store_type = 'retailer'"
                ).fetchdf()
                store_ids = stores["store_id"].tolist()

        all_forecasts = {}
        total = len(store_ids) * len(top_products)
        count = 0

        for sid in store_ids:
            for _, prod in top_products.iterrows():
                pid = prod["product_id"]
                count += 1
                try:
                    forecasts = self.predict(sid, pid, days_ahead, verbose=False)
                    self.save_forecasts(sid, pid, forecasts)
                    all_forecasts[(sid, pid)] = forecasts
                except Exception:
                    pass
                if count % 20 == 0:
                    print(f"   Progress: {count}/{total}")

        print(f"✅ Generated {len(all_forecasts)} forecasts")
        return all_forecasts

    def get_surplus_alerts(self, days_ahead: int = 3) -> pd.DataFrame:
        """
        Identify products likely to have surplus (predicted demand < current stock).
        Returns items suitable for waste cascade redistribution.
        """
        with get_db(read_only=True) as conn:
            # Get current inventory with latest forecasts
            alerts = conn.execute("""
                SELECT
                    i.store_id, i.product_id,
                    p.name as product_name, p.category,
                    p.shelf_life_days, p.carbon_footprint_kg,
                    p.unit_cost,
                    st.name as store_name, st.city,
                    i.quantity_on_hand,
                    i.days_until_expiry,
                    i.freshness_score,
                    COALESCE(f.predicted_demand, p.avg_daily_demand) as predicted_demand
                FROM inventory i
                JOIN products p ON i.product_id = p.product_id
                JOIN stores st ON i.store_id = st.store_id
                LEFT JOIN (
                    SELECT store_id, product_id, AVG(predicted_demand) as predicted_demand
                    FROM forecasts
                    WHERE CAST(forecast_date AS DATE) >= current_date
                    GROUP BY store_id, product_id
                ) f ON i.store_id = f.store_id AND i.product_id = f.product_id
                WHERE i.date = (SELECT MAX(date) FROM inventory)
                AND p.is_perishable = 1
            """).fetchdf()

        if len(alerts) == 0:
            return pd.DataFrame()

        # Calculate surplus
        alerts["estimated_surplus"] = alerts["quantity_on_hand"] - (
            alerts["predicted_demand"] * days_ahead
        )
        alerts["urgency_score"] = (
            (1 - alerts["freshness_score"]) * 0.4 +
            (alerts["estimated_surplus"] > 0).astype(float) * 0.3 +
            (1 / (alerts["days_until_expiry"] + 1)) * 0.3
        )

        # Filter to items with surplus or expiring soon
        surplus = alerts[
            (alerts["estimated_surplus"] > 0) | (alerts["days_until_expiry"] <= 2)
        ].sort_values("urgency_score", ascending=False)

        return surplus


# ── Singleton instance ──
_forecaster = None

def get_forecaster() -> DemandForecaster:
    global _forecaster
    if _forecaster is None:
        _forecaster = DemandForecaster()
    return _forecaster


if __name__ == "__main__":
    forecaster = DemandForecaster()

    # Train on all data
    metrics = forecaster.train(days_back=365, verbose=True)
    print(f"\n📈 Model Metrics: {json.dumps(metrics, indent=2)}")

    # Predict for store 1, product 1
    preds = forecaster.predict(store_id=1, product_id=1, days_ahead=7)
    print(f"\n🔮 Predictions:\n{preds}")
