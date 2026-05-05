from clean_data import clean_data
from build_features import build_features
from train_model import train_model

if __name__ == "__main__":
    print("🔄 MISE À JOUR COMPLÈTE DU MODÈLE\n")
    
    clean_data()
    build_features()
    train_model()
    
    print("\n✅ Mise à jour terminée ! Tu peux lancer simulate_one_race.py")
