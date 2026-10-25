# Installatie op Linux

De installer detecteert de pakketmanager, init-service en bestaande Nginx/Caddy-installatie. Hij installeert de applicatie als een eigen gebruiker, bewaart data buiten de code en configureert de reverse proxy voor streaming.

## Snel beginnen

```sh
git clone git@github.com:ronaldjonkers/TeslaVideoPlayer.git
cd TeslaVideoPlayer
sudo sh install.sh \
  --domain media.example.com \
  --email beheerder@example.com \
  --admin beheerder
```

Vervang het domein en e-mailadres. Het nieuwe beheerderswachtwoord wordt verborgen gevraagd; minimaal tien tekens. Er staan geen standaardaccounts, M3U-lijsten of wachtwoorden in de repo.

Wil je ook YouTube inschakelen, voeg `--youtube` toe. Dit installeert een gecontroleerde officiële yt-dlp-helper en gebruikt de Node-runtime van de app.

Vooraf alleen bekijken wat wordt gedetecteerd:

```sh
sh install.sh --plan --domain media.example.com --email beheerder@example.com
```

`--plan` wijzigt niets. Python 3.9+ moet daarvoor al aanwezig zijn. Een andere interpreter kies je met `TESLA_PYTHON=/pad/naar/python3.11`. Zonder Python kan een echte installatie Python eerst via de pakketmanager installeren.

## Wat wordt geïnstalleerd?

- Basisgereedschap en certificaatbundels via de distributie.
- Node.js 22.13+ met `node:sqlite`. Een geschikte bestaande Node-installatie blijft behouden. Indien nodig wordt Node 22 afzonderlijk geïnstalleerd met SHA-256-controle van de officiële download.
- FFmpeg met VP8 (`libvpx`), JPEG (`mjpeg`), MP3 (`libmp3lame`) en gangbare brondecoders. De installer voert ook echte encoderproeven uit.
- De gekozen webserver en bij Nginx HTTPS ook Certbot en automatische certificaatvernieuwing.
- Een `tesla-media` systeemgebruiker en service, met automatische start na herstart.
- Optioneel de YouTube-helper, uitsluitend in een eigen directory, zonder een bestaande yt-dlp-installatie te vervangen.

Er zijn geen npm-runtimepakketten nodig. Python is alleen vereist voor installatie en de installertests; de app zelf draait op Node en FFmpeg.

## Distributies en grenzen

| Familie | Gedetecteerde pakketmanager | Init |
|---|---|---|
| Debian, Ubuntu en afgeleiden | apt-get | doorgaans systemd |
| Fedora, Rocky, AlmaLinux, RHEL | dnf / yum | systemd |
| openSUSE | zypper | systemd |
| Arch, Manjaro | pacman | systemd |
| Alpine | apk | OpenRC |
| Void | xbps-install | runit |
| Gentoo | emerge | OpenRC of systemd |

Dit is geen garantie voor iedere historische release, architectuur of aangepaste init-configuratie. De detectie, opdrachtopbouw en configuraties zijn automatisch getest; niet alle distributies zijn op een verse machine volledig doorlopen. Gebruik een onderhouden distributie met Python 3.9+ en een ondersteunde Node-runtime. NixOS, Guix, immutable systemen en afwijkende init-configuraties vereisen handmatige/declaratieve installatie of [containers](#containers).

De installer voert geen algemene OS-upgrade uit. Werk een Arch-installatie vooraf normaal bij met `pacman -Syu`; er wordt geen losstaande `pacman -Sy` uitgevoerd.

### Extra codecs op Fedora / Enterprise Linux

Sommige standaardrepositories leveren geen volledige FFmpeg-build. De installer stopt wanneer verplichte encoders/decoders ontbreken, in plaats van een onwerkende speler op te leveren.

Met expliciete toestemming via een optie kan hij EPEL/RPM Fusion toevoegen:

```sh
sudo sh install.sh --domain media.example.com --email beheerder@example.com --extra-repos
```

Dit geldt voor Fedora en EL 8/9/10. Repositorybeleid en beschikbaarheid verschillen per release. Configureer zo nodig vooraf de repositories volgens de [RPM Fusion-instructies](https://rpmfusion.org/Configuration) en de [EPEL-documentatie](https://docs.fedoraproject.org/en-US/epel/getting-started/). De installer schakelt GPG-controle niet uit.

### openSUSE / Gentoo

Op openSUSE kan een volledige-codecbuild uit een toegestane aanvullende repository nodig zijn. De installer verandert niet automatisch de leverancier van al je multimediapakketten. Op Gentoo moeten FFmpeg USE-flags voor VP8, MP3 en encoding ingeschakeld zijn. Na installatie van een geschikte FFmpeg-build kun je de installer opnieuw uitvoeren.

### Alpine / musl

De installer gebruikt eerst de distributie-Node. Hij downloadt geen glibc-Node-binary op musl. Is je Alpine-release te oud, werk hem bij of geef zelf een compatibele runtime op.

## Een bestaande webserver gebruiken

`--proxy auto` kiest eerst een actieve Nginx of Caddy, daarna een aanwezige installatie. Op een nieuwe server zonder beide kiest hij Nginx. Zijn beide actief, kies dan expliciet:

```sh
sudo sh install.sh --domain media.example.com --email beheerder@example.com --proxy nginx
sudo sh install.sh --domain media.example.com --email beheerder@example.com --proxy caddy
```

Bestaande virtual hosts worden behouden. Bij een domein dat al buiten deze installer is geconfigureerd, stopt de installer met uitleg. Hij stopt geen andere webserver om poort 80/443 vrij te maken.

Nginx: de installer zoekt een actieve `conf.d/*.conf`- of `sites-enabled/*`-include in `nginx -T`. Hij schrijft één eigen vhost, test met `nginx -t` en herlaadt daarna pas. Certbot gebruikt een aparte webroot, waardoor andere sites bereikbaar blijven.

Caddy: een bestaande Caddyfile blijft staan en krijgt een import voor afzonderlijke Tesla Media-sites. De volledige configuratie wordt gevalideerd vóór herladen. Caddy regelt HTTPS zelf. Een API-beheerde of afwijkende Caddy-configuratie wordt niet automatisch aangepast.

Alleen de app installeren, bijvoorbeeld achter een reeds beheerde proxy:

```sh
sudo sh install.sh --proxy none --port 8765 --admin beheerder
```

De app luistert uitsluitend op loopback. Zie [reverse-proxyvoorbeelden](REVERSE-PROXY.md).

## DNS, HTTPS en firewall

Zet het A-record en eventueel AAAA-record op deze server. Verwijder een verkeerd AAAA-record: dat kan certificaatvalidatie verhinderen, ook als IPv4 goed staat. TCP 80 en 443 moeten vanaf internet bereikbaar zijn. Een cloud-firewall of router staat los van de lokale firewall.

De installer voegt HTTP(S) toe aan een actieve firewalld of UFW, zonder de applicatiepoort openbaar te maken. Andere firewallconfiguraties worden behouden en gemeld. Gebruik `--firewall skip` voor volledig handmatig firewallbeheer.

Voor een tijdelijke HTTP-test:

```sh
sudo sh install.sh --domain media.example.com --proxy nginx --no-tls
```

WebCodecs vereist HTTPS of localhost. Gebruik buiten localhost voor HTTP-tests ImageBitmap/MJPEG. Voor persoonlijke accounts op internet is HTTPS de normale opstelling.

## Locaties en opties

| Onderdeel | Standaard |
|---|---|
| Applicatie | `/opt/tesla-media/current` → versie onder `releases/` |
| Accounts, favorieten, geschiedenis, bronnen | `/var/lib/tesla-media/` |
| Installatiestatus | `/etc/tesla-media/installation.json` |
| Service | `tesla-media` |
| Poort | vrije poort vanaf 8765, of de eerder gebruikte poort |
| Zelf gedownloade Node | `/opt/tesla-node/` |
| YouTube-helper | `/opt/tesla-ytdlp/` |

```sh
sh install.sh --help
```

Aanvullende opties: `--install-dir`, `--data-dir`, `--node`, `--ffmpeg`, `--yt-dlp`, `--admin-name`, `--admin-password-stdin`, `--youtube`, `--no-youtube`. Gebruik toepassingsspecifieke paden; niet bijvoorbeeld `/var/lib` zelf. De data-directory moet buiten de applicatiedirectory staan.

Automatisering: het wachtwoord mag via stdin worden aangeleverd met `--admin-password-stdin`. Er is bewust geen wachtwoordargument dat in de proceslijst of shellhistorie terechtkomt. Een bestaand account wordt niet gereset of verhoogd tot beheerder.

## Bijwerken en terugzetten

Maak eerst een [backup](OPERATIONS.md#backup-en-herstel). Voer daarna in je checkout uit:

```sh
git pull --ff-only
sudo sh install.sh --domain media.example.com --email beheerder@example.com
```

Gebruik dezelfde paden en proxy-opties als bij de installatie. De poort wordt hergebruikt. Bestaande gebruikers, wachtwoorden, bronnen en favorieten blijven staan. `current` wordt atomair naar de nieuwe release gezet; eerdere code blijft beschikbaar. Gewijzigde proxybestanden krijgen een backup. Bij een configuratiefout worden de eerdere configuratie en, bij een update, vorige code teruggezet. Geïnstalleerde OS-pakketten en firewalltoevoegingen worden niet automatisch verwijderd.

Een al ingeschakelde YouTube-integratie blijft ingeschakeld. Met opnieuw `--youtube` wordt ook de helper ververst. Met `--no-youtube` verdwijnt de integratie uit het menu; geschiedenis blijft bewaard.

## Containers

Voor andere Linux-opstellingen is een Docker Compose-variant meegeleverd. Installeer eerst Docker Engine en Compose volgens de documentatie van je distributie; de native installer verandert daarvoor geen daemon- of firewallconfiguratie.

```sh
cp .env.example .env
# Vul DOMAIN en ACME_EMAIL in; zet ENABLE_YOUTUBE=true indien gewenst.
docker compose up -d --build
```

Caddy gebruikt poorten 80/443; start deze variant niet naast een bestaande webserver die die poorten al gebruikt. De app-poort wordt niet gepubliceerd. Accounts, sleutels en certificaten staan in benoemde volumes. Gebruik geen `docker compose down -v` als je die data wilt behouden.

Maak zo nodig een beheerder met privégegevens via stdin:

```sh
docker compose exec -T app node bootstrap.mjs < /privaat/account.json
```

Bijwerken: `git pull --ff-only` gevolgd door `docker compose up -d --build`. De containerbuild ondersteunt YouTube voor x64/arm64; zonder helper blijft die functie verborgen.

## Handmatig installeren

Op een systeem dat buiten de detectiematrix valt: installeer een compatibele Node, volledige FFmpeg en een service volgens je init-systeem. Kopieer alleen `stream-lab/*.mjs`, `stream-lab/package.json` en `stream-lab/static/` naar een eigen applicatiemap. Stel `HOST=127.0.0.1`, `PORT`, `DATA_DIR` en eventueel `FFMPEG_PATH` in. Start `node server.mjs` als een onprivileged servicegebruiker met schrijfrechten uitsluitend op de datamap. Configureer de [reverse proxy](REVERSE-PROXY.md) en maak een beheerder via `bootstrap.mjs`.
