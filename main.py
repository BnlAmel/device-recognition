import controle_ecran
import reconnaissance


def pause():
    input("\nAppuyez sur Entrée pour continuer...")


def safe_run(label, func):
    """Exécute une action sans que le programme plante en cas d'erreur."""
    try:
        func()
    except Exception as e:
        print(f"\nErreur pendant « {label} » : {e}")


def main():
    while True:
        print("\n" + "=" * 52)
        print(" RECONNAISSANCE ET CONTRÔLE DES PÉRIPHÉRIQUES")
        print("=" * 52)
        print(" 1. Lister tous les périphériques (par catégorie)")
        print(" 2. Générer le rapport détaillé")
        print(" 3. Contrôler l'écran (luminosité, capture...)")
        print(" 0. Quitter")
        choix = input("Votre choix : ").strip()

        if choix == "1":
            safe_run("liste des périphériques", reconnaissance.lister_peripheriques)
            pause()
        elif choix == "2":
            safe_run("rapport détaillé", reconnaissance.generer_rapport)
            pause()
        elif choix == "3":
            safe_run("contrôle de l'écran", controle_ecran.menu_ecran)
        elif choix == "0":
            break
        else:
            print("Choix invalide.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.")