"""Authentication module.

Owns: login, logout, signup (tenant + first owner), refresh, change-password,
forgot/reset-password (F2+), JWT blocklist.

Does NOT own: user CRUD or invitations — those live in ``users``. Auth only
covers identity proofs and session lifecycle.
"""
