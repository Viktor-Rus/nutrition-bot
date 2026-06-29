alter table public.subscriptions
add column if not exists trial_reminded_at timestamptz;
