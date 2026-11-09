"""DataMind v2 Universal ML Runner.

Autonomous task detection (classification, regression, clustering, timeseries),
preprocessing, cross-validated multi-model benchmarking, and feature importance.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

logger = logging.getLogger("datamind.engine.ml_runner")


class UniversalMLRunner:
    """Production AutoML benchmark engine with deterministic reproducibility."""

    @classmethod
    def auto_select_task(cls, df: pd.DataFrame, target_col: str | None) -> str:
        """Determines the appropriate ML mission based on column traits."""
        if not target_col or target_col not in df.columns:
            return "clustering"

        series = df[target_col].dropna()
        if series.empty:
            return "clustering"

        unique_count = series.nunique()
        dtype = series.dtype

        # 1. Time Series check
        datetime_cols = df.select_dtypes(include=["datetime64", "datetime"]).columns.tolist()
        if datetime_cols and pd.api.types.is_numeric_dtype(dtype):
            return "timeseries"

        # 2. Classification check (2 to 15 unique classes for discrete/categorical)
        if 2 <= unique_count <= 15 and not pd.api.types.is_float_dtype(dtype):
            return "classification"

        # 3. Regression check (> 15 unique continuous values or floating point)
        if pd.api.types.is_numeric_dtype(dtype) and (unique_count > 15 or pd.api.types.is_float_dtype(dtype)):
            return "regression"

        return "regression"

    @classmethod
    def detect_leakage_columns(
        cls, df: pd.DataFrame, target_col: str | None
    ) -> list[str]:
        """Detect columns that exhibit near-deterministic leakage (>0.95 correlation,

        >0.98 mutual info / 1-to-1 status mapping, or post-outcome timestamps).
        """
        if not target_col or target_col not in df.columns or len(df) < 5:
            return []

        leakage_cols: list[str] = []
        target_series = df[target_col].dropna()
        if target_series.nunique() < 2:
            return []

        # Encode target numerically for correlation check
        if pd.api.types.is_numeric_dtype(target_series):
            y_num = target_series.astype(float)
        else:
            try:
                y_num = pd.Series(
                    LabelEncoder().fit_transform(target_series.astype(str)),
                    index=target_series.index,
                ).astype(float)
            except Exception:
                return []

        for col in df.columns:
            if col == target_col:
                continue

            col_lower = col.lower().strip()
            target_lower = target_col.lower().strip()

            # 1. Heuristic check for outcome/status post-event mirrors
            if col_lower in (
                "reservation_status",
                "reservation_status_date",
                "outcome_status",
                "booking_status",
            ) and ("cancel" in target_lower or "status" in target_lower):
                leakage_cols.append(col)
                continue

            if ("date" in col_lower or "timestamp" in col_lower) and any(
                term in col_lower for term in ["status", "cancel", "outcome"]
            ):
                leakage_cols.append(col)
                continue

            series = df[col]
            valid_idx = series.dropna().index.intersection(y_num.index)
            if len(valid_idx) < 10:
                continue

            s_valid = series.loc[valid_idx]
            y_valid = y_num.loc[valid_idx]

            # 2. Numeric / Label-Encoded Correlation (>0.95)
            if pd.api.types.is_numeric_dtype(s_valid):
                s_num = s_valid.astype(float)
            else:
                try:
                    s_num = pd.Series(
                        LabelEncoder().fit_transform(s_valid.astype(str)),
                        index=valid_idx,
                    ).astype(float)
                except Exception as ex:
                    logger.debug("Label encoding skipped for column %s: %s", col, ex)
                    continue

            std_s = s_num.std()
            std_y = y_valid.std()
            if std_s > 1e-6 and std_y > 1e-6:
                corr = abs(s_num.corr(y_valid))
                if not np.isnan(corr) and corr > 0.95:
                    leakage_cols.append(col)
                    continue

            # 3. Categorical 1-to-1 Mapping / Contingency Purity (>0.98)
            if not pd.api.types.is_numeric_dtype(s_valid) and s_valid.nunique() <= 50:
                try:
                    grouped = y_valid.groupby(s_valid)
                    purities = []
                    counts = []
                    for _, group in grouped:
                        if len(group) > 0:
                            mode_freq = (group == group.mode().iloc[0]).mean()
                            purities.append(mode_freq)
                            counts.append(len(group))
                    if counts and sum(counts) > 0:
                        weighted_purity = sum(p * c for p, c in zip(purities, counts, strict=False)) / sum(counts)
                        if weighted_purity > 0.98:
                            leakage_cols.append(col)
                            continue
                except Exception as ex:
                    logger.debug("Purity computation skipped for column %s: %s", col, ex)

        return list(dict.fromkeys(leakage_cols))

    @classmethod
    def diagnose_data(
        cls, df: pd.DataFrame, target_col: str | None = None
    ) -> dict[str, Any]:
        """Pre-prediction validation to identify blockers, warnings, and suggested targets."""
        blockers: list[str] = []
        warnings: list[str] = []
        row_count = len(df)

        if row_count < 20:
            blockers.append(f"Insufficient rows: {row_count} rows detected. Minimum 20 rows required.")

        suggested_target = None
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        if target_col:
            if target_col not in df.columns:
                blockers.append(f"Target column '{target_col}' not found in dataset.")
            elif df[target_col].nunique() < 2:
                blockers.append(f"Target column '{target_col}' has zero variance (constant values).")
        else:
            # Suggest a candidate target
            favored = [c for c in numeric_cols if not any(x in c.lower() for x in ["id", "index", "key"])]
            if favored:
                suggested_target = favored[0]
            elif categorical_cols:
                suggested_target = categorical_cols[0]

        usable_features = [
            c for c in df.columns if c != target_col and df[c].isnull().mean() < 0.6
        ]
        if len(usable_features) < 1:
            blockers.append("Fewer than 1 usable feature column detected after null-filtering.")

        if 20 <= row_count < 100:
            warnings.append("Low sample size (<100 rows). Model validation variance may be higher.")

        if target_col and target_col in df.columns and df[target_col].nunique() <= 10:
            counts = df[target_col].value_counts()
            if not counts.empty and counts.min() > 0:
                ratio = counts.max() / counts.min()
                if ratio > 10:
                    warnings.append(f"High class imbalance ({ratio:.1f}:1). Utilizing StratifiedKFold.")

        effective_target = target_col or suggested_target
        dropped_leakage = cls.detect_leakage_columns(df, effective_target) if effective_target else []
        if dropped_leakage:
            warnings.append(
                f"Quarantined {len(dropped_leakage)} target leakage column(s): {', '.join(dropped_leakage)}."
            )

        return {
            "can_proceed": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "suggested_target": suggested_target or (target_col if target_col in df.columns else None),
            "dropped_leakage_columns": dropped_leakage,
            "row_count": row_count,
            "column_count": len(df.columns),
        }

    @classmethod
    def preprocess(
        cls, df: pd.DataFrame, target_col: str | None, task: str
    ) -> dict[str, Any]:
        """Data cleaning, null imputation, encoding, scaling, and train-test partitioning."""
        data = df.copy()

        # 0. Detect and quarantine target leakage columns
        dropped_leakage = cls.detect_leakage_columns(data, target_col)
        if dropped_leakage:
            logger.info("Quarantined %d target leakage columns: %s", len(dropped_leakage), dropped_leakage)
            data.drop(columns=dropped_leakage, inplace=True, errors="ignore")

        # 1. Drop columns with > 60% missing values
        null_mask = data.isnull().mean() > 0.6
        data.drop(columns=data.columns[null_mask], inplace=True)

        # 2. Impute remaining nulls
        for col in data.columns:
            if data[col].isnull().any():
                if pd.api.types.is_numeric_dtype(data[col]):
                    data[col] = data[col].fillna(data[col].median())
                else:
                    mode_val = data[col].mode()
                    fill_val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                    data[col] = data[col].fillna(fill_val)

        # 3. Extract temporal components if datetime exists
        dt_cols = data.select_dtypes(include=["datetime64", "datetime"]).columns.tolist()
        for col in dt_cols:
            data[f"{col}_year"] = data[col].dt.year
            data[f"{col}_month"] = data[col].dt.month
            data[f"{col}_day"] = data[col].dt.day
            data.drop(columns=[col], inplace=True)

        # 4. Separate X and y
        if task == "clustering":
            X = data.select_dtypes(include=[np.number])
            y = None
        else:
            if not target_col or target_col not in data.columns:
                target_col = data.columns[-1]
            X = data.drop(columns=[target_col])
            y = data[target_col]

        # 5. Encode Categoricals
        cat_cols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in cat_cols:
            if X[col].nunique() <= 15:
                dummies = pd.get_dummies(X[col], prefix=col, drop_first=True)
                X = pd.concat([X, dummies], axis=1)
                X.drop(columns=[col], inplace=True)
            else:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))

        # 6. Encode Target if classification
        if task == "classification" and y is not None:
            le_target = LabelEncoder()
            y = le_target.fit_transform(y.astype(str))

        # 7. Scale features
        scaler = StandardScaler()
        if not X.empty:
            X_scaled = scaler.fit_transform(X)
            X_final = pd.DataFrame(X_scaled, columns=X.columns)
        else:
            X_final = pd.DataFrame()

        if task == "clustering":
            return {
                "X": X_final,
                "feature_names": X.columns.tolist(),
                "dropped_leakage_columns": dropped_leakage,
            }

        X_train, X_test, y_train, y_test = train_test_split(
            X_final, y, test_size=0.2, random_state=42
        )
        return {
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train,
            "y_test": y_test,
            "feature_names": X.columns.tolist(),
            "dropped_leakage_columns": dropped_leakage,
        }

    @classmethod
    def run_classification(
        cls, X_train: pd.DataFrame, X_test: pd.DataFrame, y_train: Any, y_test: Any, feature_names: list[str]
    ) -> dict[str, Any]:
        """Trains candidate classifiers, performs 5-fold CV, and evaluates test set."""
        models = [
            ("RandomForest", RandomForestClassifier(n_estimators=100, random_state=42)),
            ("GradientBoosting", GradientBoostingClassifier(random_state=42)),
            ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42)),
        ]

        n_samples = len(X_train)
        n_splits = min(5, max(2, n_samples // 5))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        best_score = -1.0
        best_model = None
        best_name = ""
        leaderboard = []

        for name, model in models:
            scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
            mean_score = float(scores.mean())
            std_score = float(scores.std())
            leaderboard.append({
                "model": name,
                "metric": "accuracy",
                "mean_cv_score": round(mean_score, 4),
                "std_cv_score": round(std_score, 4),
            })
            if mean_score > best_score:
                best_score = mean_score
                best_model = model
                best_name = name

        if best_model is None:
            best_model = models[0][1]
            best_name = models[0][0]

        best_model.fit(X_train, y_train)
        y_pred = best_model.predict(X_test)
        test_acc = float(accuracy_score(y_test, y_pred))

        # Feature importances
        fi_dict: dict[str, float] = {}
        if hasattr(best_model, "feature_importances_"):
            importances = best_model.feature_importances_
            for fname, imp in zip(feature_names, importances, strict=False):
                fi_dict[fname] = round(float(imp), 4)
            fi_dict = dict(sorted(fi_dict.items(), key=lambda item: item[1], reverse=True))

        return {
            "best_model_name": best_name,
            "test_metric_name": "accuracy",
            "test_metric_value": round(test_acc, 4),
            "leaderboard": leaderboard,
            "feature_importances": fi_dict,
            "classification_report": classification_report(y_test, y_pred, output_dict=True),
        }

    @classmethod
    def run_regression(
        cls, X_train: pd.DataFrame, X_test: pd.DataFrame, y_train: Any, y_test: Any, feature_names: list[str]
    ) -> dict[str, Any]:
        """Trains candidate regressors, performs 5-fold CV, and evaluates test set."""
        models = [
            ("RandomForest", RandomForestRegressor(n_estimators=100, random_state=42)),
            ("GradientBoosting", GradientBoostingRegressor(random_state=42)),
            ("Ridge", Ridge(random_state=42)),
        ]

        n_samples = len(X_train)
        n_splits = min(5, max(2, n_samples // 5))
        cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)

        best_score = -float("inf")
        best_model = None
        best_name = ""
        leaderboard = []

        for name, model in models:
            scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="r2")
            mean_score = float(scores.mean())
            std_score = float(scores.std())
            leaderboard.append({
                "model": name,
                "metric": "r2",
                "mean_cv_score": round(mean_score, 4),
                "std_cv_score": round(std_score, 4),
            })
            if mean_score > best_score:
                best_score = mean_score
                best_model = model
                best_name = name

        if best_model is None:
            best_model = models[0][1]
            best_name = models[0][0]

        best_model.fit(X_train, y_train)
        y_pred = best_model.predict(X_test)
        test_r2 = float(r2_score(y_test, y_pred))
        test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        test_mae = float(mean_absolute_error(y_test, y_pred))

        fi_dict: dict[str, float] = {}
        if hasattr(best_model, "feature_importances_"):
            importances = best_model.feature_importances_
            for fname, imp in zip(feature_names, importances, strict=False):
                fi_dict[fname] = round(float(imp), 4)
            fi_dict = dict(sorted(fi_dict.items(), key=lambda item: item[1], reverse=True))

        return {
            "best_model_name": best_name,
            "test_metric_name": "r2",
            "test_metric_value": round(test_r2, 4),
            "rmse": round(test_rmse, 4),
            "mae": round(test_mae, 4),
            "leaderboard": leaderboard,
            "feature_importances": fi_dict,
        }

    @classmethod
    def run_clustering(cls, df: pd.DataFrame, feature_names: list[str]) -> dict[str, Any]:
        """KMeans clustering with elbow inertia optimization."""
        n_samples = min(len(df), 5000)
        df_sample = df.sample(n_samples, random_state=42) if len(df) > n_samples else df
        X = df_sample[feature_names].dropna()

        k_limit = min(6, max(2, int(np.sqrt(len(X)))))
        inertias = []
        for k in range(2, k_limit + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            km.fit(X)
            inertias.append(km.inertia_)

        optimal_k = 2
        deltas = np.diff(inertias)
        if len(deltas) > 0:
            optimal_k = int(np.argmin(deltas) + 2)

        kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X)

        cluster_counts = pd.Series(clusters).value_counts().to_dict()
        cluster_summaries = {}
        for c_id, count in cluster_counts.items():
            cluster_summaries[f"Cluster {c_id + 1}"] = {
                "count": int(count),
                "percentage": round(float(count / len(X) * 100), 1),
            }

        return {
            "optimal_k": optimal_k,
            "leaderboard": [{"model": "KMeans", "optimal_k": optimal_k, "inertia": round(float(kmeans.inertia_), 2)}],
            "cluster_summaries": cluster_summaries,
            "best_model_name": f"KMeans (k={optimal_k})",
        }
