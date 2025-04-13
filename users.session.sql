-- Add the confirmation_sent_at column to the users table
ALTER TABLE users
ADD COLUMN confirmation_sent_at TIMESTAMP WITH TIME ZONE;
-- Optional: You can verify the change with:
-- \d users