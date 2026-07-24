"""
diag.py — a lancer depuis backend/ avec : python diag.py
Isole precisement ou ca casse, sans passer par exec() en une ligne
qui masque parfois les vraies erreurs.
"""
import traceback

print("=== Test 1 : import direct de app.models.user ===")
try:
    import importlib
    import app.models.user as user_module
    print("OK - fichier charge depuis :", user_module.__file__)
    print("Contenu du module :", [x for x in dir(user_module) if not x.startswith("_")])
except Exception:
    print("ECHEC - voici la vraie erreur :")
    traceback.print_exc()

print("\n=== Test 2 : compilation syntaxique pure (sans rien importer) ===")
try:
    with open("app/models/user.py", "rb") as f:
        source = f.read()
    compile(source, "app/models/user.py", "exec")
    print("OK - aucune erreur de syntaxe")
except Exception:
    print("ECHEC - erreur de syntaxe :")
    traceback.print_exc()

print("\n=== Test 3 : contenu brut en bytes (detecte caracteres invisibles) ===")
with open("app/models/user.py", "rb") as f:
    raw = f.read()
print("Taille fichier :", len(raw), "octets")
print("Premiers octets :", raw[:20])
print("BOM UTF-8 present ?", raw.startswith(b"\xef\xbb\xbf"))
# Cherche des espaces insecables (non-breaking space, tres commun apres
# un copier-coller depuis Word/PDF/un site web) qui RESSEMBLENT a des
# espaces normaux mais n'en sont pas pour Python.
nbsp_count = raw.count(b"\xc2\xa0")
print("Nombre d'espaces insecables (NBSP) trouves :", nbsp_count)