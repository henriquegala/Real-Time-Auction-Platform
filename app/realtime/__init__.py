"""Real-time + concurrency layer (Arthur).

Owns: WebSockets, Redis Pub/Sub, atomic bid handling, winner declaration.
Does NOT own: auth endpoints, auction CRUD, SQL models, frontend.
"""
