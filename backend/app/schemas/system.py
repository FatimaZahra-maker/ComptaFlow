"""
app/schemas/system.py

Informations système en lecture seule, affichées dans Paramètres
(quel fournisseur IA est actif, quel modèle, etc.) -- utile pour que
le cabinet comprenne pourquoi le traitement se comporte d'une
certaine façon (rapide/cloud vs local/gratuit) sans avoir à demander
au développeur.
"""
from pydantic import BaseModel


class SystemInfoOut(BaseModel):
    ai_provider: str          # "cloud" ou "local"
    gemini_configure: bool     # clé Gemini présente ou non (jamais la clé elle-même)
    ollama_model: str
    ollama_url: str