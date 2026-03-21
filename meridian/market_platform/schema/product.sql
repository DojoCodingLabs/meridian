CREATE TABLE product (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    is_target BOOLEAN DEFAULT 0,
    is_competitor BOOLEAN DEFAULT 0,
    base_price REAL DEFAULT 0.0,
    has_free_tier BOOLEAN DEFAULT 0,
    has_trial BOOLEAN DEFAULT 0,
    trial_days INTEGER DEFAULT 0,
    quality_score REAL DEFAULT 0.5,
    brand_strength REAL DEFAULT 0.5,
    feature_count INTEGER DEFAULT 0,
    sales INTEGER DEFAULT 0,
    active_subscribers INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0.0,
    created_at DATETIME
);
