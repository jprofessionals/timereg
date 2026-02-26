-- Add budget tracking and tag constraints to projects
ALTER TABLE projects ADD COLUMN weekly_hours REAL;
ALTER TABLE projects ADD COLUMN monthly_hours REAL;
ALTER TABLE projects ADD COLUMN allowed_tags TEXT;
