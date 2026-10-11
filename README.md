# Reconnaissance des périphériques et prise de contrôle de l'écran (Windows)

Homework du Pr BELKHIR Abdelkader. Programme Python pour Windows qui :

1. **reconnaît tous les périphériques** de la machine et édite leurs caractéristiques ;
2. **prend le contrôle de l'écran** (luminosité, résolution, capture, souris, clavier, etc.).

## Contenu du projet

| Fichier | Rôle |
|---|---|
| `main.py` | Menu principal du programme |
| `reconnaissance.py` | Partie 1 : liste des périphériques, caractéristiques détaillées, rapport TXT |
| `controle_ecran.py` | Partie 2 : prise de contrôle de l'écran (menu de 13 actions) |
| `requirements.txt` | Dépendances Python |

## Prérequis

- Windows 10 ou 11
- Python 3.10 ou plus récent (testé avec Python 3.14)

## Installation

Dans un terminal, depuis le dossier du projet :

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Si PowerShell bloque l'activation de l'environnement virtuel :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Utilisation

```powershell
python main.py
```

Menu principal :

| Choix | Action |
|---|---|
| 1 | Lister tous les périphériques, par catégorie |
| 2 | Générer le rapport détaillé (affiché et enregistré dans `rapport_peripheriques.txt`) |
| 3 | Contrôler l'écran |
| 0 | Quitter |

Chaque module peut aussi être lancé seul : `python reconnaissance.py` ou `python controle_ecran.py`.

### Menu « Contrôle de l'écran »

| N° | Action |
|---|---|
| 1 | Informations de l'écran (nombre d'écrans, résolution, fréquence, luminosité) |
| 2 | Luminosité : augmenter, diminuer, valeur précise, démonstration |
| 3 | Changer la résolution (temporaire : retour automatique après 8 secondes) |
| 4 | Capturer l'écran (image enregistrée dans `captures_ecran/`) |
| 5 | Piloter la souris (le curseur dessine un rectangle) |
| 6 | Piloter le clavier (saisie automatique dans le Bloc-notes) |
| 7 | Mettre la fenêtre active en plein écran |
| 8 | Afficher le bureau (Windows + D) |
| 9 | Verrouiller la session |
| 10 | Éteindre l'écran (il se rallume au mouvement de la souris) |
| 11 | Changer la langue de saisie du clavier |
| 12 | Son : volume, muet, test sonore |
| 13 | Wi-Fi, Bluetooth, mode avion, économiseur de batterie |

## Précautions

- Les options 9 (verrouillage) et 10 (extinction de l'écran) interrompent l'affichage : à tester en dernier.
- Désactiver le Wi-Fi ou activer le mode avion coupe la connexion Internet. Pense à les réactiver.
- Pendant les options 5 et 6 (souris et clavier), ne touche à rien : le programme pilote le curseur et le clavier.
- Selon la machine, certaines actions (luminosité, radios, économiseur de batterie) peuvent demander un terminal lancé en administrateur.
- La luminosité se règle par logiciel sur un écran intégré (portable). Sur un écran externe, l'option peut afficher « non disponible ».

## Fichiers générés

- `rapport_peripheriques.txt` : rapport détaillé des périphériques (option 2)
- `captures_ecran/` : captures d'écran (option 4 du menu écran)

Ces fichiers ne sont pas envoyés sur GitHub (voir `.gitignore`).

## Dépendances

`wmi`, `pywin32` (accès à WMI) et `pillow` (capture d'écran). Les autres fonctions utilisent l'API Windows via `ctypes`, PowerShell et `powercfg`, déjà présents sur Windows.