# Problemen oplossen

| Symptoom | Controle |
|---|---|
| Installer stopt vóór installatie | Lees de concrete melding, draai `--plan`, controleer Linux, Python 3.9+, pakketmanager en init-systeem |
| FFmpeg mist codecs | Gebruik een volledige build; op Fedora/EL kunnen extra repositories nodig zijn, op Gentoo geschikte USE-flags |
| Node kan niet starten | Controleer Node 22.13+, `node:sqlite`, architectuur en libc; gebruik geen glibc-binary op musl |
| Poort 80/443 al bezet | Kies de bestaande proxy of `--proxy none`; stop geen andere sites om het te forceren |
| Nginx/Caddy-validatie faalt | De installer zet de beheerde configuratie terug; lees de validator en controleer dubbele domeinen/includes |
| Certificaat blijft uit | Controleer A én AAAA, router/cloud-firewall, TCP 80/443 en ACME-servicelogs |
| Aanmelden geeft origin-fout | De proxy moet de oorspronkelijke Host en juiste `X-Forwarded-Proto` doorgeven |
| HTTP 502 | Controleer app-service, lokale poort, SELinux en de upstream in de proxy |
| Geen kanalen | Voeg een eigen lijst toe of vernieuw haar; controleer provider-URL zonder die in openbare logs te plaatsen |
| Favoriet ontbreekt | Controleer het aangemelde account en of de bijbehorende lijst nog gekoppeld is |
| Geschiedenis is leeg | Zij wordt opgebouwd zodra een nieuwe stream daadwerkelijk beeld heeft getoond; bestaande oude afspeelsessies worden niet achteraf geïmporteerd |
| WebCodecs ontbreekt | Gebruik HTTPS/localhost en een geschikte browser; kies anders ImageBitmap/MJPEG |
| Wel beeld, geen geluid | Tik op Geluid, controleer mute/volume en of de bron een audiotrack heeft |
| Haperingen | Verlaag resolutie of kies 20/25 fps, meet FFmpeg-CPU en netwerk; controleer ook de provider |
| Steeds stoppen | Controleer providerlimieten, uitval en proxy/CDN-timeouts; de app probeert liveverbindingen te herstellen |
| Plex-server onbereikbaar | Controleer externe toegang, adres/certificaat en accountrechten; privé-adressen vereisen een beheerder |
| Plex-poster ontbreekt | Tesla Media probeert aanvullende metadata. Ontbreekt de bronposter echt of is de bron offline, dan verschijnt een vervangende poster |
| YouTube-menu ontbreekt | Schakel `--youtube` in, controleer `YT_DLP_PATH` en herstart de service |
| YouTube vraagt verificatie | Probeer een andere openbare video of werk de helper bij. De app gebruikt geen Google-cookies en omzeilt geen accountrestricties |
| Data na verhuizing onleesbaar | Controleer dat `secret.key` bij precies deze database hoort en dat de service alle databestanden kan lezen/schrijven |

## Eerst gericht meten

Controleer eerst de service en één ingebouwde/lokale testbron, daarna de provider. De browser moet frames tekenen én de audiotijd laten oplopen. Een succesvolle extractie van metadata alleen bewijst nog niet dat YouTube/Plex-media daadwerkelijk afspelen.

De app beperkt videothreads, slaat frames vóór het schalen/encoderen over volgens de gekozen framerate en gebruikt op macOS waar beschikbaar automatische hardwaredecodering. Linux kan een ander CPU-profiel hebben. Hogere instellingen en meerdere gebruikers vragen meer rekenkracht; stel geen vaste capaciteit vast op basis van één korte test.

## Welke test dekt wat?

```sh
npm test
python3 -m unittest discover -s tests -v
npm --prefix verify ci
npm run test:e2e
```

De Node-tests gebruiken echte FFmpeg-uitvoer en geïsoleerde lokale mediabronnen. Ze controleren dat accounts elkaar niet kunnen lezen of bedienen, dat voorkeuren/favorieten/geschiedenis een herstart overleven en dat video zonder audio blijft werken. De browsertest heeft Chrome nodig en controleert onder meer alle vier routes, volledige breedte, kwaliteit wisselen, Plex-posters en hervatten.

Installertests simuleren de detectiematrix, valideren configuratietekst, backups/rollback en veilige archiefextractie. Ze voeren geen echte OS-pakketinstallatie op alle distributies uit. De containerbuild en nieuwe distributiereleases moeten in je eigen doelomgeving worden gecontroleerd.
