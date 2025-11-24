CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50),
    last_heartbeat TIMESTAMP,
    version VARCHAR(50),
    version_mismatch BOOLEAN DEFAULT false,
    command VARCHAR(50) DEFAULT 'idle',
    progress REAL,
    fps REAL,
    current_file TEXT
);
GRANT ALL PRIVILEGES ON TABLE nodes TO transcode;
GRANT USAGE, SELECT ON SEQUENCE nodes_id_seq TO transcode;

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    filepath TEXT NOT NULL UNIQUE,
    job_type VARCHAR(20) NOT NULL DEFAULT 'transcode',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_to VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
GRANT ALL PRIVILEGES ON TABLE jobs TO transcode;
GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO transcode;

CREATE TABLE IF NOT EXISTS worker_settings (
    id SERIAL PRIMARY KEY,
    setting_name VARCHAR(255) UNIQUE NOT NULL,
    setting_value TEXT
);
GRANT ALL PRIVILEGES ON TABLE worker_settings TO transcode;
GRANT USAGE, SELECT ON SEQUENCE worker_settings_id_seq TO transcode;

CREATE TABLE IF NOT EXISTS encoded_files (
    id SERIAL PRIMARY KEY,
    job_id INTEGER,
    filename TEXT,
    original_size BIGINT,
    new_size BIGINT,
    encoded_by TEXT,
    encoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20)
);
GRANT ALL PRIVILEGES ON TABLE encoded_files TO transcode;
GRANT USAGE, SELECT ON SEQUENCE encoded_files_id_seq TO transcode;

CREATE TABLE IF NOT EXISTS failed_files (
    id SERIAL PRIMARY KEY,
    filename TEXT,
    reason TEXT,
    log TEXT,
    failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
GRANT ALL PRIVILEGES ON TABLE failed_files TO transcode;
GRANT USAGE, SELECT ON SEQUENCE failed_files_id_seq TO transcode;

-- Insert default settings on initial creation
INSERT INTO worker_settings (setting_name, setting_value) VALUES
    ('rescan_delay_minutes', '0'),
    ('worker_poll_interval', '30'),
    ('min_length', '0.5'),
    ('backup_directory', ''),
    ('hardware_acceleration', 'auto'),
    ('keep_original', 'false'),
    ('allow_hevc', 'false'),
    ('allow_av1', 'false'),
    ('auto_update', 'false'),
    ('clean_failures', 'false'),
    ('debug', 'false'),
    ('plex_url', ''),
    ('plex_token', ''),
    ('plex_libraries', ''),
    ('nvenc_cq_hd', '32'),
    ('nvenc_cq_sd', '28'),
    ('vaapi_cq_hd', '28'),
    ('vaapi_cq_sd', '24'),
    ('cpu_cq_hd', '28'),
    ('cpu_cq_sd', '24'),
    ('cq_width_threshold', '1900'),
    ('plex_path_from', ''),
    ('plex_path_to', ''),
    ('pause_job_distribution', 'false')
ON CONFLICT (setting_name) DO NOTHING;