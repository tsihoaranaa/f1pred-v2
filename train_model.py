from database import get_engine
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os

def train_model():
    """
    Étape 3b : Entraîner un modèle de Machine Learning pour prédire la position d'arrivée.
    """
    print("=" * 60)
    print("🤖 ENTRAÎNEMENT DU MODÈLE DE PRÉDICTION F1")
    print("=" * 60)
    
    engine = get_engine()
    df = pd.read_sql_query("SELECT * FROM Features", engine)
    
    print(f"Données chargées : {len(df)} lignes")
    
    # --- Définition des features (X) et de la cible (y) ---
    # X = ce que le modèle voit en entrée
    # y = ce qu'il doit prédire (la position d'arrivée)
    feature_cols = [
        'GridPosition',
        'Driver_AvgPos_Last5',
        'Driver_AvgPts_Last5',
        'Driver_DNF_Rate',
        'Driver_Circuit_Experience',
        'Driver_AvgPos_On_Circuit',
        'Driver_Best_On_Circuit',
        'Grid_vs_Form',
        'Team_AvgPos_Last5',
        'AirTemp', 'TrackTemp', 'Humidity', 'WindSpeed', 'Rainfall',
    ]
    
    X = df[feature_cols].copy()
    y = df['Position'].copy()
    
    # Convertir Rainfall (booléen) en 0/1
    X['Rainfall'] = X['Rainfall'].astype(int)
    
    # Remplir les éventuels NaN restants avec la médiane
    X = X.fillna(X.median())
    
    # --- Séparation Train / Test CHRONOLOGIQUE ---
    # On entraîne sur 2024+2025 et on teste sur 2026
    # C'est la bonne méthode ! Jamais de split aléatoire en séries temporelles.
    train_mask = df['Year'].isin([2024, 2025])
    test_mask = df['Year'] == 2026
    
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    
    print(f"\nDonnées d'entraînement : {len(X_train)} lignes (2024-2025)")
    print(f"Données de test : {len(X_test)} lignes (2026)")
    
    # --- Entraînement du modèle ---
    # GradientBoosting est un excellent compromis puissance/simplicité
    # Il construit des arbres de décision les uns après les autres, chacun corrigeant les erreurs du précédent
    print("\nEntraînement en cours...")
    
    model = XGBRegressor(
        n_estimators=200,       # Nombre d'arbres de décision
        max_depth=4,            # Profondeur maximale de chaque arbre
        learning_rate=0.1,      # Vitesse d'apprentissage
        min_child_weight=10,    # Poids minimum dans un noeud (anti-overfitting)
        subsample=0.8,          # Utilise 80% des données par arbre (anti-overfitting)
        colsample_bytree=0.8,   # Utilise 80% des features par arbre (anti-overfitting)
        random_state=42,        # Pour que les résultats soient reproductibles
        verbosity=0             # Pas de logs inutiles
    )
    
    model.fit(X_train, y_train)
    print("Entraînement terminé !")
    
    # --- Évaluation du modèle ---
    print("\n" + "=" * 60)
    print("📊 RÉSULTATS DE L'ÉVALUATION")
    print("=" * 60)
    
    # Prédictions sur les données d'entraînement (pour vérifier qu'il apprend bien)
    y_train_pred = model.predict(X_train)
    mae_train = mean_absolute_error(y_train, y_train_pred)
    
    # Prédictions sur les données de test (la vraie mesure de performance)
    y_test_pred = model.predict(X_test)
    mae_test = mean_absolute_error(y_test, y_test_pred)
    rmse_test = np.sqrt(mean_squared_error(y_test, y_test_pred))
    
    print(f"\nMAE Entraînement (2024-2025) : {mae_train:.2f} positions")
    print(f"MAE Test (2026) : {mae_test:.2f} positions")
    print(f"RMSE Test (2026) : {rmse_test:.2f} positions")
    print(f"\n→ En moyenne, le modèle se trompe de {mae_test:.1f} positions sur les courses 2026.")
    
    # --- Importance des features ---
    print("\n🏆 IMPORTANCE DES FEATURES (ce qui influence le plus la prédiction) :")
    importances = pd.Series(model.feature_importances_, index=feature_cols)
    importances = importances.sort_values(ascending=False)
    for feat, imp in importances.items():
        bar = "█" * int(imp * 50)
        print(f"  {feat:30s} {bar} {imp:.3f}")
    
    # --- Exemple de prédiction vs réalité sur les courses 2026 ---
    if len(X_test) > 0:
        print("\n" + "=" * 60)
        print("🔎 EXEMPLE : Prédictions vs Réalité (1ère course 2026)")
        print("=" * 60)
        
        test_data = df[test_mask].copy()
        test_data['Predicted_Position'] = y_test_pred
        
        # On prend la première course de 2026
        first_race = test_data['RaceNumber'].min()
        race_example = test_data[test_data['RaceNumber'] == first_race][['Abbreviation', 'TeamName', 'GridPosition', 'Position', 'Predicted_Position']]
        race_example['Predicted_Position'] = race_example['Predicted_Position'].round(1)
        race_example = race_example.sort_values('Position')
        
        print(race_example.to_string(index=False))
    
    # --- Sauvegarde du modèle entraîné ---
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/f1_model.pkl')
    print(f"\n💾 Modèle sauvegardé dans 'models/f1_model.pkl'")
    print("Tu pourras le recharger plus tard avec : model = joblib.load('models/f1_model.pkl')")

if __name__ == "__main__":
    train_model()
