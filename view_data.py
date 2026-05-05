from database import get_engine
import pandas as pd
from sqlalchemy import exc

def view_database():
    try:
        # On se connecte à la base de données
        engine = get_engine()
        
        print("🔍 APERÇU DE LA TABLE 'RACES' (Les 5 premières courses) :")
        print("-" * 50)
        df_races = pd.read_sql_query("SELECT * FROM Races LIMIT 5", engine)
        print(df_races.to_string(index=False))
        
        print("\n🏎️ APERÇU DE LA TABLE 'RESULTS' (Les 10 premiers résultats) :")
        print("-" * 50)
        df_results = pd.read_sql_query("SELECT * FROM Results LIMIT 10", engine)
        print(df_results.to_string(index=False))
        
        # Petit bonus : On compte combien de données on a téléchargé en tout !
        total_races = pd.read_sql_query("SELECT COUNT(*) as count FROM Races", engine).iloc[0]['count']
        total_results = pd.read_sql_query("SELECT COUNT(*) as count FROM Results", engine).iloc[0]['count']
        
        print(f"\n📊 STATISTIQUES GLOBALES :")
        print(f"Total des courses enregistrées : {total_races}")
        print(f"Total des lignes de résultats (pilotes) : {total_results}")
        
        # Pas besoin de fermer explicitement la connexion avec engine
        
    except exc.OperationalError:
        print("Erreur : La base de données est introuvable ou inaccessible. As-tu bien exécuté le script de téléchargement ?")

if __name__ == "__main__":
    view_database()
