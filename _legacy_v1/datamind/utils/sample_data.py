"""
Sample data utilities for DataMind v4.0

Provides sample datasets for testing without requiring external file uploads.
"""

import pandas as pd  # type: ignore[import-untyped]


def get_weather_data() -> pd.DataFrame:
    """Generate sample weather data with datetime column."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    import numpy as np  # type: ignore[import-untyped]

    np.random.seed(42)

    data = {
        "date": dates,
        "temperature": np.random.normal(18, 5, 100),
        "humidity": np.random.normal(65, 10, 100),
        "pressure": np.random.normal(1013, 5, 100),
        "wind_speed": np.random.normal(10, 4, 100),
        "weather_condition": np.random.choice(["clear", "cloudy", "rain", "sunny"], 100),
        "rainfall": np.random.exponential(2, 100),
        "visibility": np.random.normal(10, 2, 100),
    }

    return pd.DataFrame(data)


def get_sales_data() -> pd.DataFrame:
    """Generate sample sales data with various column types."""
    import numpy as np  # type: ignore[import-untyped]

    np.random.seed(42)

    products = ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"]
    regions = ["North", "South", "East", "West"]
    months = pd.date_range("2023-01-01", periods=24, freq="MS")

    data = {
        "date": np.random.choice(months, 200),
        "product": np.random.choice(products, 200),
        "region": np.random.choice(regions, 200),
        "units_sold": np.random.randint(10, 500, 200),
        "revenue": np.random.uniform(500, 50000, 200),
        "cost": np.random.uniform(200, 30000, 200),
        "discount_percentage": np.random.uniform(0, 20, 200),
        "customer_satisfaction": np.random.uniform(3, 5, 200),
        "employee_id": np.random.randint(1000, 1050, 200),
    }

    df = pd.DataFrame(data)
    # Add some nulls
    df.loc[5:10, "customer_satisfaction"] = None
    return df


def get_customer_churn_data() -> pd.DataFrame:
    """Generate sample customer churn data for classification."""
    import numpy as np  # type: ignore[import-untyped]

    np.random.seed(42)

    data = {
        "customer_id": range(1, 501),
        "age": np.random.randint(18, 80, 500),
        "tenure_months": np.random.randint(1, 72, 500),
        "monthly_charges": np.random.uniform(20, 120, 500),
        "total_charges": np.random.uniform(100, 8000, 500),
        "contract_type": np.random.choice(["Month-to-month", "One year", "Two year"], 500),
        "payment_method": np.random.choice(["Credit card", "Bank transfer", "Electronic check"], 500),
        "num_support_tickets": np.random.randint(0, 10, 500),
        "has_children": np.random.choice([True, False], 500),
        "is_married": np.random.choice([True, False], 500),
        "has_internet": np.random.choice([True, False], 500),
        "has_online_backup": np.random.choice([True, False], 500),
        "churn": np.random.choice([0, 1], 500, p=[0.7, 0.3]),
    }

    return pd.DataFrame(data)


def get_real_estate_data() -> pd.DataFrame:
    """Generate sample real estate data for regression."""
    import numpy as np  # type: ignore[import-untyped]

    np.random.seed(42)

    neighborhoods = ["Downtown", "Suburbs", "Industrial", "Waterfront", "Historic"]
    house_types = ["Single Family", "Condo", "Townhouse", "Multi-family"]

    data = {
        "date_listed": pd.date_range("2023-01-01", periods=300, freq="D"),
        "neighborhood": np.random.choice(neighborhoods, 300),
        "house_type": np.random.choice(house_types, 300),
        "bedrooms": np.random.randint(1, 6, 300),
        "bathrooms": np.random.randint(1, 4, 300),
        "sqft": np.random.randint(500, 4000, 300),
        "lot_size": np.random.randint(1000, 20000, 300),
        "age_of_home": np.random.randint(0, 100, 300),
        "has_garage": np.random.choice([True, False], 300),
        "has_pool": np.random.choice([True, False], 300),
        "school_rating": np.random.randint(1, 10, 300),
        "price": np.random.uniform(100000, 1000000, 300),
    }

    df = pd.DataFrame(data)
    # Add some nulls for diagnostics testing
    df.loc[10:15, "school_rating"] = None
    return df


# Collection of all sample datasets
SAMPLE_DATASETS = {
    "weather_data": get_weather_data,
    "sales_data": get_sales_data,
    "customer_churn": get_customer_churn_data,
    "real_estate": get_real_estate_data,
}


def load_sample_dataset(name: str) -> pd.DataFrame:
    """Load a sample dataset by name."""
    if name not in SAMPLE_DATASETS:
        raise ValueError(f"Unknown sample dataset: {name}. Available: {list(SAMPLE_DATASETS.keys())}")
    return SAMPLE_DATASETS[name]()