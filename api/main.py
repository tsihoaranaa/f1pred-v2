import sys
import os

# Ajouter le dossier parent au path pour importer nos scripts existants
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
import pandas as pd
import numpy as np
import joblib
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import fastf1

# =========================================================================
# AUTO-UPDATE SCHEDULER
# =========================================================================
def auto_update_data():
    """Vérifie et télécharge automatiquement les nouveaux résultats F1."""
    print("[Auto-Update] Verification des nouveaux resultats...")
    try:
        from build_dataset_complete import fetch_season_data
        from clean_data import clean_data
        from build_features import build_features
        from train_model import train_model
        
        os.makedirs('data/cache', exist_ok=True)
        fastf1.Cache.enable_cache('data/cache')
        
        # Récupérer les données 2026 les plus récentes
        df_races, df_results = fetch_season_data(2026)
        
        if not df_races.empty:
            from database import get_engine
            engine = get_engine()
            with engine.begin() as conn:
                # Supprimer les anciennes données 2026 et les remplacer
                conn.execute(text("DELETE FROM Races WHERE Year = 2026"))
                conn.execute(text("DELETE FROM Results WHERE Year = 2026"))
                df_races.to_sql('Races', conn, if_exists='append', index=False)
                df_results.to_sql('Results', conn, if_exists='append', index=False)
            
            # Re-nettoyer et re-entraîner
            clean_data()
            build_features()
            train_model()
            
            print("[Auto-Update] Donnees mises a jour avec succes !")
        else:
            print("[Auto-Update] Aucune nouvelle course detectee.")
    except Exception as e:
        print(f"[Auto-Update] Erreur : {e}")

# =========================================================================
# FASTAPI APP
# =========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Au démarrage : lancer le scheduler
    scheduler = BackgroundScheduler()
    # Vérifier chaque lundi à 10h
    scheduler.add_job(auto_update_data, 'cron', day_of_week='mon', hour=10)
    scheduler.start()
    print("[Scheduler] Demarre : mise a jour automatique chaque lundi a 10h")
    yield
    scheduler.shutdown()

app = FastAPI(title="F1 Prediction API", lifespan=lifespan)

# CORS : permettre au frontend d'appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les fichiers statiques du frontend
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

from database import get_engine

_model_cache = None

def get_model():
    """Charger le modèle entraîné (avec cache pour éviter de le recharger à chaque requête)."""
    global _model_cache
    if _model_cache is None:
        model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'f1_model.pkl')
        _model_cache = joblib.load(model_path)
    return _model_cache

# Couleurs des écuries
TEAM_COLORS = {
    'Red Bull Racing': '#3671C6',
    'Ferrari': '#E80020',
    'McLaren': '#FF8000',
    'Mercedes': '#27F4D2',
    'Aston Martin': '#229971',
    'Alpine': '#FF87BC',
    'Williams': '#64C4FF',
    'Racing Bulls': '#6692FF',
    'RB': '#6692FF',
    'Haas F1 Team': '#B6BABD',
    'Kick Sauber': '#52E252',
    'Audi': '#52E252',
    'Cadillac': '#FFD700',
    'Alfa Romeo': '#900000',
    'AlphaTauri': '#2B4562'
}

# =========================================================================
# PAGES HTML
# =========================================================================
@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(frontend_path, 'index.html'))

@app.get("/prediction")
async def serve_prediction():
    return FileResponse(os.path.join(frontend_path, 'prediction.html'))

@app.get("/perso")
async def serve_perso():
    return FileResponse(os.path.join(frontend_path, 'perso.html'))

# =========================================================================
# API ENDPOINTS — DASHBOARD
# =========================================================================
@app.get("/api/results")
async def get_results(year: int = 2026):
    """Retourne tous les résultats d'une saison."""
    engine = get_engine()
    try:
        df = pd.read_sql_query(f"""
            SELECT r.*, ra.EventName, ra.Country, ra.EventDate
            FROM "Results_Clean" r
            LEFT JOIN "Races_Clean" ra ON r.Year = ra.Year AND r.RaceNumber = ra.RaceNumber
            WHERE r.Year = {year}
            ORDER BY r.RaceNumber, r.Position
        """, engine)
        
        # Ajouter les couleurs des écuries
        df['TeamColor'] = df['TeamName'].map(TEAM_COLORS).fillna('#FFFFFF')
        
        return df.to_dict(orient='records')
    except Exception as e:
        print(f"Error in get_results: {e}")
        return []

@app.get("/api/standings")
async def get_standings(year: int = 2026):
    """Retourne le classement pilotes et constructeurs."""
    engine = get_engine()
    
    try:
        # Classement pilotes
        drivers = pd.read_sql_query(f"""
            SELECT Abbreviation, TeamName, SUM(Points) as TotalPoints, COUNT(DISTINCT RaceNumber) as Races
            FROM "Results_Clean" WHERE Year = {year}
            GROUP BY Abbreviation
            ORDER BY TotalPoints DESC
        """, engine)
        drivers['TeamColor'] = drivers['TeamName'].map(TEAM_COLORS).fillna('#FFFFFF')
        
        # Classement constructeurs
        constructors = pd.read_sql_query(f"""
            SELECT TeamName, SUM(Points) as TotalPoints
            FROM "Results_Clean" WHERE Year = {year}
            GROUP BY TeamName
            ORDER BY TotalPoints DESC
        """, engine)
        constructors['TeamColor'] = constructors['TeamName'].map(TEAM_COLORS).fillna('#FFFFFF')
        
        return {
            'drivers': drivers.to_dict(orient='records'),
            'constructors': constructors.to_dict(orient='records')
        }
    except Exception as e:
        print(f"Error in get_standings: {e}")
        return {'drivers': [], 'constructors': []}

@app.get("/api/points-evolution")
async def get_points_evolution(year: int = 2026):
    """Retourne l'évolution des points cumulés par course pour chaque pilote."""
    engine = get_engine()
    df = pd.read_sql_query(f"""
        SELECT r.Abbreviation, r.TeamName, r.RaceNumber, r.Points, ra.EventName
        FROM "Results_Clean" r
        LEFT JOIN "Races_Clean" ra ON r.Year = ra.Year AND r.RaceNumber = ra.RaceNumber
        WHERE r.Year = {year}
        ORDER BY r.RaceNumber
    """, engine)
    
    if df.empty:
        return {'labels': [], 'datasets': []}
    
    # Calculer les points cumulés
    races = df.groupby('RaceNumber').first()['EventName'].tolist()
    datasets = []
    
    for driver in df['Abbreviation'].unique():
        d = df[df['Abbreviation'] == driver].sort_values('RaceNumber')
        team = d['TeamName'].iloc[-1]
        cumulative = d['Points'].cumsum().tolist()
        
        datasets.append({
            'driver': driver,
            'team': team,
            'color': TEAM_COLORS.get(team, '#FFFFFF'),
            'points': cumulative
        })
    
    # Trier par total de points (le leader en premier)
    datasets.sort(key=lambda x: x['points'][-1] if x['points'] else 0, reverse=True)
    
    return {'labels': races, 'datasets': datasets}

@app.get("/api/compare")
async def compare_drivers(driver1: str, driver2: str, year: int = 2026):
    """Comparaison head-to-head entre deux pilotes."""
    engine = get_engine()
    
    stats = {}
    for driver in [driver1, driver2]:
        df = pd.read_sql_query(f"""
            SELECT * FROM "Results_Clean" WHERE Year = {year} AND Abbreviation = '{driver}'
            ORDER BY RaceNumber
        """, engine)
        
        if df.empty:
            stats[driver] = None
            continue
            
        stats[driver] = {
            'abbreviation': driver,
            'team': df['TeamName'].iloc[-1],
            'color': TEAM_COLORS.get(df['TeamName'].iloc[-1], '#FFF'),
            'total_points': int(df['Points'].sum()),
            'avg_position': round(df['Position'].mean(), 1),
            'avg_grid': round(df['GridPosition'].mean(), 1),
            'best_finish': int(df['Position'].min()),
            'podiums': int((df['Position'] <= 3).sum()),
            'wins': int((df['Position'] == 1).sum()),
            'dnfs': int(df['DNF'].sum()) if 'DNF' in df.columns else 0,
            'races': len(df),
            'positions': df['Position'].tolist(),
            'grid_positions': df['GridPosition'].tolist()
        }
    
    return stats

# =========================================================================
# API ENDPOINTS — PREDICTION
# =========================================================================
@app.get("/api/calendar")
async def get_calendar(year: int = 2026):
    """Retourne le calendrier F1."""
    os.makedirs('data/cache', exist_ok=True)
    fastf1.Cache.enable_cache('data/cache')
    
    schedule = fastf1.get_event_schedule(year)
    schedule = schedule[schedule['RoundNumber'] > 0]
    
    races = []
    for _, event in schedule.iterrows():
        races.append({
            'round': int(event['RoundNumber']),
            'name': event['EventName'],
            'country': event['Country'],
            'date': event['EventDate'].strftime('%Y-%m-%d')
        })
    
    return races

class PredictionRequest(BaseModel):
    grid: dict  # {"VER": 1, "ANT": 2, ...}
    weather: dict  # {"air_temp": 25, "track_temp": 40, ...}

@app.post("/api/predict")
async def predict_race(request: PredictionRequest):
    """Prédiction d'une course avec le modèle XGBoost."""
    model = get_model()
    engine = get_engine()
    
    # Récupérer la forme des pilotes
    real_results = pd.read_sql_query('SELECT * FROM "Results_Clean" WHERE Year = 2026', engine)
    
    driver_form = {}
    for driver in request.grid.keys():
        d = real_results[real_results['Abbreviation'] == driver].sort_values('RaceNumber')
        if not d.empty:
            positions = d['Position'].values
            weights = np.array([0.5 ** (len(positions) - 1 - i) for i in range(len(positions))])
            weights = weights / weights.sum()
            driver_form[driver] = {
                'team': d['TeamName'].iloc[-1],
                'avg_pos': float(np.average(positions, weights=weights)),
                'avg_pts': float(d['Points'].tail(5).mean()),
                'dnf_rate': float(d['DNF'].mean()) if 'DNF' in d.columns else 0.1,
            }
        else:
            driver_form[driver] = {'team': 'Unknown', 'avg_pos': 11, 'avg_pts': 5, 'dnf_rate': 0.1}
    
    # Forme des écuries
    team_form = {}
    for team in set(f['team'] for f in driver_form.values()):
        t = real_results[real_results['TeamName'] == team]
        team_positions = t.groupby('RaceNumber')['Position'].mean().values
        team_form[team] = float(np.mean(team_positions[-5:])) if len(team_positions) > 0 else 11
    
    w = request.weather
    
    rows = []
    for driver, grid_pos in request.grid.items():
        form = driver_form[driver]
        team = form['team']
        rows.append({
            'GridPosition': grid_pos,
            'Driver_AvgPos_Last5': form['avg_pos'],
            'Driver_AvgPts_Last5': form['avg_pts'],
            'Driver_DNF_Rate': form['dnf_rate'],
            'Driver_Circuit_Experience': 0,
            'Driver_AvgPos_On_Circuit': form['avg_pos'],
            'Driver_Best_On_Circuit': form['avg_pos'],
            'Grid_vs_Form': grid_pos - form['avg_pos'],
            'Team_AvgPos_Last5': team_form.get(team, 11),
            'AirTemp': w.get('air_temp', 25),
            'TrackTemp': w.get('track_temp', 40),
            'Humidity': w.get('humidity', 50),
            'WindSpeed': w.get('wind_speed', 10),
            'Rainfall': w.get('rainfall', 0),
            'Abbreviation': driver,
            'TeamName': team
        })
    
    df = pd.DataFrame(rows)
    feature_cols = [
        'GridPosition', 'Driver_AvgPos_Last5', 'Driver_AvgPts_Last5',
        'Driver_DNF_Rate', 'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit', 'Driver_Best_On_Circuit',
        'Grid_vs_Form', 'Team_AvgPos_Last5',
        'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall'
    ]
    
    predictions = model.predict(df[feature_cols])
    df['predicted_score'] = predictions
    df = df.sort_values('predicted_score').reset_index(drop=True)
    df['position'] = range(1, len(df) + 1)
    
    points_system = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
    df['points'] = df['position'].map(points_system).fillna(0).astype(int)
    df['color'] = df['TeamName'].map(TEAM_COLORS).fillna('#FFFFFF')
    
    result = df[['Abbreviation', 'TeamName', 'GridPosition', 'position', 'points', 'color']].to_dict(orient='records')
    
    return result

@app.post("/api/monte-carlo")
async def monte_carlo(request: PredictionRequest, n_simulations: int = 3000):
    """Simulation Monte Carlo — retourne les probabilités."""
    model = get_model()
    engine = get_engine()
    
    real_results = pd.read_sql_query("SELECT * FROM Results_Clean WHERE Year = 2026", engine)
    
    driver_form = {}
    for driver in request.grid.keys():
        d = real_results[real_results['Abbreviation'] == driver].sort_values('RaceNumber')
        if not d.empty:
            positions = d['Position'].values
            weights = np.array([0.5 ** (len(positions) - 1 - i) for i in range(len(positions))])
            weights = weights / weights.sum()
            driver_form[driver] = {
                'team': d['TeamName'].iloc[-1],
                'avg_pos': float(np.average(positions, weights=weights)),
                'avg_pts': float(d['Points'].tail(5).mean()),
                'dnf_rate': float(d['DNF'].mean()) if 'DNF' in d.columns else 0.1,
                'std_pos': float(d['Position'].std()) if len(d) > 1 else 3.0,
            }
        else:
            driver_form[driver] = {'team': 'Unknown', 'avg_pos': 11, 'avg_pts': 5, 'dnf_rate': 0.1, 'std_pos': 3.0}
    
    team_form = {}
    for team in set(f['team'] for f in driver_form.values()):
        t = real_results[real_results['TeamName'] == team]
        team_positions = t.groupby('RaceNumber')['Position'].mean().values
        team_form[team] = float(np.mean(team_positions[-5:])) if len(team_positions) > 0 else 11
    
    w = request.weather
    
    rows = []
    for driver, grid_pos in request.grid.items():
        form = driver_form[driver]
        team = form['team']
        rows.append({
            'GridPosition': grid_pos,
            'Driver_AvgPos_Last5': form['avg_pos'],
            'Driver_AvgPts_Last5': form['avg_pts'],
            'Driver_DNF_Rate': form['dnf_rate'],
            'Driver_Circuit_Experience': 0,
            'Driver_AvgPos_On_Circuit': form['avg_pos'],
            'Driver_Best_On_Circuit': form['avg_pos'],
            'Grid_vs_Form': grid_pos - form['avg_pos'],
            'Team_AvgPos_Last5': team_form.get(team, 11),
            'AirTemp': w.get('air_temp', 25),
            'TrackTemp': w.get('track_temp', 40),
            'Humidity': w.get('humidity', 50),
            'WindSpeed': w.get('wind_speed', 10),
            'Rainfall': w.get('rainfall', 0),
            'std_pos': form['std_pos'],
            'dnf_rate_val': form['dnf_rate'],
            'Abbreviation': driver,
            'TeamName': team
        })
    
    df = pd.DataFrame(rows)
    feature_cols = [
        'GridPosition', 'Driver_AvgPos_Last5', 'Driver_AvgPts_Last5',
        'Driver_DNF_Rate', 'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit', 'Driver_Best_On_Circuit',
        'Grid_vs_Form', 'Team_AvgPos_Last5',
        'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall'
    ]
    
    base_preds = model.predict(df[feature_cols])
    n_drivers = len(df)
    
    win_count = np.zeros(n_drivers)
    podium_count = np.zeros(n_drivers)
    top5_count = np.zeros(n_drivers)
    points_count = np.zeros(n_drivers)
    position_sum = np.zeros(n_drivers)
    
    for _ in range(n_simulations):
        noisy = base_preds.copy()
        for i in range(n_drivers):
            noisy[i] += np.random.normal(0, df.iloc[i]['std_pos'] * 0.8)
        
        dnf_mask = np.random.random(n_drivers) < df['dnf_rate_val'].values
        noisy[dnf_mask] = 25
        
        if np.random.random() < 0.20:
            mid = (noisy > 4) & (noisy < 16)
            noisy[mid] += np.random.normal(0, 1.5, mid.sum())
        
        order = np.argsort(noisy)
        positions = np.empty(n_drivers, dtype=int)
        positions[order] = np.arange(1, n_drivers + 1)
        
        position_sum += positions
        win_count += (positions == 1)
        podium_count += (positions <= 3)
        top5_count += (positions <= 5)
        points_count += (positions <= 10)
    
    results = []
    for i, row in df.iterrows():
        results.append({
            'driver': row['Abbreviation'],
            'team': row['TeamName'],
            'color': TEAM_COLORS.get(row['TeamName'], '#FFF'),
            'grid': int(row['GridPosition']),
            'win_pct': round(win_count[i] / n_simulations * 100, 1),
            'podium_pct': round(podium_count[i] / n_simulations * 100, 1),
            'top5_pct': round(top5_count[i] / n_simulations * 100, 1),
            'points_pct': round(points_count[i] / n_simulations * 100, 1),
            'avg_position': round(position_sum[i] / n_simulations, 1)
        })
    
    results.sort(key=lambda x: x['win_pct'], reverse=True)
    
    return results

# =========================================================================
# API ENDPOINTS — PERSO (Historique des prédictions)
# =========================================================================
@app.post("/api/save-prediction")
async def save_prediction(data: dict):
    """Sauvegarde une prédiction dans la base de données."""
    engine = get_engine()
    
    with engine.begin() as conn:
        # Créer la table si elle n'existe pas
        if engine.dialect.name == 'postgresql':
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "Predictions" (
                    id SERIAL PRIMARY KEY,
                    race_name TEXT,
                    year INTEGER,
                    race_number INTEGER,
                    prediction_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "Predictions" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_name TEXT,
                    year INTEGER,
                    race_number INTEGER,
                    prediction_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        import json
        conn.execute(
            text('INSERT INTO "Predictions" (race_name, year, race_number, prediction_data) VALUES (:rn, :y, :num, :data)'),
            {"rn": data.get('race_name'), "y": data.get('year'), "num": data.get('race_number'), "data": json.dumps(data.get('results', []))}
        )
    
    return {"status": "ok", "message": "Prédiction sauvegardée !"}

@app.get("/api/prediction-history")
async def get_prediction_history():
    """Retourne l'historique des prédictions sauvegardées."""
    engine = get_engine()
    
    try:
        df = pd.read_sql_query('SELECT * FROM "Predictions" ORDER BY created_at DESC', engine)
        return df.to_dict(orient='records')
    except Exception:
        return []

@app.get("/api/accuracy")
async def get_accuracy():
    """Calcule la précision des prédictions passées vs résultats réels."""
    engine = get_engine()
    
    try:
        import json
        predictions = pd.read_sql_query('SELECT * FROM "Predictions"', engine)
        results = pd.read_sql_query('SELECT * FROM "Results_Clean" WHERE Year = 2026', engine)
        
        if predictions.empty:
            return {'global_mae': None, 'per_race': []}
        
        accuracy_per_race = []
        
        for _, pred in predictions.iterrows():
            race_num = pred['race_number']
            real = results[results['RaceNumber'] == race_num]
            
            if real.empty:
                continue
            
            pred_data = json.loads(pred['prediction_data'])
            
            errors = []
            for p in pred_data:
                real_pos = real[real['Abbreviation'] == p.get('Abbreviation', p.get('driver'))]['Position']
                if not real_pos.empty:
                    errors.append(abs(p.get('position', 0) - real_pos.values[0]))
            
            if errors:
                mae = round(np.mean(errors), 2)
                accuracy_per_race.append({
                    'race_name': pred['race_name'],
                    'race_number': race_num,
                    'mae': mae,
                    'date': pred['created_at']
                })
        
        global_mae = round(np.mean([r['mae'] for r in accuracy_per_race]), 2) if accuracy_per_race else None
        
        return {'global_mae': global_mae, 'per_race': accuracy_per_race}
    except Exception as e:
        return {'global_mae': None, 'per_race': [], 'error': str(e)}

# =========================================================================
# ENDPOINT DE MISE À JOUR MANUELLE
# =========================================================================
@app.post("/api/force-update")
async def force_update():
    """Force une mise à jour des données (utile pour debug)."""
    auto_update_data()
    return {"status": "ok", "message": "Mise à jour lancée !"}

@app.get("/api/drivers")
async def get_drivers(year: int = 2026):
    """Retourne la liste des pilotes pour une saison."""
    engine = get_engine()
    last_race = pd.read_sql_query(f'SELECT MAX(RaceNumber) as max_rn FROM "Results_Clean" WHERE Year = {year}', engine).iloc[0]['max_rn']
    
    drivers = pd.read_sql_query(f"""
        SELECT Abbreviation, TeamName 
        FROM "Results_Clean" 
        WHERE Year = {year} AND RaceNumber = {last_race}
        ORDER BY Position
    """, engine)
    drivers['TeamColor'] = drivers['TeamName'].map(TEAM_COLORS).fillna('#FFFFFF')
    
    return drivers.to_dict(orient='records')
