alter table users
add column if not exists reactivation_checked_at timestamptz,
add column if not exists reactivation_sent_at timestamptz;

create index if not exists users_reactivation_pending_idx
on users(created_at)
where reactivation_checked_at is null;
