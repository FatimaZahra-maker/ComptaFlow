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
    groq_configure: bool
    ollama_model: str
