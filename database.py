import os
from sqlalchemy import create_engine

# URL de connexion à Supabase (ou autre Postgres) fournie via les variables d'environnement
DATABASE_URL = os.environ.get("DATABASE_URL")

# SQLAlchemy 1.4+ déprécie 'postgres://' et demande 'postgresql://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Instance unique du moteur de base de données
_engine = None

def get_engine():
    """
    Retourne un moteur SQLAlchemy mis en cache.
    Si DATABASE_URL est défini (ex: sur Render avec Supabase), on s'y connecte.
    Sinon, on retombe sur la base SQLite locale pour le développement.
    """
    global _engine
    if _engine is None:
        if DATABASE_URL:
            # pool_pre_ping vérifie la connexion avant de l'utiliser (utile pour les bases distantes)
            _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        else:
            # Chemin vers la base SQLite locale
            db_path = os.path.join(os.path.dirname(__file__), 'data', 'f1pred.db')
            # On s'assure que le dossier data existe
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _engine = create_engine(f"sqlite:///{db_path}")
    return _engine
