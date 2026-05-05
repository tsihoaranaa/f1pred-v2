from database import get_engine
import pandas as pd
import numpy as np
import joblib
import os

def get_driver_current_form(engine):
    """
    Calcule la forme actuelle de chaque pilote à partir des données 2026 existantes.
    Si pas assez de données 2026, utilise les dernières données disponibles.
    """
    df = pd.read_sql_query("""
        SELECT r.*, ra.AirTemp, ra.TrackTemp, ra.Humidity, ra.WindSpeed, ra.Rainfall, ra.EventName
        FROM Results_Clean r
        LEFT JOIN Races_Clean ra ON r.Year = ra.Year AND r.RaceNumber = ra.RaceNumber
        WHERE r.Year = 2026
        ORDER BY r.RaceNumber
    """, engine)
    
    if df.empty:
        print("⚠️ Aucune donnée 2026 trouvée. Le modèle se basera uniquement sur la grille de départ.")
        return {}
    
    # Calcul de la forme récente par pilote (sur toutes les courses 2026 disponibles)
    form = {}
    for driver in df['Abbreviation'].unique():
        driver_data = df[df['Abbreviation'] == driver].sort_values('RaceNumber')
        last5_pos = driver_data['Position'].tail(5).mean()
        last5_pts = driver_data['Points'].tail(5).mean()
        dnf_rate = driver_data['DNF'].mean() if 'DNF' in driver_data.columns else 0
        team = driver_data['TeamName'].iloc[-1]
        experience = len(driver_data)
        
        form[driver] = {
            'Driver_AvgPos_Last5': round(last5_pos, 2),
            'Driver_AvgPts_Last5': round(last5_pts, 2),
            'Driver_DNF_Rate': round(dnf_rate, 3),
            'Driver_Circuit_Experience': experience,
            'TeamName': team
        }
    
    return form

def get_team_form(engine):
    """Calcule la forme récente de chaque écurie en 2026."""
    df = pd.read_sql_query("""
        SELECT TeamName, RaceNumber, AVG(Position) as AvgPos
        FROM Results_Clean
        WHERE Year = 2026
        GROUP BY TeamName, RaceNumber
        ORDER BY RaceNumber
    """, engine)
    
    team_form = {}
    for team in df['TeamName'].unique():
        team_data = df[df['TeamName'] == team]
        team_form[team] = round(team_data['AvgPos'].tail(5).mean(), 2)
    
    return team_form

def simulate_next_race():
    """
    Étape 4 : Simuler la prochaine course en utilisant le modèle entraîné.
    """
    print("=" * 60)
    print("🏁 SIMULATION DE LA PROCHAINE COURSE")
    print("=" * 60)
    
    # Charger le modèle
    model = joblib.load('models/f1_model.pkl')
    engine = get_engine()
    
    # Récupérer la forme actuelle des pilotes
    driver_form = get_driver_current_form(engine)
    team_form = get_team_form(engine)
    
    # Récupérer la liste des pilotes du dernier GP
    last_race = pd.read_sql_query("""
        SELECT DISTINCT Abbreviation, TeamName 
        FROM Results_Clean 
        WHERE Year = 2026 AND RaceNumber = (SELECT MAX(RaceNumber) FROM Results_Clean WHERE Year = 2026)
    """, engine)
    
    # Pas besoin de fermer explicitement la connexion ici
    
    if last_race.empty:
        print("Erreur : Aucune donnée 2026 trouvée. Lance d'abord build_dataset_complete.py")
        return
    
    print(f"\nPilotes sur la grille : {len(last_race)}")
    
    # --- SAISIE DES QUALIFICATIONS ---
    print("\n📋 GRILLE DE DÉPART")
    print("Tu peux entrer les positions de qualification manuellement,")
    print("ou taper 'auto' pour estimer la grille à partir de la forme récente.\n")
    
    mode = input("Mode (manual / auto) : ").strip().lower()
    
    grid = {}
    if mode == 'manual':
        print("\nEntre la position de qualification de chaque pilote :")
        for _, row in last_race.iterrows():
            driver = row['Abbreviation']
            team = row['TeamName']
            while True:
                try:
                    pos = int(input(f"  {driver} ({team}) → P"))
                    grid[driver] = pos
                    break
                except ValueError:
                    print("    Entre un nombre valide.")
    else:
        # Mode auto : on estime la grille à partir de la forme récente
        print("\n🤖 Estimation automatique de la grille à partir de la forme récente...")
        sorted_drivers = sorted(driver_form.items(), key=lambda x: x[1]['Driver_AvgPos_Last5'])
        for i, (driver, stats) in enumerate(sorted_drivers, 1):
            grid[driver] = i
            print(f"  P{i}: {driver} ({stats['TeamName']}) - Forme: {stats['Driver_AvgPos_Last5']}")
    
    # --- MÉTÉO ---
    print("\n🌤️ CONDITIONS MÉTÉO")
    print("Entre les prévisions météo (ou appuie sur Entrée pour les valeurs par défaut) :\n")
    
    try:
        air_temp = float(input("  Température air (°C) [défaut: 25] : ") or 25)
        track_temp = float(input("  Température piste (°C) [défaut: 40] : ") or 40)
        humidity = float(input("  Humidité (%) [défaut: 50] : ") or 50)
        wind_speed = float(input("  Vitesse du vent (km/h) [défaut: 10] : ") or 10)
        rainfall_input = input("  Pluie ? (oui/non) [défaut: non] : ").strip().lower()
        rainfall = 1 if rainfall_input in ['oui', 'o', 'yes', 'y'] else 0
    except ValueError:
        air_temp, track_temp, humidity, wind_speed, rainfall = 25, 40, 50, 10, 0
    
    # --- CONSTRUCTION DU TABLEAU DE PRÉDICTION ---
    prediction_rows = []
    
    for _, row in last_race.iterrows():
        driver = row['Abbreviation']
        team = row['TeamName']
        
        # Récupérer la forme du pilote (ou valeurs par défaut)
        form = driver_form.get(driver, {})
        avg_pos = form.get('Driver_AvgPos_Last5', 10.0)
        avg_pts = form.get('Driver_AvgPts_Last5', 5.0)
        dnf_rate = form.get('Driver_DNF_Rate', 0.1)
        circuit_exp = form.get('Driver_Circuit_Experience', 0)
        avg_pos_circuit = form.get('Driver_AvgPos_On_Circuit', avg_pos)
        best_on_circuit = form.get('Driver_Best_On_Circuit', avg_pos)
        team_avg = team_form.get(team, 10.0)
        grid_pos = grid.get(driver, 11)
        
        prediction_rows.append({
            'Abbreviation': driver,
            'TeamName': team,
            'GridPosition': grid_pos,
            'Driver_AvgPos_Last5': avg_pos,
            'Driver_AvgPts_Last5': avg_pts,
            'Driver_DNF_Rate': dnf_rate,
            'Driver_Circuit_Experience': circuit_exp,
            'Driver_AvgPos_On_Circuit': avg_pos_circuit,
            'Driver_Best_On_Circuit': best_on_circuit,
            'Grid_vs_Form': grid_pos - avg_pos,
            'Team_AvgPos_Last5': team_avg,
            'AirTemp': air_temp,
            'TrackTemp': track_temp,
            'Humidity': humidity,
            'WindSpeed': wind_speed,
            'Rainfall': rainfall
        })
    
    df_pred = pd.DataFrame(prediction_rows)
    
    # --- PRÉDICTION ---
    feature_cols = [
        'GridPosition', 'Driver_AvgPos_Last5', 'Driver_AvgPts_Last5',
        'Driver_DNF_Rate', 'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit', 'Driver_Best_On_Circuit',
        'Grid_vs_Form',
        'Team_AvgPos_Last5', 'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall'
    ]
    
    predictions = model.predict(df_pred[feature_cols])
    df_pred['Predicted_Position'] = predictions
    
    # On trie par position prédite et on attribue les vraies positions (1, 2, 3...)
    df_pred = df_pred.sort_values('Predicted_Position').reset_index(drop=True)
    df_pred['Final_Position'] = range(1, len(df_pred) + 1)
    
    # Attribution des points F1
    points_system = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
    df_pred['Points'] = df_pred['Final_Position'].map(points_system).fillna(0).astype(int)
    
    # --- AFFICHAGE DES RÉSULTATS ---
    print("\n" + "=" * 60)
    print("🏆 RÉSULTAT PRÉDIT DE LA COURSE")
    print("=" * 60)
    
    for _, row in df_pred.iterrows():
        pos = int(row['Final_Position'])
        driver = row['Abbreviation']
        team = row['TeamName']
        pts = int(row['Points'])
        grid = int(row['GridPosition'])
        
        # Petite flèche pour montrer les gains/pertes
        diff = grid - pos
        if diff > 0:
            arrow = f"↑{diff}"
        elif diff < 0:
            arrow = f"↓{abs(diff)}"
        else:
            arrow = "="
            
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else "  "
        pts_str = f"+{pts}pts" if pts > 0 else ""
        
        print(f"  {medal} P{pos:2d} | {driver:4s} | {team:20s} | Départ P{grid:2d} ({arrow:4s}) {pts_str}")
    
    return df_pred

if __name__ == "__main__":
    simulate_next_race()
