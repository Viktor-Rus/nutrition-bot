alter table public.subscriptions
add column if not exists trial_reminded_at timestamptz,
add column if not exists trial_ended_notified_at timestamptz;
