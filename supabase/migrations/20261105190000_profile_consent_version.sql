-- Migration 8: record WHICH privacy notice the user agreed to (DPDP), next to when.

alter table public.profiles
  add column consent_version text check (char_length(consent_version) between 1 and 20);

-- A consent time and a notice version always come together.
alter table public.profiles
  add constraint profiles_consent_has_version check ((consent_at is null) = (consent_version is null));
