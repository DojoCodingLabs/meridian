CREATE TABLE price_reaction (
    reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    tier_id INTEGER,
    price_shown REAL,
    reaction TEXT CHECK(reaction IN ('accepted','rejected','compared','deferred')),
    willingness_to_pay REAL,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
