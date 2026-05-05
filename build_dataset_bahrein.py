import fastf1
from database import get_engine
import pandas as pd
import os

def fetch_race_results(year, race_number):
    """Récupère les résultats d'une course avec FastF1"""
    print(f"Chargement des données pour la course {race_number} de la saison {year}...")
    
    # 'R' pour 'Race' (course principale)
    session = fastf1.get_session(year, race_number, 'R')
    
    # load() télécharge les données
    session.load(telemetry=False, weather=True, messages=False)
    
    results = session.results
    
    # Colonnes intéressantes pour un modèle de ML
    df = results[['DriverNumber', 'BroadcastName', 'Abbreviation', 'TeamName', 'Position', 'GridPosition', 'Points', 'Status']].copy()
    df['Year'] = year
    df['RaceNumber'] = race_number
    
    # Ajout de la météo
    weather = session.weather_data
    if weather is not None and not weather.empty:
        # Calcul de la moyenne pour les valeurs numériques
        df['AirTemp_Mean'] = round(weather['AirTemp'].mean(), 2)
        df['TrackTemp_Mean'] = round(weather['TrackTemp'].mean(), 2)
        df['Humidity_Mean'] = round(weather['Humidity'].mean(), 2)
        df['WindSpeed_Mean'] = round(weather['WindSpeed'].mean(), 2)
        df['WindDirection_Mean'] = round(weather['WindDirection'].mean(), 2)
        # S'il a plu au moins une fois pendant la session.
        df['Rainfall'] = weather['Rainfall'].any()
    else:
        # Valeurs par défaut au cas où la météo n'est pas dispo (ex: vieilles courses)
        df['AirTemp_Mean'] = None
        df['TrackTemp_Mean'] = None
        df['Humidity_Mean'] = None
        df['WindSpeed_Mean'] = None
        df['WindDirection_Mean'] = None
        df['Rainfall'] = False
    
    return df

def save_to_db(df):
    """Sauvegarde le DataFrame dans une base de données"""
    print(f"Sauvegarde dans la base de données...")
    
    engine = get_engine()
    with engine.begin() as conn:
        # Écrit le dataframe dans la table 'Results'
        df.to_sql('Results', conn, if_exists='append', index=False)
        
    print("Sauvegarde terminée !")

if __name__ == "__main__":
    # Cache les données fastf1 dans un dossier pour éviter de retélécharger à chaque fois
    os.makedirs('data/cache', exist_ok=True)
    fastf1.Cache.enable_cache('data/cache')
    
    # Test : Récupérer la première course de 2024 (Bahreïn)
    df_results = fetch_race_results(2024, 1)
    
    print("\nAperçu des résultats :")
    print(df_results.head())
    
    save_to_db(df_results)
