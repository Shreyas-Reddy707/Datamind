"""DataMind v2 Instant Responder Engine (Tier 0).

Executes deterministic regex-matched statistical queries directly against
DuckDB and Parquet storage in sub-25ms with $0 LLM token cost.
Enforces strict identifier quoting, Parquet schema validation, and complete
external access lockdown (SET enable_external_access = false).
"""

from __future__ import annotations

import difflib
import logging
import re
import time
from collections import OrderedDict
from typing import Any

import duckdb

logger = logging.getLogger("datamind.engine.instant_responder")


def escape_identifier(ident: str) -> str:
    """Strict double-quoting for SQL identifiers with internal quotes escaped."""
    escaped = ident.replace('"', '""')
    return f'"{escaped}"'


class InstantResponder:
    """Sub-25ms Tier 0 engine handling deterministic summary statistics."""

    _file_connections: OrderedDict[str, duckdb.DuckDBPyConnection] = OrderedDict()
    MAX_CONNECTIONS: int = 16

    @classmethod
    def get_connection(cls, parquet_path: str) -> duckdb.DuckDBPyConnection:
        """Get or initialize a cached DuckDB in-memory table with bounded LRU and external access disabled."""
        norm_path = parquet_path.replace("\\", "/")
        if norm_path in cls._file_connections:
            cls._file_connections.move_to_end(norm_path)
            return cls._file_connections[norm_path]

        # Evict oldest if capacity reached
        if len(cls._file_connections) >= cls.MAX_CONNECTIONS:
            _oldest_key, evicted_conn = cls._file_connections.popitem(last=False)
            try:
                evicted_conn.close()
            except Exception as e:
                logger.debug("Error closing evicted DuckDB connection: %s", e)

        conn = duckdb.connect(database=":memory:", read_only=False)
        conn.execute("SET memory_limit = '512MB'; SET threads = 2;")
        # Parameterized table creation from authorized parquet
        conn.execute("CREATE TABLE dataset AS SELECT * FROM read_parquet(?)", [norm_path])
        # Lock down external access so arbitrary filesystem/HTTP probing is blocked
        conn.execute("SET enable_external_access = false;")
        cls._file_connections[norm_path] = conn
        return conn

    @staticmethod
    def escape_identifier(ident: str) -> str:
        """Strict double-quoting for SQL identifiers with internal quotes escaped."""
        return escape_identifier(ident)

    @classmethod
    def _validate_column_against_schema(
        cls, col_name: str, schema_info: dict[str, Any]
    ) -> str:
        """Validate that col_name exists in schema_info and return safe escaped identifier."""
        known_cols = schema_info.get("columns", {})
        if col_name not in known_cols:
            raise ValueError(f"Column '{col_name}' does not exist in dataset schema.")
        return escape_identifier(col_name)

    @classmethod
    def can_handle(cls, query: str) -> bool:
        """Evaluate if user query matches Tier 0 deterministic statistical patterns."""
        q = query.lower().strip()
        patterns = [
            r"how many rows",
            r"row count",
            r"total rows",
            r"list columns",
            r"what columns",
            r"show columns",
            r"(average|mean|max|min|sum|count|median|stddev)\s+of\s+.+",
            r"how many nulls",
            r"missing values",
            r"null values",
            r"null.*in\s+.+",
            r"correlation\s+between\s+.+\s+and\s+.+",
        ]
        return any(re.search(p, q) for p in patterns)

    @classmethod
    def execute(
        cls,
        query: str,
        parquet_path: str,
        schema_info: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute deterministic statistical query against DuckDB in <25ms.
        Returns {result: str, latency_ms: int, tier: 0, matched_intent: str}.
        """
        start_time = time.perf_counter()
        q_lower = query.lower().strip()
        conn = cls.get_connection(parquet_path)

        # 1. Row Count
        if any(x in q_lower for x in ["how many rows", "row count", "total rows"]):
            count = conn.execute("SELECT count(*) FROM dataset").fetchone()[0]
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": f"**{count:,} rows** found in this dataset.",
                "latency_ms": elapsed,
                "tier": 0,
                "intent": "row_count",
            }

        # 2. Column Listing
        if any(x in q_lower for x in ["list columns", "what columns", "show columns"]):
            table_md = cls._format_columns_table(schema_info)
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": table_md,
                "latency_ms": elapsed,
                "tier": 0,
                "intent": "column_listing",
            }

        # 3. Numeric Aggregations (Average, Mean, Max, Min, Sum, Count, Median, Stddev)
        agg_match = re.search(
            r"(average|mean|max|min|sum|count|median|stddev)\s+of\s+(.+)", q_lower
        )
        if agg_match:
            agg_op = agg_match.group(1)
            col_raw = agg_match.group(2).strip()
            res_text = cls._handle_aggregation(conn, agg_op, col_raw, schema_info)
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": res_text,
                "latency_ms": elapsed,
                "tier": 0,
                "intent": f"agg_{agg_op}",
            }

        # 4. Correlation between two columns
        corr_match = re.search(r"correlation\s+between\s+(.+?)\s+and\s+(.+)", q_lower)
        if corr_match:
            col1 = corr_match.group(1).strip()
            col2 = corr_match.group(2).strip()
            res_text = cls._handle_correlation(conn, col1, col2, schema_info)
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": res_text,
                "latency_ms": elapsed,
                "tier": 0,
                "intent": "correlation",
            }

        # 5. Null Summary
        if any(x in q_lower for x in ["how many nulls", "missing values", "null values"]):
            res_text = cls._handle_nulls_summary(conn, schema_info)
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": res_text,
                "latency_ms": elapsed,
                "tier": 0,
                "intent": "null_summary",
            }

        # 6. Specific Column Null Count
        col_null_match = re.search(r"null.*in\s+(.+)", q_lower)
        if col_null_match:
            col_raw = col_null_match.group(1).strip()
            res_text = cls._handle_single_column_nulls(conn, col_raw, schema_info)
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return {
                "result": res_text,
                "latency_ms": elapsed,
                "tier": 0,
                "intent": "column_null_count",
            }

        elapsed = int((time.perf_counter() - start_time) * 1000)
        return {
            "result": "Identified statistical query, but parameters could not be resolved directly.",
            "latency_ms": elapsed,
            "tier": 0,
            "intent": "unresolved_stat",
        }

    @staticmethod
    def _find_column(target: str, columns: list[str]) -> str | None:
        """Fuzzy match column name against schema."""
        clean_target = re.sub(r"[^\w\s]", "", target).strip().lower()
        # Exact match
        for col in columns:
            if col.lower() == clean_target:
                return col
        # Fuzzy match
        matches = difflib.get_close_matches(
            clean_target, [c.lower() for c in columns], n=1, cutoff=0.6
        )
        if matches:
            for col in columns:
                if col.lower() == matches[0]:
                    return col
        return None

    @classmethod
    def _handle_aggregation(
        cls,
        conn: duckdb.DuckDBPyConnection,
        op: str,
        col_query: str,
        schema_info: dict[str, Any],
    ) -> str:
        columns = list(schema_info.get("columns", {}).keys())
        target_col = cls._find_column(col_query, columns)
        if not target_col:
            return f"Could not find a column matching '{col_query}'."

        col_meta = schema_info.get("columns", {}).get(target_col, {})
        is_num = col_meta.get("dtype") == "numeric"

        sql_func_map = {
            "average": "avg",
            "mean": "avg",
            "max": "max",
            "min": "min",
            "sum": "sum",
            "count": "count",
            "median": "median",
            "stddev": "stddev",
        }
        fn = sql_func_map.get(op, "avg")

        if fn in ("avg", "sum", "median", "stddev") and not is_num:
            return f"Column **{target_col}** is not numeric ({col_meta.get('dtype', 'text')}). Cannot compute {op}."

        # Validate column against schema and escape identifier
        esc_target = cls._validate_column_against_schema(target_col, schema_info)
        res = conn.execute(f"SELECT {fn}({esc_target}) FROM dataset").fetchone()[0]  # noqa: S608
        if res is None:
            return f"**{op.capitalize()} {target_col}**: No non-null values found."

        if isinstance(res, float):
            return f"**{op.capitalize()} {target_col}**: {res:,.2f}"
        return f"**{op.capitalize()} {target_col}**: {res:,}"

    @classmethod
    def _handle_correlation(
        cls,
        conn: duckdb.DuckDBPyConnection,
        col1_query: str,
        col2_query: str,
        schema_info: dict[str, Any],
    ) -> str:
        columns = list(schema_info.get("columns", {}).keys())
        c1 = cls._find_column(col1_query, columns)
        c2 = cls._find_column(col2_query, columns)

        if not c1 or not c2:
            return f"Could not identify both columns in dataset ({col1_query}, {col2_query})."

        # Validate both columns against schema and escape identifiers
        esc_c1 = cls._validate_column_against_schema(c1, schema_info)
        esc_c2 = cls._validate_column_against_schema(c2, schema_info)
        r = conn.execute(f"SELECT corr({esc_c1}, {esc_c2}) FROM dataset").fetchone()[0]  # noqa: S608
        if r is None:
            return f"Cannot compute Pearson correlation between **{c1}** and **{c2}** (insufficient non-null numeric variance)."
        return f"**Correlation between {c1} and {c2}**: r = {r:.4f}"

    @staticmethod
    def _format_columns_table(schema_info: dict[str, Any]) -> str:
        cols = schema_info.get("columns", {})
        if not cols:
            return "No schema metadata found for this dataset."

        rows = []
        for col_name, meta in list(cols.items())[:20]:
            dtype = meta.get("dtype", "text")
            null_pct = meta.get("null_pct", 0.0)
            rows.append(f"| `{col_name}` | {dtype} | {null_pct:.1f}% |")

        table = "| Column | Type | Null Rate |\n| :--- | :--- | :--- |\n" + "\n".join(rows)
        if len(cols) > 20:
            table += f"\n\n*(Showing 20 of {len(cols)} columns)*"
        return table

    @classmethod
    def _handle_nulls_summary(
        cls, conn: duckdb.DuckDBPyConnection, schema_info: dict[str, Any]
    ) -> str:
        cols = schema_info.get("columns", {})
        null_rows = []
        for col_name, meta in cols.items():
            esc_col = cls._validate_column_against_schema(col_name, schema_info)
            cnt = conn.execute(
                f"SELECT count(*) FROM dataset WHERE {esc_col} IS NULL"  # noqa: S608
            ).fetchone()[0]
            if cnt > 0:
                null_rows.append(
                    f"- **`{col_name}`**: {cnt:,} missing rows ({meta.get('null_pct', 0):.1f}%)"
                )

        if not null_rows:
            return "✅ **No missing values detected** in this dataset."
        return "### 🔍 Missing Values Summary\n\n" + "\n".join(null_rows)

    @classmethod
    def _handle_single_column_nulls(
        cls,
        conn: duckdb.DuckDBPyConnection,
        col_query: str,
        schema_info: dict[str, Any],
    ) -> str:
        columns = list(schema_info.get("columns", {}).keys())
        c = cls._find_column(col_query, columns)
        if not c:
            return f"Could not find column matching '{col_query}'."
        esc_col = cls._validate_column_against_schema(c, schema_info)
        cnt = conn.execute(f"SELECT count(*) FROM dataset WHERE {esc_col} IS NULL").fetchone()[0]  # noqa: S608
        total = conn.execute("SELECT count(*) FROM dataset").fetchone()[0]
        pct = (cnt / total * 100) if total > 0 else 0
        return f"**{c}** has **{cnt:,} null values** ({pct:.1f}% of total {total:,} rows)."
