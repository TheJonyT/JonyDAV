import requests
import os
import sys
import urllib.parse
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET

#------------------------------------------------------------------------------
#                               Gobal Variablen
#------------------------------------------------------------------------------

server_url = None
username = None
password = None

remote_directory_path = None
local_directory_path = None

#------------------------------------------------------------------------------
#                               Methoden
#------------------------------------------------------------------------------

def read_config():
    """
    Liest die Konfiguration aus der Datei 'jonydav.config' im Root-Verzeichnis des Skripts.
    Falls die Datei nicht existiert, wird sie erstellt und mit Standard-Variablen und Anweisungen befüllt.
    Die Werte werden als globale Variablen im Skript verfügbar gemacht.
    """
    config_filename = "jonydav.config"
    
    # Prüfen, ob die Konfigurationsdatei existiert
    if not os.path.exists(config_filename):
        print("Konfigurationsdatei nicht gefunden. Erstelle eine neue jonydav.config Datei...")
        
        # Standard-Inhalt der neuen Konfigurationsdatei
        config_content = """# Konfiguration für Nextcloud WebDAV Zugriff
# Geben Sie die vollständige URL Ihres Nextcloud-Servers an
server_url = https://Ihr-Server/remote.php/dav/files/IhrBenutzername

# Geben Sie Ihren Nextcloud-Benutzernamen an
username = IhrBenutzername

# Geben Sie Ihr Passwort an (Hinweis: In der Praxis sicherer Umgang empfohlen)
password = IhrPasswort

# Geben Sie den Remote-Stammverzeichnispfad an, relativ zur URL
remote_directory_path = /Pfad/auf/dem/Server

# Geben Sie das lokale Verzeichnis an, von dem Dateien hochgeladen werden sollen
local_directory_path = /Pfad/zum/lokalen/Verzeichnis
"""

        # Erstellen und Schreiben der Konfigurationsdatei
        with open(config_filename, "w") as config_file:
            config_file.write(config_content)
        
        print(f"Die Konfigurationsdatei '{config_filename}' wurde erstellt. Bitte füllen Sie die Werte aus und starten Sie das Skript erneut.")
        sys.exit()
        

    # Konfigurationsdatei existiert, nun die Werte einlesen
    global server_url, username, password, remote_directory_path, local_directory_path

    try:
        with open(config_filename, "r") as config_file:
            for line in config_file:
                line = line.strip()
                if line and not line.startswith("#"):  # Leerzeilen und Kommentare überspringen
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Setze die Werte der Variablen
                    if key == "server_url":
                        server_url = value
                    elif key == "username":
                        username = value
                    elif key == "password":
                        password = value
                    elif key == "remote_directory_path":
                        remote_directory_path = value
                    elif key == "local_directory_path":
                        local_directory_path = value
        
        print("Konfiguration erfolgreich geladen.")

    except Exception as e:
        print(f"Fehler beim Lesen der Konfigurationsdatei: {e}")
        sys.exit()

def connect_to_nextcloud(server_url, username, password):
   
    try:
        # Senden einer PROPFIND-Anfrage, um das Wurzelverzeichnis zu überprüfen
        response = requests.request(
            method="PROPFIND",
            url=server_url,
            auth=HTTPBasicAuth(username, password),
            headers={"Depth": "0"}  # Nur das aktuelle Verzeichnis abfragen
        )

        # Prüfen, ob der Statuscode 207 Multi-Status ist (erfolgreiche PROPFIND-Antwort)
        if response.status_code == 207:
            print("Verbindung erfolgreich!")
            return True
        else:
            print(f"Fehler bei der Verbindung: HTTP-Statuscode {response.status_code}")
            sys.exit()
            

    except requests.exceptions.RequestException as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        sys.exit()
        
    
def list_files_in_remote_directory(server_url, username, password, remote_directory_path):
    """
    Listet alle Dateien und Unterverzeichnisse in einem bestimmten Verzeichnis des Nextcloud-Servers auf,
    einschließlich aller Inhalte in tieferen Ebenen (rekursiv), dekodiert URL-encodierte Zeichen
    und bereinigt den remote root-Pfad.

    Args:
        server_url (str): Die URL des Nextcloud-Servers.
        username (str): Der Benutzername für die Authentifizierung.
        password (str): Das Passwort für die Authentifizierung.
        remote_directory_path (str): Der Pfad des Verzeichnisses, das durchsucht werden soll (relativ zur root).

    Returns:
        list: Eine Liste von Dateien und Verzeichnissen im angegebenen Verzeichnis und allen Unterverzeichnissen,
              bereinigt um den Remote root-Pfad.
    """
    try:
        # Erstellen der vollständigen URL zum Verzeichnis
        full_url = f"{server_url}/{remote_directory_path.strip('/')}/"

        # Senden der PROPFIND-Anfrage mit Depth: infinity
        response = requests.request(
            method="PROPFIND",
            url=full_url,
            auth=HTTPBasicAuth(username, password),
            headers={"Depth": "infinity"}  # Abfragen aller Inhalte, unabhängig von der Tiefe
        )

        # Prüfen, ob die Anfrage erfolgreich war (Statuscode 207 = Multi-Status)
        if response.status_code != 207:
            print(f"Fehler beim Abrufen der Verzeichnisliste: HTTP-Statuscode {response.status_code}")
            return []

        # XML-Antwort parsen
        files_and_dirs = []
        root = ET.fromstring(response.content)

        # Kombinierter Root-Pfad, den wir entfernen wollen
        base_server_url = server_url.split("/", 3)[:3]
        base_server_url = "/".join(base_server_url)
        remote_root_path = f"{server_url.replace(base_server_url,'')}/{remote_directory_path.strip('/')}" # Quickfix weil das zurückgegebene XML Element die Base Url schon entfernt hat.

        # Durchlaufen der XML-Elemente, um die Dateien und Verzeichnisse zu extrahieren
        for response_element in root.findall("{DAV:}response"):
            # Extrahiere den Dateipfad
            href_element = response_element.find("{DAV:}href")
            if href_element is not None:
                # URL-dekodierung des Pfades
                file_path = urllib.parse.unquote(href_element.text)

                # Entfernen des Remote-Root-Pfades und Normalisierung des Pfades
                relative_path = file_path.replace(remote_root_path, '').strip('/').replace("\\", "/")
                
                # Nur die bereinigten Pfade speichern, keine leeren Einträge
                if relative_path:  
                    files_and_dirs.append(relative_path)

        return files_and_dirs

    except requests.exceptions.RequestException as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        return []
    
def list_files_in_local_directory(local_directory_path):
    """
    Listet alle Dateien und Unterverzeichnisse in einem bestimmten lokalen Verzeichnis auf,
    einschließlich aller Inhalte in tieferen Ebenen (rekursiv) und bereinigt um das Root-Verzeichnis.

    Args:
        local_directory_path (str): Der Pfad des lokalen Verzeichnisses.

    Returns:
        list: Eine Liste von Dateien und Verzeichnissen im angegebenen Verzeichnis und allen Unterverzeichnissen,
              bereinigt um das lokale root-Verzeichnis.
    """
    files_and_dirs = []

    # Durchlaufen des Verzeichnisses und aller Unterverzeichnisse
    for root, dirs, files in os.walk(local_directory_path):
        # Füge alle Unterverzeichnisse zur Liste hinzu
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            # Bereinigen des Root-Verzeichnisses und Normalisierung des Pfades
            relative_path = os.path.relpath(dir_path, local_directory_path).replace("\\", "/")
            files_and_dirs.append(relative_path)

        # Füge alle Dateien zur Liste hinzu
        for file_name in files:
            file_path = os.path.join(root, file_name)
            # Bereinigen des Root-Verzeichnisses und Normalisierung des Pfades
            relative_path = os.path.relpath(file_path, local_directory_path).replace("\\", "/")
            files_and_dirs.append(relative_path)

    return files_and_dirs
    
def compare_remote_and_local_directories(local_list, remote_list):

    """
    Vergleicht die lokalen und remote Verzeichnis- und Dateilisten und erstellt zwei Listen:
    - missing_folders: Verzeichnisse, die lokal vorhanden sind, aber auf dem Remote-Server fehlen.
    - missing_files: Dateien, die lokal vorhanden sind, aber auf dem Remote-Server fehlen.

    Args:
        local_list (list): Die Liste aller lokalen Dateien und Verzeichnisse (relative Pfade).
        remote_list (list): Die Liste aller Dateien und Verzeichnisse auf dem Remote-Server (relative Pfade).

    Returns:
        tuple: Zwei Listen:
            - missing_folders: Verzeichnisse, die auf dem Remote-Server fehlen.
            - missing_files: Dateien, die auf dem Remote-Server fehlen.
    """
    missing_folders = []
    missing_files = []

    # Filtere die lokalen Verzeichnisse und Dateien
    local_folders = [item for item in local_list if not '.' in item]  # Verzeichnisse haben keinen Punkt (z.B. ".txt")
    local_files = [item for item in local_list if '.' in item]  # Dateien haben einen Punkt im Namen (z.B. ".txt")

    # Filtere die remote Verzeichnisse und Dateien
    remote_folders = [item for item in remote_list if not '.' in item]
    remote_files = [item for item in remote_list if '.' in item]

    # Vergleiche die Verzeichnisse und finde die fehlenden Ordner
    for folder in local_folders:
        if folder not in remote_folders:
            missing_folders.append(folder)

    # Vergleiche die Dateien und finde die fehlenden Dateien
    for file in local_files:
        if file not in remote_files:
            missing_files.append(file)

    return missing_folders, missing_files

def create_missing_folders(server_url, username, password, missing_folders_list):
    """
    Erstellt die fehlenden Verzeichnisse auf dem Nextcloud-Server basierend auf der missing_folders_list.

    Args:
        server_url (str): Die URL des Nextcloud-Servers (Basis-URL).
        username (str): Der Benutzername für die Authentifizierung.
        password (str): Das Passwort für die Authentifizierung.
        missing_folders_list (list): Eine Liste von Verzeichnissen, die erstellt werden müssen (relative Pfade).
    """
    for folder in missing_folders_list:
        # Erstellen der vollständigen URL für das zu erstellende Verzeichnis
        full_url = f"{server_url}/{remote_directory_path.strip('/')}/{folder.strip('/')}/"

        try:
            # Senden der MKCOL-Anfrage, um das Verzeichnis zu erstellen
            response = requests.request(
                method="MKCOL",
                url=full_url,
                auth=HTTPBasicAuth(username, password)
            )

            # Überprüfen, ob die Erstellung erfolgreich war (Statuscode 201 = Created)
            if response.status_code == 201:
                print(f"Verzeichnis erfolgreich erstellt: {folder}")
            elif response.status_code == 405:
                print(f"Verzeichnis existiert bereits: {folder}")
            else:
                print(f"Fehler beim Erstellen des Verzeichnisses {folder}: HTTP-Statuscode {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"Ein Fehler ist beim Erstellen des Verzeichnisses {folder} aufgetreten: {e}")

def upload_missing_files(server_url, username, password, local_directory_path, missing_files_list):
    """
    Lädt fehlende Dateien auf den Nextcloud-Server basierend auf der missing_files_list hoch.
    Dateien werden in den richtigen Verzeichnissen abgelegt, die Uploads erfolgen nacheinander.

    Args:
        server_url (str): Die URL des Nextcloud-Servers (Basis-URL).
        username (str): Der Benutzername für die Authentifizierung.
        password (str): Das Passwort für die Authentifizierung.
        local_directory_path (str): Der lokale Pfad des Verzeichnisses, in dem sich die Dateien befinden.
        missing_files_list (list): Eine Liste von Dateien (mit Pfaden), die hochgeladen werden müssen (relative Pfade).
    """
    uploaded_files_count = 0

    for file in missing_files_list:
        # Erstellen des lokalen Pfads zur Datei
        local_file_path = os.path.join(local_directory_path, file)

        # Sicherstellen, dass der lokale Pfad korrekt ist (Backslashes durch Slashes ersetzen)
        local_file_path = local_file_path.replace("\\", "/")

        # Erstellen der vollständigen URL für den Upload
        full_url = f"{server_url}/{remote_directory_path.strip('/')}/{file.strip('/')}/"

        try:
            # Datei öffnen und hochladen
            with open(local_file_path, 'rb') as f:
                response = requests.put(
                    full_url,
                    data=f,
                    auth=HTTPBasicAuth(username, password)
                )

            # Prüfen, ob der Upload erfolgreich war (Statuscode 201 = Created)
            if response.status_code == 201:
                print(f"Datei erfolgreich hochgeladen ({uploaded_files_count + 1} / {len(missing_files_list)}): {file}")

                uploaded_files_count += 1
            else:
                print(f"Fehler beim Hochladen der Datei {file}: HTTP-Statuscode {response.status_code}")

        except FileNotFoundError:
            print(f"Datei nicht gefunden: {local_file_path}")
        except requests.exceptions.RequestException as e:
            print(f"Ein Fehler ist beim Hochladen der Datei {file} aufgetreten: {e}")

    # Zusammenfassung des Uploads
    print("")
    print("---UPLOAD REPORT---")
    print(f"Upload abgeschlossen. {uploaded_files_count} von {len(missing_files_list)} Dateien wurden erfolgreich hochgeladen.")

    
    
    
    

#------------------------------------------------------------------------------
#                               Hauptprogramm
#------------------------------------------------------------------------------

read_config()

is_connected = connect_to_nextcloud(server_url, username, password)
    
remote_directory_list = list_files_in_remote_directory(server_url, username, password, remote_directory_path)

local_directory_list = list_files_in_local_directory(local_directory_path)

missing_folders_list, missing_files_list  = compare_remote_and_local_directories(local_directory_list, remote_directory_list)


print("---LOCAL LIST---")
print(local_directory_list)
print("")
print("---REMOTE LIST---")
print(remote_directory_list)
print("")
print("---MISSING FOLDERS LIST---")
print(missing_folders_list)
print("")
print("---MISSING FILES LIST---")
print(missing_files_list)
print("")
print("")
print("---CREATE FOLDER PHASE---")
create_missing_folders(server_url, username, password, missing_folders_list)
print("")
print("")
print("---FILE UPLOAD PHASE---")
upload_missing_files(server_url, username, password, local_directory_path, missing_files_list)


