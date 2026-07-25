"""Business logic — what the app does, independent of HTTP.

Routes stay thin by delegating here; each service takes its collaborators
(pipeline, repositories) via the constructor so tests can swap them out.
"""
