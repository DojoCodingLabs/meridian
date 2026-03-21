CREATE TABLE wallet (
    wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    balance REAL DEFAULT 0.0,
    total_spent REAL DEFAULT 0.0,
    monthly_spending_limit REAL DEFAULT 0.0,
    current_month_spent REAL DEFAULT 0.0,
    last_reset_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id)
);
