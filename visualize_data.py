from database import get_engine
import pandas as pd
import matplotlib.pyplot as plt

def plot_top_drivers(year):
    print(f"Chargement des données de la saison {year} depuis la base...")
    engine = get_engine()
    
    # On récupère uniquement les résultats de l'année demandée grâce à la clause WHERE
    query = f"SELECT * FROM Results WHERE Year = {year}"
    df_results = pd.read_sql_query(query, engine)
    
    # On vérifie qu'on a bien des données
    if df_results.empty:
        print("La table Results est vide. As-tu bien exécuté le script de téléchargement ?")
        return

    print("Création du graphique en cours...")
    
    # Dictionnaire des couleurs officielles des écuries F1
    TEAM_COLORS = {
        'Red Bull Racing': '#3671C6',
        'Ferrari': '#E80020',
        'McLaren': '#FF8000',
        'Mercedes': '#27F4D2',
        'Aston Martin': '#229971',
        'Alpine': '#FF87BC', # ou #0093CC
        'Williams': '#64C4FF',
        'RB': '#6692FF',
        'Haas F1 Team': '#B6BABD',
        'Kick Sauber': '#52E252',
        'Alfa Romeo': '#900000',
        'AlphaTauri': '#2B4562'
    }

    # On groupe par pilote pour avoir la somme des points ET on garde le nom de son écurie
    driver_stats = df_results.groupby('Abbreviation').agg({
        'Points': 'sum',
        'TeamName': 'last' # 'last' prend la dernière écurie du pilote s'il a changé en cours de saison
    }).sort_values(by='Points', ascending=False).head(10)

    # On génère une liste de couleurs basée sur l'écurie de chaque pilote (Blanc si écurie non trouvée)
    bar_colors = [TEAM_COLORS.get(team, '#FFFFFF') for team in driver_stats['TeamName']]

    # Paramétrage visuel du graphique
    plt.style.use('dark_background')
    plt.figure(figsize=(10, 6))
    
    # On dessine les barres avec nos belles couleurs dynamiques
    bars = driver_stats['Points'].plot(kind='bar', color=bar_colors)
    
    plt.title(f"Top 10 Pilotes - Championnat {year}", fontsize=14, fontweight='bold')
    plt.xlabel("Pilotes", fontsize=12)
    plt.ylabel("Points Cumulés", fontsize=12)
    plt.xticks(rotation=0)
    
    # On ajoute la valeur exacte au-dessus de chaque barre
    for bar in bars.containers:
        bars.bar_label(bar, fmt='%.0f', label_type='edge', padding=3)

    plt.tight_layout()
    
    # Affichage du graphique
    print("Affichage du graphique")
    plt.show()
    
    # Pas besoin de fermer la connexion avec engine

if __name__ == "__main__":
    annee = int(input("Entrez l'année à visualiser entre 2024 et 2026 : "))
    plot_top_drivers(annee)
