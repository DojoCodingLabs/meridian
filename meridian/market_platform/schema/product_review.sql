CREATE TABLE product_review (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    content TEXT,
    sentiment_score REAL,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
