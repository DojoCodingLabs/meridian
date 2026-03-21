CREATE TABLE user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER,
    user_name TEXT,
    name TEXT,
    bio TEXT,
    created_at DATETIME,
    num_followings INTEGER DEFAULT 0,
    num_followers INTEGER DEFAULT 0,
    segment TEXT,
    monthly_budget REAL DEFAULT 0.0,
    price_sensitivity REAL DEFAULT 0.5,
    tech_savviness REAL DEFAULT 0.5,
    brand_loyalty REAL DEFAULT 0.5,
    risk_tolerance REAL DEFAULT 0.5
);
