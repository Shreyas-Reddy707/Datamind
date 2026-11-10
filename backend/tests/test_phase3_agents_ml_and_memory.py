"""DataMind v2 Phase 3 Automated Pytest Verification Suite.

Validates Universal ML Runner, Chart Factory, LLM client & 768-D embeddings,
Pattern Learner with pgvector, Tiered Context Builder, Chat Classifier,
Bounded LangGraph Agent Graph with SchemaFirewall, and Phase 3 API endpoints.
"""

from __future__ import annotations

import math
import uuid

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.classifier import ChatClassifier
from app.agents.graph import build_agent_graph
from app.config import settings
from app.db.session import get_db
from app.engine.chart_builder import ChartBuilder
from app.engine.duckdb_manager import DuckDBManager
from app.engine.ml_runner import UniversalMLRunner
from app.engine.parquet_ingestor import ParquetIngestor
from app.llm.client import llm_client
from app.main import app
from app.memory.context_builder import ContextBuilder
from app.memory.feedback import FeedbackManager
from app.memory.learner import PatternLearner
from app.memory.query_cache import QueryCache
from app.models.organization import Organization
from app.models.pattern import LearnedPattern
from app.models.user import User
from app.security.auth import create_access_token


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_session():
    """Yields clean async session connected to live test Postgres with NullPool."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_db_dependency():
    """Ensure FastAPI endpoints use NullPool session isolated to active event loop."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def test_user_and_file(db_session: AsyncSession):
    """Provisions a test organization, user, and ingested Parquet dataset."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name="Phase3 Org", slug=f"org-p3-{suffix}")
    db_session.add(org)
    await db_session.flush()

    user = User(
        org_id=org.id,
        email=f"phase3_{suffix}@datamind.local",
        password_hash="argon2id$mockhash",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Ingest a 60-row realistic dataset with numeric, categorical, and target columns
    np.random.seed(42)
    salaries = np.random.randint(40000, 150000, size=60).astype(float)
    # Add strong correlation between salary and bonus: bonus = 0.15 * salary + small noise
    bonuses = salaries * 0.15 + np.random.normal(0, 100, size=60)
    # Introduce 2 clear statistical outliers (> 3 sigma)
    salaries[0] = 1_500_000.0
    salaries[1] = 1_800_000.0
    bonuses[0] = 250_000.0
    bonuses[1] = 300_000.0

    rows = []
    for i in range(60):
        dept = ["Tech", "Finance", "Health"][i % 3]
        perf = ["Low", "Medium", "High"][i % 3]
        churn = i % 2
        rows.append(f"{i+1},{dept},{salaries[i]},{bonuses[i]},{perf},{churn}")
    csv_bytes = ("id,department,salary,bonus,performance,churn\n" + "\n".join(rows)).encode("utf-8")

    uf, gf, _ = await ParquetIngestor.ingest_file(
        csv_bytes, "phase3_workforce.csv", user.id, org.id, db_session
    )
    return user, uf, gf


# ==============================================================================
# 1. Universal ML Runner Tests
# ==============================================================================
def test_ml_runner_task_auto_selection_and_preprocessing():
    df = pd.DataFrame({
        "feature1": [1.0, 2.0, 3.0, 4.0] * 10,
        "feature2": ["A", "B", "A", "B"] * 10,
        "reg_target": [float(i * 2.5) for i in range(40)],
        "clf_target": [0, 1, 0, 1] * 10,
    })

    # Task detection
    assert UniversalMLRunner.auto_select_task(df, "clf_target") == "classification"
    assert UniversalMLRunner.auto_select_task(df, "reg_target") == "regression"
    assert UniversalMLRunner.auto_select_task(df, None) == "clustering"

    # Preprocessing
    prep_clf = UniversalMLRunner.preprocess(df, "clf_target", "classification")
    assert "X_train" in prep_clf and "y_train" in prep_clf
    assert len(prep_clf["feature_names"]) >= 2

    # Benchmark classification
    clf_res = UniversalMLRunner.run_classification(
        prep_clf["X_train"], prep_clf["X_test"], prep_clf["y_train"], prep_clf["y_test"], prep_clf["feature_names"]
    )
    assert clf_res["best_model_name"] in ["RandomForest", "GradientBoosting", "LogisticRegression"]
    assert "accuracy" in clf_res["test_metric_name"]
    assert len(clf_res["leaderboard"]) == 3

    # Benchmark regression
    prep_reg = UniversalMLRunner.preprocess(df, "reg_target", "regression")
    reg_res = UniversalMLRunner.run_regression(
        prep_reg["X_train"], prep_reg["X_test"], prep_reg["y_train"], prep_reg["y_test"], prep_reg["feature_names"]
    )
    assert reg_res["best_model_name"] in ["RandomForest", "GradientBoosting", "Ridge"]
    assert "r2" in reg_res["test_metric_name"]
    assert len(reg_res["leaderboard"]) == 3

    # Clustering
    clust_res = UniversalMLRunner.run_clustering(df, ["feature1"])
    assert "KMeans" in clust_res["best_model_name"]
    assert clust_res["optimal_k"] >= 2


def test_ml_diagnostics_validation():
    # 1. Dataset too small (<20 rows)
    small_df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    diag_small = UniversalMLRunner.diagnose_data(small_df, "y")
    assert diag_small["can_proceed"] is False
    assert any("Insufficient rows" in b for b in diag_small["blockers"])

    # 2. Zero variance target
    const_df = pd.DataFrame({"x": list(range(30)), "y": [1] * 30})
    diag_const = UniversalMLRunner.diagnose_data(const_df, "y")
    assert diag_const["can_proceed"] is False
    assert any("zero variance" in b for b in diag_const["blockers"])


# ==============================================================================
# 2. Chart Builder Tests
# ==============================================================================
def test_chart_builder_dark_mode_specs():
    df = pd.DataFrame({
        "salary": [50000, 60000, 75000, 90000, 110000],
        "bonus": [5000, 6000, 7000, 9000, 12000],
        "dept": ["Tech", "Tech", "HR", "Sales", "HR"],
    })

    # Distribution
    dist_spec = ChartBuilder.build_distribution(df, "salary")
    assert dist_spec is not None
    assert dist_spec["layout"]["paper_bgcolor"] == "#09090B"

    # Scatter
    scatter_spec = ChartBuilder.build_scatter(df, "salary", "bonus", color_col="dept")
    assert scatter_spec is not None
    assert len(scatter_spec["data"]) >= 1

    # Heatmap
    heatmap_spec = ChartBuilder.build_heatmap(df)
    assert heatmap_spec is not None
    assert heatmap_spec["data"][0]["type"] == "heatmap"

    # Feature Importance
    fi_spec = ChartBuilder.build_feature_importance({"salary": 0.65, "bonus": 0.25, "age": 0.10})
    assert fi_spec["data"][0]["orientation"] == "h"


# ==============================================================================
# 3. LLM Client & 768-D Deterministic Embeddings
# ==============================================================================
@pytest.mark.asyncio
async def test_llm_client_embeddings_dimension_and_norm():
    text = "Autonomous analytical patterns in financial time series."
    vec = await llm_client.get_embedding(text)

    # Must match pgvector Vector(768)
    assert len(vec) == 768
    # Must be L2 unit normalized
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)

    # Determinism check: identical text yields identical coordinates
    vec2 = await llm_client.get_embedding(text)
    assert vec == vec2


# ==============================================================================
# 4. Pattern Learner & Feedback Manager Tests (pgvector)
# ==============================================================================
@pytest.mark.asyncio
async def test_pattern_learner_and_feedback(db_session: AsyncSession, test_user_and_file):
    user, uf, gf = test_user_and_file

    # Extract statistical patterns
    patterns = await PatternLearner.extract_statistical_patterns(
        gf.parquet_path, user.id, uf.id, db_session
    )
    assert len(patterns) >= 1

    # Verify Vector(768) in database
    p_id = patterns[0].id
    p_record = await db_session.get(LearnedPattern, p_id)
    assert p_record is not None
    assert p_record.confidence_score > 0.0

    # Test feedback loop with Laplace smoothing
    fb1 = await FeedbackManager.record_pattern_vote(p_id, user.id, is_helpful=True, db=db_session)
    assert fb1 is not None
    assert fb1["helpful_votes"] == 1
    # Initial: 0 up, 0 down -> (1+1)/(1+0+2) = 2/3 = 0.667
    assert fb1["confidence_score"] == 0.667

    fb2 = await FeedbackManager.record_pattern_vote(p_id, user.id, is_helpful=False, db=db_session)
    # Now: 1 up, 1 down -> (1+1)/(1+1+2) = 2/4 = 0.500
    assert fb2["confidence_score"] == 0.500


# ==============================================================================
# 5. Tiered Context Builder & Chat Classifier Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_chat_classifier_and_context_builder(db_session: AsyncSession, test_user_and_file):
    user, uf, gf = test_user_and_file
    active_cols = list(gf.schema_json.get("columns", {}).keys())

    # 1. Tier 1 routing
    c1 = ChatClassifier.classify("how many rows are there", active_cols)
    assert c1["tier"] == 1
    assert c1["intent"] == "stat"

    # 2. Tier 3 routing (Prediction / Lab Triggers)
    c2 = ChatClassifier.classify("predict churn rate for marketing team", active_cols)
    assert c2["tier"] == 3
    assert c2["intent"] == "prediction"

    # 3. Tier 2 conversational routing
    c3 = ChatClassifier.classify("why is department variable important?", active_cols)
    assert c3["tier"] == 2

    # 4. Context packaging
    tier2_ctx = await ContextBuilder.build_tier2_context(
        "salary summary", gf.schema_json, [{"role": "user", "content": "hi"}]
    )
    assert len(tier2_ctx) <= 2500
    assert "ACTIVE DATASET" in tier2_ctx

    profile = DuckDBManager.generate_data_profile(gf.parquet_path)
    tier3_ctx = await ContextBuilder.build_tier3_context(
        "deep analysis of salary and bonus",
        gf.schema_json,
        user.id,
        uf.id,
        db_session,
        data_profile=profile,
    )
    assert len(tier3_ctx) <= 6000
    assert "DATASET INTELLIGENCE DOSSIER" in tier3_ctx


# ==============================================================================
# 6. Bounded LangGraph Agent State Machine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_langgraph_bounded_execution(test_user_and_file):
    user, uf, gf = test_user_and_file
    graph = build_agent_graph()
    profile = DuckDBManager.generate_data_profile(gf.parquet_path)

    initial_state = {
        "query": "Give me a summary overview of this dataset",
        "user_id": str(user.id),
        "user_file_id": str(uf.id),
        "parquet_path": gf.parquet_path,
        "schema_json": gf.schema_json,
        "data_profile": profile,
        "recent_history": [],
        "intent": "summarize",
        "target_columns": [],
        "current_step": 0,
        "max_steps": 8,
        "token_budget": 6000,
        "tokens_used": 0,
        "brief_response": "",
        "detailed_narrative": "",
        "lab_artifact": None,
        "firewall_passed": False,
        "firewall_feedback": None,
        "error": None,
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["current_step"] <= 8
    assert final_state["firewall_passed"] is True
    assert len(final_state["brief_response"]) > 0


# ==============================================================================
# 7. Query Cache Scoped Isolation Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_query_cache_tier_isolation():
    cache = QueryCache()
    u_id = uuid.uuid4()
    f_id = uuid.uuid4()

    # Tier 1 is cacheable
    await cache.set(u_id, f_id, "how many rows", {"text": "60 rows"}, tier=1)
    res = await cache.get(u_id, f_id, "how many rows")
    assert res is not None
    assert res["text"] == "60 rows"

    # Tier 3 is non-cacheable
    await cache.set(u_id, f_id, "predict churn", {"text": "non-cached"}, tier=3)
    res3 = await cache.get(u_id, f_id, "predict churn")
    assert res3 is None


# ==============================================================================
# 8. End-to-End API Integration Tests (Chat, Lab, Predict)
# ==============================================================================
@pytest.mark.asyncio
async def test_chat_sse_stream_and_history(test_user_and_file):
    user, uf, gf = test_user_and_file
    token = create_access_token({"sub": str(user.id), "org_id": str(user.org_id), "role": user.role})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Chat Stream SSE (Tier 1 instant)
        res = await client.post(
            f"/api/v1/chat/{uf.id}/stream",
            json={"query": "how many rows"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert "tier_detected" in res.text
        assert "60 rows" in res.text

        # 2. Chat History
        hist_res = await client.get(
            f"/api/v1/chat/{uf.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert hist_res.status_code == 200
        messages = hist_res.json()
        assert len(messages) >= 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_lab_and_predict_endpoints(test_user_and_file):
    user, uf, gf = test_user_and_file
    token = create_access_token({"sub": str(user.id), "org_id": str(user.org_id), "role": user.role})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Lab Overview
        overview_res = await client.get(
            f"/api/v1/lab/{uf.id}/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert overview_res.status_code == 200
        assert overview_res.json()["row_count"] == 60

        # 2. Lab Visualize (Distribution)
        viz_res = await client.post(
            f"/api/v1/lab/{uf.id}/visualize",
            json={"chart_type": "distribution", "column": "salary"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert viz_res.status_code == 200
        assert "data" in viz_res.json()

        # 3. Lab Analyze & Export PDF
        analyze_res = await client.post(
            f"/api/v1/lab/{uf.id}/analyze",
            json={"query": "Evaluate salary vs performance distribution"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert analyze_res.status_code == 200
        assert "finding_text" in analyze_res.json()

        export_res = await client.get(
            f"/api/v1/lab/{uf.id}/export-pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert export_res.status_code == 200
        assert "markdown_report" in export_res.json()

        # 4. Predict Diagnose
        diag_res = await client.post(
            f"/api/v1/predict/{uf.id}/diagnose",
            json={"target_col": "churn"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert diag_res.status_code == 200
        assert diag_res.json()["can_proceed"] is True

        # 5. Predict Run (AutoML Job Trigger)
        run_res = await client.post(
            f"/api/v1/predict/{uf.id}/run",
            json={"target_col": "churn", "task_type": "classification"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert run_res.status_code == 200
        job_data = run_res.json()
        assert job_data["status"] in ["queued", "completed"]
        job_id = job_data["id"]

        # 6. Predict Job Poll
        job_res = await client.get(
            f"/api/v1/predict/{uf.id}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert job_res.status_code == 200
        assert job_res.json()["id"] == job_id


@pytest.mark.asyncio
async def test_smart_query_three_modes_and_visual_join(test_user_and_file):
    user, uf, gf = test_user_and_file
    token = create_access_token({"sub": str(user.id), "org_id": str(user.org_id), "role": user.role})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Visual Builder Mode
        builder_res = await client.post(
            f"/api/v1/lab/{uf.id}/query",
            json={
                "mode": "builder",
                "group_by": ["department"],
                "metrics": [{"col": "salary", "agg": "avg"}, {"col": "*", "agg": "count"}],
                "filters": [{"col": "department", "op": "not_null"}],
                "sort_dir": "desc",
                "limit": 10,
            },
            headers=headers,
        )
        assert builder_res.status_code == 200
        b_data = builder_res.json()
        assert b_data["row_count"] == 3
        assert "department" in b_data["columns"]
        assert "avg_salary" in b_data["columns"]
        assert "generated_sql" in b_data
        assert "explanation" in b_data

        # 2. Natural-Language Question Mode
        nl_res = await client.post(
            f"/api/v1/lab/{uf.id}/query",
            json={
                "mode": "question",
                "question": "top 2 departments by average salary",
            },
            headers=headers,
        )
        assert nl_res.status_code == 200
        nl_data = nl_res.json()
        assert nl_data["row_count"] == 2
        assert "department" in nl_data["columns"]
        assert "avg_salary" in nl_data["columns"]

        # 3. Advanced Raw SQL Fallback Mode
        sql_res = await client.post(
            f"/api/v1/lab/{uf.id}/query",
            json={
                "mode": "sql",
                "sql": "SELECT department, COUNT(*) AS cnt FROM dataset GROUP BY department",
            },
            headers=headers,
        )
        assert sql_res.status_code == 200
        assert sql_res.json()["row_count"] == 3

        # 4. No-Code Visual Join Preview (two file entries)
        join_res = await client.post(
            "/api/v1/files/join-preview",
            json={
                "files": [
                    {"file_id": str(uf.id), "alias": "left_ds"},
                    {"file_id": str(uf.id), "alias": "right_ds"},
                ],
                "left_col": "id",
                "right_col": "id",
                "join_type": "inner",
                "group_by": ["department"],
                "metrics": [{"col": "*", "agg": "count"}],
                "limit": 5,
            },
            headers=headers,
        )
        assert join_res.status_code == 200
        assert join_res.json()["count"] == 3

