# Tesla Media / TeslaVideoPlayer

De actuele gebruikersapplicatie. Zie [de hoofd-README](../README.md) voor installatie, accounts, tests en bronbeheer.

## Structuur

- `server.mjs`: HTTP-server, authenticatie, bronnen per gebruiker en eigenaarscontrole voor afspeelsessies.
- `store.mjs`: SQLite, scrypt-wachtwoorden, sessies, versleutelde brongegevens, voorkeuren, favorieten en kijkposities.
- `plex.mjs`: Plex-aanmelding, serverkoppelingen, metadata, bibliotheken, afbeeldingen en tijdlijnupdates.
- `network.mjs`: begrensde bronverzoeken en controle van bronadressen.
- `playback.mjs` / `media.mjs`: één FFmpeg-bronverbinding voor beeld en audio, kwaliteitsprofielen en herstel.
- `static/player.js`: canvas- en GPU-weergave, audio, frames overslaan en hervatten.
- `static/app.js`: accounts, TV, Plex, Instellingen en navigatie.
- `test-support/`: lokale testbronnen zonder persoonlijke gegevens.
- `deploy/`: voorbeelden voor systemd en Nginx.

## Data en secrets

De code bevat geen M3U-adres, Plex-token of bestaand gebruikerswachtwoord. Gebruikers voegen hun eigen bronnen toe. De database en encryptiesleutel staan buiten de repository in `DATA_DIR` of lokaal in de genegeerde map `data/`.

De service heeft schrijfrechten nodig voor `DATA_DIR`, waaronder de SQLite WAL-bestanden. Het meegeleverde systemd-voorbeeld gebruikt daarvoor `StateDirectory=tv-stream-lab`. Maak bij backups een consistente kopie van de database inclusief de encryptiesleutel. Wachtwoorden worden uitsluitend als gesalte scrypt-hash opgeslagen.

## Afspeelgedrag

De standaard is ImageBitmap, 540p en 20 fps. Elke gebruiker kan de methode en standaardkwaliteit wijzigen. De speler kan resolutie en framerate tijdens afspelen veranderen; Plex hervat op de huidige positie. De onderliggende bron bepaalt de werkelijke details, beschikbare audio en unieke frames.

Audio loopt via een audio-element, beeld via canvas. Een beëindigde of vastgelopen audioklok houdt het beeld niet permanent tegen. Live-bronnen krijgen automatische herverbindingspogingen; VOD-bestanden eindigen normaal. Stoppen en uitloggen ruimen afspeelsessies op.

Plex vereist een eigen account en een bereikbare Plex Media Server. Koppelen kan via de Plex-aanmeldpagina of handmatig met serveradres en token. De app bewaart kijkposities per gebruiker en meldt de tijdlijn ook aan Plex. Er is geen wachtwoordherstel via e-mail en er zijn geen ondertitelselectie- of castfuncties geïmplementeerd.
