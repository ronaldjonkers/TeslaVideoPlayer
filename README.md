# Tesla Media · TeslaVideoPlayer

Een persoonlijke mediaspeler, vernoemd naar Nikola Tesla. TV, Plex en optioneel YouTube komen samen in een rustige interface met een menu onderaan. Beeld wordt op canvas getekend; geluid loopt via een audio-element. Er wordt geen video-element gebruikt.

## Wat je krijgt

- Een persoonlijke homepage met recent bekeken kanalen en video’s.
- Eigen accounts, M3U-lijsten, favorieten, kijkgeschiedenis en standaardvoorkeuren op de server.
- TV-kaarten met logo’s, zoeken en groepen; een aparte brede speler met favorieten eronder.
- Plex-bibliotheken met posters, films/series/afleveringen, zoeken en hervatten.
- Optioneel YouTube zoeken en afspelen via dezelfde canvas-/audioroute, inclusief spoelen en geschiedenis.
- ImageBitmap, MJPEG, WebCodecs en WebGL; 360p–1080p en 20–60 fps. Standaard **540p / 20 fps**.
- Kwaliteit wijzigen tijdens het kijken; een minimalistische interface voor desktop en mobiel.

De repo bevat geen bestaande accounts, M3U-inloggegevens of Plex-tokens. Netflix is niet geïntegreerd: daarvoor is geen werkende afspeelroute in deze architectuur gebouwd.

## Een Linux-server instellen

```sh
git clone git@github.com:ronaldjonkers/TeslaVideoPlayer.git
cd TeslaVideoPlayer
sudo sh install.sh \
  --domain media.example.com \
  --email beheerder@example.com \
  --admin beheerder \
  --youtube
```

Vervang domein en e-mailadres. Het wachtwoord wordt verborgen gevraagd. Laat `--youtube` weg wanneer je die integratie niet nodig hebt.

De installer detecteert **apt, dnf, yum, zypper, pacman, apk, xbps en emerge**, en **systemd, OpenRC of runit**. Hij controleert Node/SQLite en FFmpeg-codecs, kiest een vrije lokale poort, detecteert Caddy/Nginx, bewaart bestaande sites en regelt waar mogelijk HTTPS en certificaatvernieuwing. Extra codec-repositories zijn een expliciete optie.

Niet iedere historische Linux-release of maatwerkconfiguratie kan automatisch worden ingericht. Ondersteuning en testgrenzen staan in de [installatiehandleiding](docs/INSTALLATION.md). Voor afwijkende/immutable systemen is ook [Docker Compose](docs/INSTALLATION.md#containers) beschikbaar.

Eerst een plan zonder wijzigingen bekijken:

```sh
sh install.sh --plan --domain media.example.com --email beheerder@example.com
```

## Documentatie

| Handleiding | Inhoud |
|---|---|
| [Installatie](docs/INSTALLATION.md) | Distributies, dependencies, Caddy/Nginx-detectie, TLS, opties, containers en updates |
| [Gebruik](docs/USAGE.md) | Accounts, homepage, TV, favorieten, kwaliteit en Plex-posters |
| [Beheer](docs/OPERATIONS.md) | Services, logs, instellingen, backups, herstel en wachtwoordrecovery |
| [Reverse proxy](docs/REVERSE-PROXY.md) | Handmatige Nginx/Caddy-configuraties en streamingheaders |
| [Integraties](docs/INTEGRATIONS.md) | Plex en YouTube, advertentiegedrag, beperkingen en Netflix |
| [Problemen oplossen](docs/TROUBLESHOOTING.md) | Gerichte controles en wat de tests wel/niet aantonen |
| [Plex subtitles](docs/SUBTITLES.md) | Subtitle selection, language preferences and supported formats |
| [Code-indeling](stream-lab/README.md) | Onderdelen van de applicatie |

## Lokaal ontwikkelen

Vereist: Node.js **22.13+** en FFmpeg met `libvpx`, `mjpeg`, `libmp3lame` en de benodigde brondecoders. Er zijn geen npm-runtimeafhankelijkheden.

```sh
npm start
```

Open http://localhost:8765 en maak een account. `PORT=8000 npm start` kiest een andere poort. Voeg je eigen bronnen toe in Instellingen. De YouTube-functie verschijnt alleen als `YT_DLP_PATH` naar een geschikte helper wijst.

Gegevens staan standaard in `stream-lab/data/`, of in `DATA_DIR`. De directory en encryptiesleutel zijn uitgesloten van Git. Bewaar voor backups de **database én `secret.key`** samen.

## Testen

```sh
npm test
python3 -m unittest discover -s tests -v
npm --prefix verify ci
npm run test:e2e
```

De Node-tests gebruiken echte FFmpeg-uitvoer en geïsoleerde bronfixtures. De Chrome-browsertest controleert onder meer gebruikersisolatie, alle vier routes, TV/favorieten, volledige breedte, Plex-posters/hervatten, YouTube en persoonlijke geschiedenis. YouTube gebruikt daarbij lokale testmedia; een live externe stream blijft een afzonderlijke controle.

De installertests controleren detectie, configuraties, backups en archiefveiligheid. Ze zijn geen claim dat iedere distributie volledig op een verse machine is geïnstalleerd.

`stream-lab/` is de huidige app. `index.html` en `rust-server/` zijn eerdere experimenten en worden niet door de installer uitgerold.
