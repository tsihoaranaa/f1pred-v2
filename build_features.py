from database import get_engine
import pandas as pd
import numpy as np

def build_features():
    """
    Étape 3a : Créer les features (caractéristiques) qui vont nourrir notre modèle de ML.
    On transforme les données brutes en informations exploitables par un algorithme.
    """
    print("=" * 60)
    print("🧠 CONSTRUCTION DES FEATURES")
    print("=" * 60)
    
    engine = get_engine()
    
    # On charge les tables nettoyées
    df_results = pd.read_sql_query("SELECT * FROM Results_Clean", engine)
    df_races = pd.read_sql_query("SELECT * FROM Races_Clean", engine)
    
    # --- JOINTURE : On fusionne les résultats avec les infos de la course (météo, circuit) ---
    # C'est ici qu'on réunit nos deux tables propres en un seul grand tableau
    df = df_results.merge(df_races, on=['Year', 'RaceNumber'], how='left')
    
    print(f"Données chargées : {len(df)} lignes")
    
    # On trie par ordre chronologique (essentiel pour les calculs de forme récente)
    df = df.sort_values(by=['Year', 'RaceNumber']).reset_index(drop=True)
    
    # =========================================================================
    # GESTION DU CHANGEMENT DE RÉGLEMENTATION
    # =========================================================================
    # En 2026, nouvelles voitures et nouveaux moteurs → la hiérarchie est complètement bouleversée.
    # On ne veut PAS que la forme de fin 2025 contamine les prédictions de début 2026.
    # Solution : on crée une "ère réglementaire" et on regroupe par ère.
    # Ainsi, les moyennes glissantes redémarrent à zéro au début de chaque nouvelle ère.
    
    REGULATION_ERAS = {
        2024: 'era_2022_2025',  # Réglementation 2022 (effet de sol)
        2025: 'era_2022_2025',
        2026: 'era_2026',       # Nouvelle réglementation 2026
    }
    df['RegEra'] = df['Year'].map(REGULATION_ERAS)
    print(f"\nÈres réglementaires : {df['RegEra'].value_counts().to_dict()}")
    
    # =========================================================================
    # FEATURE 1 : Forme récente du pilote (moyenne PONDÉRÉE des positions)
    # =========================================================================
    # On utilise une moyenne exponentielle (EWM) au lieu d'une moyenne simple.
    # EWM donne PLUS de poids aux courses récentes et MOINS aux anciennes.
    # Exemple avec span=5 :
    #   Course la plus récente → poids ~33%
    #   Course d'il y a 5 courses → poids ~7%
    # Ainsi, un pilote en chute libre sera pénalisé, et un pilote en montée sera récompensé.
    print("\n1. Calcul de la forme récente des pilotes (moyenne pondérée)...")
    
    df['Driver_AvgPos_Last5'] = (
        df.groupby(['RegEra', 'Abbreviation'])['Position']
        .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
    )
    # shift(1) est CRUCIAL : on décale d'une ligne pour ne pas inclure la course actuelle
    # Cela évite le "Data Leakage" (tricher en utilisant le résultat qu'on essaie de prédire)
    
    # =========================================================================
    # FEATURE 2 : Points récents du pilote (moyenne PONDÉRÉE)
    # =========================================================================
    print("2. Calcul des points moyens récents des pilotes (pondérés)...")
    
    df['Driver_AvgPts_Last5'] = (
        df.groupby(['RegEra', 'Abbreviation'])['Points']
        .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
    )
    
    # =========================================================================
    # FEATURE 3 : Taux d'abandon récent du pilote (sur les 10 dernières courses)
    # =========================================================================
    print("3. Calcul du taux d'abandon récent des pilotes...")
    
    df['Driver_DNF_Rate'] = (
        df.groupby(['RegEra', 'Abbreviation'])['DNF']
        .transform(lambda x: x.shift(1).rolling(window=10, min_periods=1).mean())
    )
    
    # =========================================================================
    # FEATURE 4 : Forme récente du constructeur (moyenne des positions de ses 2 pilotes)
    # =========================================================================
    print("4. Calcul de la forme récente des constructeurs...")
    
    # D'abord, on calcule la position moyenne de l'écurie par course
    team_avg = df.groupby(['Year', 'RaceNumber', 'TeamName', 'RegEra'])['Position'].mean().reset_index()
    team_avg.columns = ['Year', 'RaceNumber', 'TeamName', 'RegEra', 'Team_AvgPos_Race']
    
    # Ensuite, on calcule la moyenne glissante sur 5 courses pour chaque écurie
    team_avg = team_avg.sort_values(by=['Year', 'RaceNumber'])
    team_avg['Team_AvgPos_Last5'] = (
        team_avg.groupby(['RegEra', 'TeamName'])['Team_AvgPos_Race']
        .transform(lambda x: x.shift(1).rolling(window=5, min_periods=1).mean())
    )
    
    # On fusionne cette info dans notre tableau principal
    df = df.merge(team_avg[['Year', 'RaceNumber', 'TeamName', 'Team_AvgPos_Last5']], 
                  on=['Year', 'RaceNumber', 'TeamName'], how='left')
    
    # =========================================================================
    # FEATURE 5 : Expérience du pilote sur ce circuit
    # =========================================================================
    print("5. Calcul de l'expérience par circuit...")
    
    # Nombre de fois que le pilote a déjà couru sur ce circuit (avant cette course)
    df['Driver_Circuit_Experience'] = (
        df.groupby(['Abbreviation', 'EventName']).cumcount()
    )
    
    # =========================================================================
    # FEATURE 5b : Position moyenne du pilote sur ce circuit (historique)
    # =========================================================================
    # Ex: Hamilton à Silverstone a une moyenne de 2.3 → il est un monstre là-bas
    print("5b. Calcul de la position moyenne par circuit...")
    
    df['Driver_AvgPos_On_Circuit'] = (
        df.groupby(['Abbreviation', 'EventName'])['Position']
        .transform(lambda x: x.shift(1).expanding().mean())
    )
    # expanding().mean() = moyenne de TOUTES les courses précédentes sur ce circuit
    # shift(1) pour ne pas inclure la course actuelle (anti Data Leakage)
    
    # =========================================================================
    # FEATURE 5c : Meilleur résultat du pilote sur ce circuit
    # =========================================================================
    # Ex: Verstappen à Spa a un best de 1 → il sait qu'il peut gagner ici
    print("5c. Calcul du meilleur résultat par circuit...")
    
    df['Driver_Best_On_Circuit'] = (
        df.groupby(['Abbreviation', 'EventName'])['Position']
        .transform(lambda x: x.shift(1).expanding().min())
    )
    # expanding().min() = le minimum (meilleur résultat) parmi toutes les courses passées
    
    # =========================================================================
    # FEATURE 6 : Différence entre GridPosition et la forme récente
    # =========================================================================
    # Si un pilote qualifie mieux que sa forme récente, c'est un signal fort
    print("6. Calcul du delta Grid vs Forme...")
    
    df['Grid_vs_Form'] = df['GridPosition'] - df['Driver_AvgPos_Last5']
    
    # =========================================================================
    # RÉSUMÉ : On sélectionne les features finales pour l'entraînement
    # =========================================================================
    feature_columns = [
        # Identifiants (pas des features, mais utiles pour analyser les résultats)
        'Year', 'RaceNumber', 'Abbreviation', 'TeamName', 'EventName',
        
        # La cible à prédire (target)
        'Position',
        
        # Features du pilote
        'GridPosition',
        'Driver_AvgPos_Last5',
        'Driver_AvgPts_Last5',
        'Driver_DNF_Rate',
        'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit',
        'Driver_Best_On_Circuit',
        'Grid_vs_Form',
        
        # Features de l'écurie
        'Team_AvgPos_Last5',
        
        # Features météo (venant de la table Races)
        'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall',
        
        # Feature utile
        'DNF'
    ]
    
    df_features = df[feature_columns].copy()
    
    # On supprime les premières courses de chaque pilote (pas assez d'historique pour les moyennes)
    before = len(df_features)
    df_features = df_features.dropna(subset=['Driver_AvgPos_Last5', 'Team_AvgPos_Last5'])
    after = len(df_features)
    print(f"\n7. Lignes supprimées (pas assez d'historique) : {before - after}")
    
    # --- Sauvegarde dans la base de données ---
    with engine.begin() as conn:
        df_features.to_sql('Features', conn, if_exists='replace', index=False)
    
    print(f"\n✅ Table 'Features' créée avec {len(df_features)} lignes et {len(feature_columns)} colonnes !")
    print(f"Features utilisées : {[c for c in feature_columns if c not in ['Year','RaceNumber','Abbreviation','TeamName','EventName','Position','DNF']]}")
    
    return df_features

if __name__ == "__main__":
    df = build_features()
    print("\nAperçu des 5 premières lignes :")
    print(df.head().to_string(index=False))
