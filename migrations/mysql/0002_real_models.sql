CREATE TABLE IF NOT EXISTS variable_metadata (
    variable_code VARCHAR(128) PRIMARY KEY,
    raw_unit VARCHAR(64) NOT NULL,
    standard_unit VARCHAR(64) NOT NULL,
    minimum_valid DOUBLE NULL,
    maximum_valid DOUBLE NULL,
    sensor_resolution DOUBLE NULL,
    verified_at DATETIME NULL,
    verified_by VARCHAR(255) NULL
);

CREATE TABLE IF NOT EXISTS model_forecasts (
    forecast_id VARCHAR(160) PRIMARY KEY,
    pond_id VARCHAR(128) NOT NULL,
    model_code VARCHAR(128) NOT NULL,
    asset_id VARCHAR(160) NULL,
    issued_at DATETIME NOT NULL,
    target_time DATETIME NOT NULL,
    input_window_start DATETIME NOT NULL,
    input_window_end DATETIME NOT NULL,
    predicted_variable VARCHAR(128) NOT NULL,
    predicted_value DOUBLE NOT NULL,
    unit VARCHAR(64) NOT NULL,
    observed_value DOUBLE NULL,
    absolute_error DOUBLE NULL,
    quality_json JSON NOT NULL,
    payload_json JSON NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_forecast_pond_target (pond_id, target_time),
    INDEX ix_forecast_model_time (model_code, issued_at)
);

CREATE TABLE IF NOT EXISTS fish_biometric_samples (
    sample_id VARCHAR(160) PRIMARY KEY,
    pond_id VARCHAR(128) NOT NULL,
    sampled_at DATETIME NOT NULL,
    average_length_mm DOUBLE NULL,
    average_weight_g DOUBLE NULL,
    sample_size INT NULL,
    source VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_biometric_pond_time (pond_id, sampled_at)
);
