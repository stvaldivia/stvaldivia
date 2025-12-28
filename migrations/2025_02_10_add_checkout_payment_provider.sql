ALTER TABLE checkout_sessions
    ADD COLUMN payment_provider VARCHAR(50) NULL;

CREATE INDEX idx_checkout_sessions_payment_provider
    ON checkout_sessions (payment_provider);
