alter table users
add column if not exists age int,
add column if not exists activity_level text,
add column if not exists diet_preferences text,
add column if not exists restrictions text,
add column if not exists profile_completed_at timestamptz;
