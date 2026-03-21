CREATE TABLE 'transaction' (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    tier_id INTEGER,
    type TEXT CHECK(type IN ('purchase','subscription_payment','refund','upgrade','downgrade','trial_start')),
    amount REAL,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
