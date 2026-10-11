"""Reconnaissance des périphériques d'une machine Windows (via WMI)."""
from collections import defaultdict
from datetime import datetime
import platform

import wmi

_connexion = None


def wmi_conn():
    """Connexion WMI, créée une seule fois."""
    global _connexion
    if _connexion is None:
        _connexion = wmi.WMI()
    return _connexion


# ---------------------------------------------------------------
# Partie 1 : liste de tous les périphériques
# ---------------------------------------------------------------
def lister_peripheriques():
    """Liste tous les périphériques PnP, regroupés par catégorie."""
    groupes = defaultdict(list)
    total = 0
    for d in wmi_conn().Win32_PnPEntity():
        groupes[d.PNPClass or "Autre"].append(d)
        total += 1

    print(f"Total : {total} périphériques dans {len(groupes)} catégories\n")
    for classe in sorted(groupes):
        print(f"[{classe}] ({len(groupes[classe])})")
        for d in groupes[classe]:
            nom = d.Name or "(sans nom)"
            print(f"   - {nom}  |  {d.Manufacturer or 'Inconnu'}  |  {d.Status or 'Inconnu'}")
        print()


# ---------------------------------------------------------------
# Partie 2 : caractéristiques détaillées
# ---------------------------------------------------------------
def en_go(valeur):
    try:
        return f"{int(valeur) / (1024 ** 3):.1f} Go"
    except (TypeError, ValueError):
        return "N/A"


def en_mhz(valeur):
    return f"{valeur} MHz" if valeur else "N/A"


# Catégorie -> (classe WMI, [(propriété, libellé, formateur optionnel)])
CATEGORIES = {
    "Processeur": ("Win32_Processor", [
        ("Name", "Nom", None),
        ("Manufacturer", "Fabricant", None),
        ("NumberOfCores", "Coeurs", None),
        ("NumberOfLogicalProcessors", "Threads", None),
        ("MaxClockSpeed", "Fréquence max", en_mhz),
    ]),
    "Mémoire RAM": ("Win32_PhysicalMemory", [
        ("Manufacturer", "Fabricant", None),
        ("Capacity", "Capacité", en_go),
        ("Speed", "Vitesse", en_mhz),
    ]),
    "Disques": ("Win32_DiskDrive", [
        ("Model", "Modèle", None),
        ("InterfaceType", "Interface", None),
        ("Size", "Capacité", en_go),
        ("Partitions", "Partitions", None),
        ("Status", "État", None),
    ]),
    "Carte graphique": ("Win32_VideoController", [
        ("Name", "Nom", None),
        ("DriverVersion", "Version driver", None),
        ("CurrentHorizontalResolution", "Résolution H", None),
        ("CurrentVerticalResolution", "Résolution V", None),
        ("CurrentRefreshRate", "Fréquence (Hz)", None),
    ]),
    "Réseau": ("Win32_NetworkAdapter", [
        ("Name", "Nom", None),
        ("Manufacturer", "Fabricant", None),
        ("MACAddress", "Adresse MAC", None),
        ("NetEnabled", "Connecté", None),
        ("NetConnectionID", "Nom de connexion", None),
    ]),
    "Audio": ("Win32_SoundDevice", [
        ("Name", "Nom", None),
        ("Manufacturer", "Fabricant", None),
        ("Status", "État", None),
    ]),
    "Batterie": ("Win32_Battery", [
        ("Name", "Nom", None),
        ("EstimatedChargeRemaining", "Charge (%)", None),
        ("BatteryStatus", "Code statut", None),
    ]),
    "Clavier": ("Win32_Keyboard", [
        ("Name", "Nom", None),
        ("Layout", "Disposition", None),
        ("Status", "État", None),
    ]),
    "Souris / pavé tactile": ("Win32_PointingDevice", [
        ("Name", "Nom", None),
        ("Manufacturer", "Fabricant", None),
        ("Status", "État", None),
    ]),
    "Contrôleurs USB": ("Win32_USBController", [
        ("Name", "Nom", None),
        ("Manufacturer", "Fabricant", None),
        ("Status", "État", None),
    ]),
    "Imprimantes": ("Win32_Printer", [
        ("Name", "Nom", None),
        ("DriverName", "Driver", None),
        ("Default", "Par défaut", None),
    ]),
    "BIOS": ("Win32_BIOS", [
        ("Manufacturer", "Fabricant", None),
        ("SMBIOSBIOSVersion", "Version", None),
        ("ReleaseDate", "Date", None),
    ]),
}

STATUT_BATTERIE = {
    1: "Sur batterie", 2: "Sur secteur", 3: "Chargée", 4: "Faible",
    5: "Critique", 6: "En charge", 7: "En charge (haute)",
    8: "En charge (faible)", 9: "En charge (critique)",
    10: "Indéfini", 11: "Partiellement chargée",
}

DISPOSITIONS_CLAVIER = {
    "0000040C": "Français (France)",
    "00000409": "Anglais (US)",
    "00000401": "Arabe",
    "0000080C": "Français (Belgique)",
}

OUI_NON = {True: "Oui", False: "Non"}


def collecter():
    """Interroge WMI pour chaque catégorie et retourne les valeurs brutes."""
    resultat = {}
    for titre, (classe_wmi, proprietes) in CATEGORIES.items():
        elements = []
        try:
            for obj in getattr(wmi_conn(), classe_wmi)():
                element = {}
                for prop, libelle, formateur in proprietes:
                    valeur = getattr(obj, prop, None)
                    if formateur:
                        valeur = formateur(valeur)
                    element[libelle] = valeur if valeur not in (None, "") else "N/A"
                elements.append(element)
        except Exception as e:
            elements.append({"Erreur": str(e)})
        resultat[titre] = elements
    return resultat


def nettoyer(donnees):
    """Rend les valeurs lisibles. Retourne (données, nb d'adaptateurs masqués)."""
    for el in donnees.get("Batterie", []):
        code = el.pop("Code statut", None)
        el["État"] = STATUT_BATTERIE.get(code, "Inconnu")

    for el in donnees.get("Clavier", []):
        disposition = el.get("Disposition")
        el["Disposition"] = DISPOSITIONS_CLAVIER.get(disposition, disposition)

    for el in donnees.get("BIOS", []):
        brut = str(el.get("Date", ""))
        try:
            el["Date"] = datetime.strptime(brut[:8], "%Y%m%d").strftime("%d/%m/%Y")
        except ValueError:
            pass

    for el in donnees.get("Réseau", []):
        el["Connecté"] = OUI_NON.get(el.get("Connecté"), el.get("Connecté"))

    for el in donnees.get("Imprimantes", []):
        el["Par défaut"] = OUI_NON.get(el.get("Par défaut"), el.get("Par défaut"))

    # Réseau : on ne garde que les adaptateurs qui ont un nom de connexion
    tous = donnees.get("Réseau", [])
    gardes = [e for e in tous if e.get("Nom de connexion") != "N/A"]
    donnees["Réseau"] = gardes
    return donnees, len(tous) - len(gardes)


def fusionner_doublons(elements):
    """Regroupe les éléments identiques avec une colonne Quantité."""
    compteurs, ordre = {}, []
    for el in elements:
        cle = repr(sorted(el.items()))
        if cle not in compteurs:
            compteurs[cle] = [el, 0]
            ordre.append(cle)
        compteurs[cle][1] += 1

    fusionnes = []
    for cle in ordre:
        el, n = compteurs[cle]
        fusionnes.append({"Quantité": n, **el} if n > 1 else el)
    return fusionnes


def tableau(elements, largeur_max=38):
    colonnes = list(elements[0].keys())
    lignes = [[str(el.get(c, ""))[:largeur_max] for c in colonnes] for el in elements]
    largeurs = [max(len(c), *(len(l[i]) for l in lignes)) for i, c in enumerate(colonnes)]

    def ligne(cellules):
        return " | ".join(cell.ljust(w) for cell, w in zip(cellules, largeurs))

    sortie = [ligne(colonnes), "-+-".join("-" * w for w in largeurs)]
    sortie += [ligne(l) for l in lignes]
    return sortie


def construire_rapport(donnees, masques):
    lignes = [
        "RAPPORT DES PÉRIPHÉRIQUES",
        f"Machine : {platform.node()}",
        f"Système : {platform.platform()}",
        f"Généré le {datetime.now():%d/%m/%Y à %H:%M}",
        "",
    ]
    for titre, elements in donnees.items():
        total = sum(e.get("Quantité", 1) for e in elements)
        lignes.append(f"## {titre} ({total})")
        if not elements:
            lignes.append("   Aucun périphérique détecté")
        elif len(elements) == 1:
            for libelle, valeur in elements[0].items():
                lignes.append(f"   {libelle:<18}: {valeur}")
        else:
            lignes += ["   " + l for l in tableau(elements)]
        if titre == "Réseau" and masques:
            lignes.append(f"   ({masques} adaptateurs virtuels sans connexion masqués)")
        lignes.append("")
    return lignes


def generer_rapport():
    """Affiche le rapport détaillé et l'enregistre dans rapport_peripheriques.txt."""
    donnees, masques = nettoyer(collecter())
    donnees = {titre: fusionner_doublons(el) for titre, el in donnees.items()}
    lignes = construire_rapport(donnees, masques)

    print("\n".join(lignes))
    with open("rapport_peripheriques.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    print("Fichier créé : rapport_peripheriques.txt")


if __name__ == "__main__":
    lister_peripheriques()
    generer_rapport()