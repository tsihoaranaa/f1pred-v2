import fastf1
from database import get_engine
import pandas as pd
import os
from datetime import datetime

def fetch_season_data(year):
    """
    Récupère toutes les courses terminées d'une saison donnée
    et renvoie deux DataFrames : un pour les Courses (Races) et un pour les Résultats.
    """
    print(f"\n--- Récupération de la saison {year} ---")
    
    # get_event_schedule récupère le calendrier complet de la saison
    schedule = fastf1.get_event_schedule(year)
    
    races_data = []
    results_data = []
    
    now = pd.Timestamp.now()
    
    # On itère sur chaque événement du calendrier
    for index, event in schedule.iterrows():
        # L'événement 0 est souvent les tests de pré-saison, on l'ignore
        if event['RoundNumber'] == 0:
            continue
            
        # Si la date de l'événement est dans le futur, la course n'a pas encore eu lieu
        # (Très utile pour arrêter proprement la boucle en plein milieu de 2026)
        if event['EventDate'] > now:
            print(f"Course {event['RoundNumber']} ({event['EventName']}) pas encore passée. Fin de la saison.")
            break
            
        race_number = event['RoundNumber']
        print(f"Chargement Course {race_number} : {event['EventName']}...")
        
        try:
            # On charge la session de course (R)
            session = fastf1.get_session(year, race_number, 'R')
            # On ignore la télémétrie pour gagner du temps, mais on télécharge la météo
            session.load(telemetry=False, weather=True, messages=False)
            
            # --- 1. Extraction pour la table RACES (La Météo et les infos de la course) ---
            weather = session.weather_data
            if weather is not None and not weather.empty:
                air_temp = round(weather['AirTemp'].mean(), 2)
                track_temp = round(weather['TrackTemp'].mean(), 2)
                humidity = round(weather['Humidity'].mean(), 2)
                wind_speed = round(weather['WindSpeed'].mean(), 2)
                rainfall = bool(weather['Rainfall'].any())
            else:
                air_temp = track_temp = humidity = wind_speed = None
                rainfall = False
                
            races_data.append({
                'Year': year,
                'RaceNumber': race_number,
                'EventName': event['EventName'],
                'Country': event['Country'],
                'EventDate': event['EventDate'].strftime('%Y-%m-%d'),
                'AirTemp': air_temp,
                'TrackTemp': track_temp,
                'Humidity': humidity,
                'WindSpeed': wind_speed,
                'Rainfall': rainfall
            })
            
            # --- 2. Extraction pour la table RESULTS (Les performances des pilotes) ---
            # session.results s'adapte automatiquement au nombre de pilotes ! 
            results = session.results
            df_res = results[['DriverNumber', 'BroadcastName', 'Abbreviation', 'TeamName', 'Position', 'GridPosition', 'Points', 'Status']].copy()
            df_res['Year'] = year
            df_res['RaceNumber'] = race_number
            results_data.append(df_res)
            
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement de la course {race_number} : {e}")
            
    # On transforme nos listes en tableaux Pandas
    df_races_final = pd.DataFrame(races_data)
    df_results_final = pd.concat(results_data, ignore_index=True) if results_data else pd.DataFrame()
    
    return df_races_final, df_results_final

def save_to_db(df_races, df_results):
    """
    Sauvegarde les deux tableaux dans deux tables distinctes de la base de données.
    """
    engine = get_engine()
    
    with engine.begin() as conn:
        # On écrit le tableau races dans la table 'Races'
        df_races.to_sql('Races', conn, if_exists='append', index=False)
        
        # On écrit le tableau results dans la table 'Results'
        df_results.to_sql('Results', conn, if_exists='append', index=False)
    
    print("\n✅ Sauvegarde réussie des Courses et des Résultats dans la base de données !")

if __name__ == "__main__":
    # Activation du cache pour accélérer drastiquement les futurs lancements
    os.makedirs('data/cache', exist_ok=True)
    fastf1.Cache.enable_cache('data/cache')
    
    # On cible nos saisons
    years_to_fetch = [2024, 2025, 2026]
    
    all_races = []
    all_results = []
    
    # On boucle sur chaque saison
    for y in years_to_fetch:
        df_r, df_res = fetch_season_data(y)
        if not df_r.empty:
            all_races.append(df_r)
        if not df_res.empty:
            all_results.append(df_res)
            
    # Si on a bien récupéré des données, on les fusionne et on les sauvegarde
    if all_races and all_results:
        final_races = pd.concat(all_races, ignore_index=True)
        final_results = pd.concat(all_results, ignore_index=True)
        
        save_to_db(final_races, final_results)
    else:
        print("Aucune donnée n'a été récupérée.")
