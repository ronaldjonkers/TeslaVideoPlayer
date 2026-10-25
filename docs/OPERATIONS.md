# Beheer, updates en herstel

De onderstaande namen en paden horen bij de nieuwe installer. Oudere handmatige installaties kunnen andere service- en datapaden hebben. Lees bij twijfel `/etc/tesla-media/installation.json`; dat bestand bevat geen bronwachtwoorden.

## Status en logs

### systemd

```sh
sudo systemctl status tesla-media
sudo journalctl -u tesla-media -n 100 --no-pager
sudo systemctl restart tesla-media
```

### OpenRC

```sh
sudo rc-service tesla-media status
sudo rc-service tesla-media restart
sudo tail -n 100 /var/log/tesla-media/error.log
```

### runit

```sh
sudo sv status /var/service/tesla-media
sudo sv restart /var/service/tesla-media
sudo tail -n 100 /var/log/tesla-media/current
```

### Containers

```sh
docker compose ps
docker compose logs --tail=100 app caddy
```

Gedeelde logbestanden mogen geen M3U-URLs, Plex-tokens of wachtwoorden bevatten. De app bewaart ruwe FFmpeg-foutmeldingen daarom niet. Verwijder ook sessiecookies uit foutmeldingen die je met anderen deelt.

## Omgevingsvariabelen

| Variabele | Betekenis |
|---|---|
| `HOST` | Bind-adres. Native achter proxy: `127.0.0.1`; container: `0.0.0.0` op het interne netwerk |
| `PORT` | HTTP-poort van de app |
| `DATA_DIR` | Directory met SQLite, WAL en encryptiesleutel |
| `FFMPEG_PATH` | Volledig pad naar FFmpeg, anders `ffmpeg` in PATH |
| `YT_DLP_PATH` | Optionele recente officiële YouTube-helper; zonder geldig bestand blijft de functie verborgen |
| `ALLOW_PRIVATE_NETWORKS` | Alleen voor geïsoleerde ontwikkeltests. Zet dit niet op `1` voor alle internetgebruikers |

Een beheerder mag ook een bron op een privé-adres gebruiken. Gewone gebruikers moeten publieke bronadressen gebruiken. Dat onderscheid verandert niets aan de scheiding van hun persoonlijke lijsten en tokens.

## Backup en herstel

De gegevens zijn alleen bruikbaar met **database én `secret.key`**. Een losse SQLite-kopie terwijl de app draait is niet voldoende: recente writes kunnen in WAL-bestanden staan.

Voor een eenvoudige consistente native backup, stop de service kort. Voor systemd:

```sh
sudo systemctl stop tesla-media
sudo install -d -m 700 /var/backups/tesla-media
sudo sh -c 'umask 077; tar -C /var/lib/tesla-media -czf /var/backups/tesla-media/data-$(date +%Y%m%d-%H%M%S).tar.gz .'
sudo systemctl start tesla-media
```

Gebruik bij OpenRC/runit de bijbehorende stop/start-opdracht. Bewaar backups buiten de repo en behandel ze als privégegevens.

Herstel met gestopte service naar de ingestelde `DATA_DIR`. Controleer de inhoud van een backup voordat je hem uitpakt. De datamap hoort bij gebruiker/groep `tesla-media` en heeft mode `700`; privébestanden horen niet wereldwijd leesbaar te zijn. Start daarna de service en controleer aanmelden, favorieten en een bron.

Voor containers: stop `app`, maak een consistente kopie van het benoemde `media_data`-volume en start `app` weer. Bewaar voor een volledige hostmigratie ook de Caddy-volumes of laat Caddy op de nieuwe host opnieuw certificaten aanvragen. `docker compose down` bewaart volumes; de optie `-v` verwijdert ze.

## Updates

```sh
git pull --ff-only
sudo sh install.sh --domain media.example.com --email beheerder@example.com
```

Voer dezelfde paden/proxy-opties uit als bij de eerste installatie. Dat voorkomt een tweede service of datamap. Eerdere applicatiereleases blijven onder `/opt/tesla-media/releases/` staan. Oude releases kunnen later handmatig worden verwijderd; verwijder niet de release waar `current` naar wijst.

YouTube-helper bijwerken: voeg `--youtube` toe. Die optie downloadt de laatste officiële helper in een eigen versiedirectory en controleert SHA-256. Een recente helper is nodig omdat YouTube regelmatig verandert. Distro-Node/FFmpeg worden via regulier systeemonderhoud bijgewerkt; de installer hergebruikt een geschikte runtime.

Gebruik bij een mislukte update de bewaarde vorige release en de configuratiebackups. Bij een toekomstige incompatibele datamigratie kan daarnaast een databasebackup nodig zijn; verwijder daarom geen backups direct na een update.

## Accountbeheer

Gebruikers kunnen hun bekende wachtwoord wijzigen onder Instellingen. Voor accountrecovery op de server is een lokale beheeropdracht beschikbaar. Hij heeft toegang tot de privé-datamap nodig:

```sh
sudo -u tesla-media env DATA_DIR=/var/lib/tesla-media \
  /pad/naar/node /opt/tesla-media/current/manage.mjs list-users
```

Een wachtwoordreset verwacht alleen via stdin een privé-JSON-object met `password`:

```sh
sudo -u tesla-media env DATA_DIR=/var/lib/tesla-media \
  /pad/naar/node /opt/tesla-media/current/manage.mjs reset-password gebruikersnaam \
  < /privaat/reset.json
```

De opdracht slaat een gesalte hash op en trekt alle sessies van dat account in. Hij toont het wachtwoord niet en verandert geen bronnen, voorkeuren of favorieten. Zet het JSON-bestand niet in Git en verwijder het na gebruik. Er is geen herstel per e-mail.

## Certificaten

Nginx-installaties krijgen `tesla-media-cert-renew.timer` op systemd of een beheerde root-crontaak op OpenRC/runit. De deploy-hook herlaadt alleen na succesvolle vernieuwing. Controleer periodiek:

```sh
sudo certbot renew --cert-name media.example.com --dry-run
```

Caddy beheert certificaten zelf. Controleer bij problemen de Caddy-servicelog, DNS en bereikbaarheid van 80/443. Verplaats het domein niet zonder de proxy en eventuele oude vhost/vernieuwingstaak mee te nemen.

## Verwijderen

Stop en disable de eigen app-service. Verwijder alleen de eigen Tesla Media-vhost/importsite, valideer de webserver en herlaad. Verwijder daarna desgewenst de code-directory. De installer heeft geen destructieve automatische verwijderfunctie: je data en encryptiesleutel worden niet als onderdeel van een uninstall gewist. Verwijder de datamap pas nadat je zelf hebt vastgesteld dat je de accounts en bronnen niet meer nodig hebt.
