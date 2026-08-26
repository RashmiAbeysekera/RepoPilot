# The 'schemas' package contains Pydantic models for request/response validation.
# Schemas define the shape of data coming IN (requests) and going OUT (responses).
# They are separate from SQLAlchemy models on purpose:
#   - SQLAlchemy models represent database rows
#   - Pydantic schemas represent API contract shapes
# This separation lets us control exactly what data is exposed via the API.
