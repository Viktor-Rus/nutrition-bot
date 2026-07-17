alter table users
add column if not exists is_blocked boolean not null default false;

create index if not exists users_is_blocked_idx
on users(is_blocked);
