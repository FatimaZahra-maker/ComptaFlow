"""
backend/app/schemas/auth.py

Schema de la reponse renvoyee apres un login reussi.
"""
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"