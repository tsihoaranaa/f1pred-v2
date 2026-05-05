from database import get_engine
import pandas as pd
import numpy as np
import joblib
import fastf1
import os

def simulate_full_season():
    """
    Étape 5 : Simuler toutes les courses restantes de la saison 2026
    et générer le classement final du Championnat du Monde.
    """
    print("=" * 60)
    print("🏆 SIMULATION COMPLÈTE DE LA SAISON 2026")
    print("=" * 60)
    
    # Charger le modèle entraîné
    model = joblib.load('models/f1_model.pkl')
    engine = get_engine()
    
    # --- Récupérer les courses déjà passées en 2026 ---
    real_results = pd.read_sql_query("SELECT * FROM Results_Clean WHERE Year = 2026", engine)
    real_races = pd.read_sql_query("SELECT * FROM Races_Clean WHERE Year = 2026", engine)
    last_race_done = int(real_results['RaceNumber'].max()) if not real_results.empty else 0
    
    print(f"\nCourses déjà passées en 2026 : {last_race_done}")
    
    # --- Récupérer le calendrier complet 2026 ---
    os.makedirs('data/cache', exist_ok=True)
    fastf1.Cache.enable_cache('data/cache')
    schedule = fastf1.get_event_schedule(2026)
    schedule = schedule[schedule['RoundNumber'] > 0]  # Ignorer les tests
    
    total_races = len(schedule)
    remaining_races = schedule[schedule['RoundNumber'] > last_race_done]
    print(f"Courses restantes à simuler : {len(remaining_races)} sur {total_races}")
    
    # --- Récupérer la liste des pilotes et leur forme actuelle ---
    drivers = pd.read_sql_query(f"""
        SELECT DISTINCT Abbreviation, TeamName 
        FROM Results_Clean 
        WHERE Year = 2026 AND RaceNumber = {last_race_done}
    """, engine)
    
    # Calculer la forme actuelle de chaque pilote à partir des vraies courses 2026
    driver_stats = {}
    for driver in drivers['Abbreviation'].unique():
        d = real_results[real_results['Abbreviation'] == driver].sort_values('RaceNumber')
        driver_stats[driver] = {
            'TeamName': d['TeamName'].iloc[-1],
            'positions': list(d['Position'].values),
            'points_history': list(d['Points'].values),
            'dnf_history': list(d['DNF'].values) if 'DNF' in d.columns else [False] * len(d),
            'total_points': float(d['Points'].sum()),
        }
    
    # Forme actuelle des écuries
    team_stats = {}
    for team in drivers['TeamName'].unique():
        t = real_results[real_results['TeamName'] == team].sort_values('RaceNumber')
        team_positions = t.groupby('RaceNumber')['Position'].mean().values
        team_stats[team] = {
            'positions': list(team_positions),
            'total_points': float(t['Points'].sum()),
        }
    
    # Points F1
    points_system = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
    
    # --- Historique des points pour le graphique d'évolution ---
    points_evolution = {}
    for driver, stats in driver_stats.items():
        points_evolution[driver] = [stats['total_points']]
    
    # --- BOUCLE DE SIMULATION ---
    print("\n" + "-" * 60)
    
    for _, event in remaining_races.iterrows():
        race_num = event['RoundNumber']
        race_name = event['EventName']
        
        print(f"\n🏁 Course {race_num}/{total_races} : {race_name}")
        
        # Estimer la grille de départ à partir de la forme récente
        grid_estimates = []
        for driver, stats in driver_stats.items():
            avg_pos = np.mean(stats['positions'][-5:]) if stats['positions'] else 11
            grid_estimates.append((driver, avg_pos))
        
        grid_estimates.sort(key=lambda x: x[1])
        grid = {driver: pos + 1 for pos, (driver, _) in enumerate(grid_estimates)}
        
        # Construire les features pour chaque pilote
        prediction_rows = []
        for driver, stats in driver_stats.items():
            team = stats['TeamName']
            avg_pos = np.mean(stats['positions'][-5:]) if stats['positions'] else 11.0
            avg_pts = np.mean(stats['points_history'][-5:]) if stats['points_history'] else 5.0
            dnf_rate = np.mean(stats['dnf_history'][-10:]) if stats['dnf_history'] else 0.1
            circuit_exp = 0  # Simplifié pour la simulation
            avg_pos_circuit = avg_pos  # Pas d'historique circuit pour les courses futures
            best_on_circuit = avg_pos
            team_avg = np.mean(team_stats[team]['positions'][-5:]) if team_stats[team]['positions'] else 11.0
            grid_pos = grid[driver]
            
            prediction_rows.append({
                'Abbreviation': driver,
                'TeamName': team,
                'GridPosition': grid_pos,
                'Driver_AvgPos_Last5': round(avg_pos, 2),
                'Driver_AvgPts_Last5': round(avg_pts, 2),
                'Driver_DNF_Rate': round(dnf_rate, 3),
                'Driver_Circuit_Experience': circuit_exp,
                'Driver_AvgPos_On_Circuit': round(avg_pos_circuit, 2),
                'Driver_Best_On_Circuit': round(best_on_circuit, 2),
                'Grid_vs_Form': grid_pos - avg_pos,
                'Team_AvgPos_Last5': round(team_avg, 2),
                'AirTemp': 25, 'TrackTemp': 40, 'Humidity': 50,
                'WindSpeed': 10, 'Rainfall': 0
            })
        
        df_pred = pd.DataFrame(prediction_rows)
        
        feature_cols = [
            'GridPosition', 'Driver_AvgPos_Last5', 'Driver_AvgPts_Last5',
            'Driver_DNF_Rate', 'Driver_Circuit_Experience',
            'Driver_AvgPos_On_Circuit', 'Driver_Best_On_Circuit',
            'Grid_vs_Form',
            'Team_AvgPos_Last5', 'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall'
        ]
        
        predictions = model.predict(df_pred[feature_cols])
        df_pred['Predicted_Position'] = predictions
        df_pred = df_pred.sort_values('Predicted_Position').reset_index(drop=True)
        df_pred['Final_Position'] = range(1, len(df_pred) + 1)
        df_pred['Points'] = df_pred['Final_Position'].map(points_system).fillna(0).astype(int)
        
        # Afficher le podium
        podium = df_pred.head(3)
        print(f"  🥇 {podium.iloc[0]['Abbreviation']} ({podium.iloc[0]['TeamName']})")
        print(f"  🥈 {podium.iloc[1]['Abbreviation']} ({podium.iloc[1]['TeamName']})")
        print(f"  🥉 {podium.iloc[2]['Abbreviation']} ({podium.iloc[2]['TeamName']})")
        
        # --- MISE À JOUR DYNAMIQUE (le plus important !) ---
        # Après chaque course simulée, on met à jour la forme de chaque pilote
        for _, row in df_pred.iterrows():
            driver = row['Abbreviation']
            team = row['TeamName']
            pos = row['Final_Position']
            pts = row['Points']
            
            driver_stats[driver]['positions'].append(pos)
            driver_stats[driver]['points_history'].append(pts)
            driver_stats[driver]['dnf_history'].append(False)
            driver_stats[driver]['total_points'] += pts
            
            # Mettre à jour les stats de l'écurie
            if team in team_stats:
                team_stats[team]['total_points'] += pts
        
        # Mettre à jour les positions moyennes des écuries
        for team in team_stats:
            team_drivers = [d for d, s in driver_stats.items() if s['TeamName'] == team]
            if team_drivers:
                avg = np.mean([df_pred[df_pred['Abbreviation'] == d]['Final_Position'].values[0] for d in team_drivers if d in df_pred['Abbreviation'].values])
                team_stats[team]['positions'].append(avg)
        
        # Sauvegarder l'évolution des points
        for driver in driver_stats:
            points_evolution[driver].append(driver_stats[driver]['total_points'])
    
    # on n'a plus besoin de fermer explicitement la connexion ici
    
    # =========================================================================
    # CLASSEMENT FINAL DU CHAMPIONNAT DU MONDE DES PILOTES
    # =========================================================================
    print("\n" + "=" * 60)
    print("🏆 CHAMPIONNAT DU MONDE DES PILOTES 2026")
    print("=" * 60)
    
    wdc = sorted(driver_stats.items(), key=lambda x: x[1]['total_points'], reverse=True)
    for pos, (driver, stats) in enumerate(wdc, 1):
        team = stats['TeamName']
        pts = int(stats['total_points'])
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else "  "
        print(f"  {medal} P{pos:2d} | {driver:4s} | {team:20s} | {pts:4d} pts")
    
    # =========================================================================
    # CLASSEMENT FINAL DU CHAMPIONNAT DU MONDE DES CONSTRUCTEURS
    # =========================================================================
    print("\n" + "=" * 60)
    print("🏆 CHAMPIONNAT DU MONDE DES CONSTRUCTEURS 2026")
    print("=" * 60)
    
    wcc = {}
    for driver, stats in driver_stats.items():
        team = stats['TeamName']
        wcc[team] = wcc.get(team, 0) + stats['total_points']
    
    wcc_sorted = sorted(wcc.items(), key=lambda x: x[1], reverse=True)
    for pos, (team, pts) in enumerate(wcc_sorted, 1):
        pts = int(pts)
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else "  "
        print(f"  {medal} P{pos:2d} | {team:20s} | {pts:4d} pts")
    
    # Sauvegarder l'évolution des points pour le futur dashboard
    df_evolution = pd.DataFrame(points_evolution)
    df_evolution.to_csv('data/points_evolution_2026.csv', index=False)
    print(f"\n📊 Évolution des points sauvegardée dans 'data/points_evolution_2026.csv'")
    
    return wdc, wcc_sorted

if __name__ == "__main__":
    simulate_full_season()
