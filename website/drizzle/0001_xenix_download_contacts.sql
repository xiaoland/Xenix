CREATE TABLE IF NOT EXISTS xenix_download_contacts (
  id TEXT PRIMARY KEY,
  contact TEXT NOT NULL UNIQUE,
  contact_type TEXT NOT NULL CHECK (contact_type IN ('email', 'phone')),
  created_at TEXT NOT NULL,
  user_agent TEXT,
  cf_country TEXT
);

CREATE INDEX IF NOT EXISTS xenix_download_contacts_created_at_idx
ON xenix_download_contacts (created_at);
