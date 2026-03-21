CREATE TABLE product_feature (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    feature_key TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    description TEXT,
    importance_weight REAL DEFAULT 0.5,
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
