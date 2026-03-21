CREATE TABLE referral (
    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_user_id INTEGER,
    referred_user_id INTEGER,
    product_id INTEGER,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','signed_up','converted')),
    created_at DATETIME,
    converted_at DATETIME,
    FOREIGN KEY(referrer_user_id) REFERENCES user(user_id),
    FOREIGN KEY(referred_user_id) REFERENCES user(user_id),
    FOREIGN KEY(product_id) REFERENCES product(product_id)
);
