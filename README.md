# TeslaVideoPlayer

Een persoonlijke mediaspeler met een minimalistische, op Tesla geïnspireerde interface. Beeld wordt op canvas getekend; geluid loopt via een audio-element. Er wordt geen video-element gebruikt.

- Persoonlijke accounts met serveropslag voor instellingen, speellijsten en favorieten.
- TV: meerdere M3U-speellijsten, zoeken, groepen, kanaalkaarten met logo’s en een aparte speler met favorieten.
- Plex: aanmelden met Plex of handmatig verbinden, bibliotheken, films, series, afleveringen, zoeken en verder kijken.
- Vier afspeelmethodes: ImageBitmap, MJPEG, WebCodecs en WebGL.
- Resoluties 360p–1080p en 20–60 fps, ook tijdens het kijken aanpasbaar. Standaard 540p / 20 fps.
- Menu onderaan met TV, Plex en Instellingen; speler over de volledige browserbreedte.

## Lokaal starten

Vereist: Node.js 22.13 of nieuwer en FFmpeg met libvpx, MJPEG, libmp3lame en de benodigde brondecoders. De server heeft geen npm-afhankelijkheden.

```sh
npm start
```

Open http://localhost:8765. Maak een account en voeg je eigen M3U-lijst of Plex-verbinding toe in Instellingen. Bij het klonen zijn er geen accounts, tokens of standaardlijsten aanwezig.

Voor een andere poort:

```sh
PORT=8000 npm start
```

Accounts en versleutelde brongegevens staan standaard in `stream-lab/data/`. Met `DATA_DIR` kies je een andere locatie. Deze directory, databases, sleutels en lokale instellingen zijn uitgesloten van Git. Bewaar voor een backup de database én `secret.key` samen.

## Beheerdersaccount

Een normaal account kan publieke bronadressen gebruiken. Een beheerdersaccount kan ook een Plex-server op het lokale netwerk bereiken. Maak dit account op de server met de bootstrapopdracht; geef de gegevens via stdin in een privébestand door:

```sh
node stream-lab/bootstrap.mjs < /privaat/account.json
```

Het JSON-bestand bevat `username`, `name` en `password`. Bestaande accounts en wachtwoorden worden niet overschreven. Neem dit bestand niet op in je repository.

## Testen

```sh
npm test
npm --prefix verify ci
npm run test:e2e
```

De integratietests controleren onder meer gebruikersisolatie, versleutelde opslag, favorieten na een serverherstart, kanaallogo’s, Plex-bibliotheken en afspeelposities, verbindingsherstel en echte FFmpeg-uitvoer. De browsertests gebruiken Chrome en lokale testmedia.

## Implementatie en hosting

De huidige applicatie staat in `stream-lab/`. Service- en Nginx-voorbeelden staan in `stream-lab/deploy/`. Gebruik HTTPS voor WebCodecs en beveiligde sessiecookies. Laat Nginx streamingverkeer zonder buffering doorgeven. Geef de service een schrijfbare `DATA_DIR`; applicatiecode kan alleen-lezen blijven.

`index.html` en `rust-server/` zijn eerdere experimenten en maken geen deel uit van de huidige gebruikersapp.
