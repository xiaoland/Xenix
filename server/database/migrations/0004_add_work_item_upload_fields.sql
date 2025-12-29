-- Add upload step result fields to work_items table
ALTER TABLE work_items ADD COLUMN dataset_id INTEGER;
ALTER TABLE work_items ADD COLUMN feature_columns TEXT;
ALTER TABLE work_items ADD COLUMN target_column TEXT;
