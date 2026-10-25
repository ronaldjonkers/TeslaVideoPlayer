# Gebruik

## Je account en homepage

Maak een account op de aanmeldpagina of log in met je bestaande account. De homepage toont de laatste TV-kanalen, Plex-video’s en — indien ingeschakeld — YouTube-video’s die je hebt afgespeeld. Deze geschiedenis is persoonlijk en staat op de server. De homepage toont maximaal 24 recente items; de opslag houdt maximaal 100 bronnen per gebruiker bij. Herhaald kijken maakt geen duplicaat van hetzelfde item.

Een kanaal op de homepage begint weer live. Een Plex- of YouTube-video kan verder vanaf de opgeslagen positie. Als je een bron ontkoppelt, verdwijnt de bijbehorende vermelding uit het overzicht.

## TV

1. Open Instellingen → TV-speellijsten.
2. Geef een naam en de online M3U-URL op.
3. Open TV. Zoek op naam of groep, kies een lijst/groep en open een kanaalkaart.
4. Klik op een ster om een favoriet toe te voegen of te verwijderen.

Het volledige kanaaloverzicht blijft een aparte pagina. In de speler staat het beeld over de volledige browserbreedte; daaronder kun je snel tussen favorieten schakelen. Kanalen zonder bruikbaar logo krijgen hun initialen.

Lijsten worden op de server opgeslagen en gecachet. De knop Vernieuwen haalt de lijst opnieuw bij de aanbieder op. Je provider bepaalt of een kanaal bereikbaar is en hoeveel gelijktijdige verbindingen worden toegestaan.

## Voorkeuren en afspelen

Instellingen → Beeld & afspelen bewaart je standaardmethode, resolutie en framerate bij je account. De standaard is ImageBitmap / 540p / 20 fps.

| Methode | Gebruik |
|---|---|
| ImageBitmap | Rechtstreekse JPEG-bitmapoverdracht naar canvas |
| MJPEG | JPEG decode naar een 2D-canvas, brede browsercompatibiliteit |
| WebCodecs | VP8-decodering naar een 2D-canvas; vereist veilige browsercontext |
| WebGL | VP8-decodering met GPU-weergave; vereist WebCodecs én WebGL |

Tijdens het kijken blijven resolutie en framerate instelbaar. Zo’n wijziging herstart de omzetting; bij VOD wordt de huidige positie meegenomen. Dit is geen naadloze adaptive-bitrate-switch. Een hogere instelling kan geen ontbrekend brondetail of echte bronframes toevoegen. Bij belasting worden achterlopende beelden overgeslagen om de vertraging te begrenzen.

Geluid loopt via een audio-element. Als de browser automatisch geluid weigert, gebruik de knop Geluid. Het volume en volledig-scherm staan bij de speler. Bij TV betekent pauzeren het stoppen van de liveverbinding; hervatten is weer live.

## Plex

Open Instellingen → Verbind met Plex. Kies aanmelden bij Plex en daarna de gewenste server. Je Plex-wachtwoord wordt niet aan Tesla Media doorgegeven. Je kunt ook handmatig een bereikbaar serveradres en een Plex-token invullen.

Open Plex in het onderste menu. Je kunt meerdere servers kiezen, bibliotheken doorlopen, zoeken, series/seizoenen/afleveringen openen en verder kijken. Films en series krijgen een posterafbeelding. Ontbreekt de poster in een lijst, dan vraagt de server aanvullende metadata op. Als Plex zelf geen bruikbare poster heeft, wordt dat op een vervangende poster vermeld.

Kijkposities staan lokaal per gebruiker en worden ook aan de gekoppelde Plex-server gemeld. Het gekoppelde Plex-account bepaalt welke bibliotheken toegankelijk zijn. Een onderbroken Plex-server kan lokaal opslaan nog steeds toestaan, terwijl synchronisatie naar Plex tijdelijk mislukt.

Zie [integraties en beperkingen](INTEGRATIONS.md).
