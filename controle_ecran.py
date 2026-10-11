"""Prise de contrôle de l'écran sous Windows (API user32 via ctypes, WMI, PowerShell)."""
import base64
import ctypes
import os
import re
import subprocess
import time
import winsound
from datetime import datetime

import wmi

user32 = ctypes.windll.user32
PAS = 10  # variation de luminosité (en %)
KEYEVENTF_KEYUP = 0x0002


# ===============================================================
# 1. Informations sur l'écran
# ===============================================================
def afficher_infos():
    print(f"  Nombre d'écrans : {user32.GetSystemMetrics(80)}")
    for gpu in wmi.WMI().Win32_VideoController():
        print(f"  Carte graphique : {gpu.Name}")
        print(f"  Résolution      : {gpu.CurrentHorizontalResolution} x {gpu.CurrentVerticalResolution}")
        print(f"  Fréquence       : {gpu.CurrentRefreshRate} Hz")
    lum = get_brightness()
    print(f"  Luminosité      : {lum} %" if lum is not None else "  Luminosité      : non disponible")


# ===============================================================
# 2. Luminosité (WMI, espace de noms root\wmi)
# ===============================================================
def get_brightness():
    """Luminosité actuelle (0-100), ou None si l'écran ne la gère pas."""
    try:
        moniteurs = wmi.WMI(namespace="root\\wmi").WmiMonitorBrightness()
        return int(moniteurs[0].CurrentBrightness) if moniteurs else None
    except Exception:
        return None


def set_brightness(valeur):
    valeur = max(0, min(100, int(valeur)))
    methodes = wmi.WMI(namespace="root\\wmi").WmiMonitorBrightnessMethods()
    if not methodes:
        raise RuntimeError("cet écran ne permet pas le réglage logiciel de la luminosité")
    methodes[0].WmiSetBrightness(Brightness=valeur, Timeout=0)
    return valeur


def change_brightness(delta):
    actuelle = get_brightness()
    if actuelle is None:
        raise RuntimeError("luminosité illisible sur cet écran")
    return actuelle, set_brightness(actuelle + delta)


def demo_luminosite(pas=10, pause=0.6):
    """Baisse la luminosité par paliers puis la remonte à sa valeur d'origine."""
    origine = get_brightness()
    if origine is None:
        raise RuntimeError("luminosité illisible sur cet écran")
    descente = list(range(origine, 9, -pas))
    try:
        for v in descente + descente[::-1]:
            set_brightness(v)
            print(f"  {v} %")
            time.sleep(pause)
    finally:
        set_brightness(origine)


def menu_luminosite():
    saisie = input("[+] augmenter, [-] diminuer, [d] démonstration, ou un nombre 0-100 : ").strip().lower()
    if saisie in ("+", "-"):
        avant, apres = change_brightness(PAS if saisie == "+" else -PAS)
        print(f"Luminosité : {avant} % -> {apres} %" + ("  (limite atteinte)" if avant == apres else ""))
    elif saisie == "d":
        print("Démonstration (ne touche à rien) :")
        demo_luminosite()
        print("Luminosité d'origine restaurée.")
    elif saisie.isdigit() and 0 <= int(saisie) <= 100:
        avant = get_brightness()
        print(f"Luminosité : {avant} % -> {set_brightness(int(saisie))} %")
    else:
        print("Saisie invalide.")


# ===============================================================
# 3. Résolution de l'écran (changement temporaire)
# ===============================================================
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
CDS_FULLSCREEN = 0x00000004   # changement temporaire
ENUM_CURRENT_SETTINGS = -1


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_ulong),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", ctypes.c_ulong),
        ("dmDisplayFixedOutput", ctypes.c_ulong),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort),
        ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong),
        ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong),
        ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong),
        ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong),
        ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong),
        ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong),
        ("dmPanningHeight", ctypes.c_ulong),
    ]


def _nouveau_devmode():
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    return dm


def resolutions_disponibles():
    """Retourne (liste des résolutions compatibles, résolution actuelle)."""
    courant = _nouveau_devmode()
    user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(courant))

    trouvees, dm, i = set(), _nouveau_devmode(), 0
    while user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        if (dm.dmDisplayFrequency == courant.dmDisplayFrequency
                and dm.dmBitsPerPel == courant.dmBitsPerPel
                and dm.dmPelsWidth >= 1024):
            trouvees.add((dm.dmPelsWidth, dm.dmPelsHeight))
        i += 1
    return sorted(trouvees, reverse=True), (courant.dmPelsWidth, courant.dmPelsHeight)


def changer_resolution_temporaire(largeur, hauteur, duree=8):
    """Applique une résolution pendant 'duree' secondes, puis revient à l'ancienne."""
    dm = _nouveau_devmode()
    user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    dm.dmPelsWidth, dm.dmPelsHeight = largeur, hauteur
    dm.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT

    code = user32.ChangeDisplaySettingsW(ctypes.byref(dm), CDS_FULLSCREEN)
    if code != 0:
        raise RuntimeError(f"changement de résolution refusé (code {code})")
    try:
        time.sleep(duree)
    finally:
        user32.ChangeDisplaySettingsW(None, 0)  # retour à la résolution d'origine


def menu_resolution():
    liste, actuelle = resolutions_disponibles()
    print(f"Résolution actuelle : {actuelle[0]} x {actuelle[1]}")
    for i, (larg, haut) in enumerate(liste, 1):
        print(f"  {i}. {larg} x {haut}")
    choix = input("Numéro à tester (Entrée pour annuler) : ").strip()
    if not choix:
        return
    if not choix.isdigit() or not 1 <= int(choix) <= len(liste):
        print("Choix invalide.")
        return
    larg, haut = liste[int(choix) - 1]
    print(f"Passage en {larg} x {haut} pendant 8 secondes, puis retour automatique...")
    changer_resolution_temporaire(larg, haut)
    print("Résolution d'origine restaurée.")


# ===============================================================
# 4. Capture d'écran
# ===============================================================
def capture_ecran():
    from PIL import ImageGrab  # Pillow n'est chargé que si on en a besoin

    os.makedirs("captures_ecran", exist_ok=True)
    nom = datetime.now().strftime("capture_%Y%m%d_%H%M%S.png")
    chemin = os.path.join("captures_ecran", nom)
    ImageGrab.grab(all_screens=True).save(chemin)
    return os.path.abspath(chemin)


# ===============================================================
# 5. Piloter la souris
# ===============================================================
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def position_souris():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def deplacer_souris(x, y, duree=0.6, pas=30):
    """Déplace le curseur de façon fluide jusqu'au point (x, y)."""
    x0, y0 = position_souris()
    for i in range(1, pas + 1):
        user32.SetCursorPos(int(x0 + (x - x0) * i / pas), int(y0 + (y - y0) * i / pas))
        time.sleep(duree / pas)


def demo_souris():
    """Le curseur dessine un rectangle au milieu de l'écran, puis revient."""
    largeur, hauteur = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    depart = position_souris()
    for fx, fy in [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.25, 0.25)]:
        deplacer_souris(int(largeur * fx), int(hauteur * fy))
    deplacer_souris(*depart)


# ===============================================================
# 6. Piloter le clavier (saisie automatique dans le Bloc-notes)
# ===============================================================
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _UNION_INPUT(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _UNION_INPUT)]


def _envoyer_caractere(caractere):
    for drapeaux in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
        entree = INPUT(type=INPUT_KEYBOARD,
                       u=_UNION_INPUT(ki=KEYBDINPUT(0, ord(caractere), drapeaux, 0, None)))
        user32.SendInput(1, ctypes.byref(entree), ctypes.sizeof(INPUT))


def demo_clavier(texte="Controle automatique de l'ecran : test reussi."):
    """Ouvre le Bloc-notes et y tape un texte automatiquement."""
    subprocess.Popen(["notepad.exe"])
    time.sleep(3)  # laisse le temps au Bloc-notes de s'ouvrir
    for caractere in texte:
        _envoyer_caractere(caractere)
        time.sleep(0.05)


# ===============================================================
# 7. Fenêtres : plein écran et affichage du bureau
# ===============================================================
def plein_ecran_fenetre_active(attente=3):
    """Maximise la fenêtre active au bout de 'attente' secondes."""
    time.sleep(attente)
    fenetre = user32.GetForegroundWindow()
    if not fenetre:
        raise RuntimeError("aucune fenêtre active trouvée")
    user32.ShowWindow(fenetre, 3)  # 3 = SW_MAXIMIZE


def afficher_bureau():
    """Réduit toutes les fenêtres (Windows + D). Refaire l'action les restaure."""
    VK_LWIN, VK_D = 0x5B, 0x44
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_D, 0, 0, 0)
    user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


# ===============================================================
# 8. Verrouillage et extinction de l'écran
# ===============================================================
def verrouiller_ecran():
    user32.LockWorkStation()


def eteindre_ecran(delai=2):
    """Éteint l'écran (il se rallume au mouvement de la souris)."""
    time.sleep(delai)
    HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF = 0xFFFF, 0x0112, 0xF170, 2
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)


# ===============================================================
# 9. Langue de saisie (disposition du clavier)
# ===============================================================
WM_INPUTLANGCHANGEREQUEST = 0x0050
LOCALE_SLOCALIZEDDISPLAYNAME = 0x00000002

_u32 = ctypes.WinDLL("user32")
_u32.GetForegroundWindow.restype = ctypes.c_void_p
_u32.GetKeyboardLayout.restype = ctypes.c_void_p
_u32.GetKeyboardLayout.argtypes = [ctypes.c_ulong]
_u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_u32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
_u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]


def _nom_langue(hkl):
    """Nom lisible d'une langue de saisie (ex. : français (France))."""
    langid = (hkl or 0) & 0xFFFF
    tampon = ctypes.create_unicode_buffer(128)
    ctypes.windll.kernel32.GetLocaleInfoW(langid, LOCALE_SLOCALIZEDDISPLAYNAME, tampon, 128)
    return tampon.value or f"langue {langid:#06x}"


def langue_courante():
    fenetre = _u32.GetForegroundWindow()
    fil = _u32.GetWindowThreadProcessId(fenetre, None)
    return _u32.GetKeyboardLayout(fil)


def langues_installees():
    n = _u32.GetKeyboardLayoutList(0, None)
    tampon = (ctypes.c_void_p * n)()
    _u32.GetKeyboardLayoutList(n, tampon)
    return list(tampon)


def changer_langue(hkl):
    """Demande à la fenêtre active de passer à la langue de saisie choisie."""
    fenetre = _u32.GetForegroundWindow()
    if not fenetre:
        raise RuntimeError("aucune fenêtre active trouvée")
    _u32.PostMessageW(fenetre, WM_INPUTLANGCHANGEREQUEST, 0, hkl)


def menu_langue():
    langues = langues_installees()
    courante = langue_courante()
    print(f"Langue de saisie actuelle : {_nom_langue(courante)}")
    for i, hkl in enumerate(langues, 1):
        marque = "   <- actuelle" if hkl == courante else ""
        print(f"  {i}. {_nom_langue(hkl)}{marque}")

    if len(langues) < 2:
        print("Une seule langue est installée. Ajoute-en une dans Paramètres > "
              "Heure et langue > Langue et région.")
        return

    choix = input("Numéro de la langue (Entrée pour annuler) : ").strip()
    if not choix:
        return
    if not choix.isdigit() or not 1 <= int(choix) <= len(langues):
        print("Choix invalide.")
        return

    changer_langue(langues[int(choix) - 1])
    time.sleep(0.5)
    print(f"Langue de saisie : {_nom_langue(langue_courante())}")


# ===============================================================
# 10. Son (volume, muet, test sonore)
# ===============================================================
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF


def _touche_media(vk, fois=1):
    """Simule l'appui sur une touche multimédia (chaque appui = environ 2 %)."""
    for _ in range(fois):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)


def augmenter_volume(pourcent=10):
    _touche_media(VK_VOLUME_UP, pourcent // 2)


def diminuer_volume(pourcent=10):
    _touche_media(VK_VOLUME_DOWN, pourcent // 2)


def basculer_muet():
    _touche_media(VK_VOLUME_MUTE)


def definir_volume(pourcent):
    """Ramène le volume à 0 puis le monte jusqu'au niveau demandé (environ)."""
    _touche_media(VK_VOLUME_DOWN, 50)
    _touche_media(VK_VOLUME_UP, pourcent // 2)


def test_sonore():
    """Joue trois notes pour vérifier que le son fonctionne."""
    for frequence in (440, 554, 659):
        winsound.Beep(frequence, 300)


def menu_son():
    saisie = input("[+] augmenter, [-] diminuer, [m] muet/rétablir, "
                   "[t] test sonore, ou un nombre 0-100 : ").strip().lower()
    if saisie == "+":
        augmenter_volume()
        print("Volume +10 %.")
    elif saisie == "-":
        diminuer_volume()
        print("Volume -10 %.")
    elif saisie == "m":
        basculer_muet()
        print("Son coupé ou rétabli (bascule).")
    elif saisie == "t":
        test_sonore()
        print("Test sonore terminé.")
    elif saisie.isdigit() and 0 <= int(saisie) <= 100:
        definir_volume(int(saisie))
        print(f"Volume réglé à environ {saisie} %.")
    else:
        print("Saisie invalide.")


# ===============================================================
# 11. Wi-Fi, Bluetooth, mode avion, économiseur de batterie
# ===============================================================
_PS_RADIOS = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($task, $type) {
    $netTask = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($task))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
"""


def _powershell(script):
    """Exécute un script Windows PowerShell et retourne sa sortie texte."""
    script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;\n" + script
    encode = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encode],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "commande PowerShell en échec")
    return r.stdout.strip()


def lister_radios():
    """Retourne la liste des radios sous la forme [(type, nom, état)]."""
    sortie = _powershell(_PS_RADIOS + '$radios | ForEach-Object { "$($_.Kind)|$($_.Name)|$($_.State)" }')
    radios = []
    for ligne in sortie.splitlines():
        parties = ligne.split("|")
        if len(parties) == 3:
            radios.append(tuple(parties))
    return radios


def regler_radio(type_radio, allumer):
    """Active ou désactive la radio d'un type donné (WiFi, Bluetooth...)."""
    etat = "On" if allumer else "Off"
    script = _PS_RADIOS + (
        "$trouve = $false\n"
        f"foreach ($r in $radios) {{ if ($r.Kind -eq '{type_radio}') {{ $trouve = $true; "
        f"Await ($r.SetStateAsync('{etat}')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null }} }}\n"
        "if (-not $trouve) { Write-Output 'ABSENT' }"
    )
    if _powershell(script) == "ABSENT":
        raise RuntimeError(f"aucune radio {type_radio} trouvée sur cette machine")


def mode_avion(activer):
    """Coupe (ou rétablit) toutes les radios : reproduit l'effet du mode avion."""
    types = {t for t, _, _ in lister_radios() if t in ("WiFi", "Bluetooth", "MobileBroadband")}
    if not types:
        raise RuntimeError("aucune radio détectée")
    for t in sorted(types):
        regler_radio(t, not activer)


def seuil_economiseur():
    """Seuil d'activation automatique de l'économiseur de batterie (0 à 100)."""
    r = subprocess.run(
        ["powercfg", "/query", "SCHEME_CURRENT", "SUB_ENERGYSAVER", "ESBATTTHRESHOLD"],
        capture_output=True, text=True,
    )
    valeurs = re.findall(r"0x[0-9a-fA-F]{8}", r.stdout)
    if r.returncode != 0 or not valeurs:
        raise RuntimeError("réglage de l'économiseur non disponible sur ce PC")
    return int(valeurs[-1], 16)


def regler_economiseur(seuil):
    """100 = actif dès que l'on est sur batterie, 0 = jamais."""
    commandes = (
        ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_ENERGYSAVER", "ESBATTTHRESHOLD", str(seuil)],
        ["powercfg", "/setactive", "SCHEME_CURRENT"],
    )
    for commande in commandes:
        r = subprocess.run(commande, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip() or "powercfg a échoué")


def _libelle_etat(etat):
    return {"On": "activé", "Off": "désactivé"}.get(etat, "indisponible")


def _libelle_seuil(seuil):
    if seuil is None:
        return "indisponible"
    if seuil == 0:
        return "jamais activé automatiquement"
    if seuil >= 100:
        return "activé dès que tu es sur batterie"
    return f"activé sous {seuil} % de batterie"


def _demander_activation():
    reponse = input("[a] activer, [d] désactiver : ").strip().lower()
    return True if reponse == "a" else False if reponse == "d" else None


def _confirmer(message):
    return input(f"{message} (o/N) : ").strip().lower() == "o"


def menu_connectivite():
    while True:
        try:
            etats = {t: e for t, _, e in lister_radios()}
        except Exception as e:
            etats = {}
            print(f"(lecture des radios impossible : {e})")
        try:
            seuil = seuil_economiseur()
        except Exception:
            seuil = None

        print("\n" + "-" * 52)
        print(" WI-FI, BLUETOOTH, MODE AVION, ÉCONOMISEUR")
        print(f" Wi-Fi : {_libelle_etat(etats.get('WiFi'))}   Bluetooth : {_libelle_etat(etats.get('Bluetooth'))}")
        print(f" Économiseur de batterie : {_libelle_seuil(seuil)}")
        print("-" * 52)
        print(" 1. Wi-Fi")
        print(" 2. Bluetooth")
        print(" 3. Mode avion")
        print(" 4. Économiseur de batterie")
        print(" 0. Retour")
        choix = input("Votre choix : ").strip()

        try:
            if choix == "1":
                action = _demander_activation()
                if action is None:
                    print("Action invalide.")
                elif action or _confirmer("Désactiver le Wi-Fi coupe ta connexion Internet. Continuer ?"):
                    regler_radio("WiFi", action)
                    print("Wi-Fi activé." if action else "Wi-Fi désactivé. Pense à le réactiver.")
            elif choix == "2":
                action = _demander_activation()
                if action is None:
                    print("Action invalide.")
                else:
                    regler_radio("Bluetooth", action)
                    print("Bluetooth activé." if action else "Bluetooth désactivé.")
            elif choix == "3":
                action = _demander_activation()
                if action is None:
                    print("Action invalide.")
                elif not action or _confirmer("Le mode avion coupe le Wi-Fi et le Bluetooth. Continuer ?"):
                    mode_avion(action)
                    print("Mode avion activé." if action else "Mode avion désactivé (radios rétablies).")
            elif choix == "4":
                saisie = input("[a] activer sur batterie, [d] désactiver, ou un seuil 0-100 : ").strip().lower()
                if saisie == "a":
                    regler_economiseur(100)
                elif saisie == "d":
                    regler_economiseur(0)
                elif saisie.isdigit() and 0 <= int(saisie) <= 100:
                    regler_economiseur(int(saisie))
                else:
                    print("Saisie invalide.")
                    continue
                print(f"Économiseur de batterie : {_libelle_seuil(seuil_economiseur())}.")
            elif choix == "0":
                break
            else:
                print("Choix invalide.")
        except Exception as e:
            print(f"Erreur : {e}")


# ===============================================================
# Menu
# ===============================================================
def menu_ecran():
    while True:
        print("\n" + "=" * 52)
        print(" CONTRÔLE DE L'ÉCRAN")
        print("=" * 52)
        print("  1. Informations de l'écran")
        print("  2. Luminosité")
        print("  3. Changer la résolution (temporaire)")
        print("  4. Capturer l'écran")
        print("  5. Piloter la souris (démonstration)")
        print("  6. Piloter le clavier (Bloc-notes)")
        print("  7. Mettre la fenêtre active en plein écran")
        print("  8. Afficher le bureau (Windows + D)")
        print("  9. Verrouiller la session")
        print(" 10. Éteindre l'écran")
        print(" 11. Changer la langue de saisie (clavier)")
        print(" 12. Son (volume, muet, test sonore)")
        print(" 13. Activation/Desactivation de Wi-Fi, Bluetooth, mode avion, économiseur")
        print("  0. Retour")
        choix = input("Votre choix : ").strip()

        try:
            if choix == "1":
                afficher_infos()
            elif choix == "2":
                menu_luminosite()
            elif choix == "3":
                menu_resolution()
            elif choix == "4":
                print(f"Capture enregistrée : {capture_ecran()}")
            elif choix == "5":
                print("La souris va dessiner un rectangle ")
                demo_souris()
                print("Terminé.")
            elif choix == "6":
                print("Ouverture du Bloc-notes, puis saisie automatique ")
                demo_clavier()
                print("Terminé.")
            elif choix == "7":
                print("Clique sur la fenêtre à agrandir : maximisation dans 3 secondes...")
                plein_ecran_fenetre_active()
                print("Fenêtre maximisée.")
            elif choix == "8":
                afficher_bureau()
                print("Bureau affiché (refais l'action pour tout restaurer).")
            elif choix == "9":
                if input("Verrouiller la session maintenant ? (o/N) : ").strip().lower() == "o":
                    verrouiller_ecran()
            elif choix == "10":
                print("L'écran s'éteint dans 2 secondes (bouge la souris pour le rallumer).")
                eteindre_ecran()
            elif choix == "11":
                menu_langue()
            elif choix == "12":
                menu_son()
            elif choix == "13":
                menu_connectivite()
            elif choix == "0":
                break
            else:
                print("Choix invalide.")
        except Exception as e:
            print(f"Erreur : {e}")


if __name__ == "__main__":
    menu_ecran()
