from database import get_engine
import pandas as pd
import numpy as np
import joblib

def simulate_monte_carlo(n_simulations=5000):
    """
    Simulation Monte Carlo : au lieu de prédire UN seul résultat,
    on simule la course des milliers de fois avec de l'aléatoire
    pour obtenir des PROBABILITÉS.
    
    À chaque simulation, on ajoute du bruit pour modéliser :
    - Les accidents / problèmes mécaniques (DNF aléatoire)
    - Les safety cars (mélangent le milieu de peloton)
    - La variance naturelle de performance (un pilote peut avoir un bon ou mauvais jour)
    """
    print("=" * 60)
    print(f"🎲 SIMULATION MONTE CARLO ({n_simulations} simulations)")
    print("=" * 60)
    
    # Charger le modèle et les données
    model = joblib.load('models/f1_model.pkl')
    engine = get_engine()
    
    # Récupérer les données 2026
    real_results = pd.read_sql_query("SELECT * FROM Results_Clean WHERE Year = 2026", engine)
    last_race = int(real_results['RaceNumber'].max())
    
    # Liste des pilotes du dernier GP
    drivers = pd.read_sql_query(f"""
        SELECT DISTINCT Abbreviation, TeamName 
        FROM Results_Clean 
        WHERE Year = 2026 AND RaceNumber = {last_race}
    """, engine)
    
    # Calcul de la forme actuelle
    driver_form = {}
    for driver in drivers['Abbreviation'].unique():
        d = real_results[real_results['Abbreviation'] == driver].sort_values('RaceNumber')
        positions = d['Position'].values
        # Moyenne pondérée exponentielle (cohérent avec build_features.py)
        weights = np.array([0.5 ** (len(positions) - 1 - i) for i in range(len(positions))])
        weights = weights / weights.sum()
        
        driver_form[driver] = {
            'TeamName': d['TeamName'].iloc[-1],
            'avg_pos': np.average(positions, weights=weights) if len(positions) > 0 else 11,
            'avg_pts': d['Points'].tail(5).mean() if len(d) > 0 else 5,
            'dnf_rate': d['DNF'].mean() if 'DNF' in d.columns and len(d) > 0 else 0.1,
            'std_pos': d['Position'].std() if len(d) > 1 else 3.0  # Écart-type = mesure de la régularité
        }
    
    # Forme des écuries
    team_form = {}
    for team in drivers['TeamName'].unique():
        t = real_results[real_results['TeamName'] == team]
        team_positions = t.groupby('RaceNumber')['Position'].mean().values
        team_form[team] = np.mean(team_positions[-5:]) if len(team_positions) > 0 else 11
    
    # Pas besoin de fermer explicitement la connexion ici
    
    # --- Saisie de la grille ---
    print("\n📋 GRILLE DE DÉPART")
    mode = input("Mode (manual / auto) : ").strip().lower()
    
    grid = {}
    if mode == 'manual':
        print("\nEntre la position de qualification de chaque pilote :")
        for _, row in drivers.iterrows():
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
        sorted_drivers = sorted(driver_form.items(), key=lambda x: x[1]['avg_pos'])
        for i, (driver, stats) in enumerate(sorted_drivers, 1):
            grid[driver] = i
        print("Grille estimée automatiquement depuis la forme récente.")
    
    # --- Météo ---
    print("\n🌤️ CONDITIONS MÉTÉO")
    try:
        air_temp = float(input("  Température air (°C) [défaut: 25] : ") or 25)
        track_temp = float(input("  Température piste (°C) [défaut: 40] : ") or 40)
        humidity = float(input("  Humidité (%) [défaut: 50] : ") or 50)
        wind_speed = float(input("  Vitesse du vent (km/h) [défaut: 10] : ") or 10)
        rainfall_input = input("  Pluie ? (oui/non) [défaut: non] : ").strip().lower()
        rainfall = 1 if rainfall_input in ['oui', 'o', 'yes', 'y'] else 0
    except ValueError:
        air_temp, track_temp, humidity, wind_speed, rainfall = 25, 40, 50, 10, 0
    
    # --- Construction du tableau de base ---
    base_rows = []
    for driver, stats in driver_form.items():
        team = stats['TeamName']
        grid_pos = grid.get(driver, 11)
        base_rows.append({
            'Abbreviation': driver,
            'TeamName': team,
            'GridPosition': grid_pos,
            'Driver_AvgPos_Last5': stats['avg_pos'],
            'Driver_AvgPts_Last5': stats['avg_pts'],
            'Driver_DNF_Rate': stats['dnf_rate'],
            'Driver_Circuit_Experience': 0,
            'Driver_AvgPos_On_Circuit': stats['avg_pos'],
            'Driver_Best_On_Circuit': stats['avg_pos'],
            'Grid_vs_Form': grid_pos - stats['avg_pos'],
            'Team_AvgPos_Last5': team_form.get(team, 11),
            'AirTemp': air_temp, 'TrackTemp': track_temp,
            'Humidity': humidity, 'WindSpeed': wind_speed, 'Rainfall': rainfall,
            'std_pos': stats['std_pos'],
            'dnf_rate': stats['dnf_rate']
        })
    
    df_base = pd.DataFrame(base_rows)
    
    feature_cols = [
        'GridPosition', 'Driver_AvgPos_Last5', 'Driver_AvgPts_Last5',
        'Driver_DNF_Rate', 'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit', 'Driver_Best_On_Circuit',
        'Grid_vs_Form',
        'Team_AvgPos_Last5', 'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall'
    ]
    
    # Prédiction de base du modèle XGBoost
    base_predictions = model.predict(df_base[feature_cols])
    
    # =========================================================================
    # MONTE CARLO : On simule N fois la course avec de l'aléatoire
    # =========================================================================
    print(f"\n🎲 Lancement de {n_simulations} simulations...\n")
    
    n_drivers = len(df_base)
    
    # Compteurs de résultats
    win_count = {d: 0 for d in df_base['Abbreviation']}
    podium_count = {d: 0 for d in df_base['Abbreviation']}
    points_count = {d: 0 for d in df_base['Abbreviation']}
    dnf_count = {d: 0 for d in df_base['Abbreviation']}
    position_sum = {d: 0 for d in df_base['Abbreviation']}
    top5_count = {d: 0 for d in df_base['Abbreviation']}
    
    for sim in range(n_simulations):
        # 1. Partir de la prédiction XGBoost
        noisy_predictions = base_predictions.copy()
        
        # 2. Ajouter du bruit gaussien (variance de performance)
        # L'écart-type est propre à chaque pilote (un pilote régulier a un faible std)
        for i, row in df_base.iterrows():
            noise = np.random.normal(0, row['std_pos'] * 0.8)
            noisy_predictions[i] += noise
        
        # 3. Simuler les DNF aléatoires (basé sur le taux historique de chaque pilote)
        dnf_mask = np.random.random(n_drivers) < df_base['dnf_rate'].values
        noisy_predictions[dnf_mask] = 25  # DNF → dernière position
        
        # 4. Safety Car aléatoire (20% de chance) → compresse le peloton
        if np.random.random() < 0.20:
            # Le safety car réduit les écarts entre les pilotes du milieu (positions 5 à 15)
            mid_pack = (noisy_predictions > 4) & (noisy_predictions < 16)
            noisy_predictions[mid_pack] += np.random.normal(0, 1.5, mid_pack.sum())
        
        # 5. Convertir en classement (positions 1, 2, 3...)
        sorted_indices = np.argsort(noisy_predictions)
        positions = np.empty(n_drivers, dtype=int)
        positions[sorted_indices] = np.arange(1, n_drivers + 1)
        
        # 6. Comptabiliser les résultats de cette simulation
        for i, row in df_base.iterrows():
            driver = row['Abbreviation']
            pos = positions[i]
            
            if dnf_mask[i]:
                dnf_count[driver] += 1
            
            position_sum[driver] += pos
            if pos == 1:
                win_count[driver] += 1
            if pos <= 3:
                podium_count[driver] += 1
            if pos <= 5:
                top5_count[driver] += 1
            if pos <= 10:
                points_count[driver] += 1
    
    # =========================================================================
    # RÉSULTATS AGRÉGÉS
    # =========================================================================
    print("=" * 70)
    print("🏆 PROBABILITÉS DE RÉSULTATS")
    print("=" * 70)
    
    results = []
    for driver in df_base['Abbreviation']:
        results.append({
            'Pilote': driver,
            'Écurie': driver_form[driver]['TeamName'],
            'Départ': f"P{grid.get(driver, '?')}",
            'Victoire': f"{win_count[driver] / n_simulations * 100:.1f}%",
            'Podium': f"{podium_count[driver] / n_simulations * 100:.1f}%",
            'Top 5': f"{top5_count[driver] / n_simulations * 100:.1f}%",
            'Points': f"{points_count[driver] / n_simulations * 100:.1f}%",
            'DNF': f"{dnf_count[driver] / n_simulations * 100:.1f}%",
            'Pos Moy': round(position_sum[driver] / n_simulations, 1),
            '_win_pct': win_count[driver] / n_simulations
        })
    
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('_win_pct', ascending=False).reset_index(drop=True)
    
    # Affichage propre
    display_cols = ['Pilote', 'Écurie', 'Départ', 'Victoire', 'Podium', 'Top 5', 'Points', 'DNF', 'Pos Moy']
    print(df_results[display_cols].to_string(index=False))
    
    # Top 3 des favoris
    print("\n" + "=" * 70)
    print("🔮 VERDICT MONTE CARLO")
    print("=" * 70)
    top3 = df_results.head(3)
    print(f"\n  🥇 FAVORI : {top3.iloc[0]['Pilote']} ({top3.iloc[0]['Écurie']}) — {top3.iloc[0]['Victoire']} de chances de victoire")
    print(f"  🥈 OUTSIDER : {top3.iloc[1]['Pilote']} ({top3.iloc[1]['Écurie']}) — {top3.iloc[1]['Victoire']} de chances de victoire")
    print(f"  🥉 DARK HORSE : {top3.iloc[2]['Pilote']} ({top3.iloc[2]['Écurie']}) — {top3.iloc[2]['Victoire']} de chances de victoire")
    
    return df_results

if __name__ == "__main__":
    simulate_monte_carlo(n_simulations=5000)
