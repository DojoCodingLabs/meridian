CREATE TABLE product_tier (
    tier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    tier_name TEXT NOT NULL,
    monthly_price REAL DEFAULT 0.0,
    annual_price REAL DEFAULT 0.0,
    one_time_price REAL,
    feature_set TEXT,
    max_users INTEGER DEFAULT 1,
    is_default BOOLEAN DEFAULT 0,
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
