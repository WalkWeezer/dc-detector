CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS detections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected BOOLEAN NOT NULL,
  confidence REAL NOT NULL,
  payload JSONB NOT NULL DEFAULT '[]'::jsonb,
  captured_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_detections_created_at
  ON detections(created_at DESC);


