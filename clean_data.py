from database import get_engine
import pandas as pd

def inspect_data():
    """
    Étape 2a : Inspecter les données brutes pour repérer les problèmes
    avant de les nettoyer.
    """
    engine = get_engine()
    
    df_results = pd.read_sql_query('SELECT * FROM "Results"', engine)
    df_races = pd.read_sql_query('SELECT * FROM "Races"', engine)
    
    print("=" * 60)
    print("🔍 INSPECTION DE LA TABLE 'RESULTS'")
    print("=" * 60)
    
    # 1. Dimensions du tableau
    print(f"\nNombre de lignes : {len(df_results)}")
    print(f"Nombre de colonnes : {len(df_results.columns)}")
    print(f"Colonnes : {list(df_results.columns)}")
    
    # 2. Types de données (un entier stocké comme texte peut poser problème au modèle)
    print(f"\n📋 Types de données :")
    print(df_results.dtypes)
    
    # 3. Valeurs manquantes (NaN / None)
    print(f"\n⚠️ Valeurs manquantes par colonne :")
    missing = df_results.isnull().sum()
    print(missing[missing > 0] if missing.any() else "Aucune valeur manquante !")
    
    # 4. Doublons (si le script a été lancé plusieurs fois)
    duplicates = df_results.duplicated().sum()
    print(f"\n🔄 Nombre de doublons : {duplicates}")
    
    # 5. Analyse de la colonne 'Status' (Finished, DNF, +1 Lap, etc.)
    print(f"\n🏁 Valeurs uniques de 'Status' :")
    print(df_results['Status'].value_counts())
    
    # 6. Analyse de la colonne 'Position' (peut contenir des NaN pour les abandons)
    print(f"\n📊 Statistiques de 'Position' :")
    print(df_results['Position'].describe())
    
    # 7. Analyse de la colonne 'GridPosition' (0 = départ depuis la pit lane)
    print(f"\n🏎️ GridPosition = 0 (départ pit lane) :")
    pitlane_starts = df_results[df_results['GridPosition'] == 0]
    print(f"{len(pitlane_starts)} cas trouvés")
    
    print("\n" + "=" * 60)
    print("🔍 INSPECTION DE LA TABLE 'RACES'")
    print("=" * 60)
    
    print(f"\nNombre de courses : {len(df_races)}")
    print(f"\n⚠️ Valeurs manquantes :")
    missing_races = df_races.isnull().sum()
    print(missing_races[missing_races > 0] if missing_races.any() else "Aucune valeur manquante !")
    
    return df_results, df_races

def clean_data():
    """
    Étape 2b : Nettoyer les données et les sauvegarder dans de nouvelles tables propres.
    """
    engine = get_engine()
    
    df_results = pd.read_sql_query('SELECT * FROM "Results"', engine)
    df_races = pd.read_sql_query('SELECT * FROM "Races"', engine)
    
    print("\n" + "=" * 60)
    print("🧹 NETTOYAGE EN COURS...")
    print("=" * 60)
    
    # --- 1. Suppression des doublons ---
    before = len(df_results)
    df_results = df_results.drop_duplicates()
    after = len(df_results)
    print(f"\n1. Doublons supprimés : {before - after}")
    
    # --- 2. Conversion des types ---
    # Position et GridPosition doivent être des nombres entiers
    # Certaines positions peuvent être NaN (abandon avant classement)
    df_results['Position'] = pd.to_numeric(df_results['Position'], errors='coerce')
    df_results['GridPosition'] = pd.to_numeric(df_results['GridPosition'], errors='coerce')
    df_results['Points'] = pd.to_numeric(df_results['Points'], errors='coerce')
    print("2. Conversion des types (Position, GridPosition, Points) → numérique ✅")
    
    # --- 3. Création d'une feature 'DNF' (Did Not Finish) ---
    # C'est LA feature clé pour le Machine Learning !
    # Un pilote qui a terminé la course a un Status qui contient 'Finished' ou '+X Lap'
    # Un pilote qui a abandonné a un Status comme 'Engine', 'Collision', 'Retired', etc.
    finished_keywords = ['Finished', 'Lap']
    df_results['DNF'] = ~df_results['Status'].str.contains('|'.join(finished_keywords), case=False, na=True)
    dnf_count = df_results['DNF'].sum()
    print(f"3. Feature 'DNF' créée : {dnf_count} abandons détectés sur {len(df_results)} résultats")
    
    # --- 4. Gestion des positions manquantes pour les DNF ---
    # Pour les pilotes qui ont abandonné, on leur attribue la dernière position (ex: 20 ou 22)
    # C'est une convention classique en Data Science F1
    max_pos = df_results.groupby(['Year', 'RaceNumber'])['Position'].transform('max')
    df_results['Position'] = df_results['Position'].fillna(max_pos)
    print("4. Positions manquantes (DNF) remplies avec la dernière position de la course ✅")
    
    # --- 5. Gestion des GridPosition = 0 (pit lane start) ---
    # On remplace 0 par la dernière position de la grille (ex: 20 ou 22)
    # car 0 n'a pas de sens numérique pour un modèle de ML
    mask_pitlane = df_results['GridPosition'] == 0
    df_results.loc[mask_pitlane, 'GridPosition'] = max_pos[mask_pitlane]
    print(f"5. GridPosition = 0 (pit lane) remplacés : {mask_pitlane.sum()} cas corrigés ✅")
    
    # --- 6. Suppression des doublons dans Races ---
    before_races = len(df_races)
    df_races = df_races.drop_duplicates()
    print(f"6. Doublons Races supprimés : {before_races - len(df_races)}")
    
    # --- 7. Sauvegarde des données nettoyées dans de nouvelles tables ---
    # On garde les anciennes tables intactes (au cas où) et on crée des tables "_clean"
    with engine.begin() as conn:
        df_results.to_sql('Results_Clean', conn, if_exists='replace', index=False)
        df_races.to_sql('Races_Clean', conn, if_exists='replace', index=False)
    
    print(f"\n✅ Nettoyage terminé !")
    print(f"Tables 'Results_Clean' et 'Races_Clean' créées dans f1pred.db")
    print(f"Les tables originales ('Results', 'Races') sont toujours intactes.")

if __name__ == "__main__":
    # D'abord on inspecte pour voir les problèmes
    inspect_data()
    
    # Ensuite on nettoie
    clean_data()
