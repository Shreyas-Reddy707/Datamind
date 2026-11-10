"""DataMind v2 Universal ML Runner.

Autonomous task detection (classification, regression, clustering, timeseries),
preprocessing, cross-validated multi-model benchmarking, and feature importance.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

logger = logging.getLogger("datamind.engine.ml_runner")


class UniversalMLRunner:
    """Production AutoML benchmark engine with deterministic reproducibility."""

    _simulator_cache: OrderedDict[tuple[str, str, str, tuple[str, ...]], dict[str, Any]] = OrderedDict()
    MAX_SIMULATOR_CACHE = 16

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
        if len(data) > 10000:
            logger.info("Sampling %d rows down to 10000 for interactive AutoML preprocessing", len(data))
            data = data.sample(n=10000, random_state=42)

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
            ("RandomForest", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)),
            ("GradientBoosting", GradientBoostingClassifier(random_state=42)),
            ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42)),
        ]

        n_samples = len(X_train)
        n_splits = 3 if n_samples > 2000 else min(5, max(2, n_samples // 5))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        best_score = -1.0
        best_model = None
        best_name = ""
        leaderboard = []

        for name, model in models:
            t0 = time.perf_counter()
            scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
            elapsed = round(time.perf_counter() - t0, 2)
            mean_score = float(scores.mean())
            std_score = float(scores.std())
            leaderboard.append({
                "model": name,
                "model_name": name,
                "metric": "accuracy",
                "metric_name": "accuracy",
                "cv_mean": round(mean_score, 4),
                "cv_std": round(std_score, 4),
                "mean_cv_score": round(mean_score, 4),
                "std_cv_score": round(std_score, 4),
                "train_time_sec": elapsed,
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
            ("RandomForest", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
            ("GradientBoosting", GradientBoostingRegressor(random_state=42)),
            ("Ridge", Ridge(random_state=42)),
        ]

        n_samples = len(X_train)
        n_splits = 3 if n_samples > 2000 else min(5, max(2, n_samples // 5))
        cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)

        best_score = -float("inf")
        best_model = None
        best_name = ""
        leaderboard = []

        for name, model in models:
            t0 = time.perf_counter()
            scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="r2")
            elapsed = round(time.perf_counter() - t0, 2)
            mean_score = float(scores.mean())
            std_score = float(scores.std())
            leaderboard.append({
                "model": name,
                "model_name": name,
                "metric": "r2",
                "metric_name": "r2",
                "cv_mean": round(mean_score, 4),
                "cv_std": round(std_score, 4),
                "mean_cv_score": round(mean_score, 4),
                "std_cv_score": round(std_score, 4),
                "train_time_sec": elapsed,
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

        t0 = time.perf_counter()
        kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X)
        elapsed = round(time.perf_counter() - t0, 2)
        inertia_val = round(float(kmeans.inertia_), 2)

        cluster_counts = pd.Series(clusters).value_counts().to_dict()
        cluster_summaries = {}
        for c_id, count in cluster_counts.items():
            cluster_summaries[f"Cluster {c_id + 1}"] = {
                "count": int(count),
                "percentage": round(float(count / len(X) * 100), 1),
            }

        return {
            "optimal_k": optimal_k,
            "test_metric_name": "inertia",
            "test_metric_value": inertia_val,
            "leaderboard": [
                {
                    "model": "KMeans",
                    "model_name": "KMeans",
                    "metric": "inertia",
                    "metric_name": "inertia",
                    "cv_mean": inertia_val,
                    "cv_std": 0.0,
                    "mean_cv_score": inertia_val,
                    "std_cv_score": 0.0,
                    "train_time_sec": elapsed,
                    "optimal_k": optimal_k,
                    "inertia": inertia_val,
                }
            ],
            "feature_importances": {},
            "cluster_summaries": cluster_summaries,
            "best_model_name": f"KMeans (k={optimal_k})",
        }

    @classmethod
    def _extract_raw_feature_weights(
        cls,
        df: pd.DataFrame,
        target_col: str,
        feature_importances: dict[str, Any] | list[Any] | None,
        leakage_cols: list[str],
    ) -> list[tuple[str, float]]:
        """Map encoded feature names (e.g. deposit_type_Non Refund) back to raw df columns."""
        excluded = {target_col, *leakage_cols}
        raw_cols = [c for c in df.columns if c not in excluded and df[c].isnull().mean() < 0.6]
        sorted_raw = sorted(raw_cols, key=len, reverse=True)
        weights: dict[str, float] = {}

        pairs: list[tuple[str, float]] = []
        if isinstance(feature_importances, dict):
            for k, v in feature_importances.items():
                try:
                    pairs.append((str(k), float(v)))
                except (TypeError, ValueError):
                    continue
        elif isinstance(feature_importances, list):
            for entry in feature_importances:
                if isinstance(entry, dict):
                    fname = str(entry.get("feature") or entry.get("name") or "")
                    try:
                        val = float(entry.get("importance") or entry.get("score") or 0.0)
                    except (TypeError, ValueError):
                        val = 0.0
                    if fname:
                        pairs.append((fname, val))

        for encoded_name, imp in pairs:
            if encoded_name in excluded:
                continue
            if encoded_name in raw_cols:
                weights[encoded_name] = weights.get(encoded_name, 0.0) + imp
                continue
            matched = next((rc for rc in sorted_raw if encoded_name.startswith(f"{rc}_")), None)
            if matched:
                weights[matched] = weights.get(matched, 0.0) + imp

        # Ensure we always have up to 5 actionable features even if feature_importances was sparse
        if len(weights) < 5:
            num_cols = df[raw_cols].select_dtypes(include=[np.number]).columns.tolist()
            if pd.api.types.is_numeric_dtype(df[target_col]) and num_cols:
                corrs = []
                y_ser = df[target_col].astype(float)
                for nc in num_cols:
                    if nc in weights:
                        continue
                    cval = abs(df[nc].astype(float).corr(y_ser))
                    corrs.append((nc, 0.0 if np.isnan(cval) else float(cval)))
                corrs.sort(key=lambda x: x[1], reverse=True)
                for nc, cv in corrs:
                    if nc not in weights:
                        weights[nc] = round(max(0.01, cv * 0.2), 4)
            for rc in raw_cols:
                if rc not in weights:
                    weights[rc] = 0.01
                if len(weights) >= 5:
                    break

        ranked = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        total = sum(w for _, w in ranked[:8]) or 1.0
        return [(col, round(w / total, 4)) for col, w in ranked[:8]]

    @classmethod
    def _build_or_get_surrogate(
        cls,
        cache_key: tuple[str, str, str, tuple[str, ...]],
        sample_df: pd.DataFrame,
        selected_cols: list[str],
        target_col: str,
        task_type: str,
    ) -> dict[str, Any]:
        """Train or retrieve fast cached surrogate pipeline on top weighted raw columns."""
        if cache_key in cls._simulator_cache:
            cls._simulator_cache.move_to_end(cache_key)
            return cls._simulator_cache[cache_key]

        work = sample_df[selected_cols + [target_col]].dropna(subset=[target_col]).copy()
        num_feats = [c for c in selected_cols if pd.api.types.is_numeric_dtype(work[c])]
        cat_feats = [c for c in selected_cols if c not in num_feats]

        for cf in cat_feats:
            work[cf] = work[cf].astype(str)

        transformers: list[tuple[str, Any, list[str]]] = []
        if num_feats:
            transformers.append((
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
                num_feats,
            ))
        if cat_feats:
            transformers.append((
                "cat",
                Pipeline([
                    ("imp", SimpleImputer(strategy="most_frequent")),
                    ("ohe", OneHotEncoder(handle_unknown="ignore", max_categories=12)),
                ]),
                cat_feats,
            ))

        pre = ColumnTransformer(transformers=transformers, remainder="drop")
        if task_type == "classification":
            y_raw = work[target_col]
            le = LabelEncoder()
            y_enc = le.fit_transform(y_raw.astype(str))
            model = LogisticRegression(max_iter=500, random_state=42)
            pipe = Pipeline([("pre", pre), ("clf", model)])
            pipe.fit(work[selected_cols], y_enc)
            classes = [str(c) for c in le.classes_]
            bundle = {
                "pipeline": pipe,
                "task_type": "classification",
                "classes": classes,
                "y_mean": float(y_enc.mean()) if len(classes) == 2 else float(pipe.predict_proba(work[selected_cols]).max(axis=1).mean()),
                "y_std": float(y_enc.std()) if len(classes) == 2 else 0.15,
            }
        else:
            y_num = work[target_col].astype(float)
            model = Ridge(alpha=1.0, random_state=42)
            pipe = Pipeline([("pre", pre), ("reg", model)])
            pipe.fit(work[selected_cols], y_num)
            preds = pipe.predict(work[selected_cols])
            residual_std = float(np.std(y_num - preds))
            bundle = {
                "pipeline": pipe,
                "task_type": "regression",
                "classes": [],
                "y_mean": float(y_num.mean()),
                "y_std": residual_std,
            }

        cls._simulator_cache[cache_key] = bundle
        if len(cls._simulator_cache) > cls.MAX_SIMULATOR_CACHE:
            cls._simulator_cache.popitem(last=False)
        return bundle

    @classmethod
    def _predict_single_score(cls, bundle: dict[str, Any], row_df: pd.DataFrame) -> dict[str, Any]:
        """Compute scalar outcome score + label for a single-row DataFrame."""
        pipe = bundle["pipeline"]
        if bundle["task_type"] == "classification":
            probs = pipe.predict_proba(row_df)[0]
            classes = bundle["classes"]
            best_idx = int(np.argmax(probs))
            # For binary classification, treat positive class ('1', 'yes', 'true', or index 1) as risk/outcome score
            pos_idx = 1 if len(classes) == 2 else best_idx
            score = float(probs[pos_idx]) * 100.0
            return {
                "scalar": score,
                "predicted_class": classes[best_idx],
                "probability_pct": round(float(probs[best_idx]) * 100.0, 1),
                "positive_class": classes[pos_idx],
                "positive_probability_pct": round(score, 1),
            }
        val = float(pipe.predict(row_df)[0])
        return {
            "scalar": val,
            "predicted_value": round(val, 2),
            "confidence_band": round(float(bundle.get("y_std", 0.0)), 2),
        }

    @classmethod
    def simulate_outcome(
        cls,
        parquet_path: str,
        df: pd.DataFrame,
        target_col: str,
        task_type: str,
        feature_importances: dict[str, Any] | list[Any] | None = None,
        inputs: dict[str, Any] | None = None,
        best_model_name: str | None = None,
    ) -> dict[str, Any]:
        """Compute top-driver What-If simulation, factor contributions, presets, and plain-English insights."""
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset.")

        sample_df = df.sample(n=min(len(df), 10000), random_state=42) if len(df) > 10000 else df
        leakage_cols = cls.detect_leakage_columns(sample_df, target_col)
        ranked_raw = cls._extract_raw_feature_weights(sample_df, target_col, feature_importances, leakage_cols)
        top_features = [col for col, _ in ranked_raw[:5]]
        if not top_features:
            raise ValueError("No usable feature columns available for What-If simulation.")

        weight_map = dict(ranked_raw)
        cache_key = (parquet_path, target_col, task_type, tuple(top_features))
        bundle = cls._build_or_get_surrogate(cache_key, sample_df, top_features, target_col, task_type)

        # Build baseline record & controls metadata
        controls: list[dict[str, Any]] = []
        baseline_row: dict[str, Any] = {}
        high_risk_inputs: dict[str, Any] = {}
        optimal_inputs: dict[str, Any] = {}

        # Target numeric series for computing driver correlations & group averages
        if task_type == "classification":
            y_series = pd.Series(
                LabelEncoder().fit_transform(sample_df[target_col].fillna("Unknown").astype(str)),
                index=sample_df.index,
            ).astype(float)
        else:
            y_series = pd.to_numeric(sample_df[target_col], errors="coerce")

        primary_drivers_text: list[str] = []
        actionable_levers: list[str] = []

        for col in top_features:
            ser = sample_df[col]
            weight_pct = round(weight_map.get(col, 0.0) * 100, 1)
            if pd.api.types.is_numeric_dtype(ser):
                clean = pd.to_numeric(ser, errors="coerce").dropna()
                c_min = float(clean.quantile(0.01)) if not clean.empty else 0.0
                c_max = float(clean.quantile(0.99)) if not clean.empty else 100.0
                if c_max <= c_min:
                    c_max = c_min + 1.0
                c_med = float(clean.median()) if not clean.empty else 0.0
                c_q25 = float(clean.quantile(0.25)) if not clean.empty else c_min
                c_q75 = float(clean.quantile(0.75)) if not clean.empty else c_max
                c_mean = float(clean.mean()) if not clean.empty else 0.0
                span = c_max - c_min
                step = 1.0 if pd.api.types.is_integer_dtype(ser) or span >= 20 else round(max(0.01, span / 50), 2)

                raw_in = (inputs or {}).get(col)
                cur_val = float(raw_in) if raw_in is not None and str(raw_in) != "" else round(c_med, 2)
                cur_val = max(c_min, min(c_max, cur_val))

                valid_idx = clean.index.intersection(y_series.dropna().index)
                corr_val = float(clean.loc[valid_idx].corr(y_series.loc[valid_idx])) if len(valid_idx) > 10 and clean.std() > 1e-6 else 0.0
                if np.isnan(corr_val):
                    corr_val = 0.0

                baseline_row[col] = round(c_med, 2)
                if corr_val >= 0:
                    high_risk_inputs[col] = round(c_q75, 2)
                    optimal_inputs[col] = round(c_q25, 2)
                    direction_word = "increases"
                    lever_range = f"lower `{col}` near {round(c_q25, 1)} (vs {round(c_q75, 1)})"
                else:
                    high_risk_inputs[col] = round(c_q25, 2)
                    optimal_inputs[col] = round(c_q75, 2)
                    direction_word = "decreases"
                    lever_range = f"raise `{col}` toward {round(c_q75, 1)} (vs {round(c_q25, 1)})"

                hint = f"Avg {round(c_mean, 1)} | r={corr_val:+.2f}"
                controls.append({
                    "name": col,
                    "type": "numeric",
                    "weight": weight_map.get(col, 0.0),
                    "min": round(c_min, 2),
                    "max": round(c_max, 2),
                    "step": step,
                    "baseline_value": round(c_med, 2),
                    "current_value": round(cur_val, 2),
                    "summary_hint": hint,
                })
                if len(primary_drivers_text) < 3:
                    primary_drivers_text.append(
                        f"**{col}** ({weight_pct}% influence): Higher values {direction_word} predicted `{target_col}` (dataset mean {round(c_mean, 1)}, r={corr_val:+.2f})."
                    )
                    actionable_levers.append(
                        f"Keep {lever_range} to reduce predicted `{target_col}` variance."
                    )
            else:
                str_ser = ser.fillna("Unknown").astype(str)
                counts = str_ser.value_counts().head(12)
                options = counts.index.tolist() or ["Unknown"]
                mode_val = options[0]
                raw_in = (inputs or {}).get(col)
                cur_val = str(raw_in) if raw_in is not None and str(raw_in) in options else mode_val

                grouped = pd.DataFrame({"cat": str_ser, "y": y_series}).dropna().groupby("cat")["y"].mean()
                best_cat = str(grouped.idxmin()) if not grouped.empty else mode_val
                worst_cat = str(grouped.idxmax()) if not grouped.empty else mode_val
                max_rate = float(grouped.max()) if not grouped.empty else 0.0
                min_rate = float(grouped.min()) if not grouped.empty else 0.0

                baseline_row[col] = mode_val
                high_risk_inputs[col] = worst_cat
                optimal_inputs[col] = best_cat

                rate_unit = "%" if task_type == "classification" and max_rate <= 1.0 else ""
                max_disp = round(max_rate * 100, 1) if rate_unit else round(max_rate, 2)
                min_disp = round(min_rate * 100, 1) if rate_unit else round(min_rate, 2)
                controls.append({
                    "name": col,
                    "type": "categorical",
                    "weight": weight_map.get(col, 0.0),
                    "options": options,
                    "baseline_value": mode_val,
                    "current_value": cur_val,
                    "summary_hint": f"Peak: {worst_cat} ({max_disp}{rate_unit})",
                })
                if len(primary_drivers_text) < 3:
                    primary_drivers_text.append(
                        f"**{col}** ({weight_pct}% influence): `{worst_cat}` shows the highest average `{target_col}` ({max_disp}{rate_unit}) vs `{best_cat}` ({min_disp}{rate_unit})."
                    )
                    actionable_levers.append(
                        f"Shift `{col}` from `{worst_cat}` toward `{best_cat}` to lower `{target_col}` from {max_disp}{rate_unit} to {min_disp}{rate_unit}."
                    )

        current_row = {ctrl["name"]: ctrl["current_value"] for ctrl in controls}
        baseline_pred = cls._predict_single_score(bundle, pd.DataFrame([baseline_row]))
        current_pred = cls._predict_single_score(bundle, pd.DataFrame([current_row]))

        # Compute Factor Contributions relative to dataset baseline
        contributions: list[dict[str, Any]] = []
        for ctrl in controls:
            col = ctrl["name"]
            perturbed = dict(baseline_row)
            perturbed[col] = ctrl["current_value"]
            p_pred = cls._predict_single_score(bundle, pd.DataFrame([perturbed]))
            delta = round(p_pred["scalar"] - baseline_pred["scalar"], 2)
            direction = "increases" if delta > 0.05 else ("decreases" if delta < -0.05 else "neutral")
            contributions.append({
                "feature": col,
                "current_value": ctrl["current_value"],
                "baseline_value": ctrl["baseline_value"],
                "delta": delta,
                "direction": direction,
                "weight": ctrl["weight"],
            })

        unit = "%" if task_type == "classification" else ""
        sim_delta = round(current_pred["scalar"] - baseline_pred["scalar"], 2)

        what_text = (
            f"Predicting **{target_col}** ({task_type.capitalize()} via {best_model_name or 'AutoML'}). "
            f"Baseline typical record predicts **{round(baseline_pred['scalar'], 1)}{unit}**; "
            f"your current What-If scenario shifts this to **{round(current_pred['scalar'], 1)}{unit}** ({sim_delta:+.1f}{unit})."
        )

        return {
            "target_column": target_col,
            "task_type": task_type,
            "top_drivers": top_features[:2],
            "quarantined_leakage": leakage_cols,
            "feature_controls": controls,
            "baseline_prediction": baseline_pred,
            "simulated_prediction": current_pred,
            "delta": sim_delta,
            "unit": unit,
            "factor_contributions": contributions,
            "presets": [
                {"id": "baseline", "label": "Typical Record (Baseline)", "inputs": baseline_row},
                {"id": "high_impact", "label": "High-Risk / Peak Scenario", "inputs": high_risk_inputs},
                {"id": "optimal", "label": "Optimal / Low-Risk Scenario", "inputs": optimal_inputs},
            ],
            "executive_summary": {
                "what_is_predicted": what_text,
                "primary_drivers": primary_drivers_text,
                "actionable_levers": actionable_levers,
            },
        }
