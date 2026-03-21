CREATE TABLE competitor (
    competitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_product_id INTEGER,
    competitor_product_id INTEGER,
    overlap_score REAL DEFAULT 0.5,
    price_difference REAL DEFAULT 0.0,
    FOREIGN KEY(target_product_id) REFERENCES product(product_id),
    FOREIGN KEY(competitor_product_id) REFERENCES product(product_id)
);
