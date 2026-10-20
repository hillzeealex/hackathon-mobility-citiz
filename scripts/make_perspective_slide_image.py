"""
Génère l'image de présentation pour la slide 'Perspective : flottes professionnelles'.
Sauvegarde dans slides/perspective_flottes_pro.png.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
SLIDES_DIR = BASE_DIR / "slides"
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = SLIDES_DIR / "perspective_flottes_pro.png"

def make_slide():
    # 16:9 ratio high-res slide (1920x1080 equivalent at 150 dpi: 12.8 x 7.2 inches)
    fig = plt.figure(figsize=(13.33, 7.5), dpi=150, facecolor="#F8FAFC")
    
    # Header
    fig.text(0.05, 0.93, "PERSPECTIVE STRATÉGIQUE · FLOTTES PROFESSIONNELLES (B2B)", 
             fontsize=11, fontweight="bold", color="#E6007E", family="sans-serif")
    fig.text(0.05, 0.86, "Développer l'autopartage Citiz pour les entreprises de Nantes Métropole", 
             fontsize=19, fontweight="bold", color="#0F172A", family="sans-serif")
    fig.text(0.05, 0.81, "Exploration basée sur la base Sirene géolocalisée (130k établissements actifs) et le cadastre ZAE Open Data", 
             fontsize=11, color="#64748B", family="sans-serif")
    
    # Card 1: 3-Scenarios Comparison Bar Chart (Left)
    ax1 = fig.add_axes([0.06, 0.12, 0.42, 0.62], facecolor="#FFFFFF")
    ax1.set_axisbelow(True)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, color="#E2E8F0")
    
    scenarios = ["1. Particuliers\n(officiel, α=0)", "2. Mixte\n(recommandé, α=0.3)", "3. Pros\n(100% flottes)"]
    habs = [117426, 117426, 88623]
    emps = [18766, 18766, 29406]
    
    x = np.arange(len(scenarios))
    w = 0.35
    
    b1 = ax1.bar(x - w/2, [h/1000 for h in habs], width=w, label="Habitants desservis (k)", color="#0072B2", edgecolor="none", zorder=3)
    b2 = ax1.bar(x + w/2, [e/1000 for e in emps], width=w, label="Emplois desservis (k)", color="#8000B4", edgecolor="none", zorder=3)
    
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=10, fontweight="bold", color="#1E293B")
    ax1.set_ylabel("Personnes nouvellement couvertes à 5 min (en milliers)", fontsize=10, color="#475569")
    ax1.set_title("Impact comparé des 3 scénarios sous budget 500 k€ (12 stations)", fontsize=11, fontweight="bold", pad=12, color="#0F172A")
    ax1.legend(loc="upper right", frameon=False, fontsize=9)
    ax1.set_ylim(0, 140)
    
    for bar in b1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 2, f"{int(yval)}k", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#0072B2")
    for bar in b2:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 2, f"{yval:.1f}k", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#8000B4")
        
    for spine in ["top", "right", "left", "bottom"]:
        ax1.spines[spine].set_color("#CBD5E1")
        
    # Card 2: Top Unserved Employment Hubs (Right Top)
    ax2 = fig.add_axes([0.54, 0.43, 0.41, 0.31], facecolor="#FFFFFF")
    ax2.set_axisbelow(True)
    ax2.grid(axis="x", linestyle="--", alpha=0.5, color="#E2E8F0")
    
    poles = [
        "Atlantis - ZAC d'Armor",
        "Nantes Nord - Pont du Cens",
        "Ragon / Océane (Rezé)",
        "Parc Tertiaire Ar Mor",
        "Aéroport D2A (Airbus)",
        "ZI Lorie (Saint-Herblain)"
    ][::-1]
    unserved_jobs = [20582, 13055, 11032, 8455, 7981, 5596][::-1]
    
    y_pos = np.arange(len(poles))
    b_poles = ax2.barh(y_pos, [j/1000 for j in unserved_jobs], height=0.55, color="#E6007E", alpha=0.85, zorder=3)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(poles, fontsize=9, fontweight="bold", color="#1E293B")
    ax2.set_xlabel("Emplois sans autopartage à 5 min (milliers)", fontsize=9, color="#475569")
    ax2.set_title("Top 6 des pôles d'activités non desservis (sur 130 ZAE)", fontsize=11, fontweight="bold", pad=8, color="#0F172A")
    ax2.set_xlim(0, 24)
    
    for bar in b_poles:
        xval = bar.get_width()
        ax2.text(xval + 0.4, bar.get_y() + bar.get_height()/2, f"{xval:.1f}k", ha="left", va="center", fontsize=8.5, fontweight="bold", color="#BE185D")
        
    for spine in ["top", "right", "left", "bottom"]:
        ax2.spines[spine].set_color("#CBD5E1")

    # Card 3: Key Insights / Strategic Takeaways (Right Bottom)
    ax3 = fig.add_axes([0.54, 0.12, 0.41, 0.24], facecolor="#F1F5F9")
    ax3.axis("off")
    
    box_rect = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.03", ec="#CBD5E1", fc="#FFFFFF", lw=1.2)
    ax3.add_patch(box_rect)
    
    ax3.text(0.04, 0.82, "ENVOIS CLÉS POUR LE JURY & LA COOPÉRATIVE CITIZ :", fontsize=9.5, fontweight="bold", color="#E6007E")
    
    t1 = "1. Double dividende résidentiel & pro :"
    d1 = "Le scénario Mixte (α=0.3) retient 100% des stations du scénario officiel (117k hab. + 18.7k emplois)."
    t2 = "2. Complémentarité horaire :"
    d2 = "Flottes pro en journée (9h-17h) + Particuliers soirs & week-ends = rentabilité maximale sans conflit."
    t3 = "3. Limite méthodologique assumée :"
    d3 = "Modèle prédictif LightGBM calibré sur l'historique résidentiel, à enrichir avec les flux B2B réels."

    ax3.text(0.04, 0.64, t1, fontsize=8.5, fontweight="bold", color="#0F172A")
    ax3.text(0.04, 0.51, d1, fontsize=8, color="#475569")
    ax3.text(0.04, 0.35, t2, fontsize=8.5, fontweight="bold", color="#0F172A")
    ax3.text(0.04, 0.22, d2, fontsize=8, color="#475569")
    ax3.text(0.04, 0.08, t3, fontsize=8.5, fontweight="bold", color="#0F172A")
    ax3.text(0.55, 0.08, "(chiffres exploratoires distincts de l'officiel)", fontsize=7.5, color="#64748B", style="italic")

    plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Slide générée avec succès dans : {OUT_PATH}")

if __name__ == "__main__":
    make_slide()
