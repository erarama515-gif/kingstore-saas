"""Cross-cutting infrastructure: DB base, security, errors, tenant context.

Nothing in ``core`` should know about a specific business module. Modules
depend on ``core``; ``core`` does not depend on modules.
"""
