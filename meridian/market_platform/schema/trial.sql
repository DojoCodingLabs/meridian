CREATE TABLE trial (
    trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    tier_id INTEGER,
    started_at DATETIME,
    ends_at DATETIME,
    converted BOOLEAN DEFAULT 0,
    converted_at DATETIME,
    abandon_reason TEXT,
    engagement_during_trial REAL DEFAULT 0.0,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
