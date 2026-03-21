CREATE TABLE funnel_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    stage TEXT NOT NULL CHECK(stage IN ('unaware','aware','interested','considering','trialing','subscribed','churned','advocate')),
    previous_stage TEXT,
    trigger_type TEXT,
    created_at DATETIME,
    metadata TEXT,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
