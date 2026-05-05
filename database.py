import os
from sqlalchemy import create_engine

# URL de connexion à Supabase (ou autre Postgres) fournie via les variables d'environnement
DATABASE_URL = os.environ.get("DATABASE_URL")

# SQLAlchemy 1.4+ déprécie 'postgres://' et demande 'postgresql://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_engine():
    """
    Retourne un moteur SQLAlchemy.
    Si DATABASE_URL est défini (ex: sur Render avec Supabase), on s'y connecte.
    Sinon, on retombe sur la base SQLite locale pour le développement.
    """
    if DATABASE_URL:
        # pool_pre_ping vérifie la connexion avant de l'utiliser (utile pour les bases distantes)
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    else:
        # Chemin vers la base SQLite locale
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'f1pred.db')
        # On s'assure que le dossier data existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return create_engine(f"sqlite:///{db_path}")
