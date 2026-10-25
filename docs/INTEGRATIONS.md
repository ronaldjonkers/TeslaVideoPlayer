# Integraties en grenzen

## M3U / IPTV

Tesla Media laadt HTTP(S)-speellijsten en verwerkt mediabronnen via FFmpeg. M3U-attributen voor kanaalnaam, groep en logo worden gebruikt. Er worden geen provideraccounts meegeleverd. De bron-URL en gecachete kanaalgegevens worden versleuteld in de eigen serverdatabase opgeslagen.

## Plex

Aanmelden gebeurt met de Plex PIN-flow, of met een handmatig token. Serververzoeken, posters en mediabestanden worden via de app-server opgehaald. Tokens worden niet in afspeellinks naar de browser gestuurd.

Ondersteund: filmbibliotheken, series/seizoenen/afleveringen, zoeken, recent toegevoegd, verder kijken, lokale kijkposities en Plex-tijdlijnupdates. De eerste beschikbare mediapart wordt afgespeeld. Er zijn geen ondertitelkeuze, alternatieve audio-trackkeuze, casting of volledige Plex Home-profielkeuze ingebouwd. DRM-beveiligde bronnen worden niet ontsleuteld.

Posters: de app gebruikt de echte poster uit Plex. Wanneer lijstmetadata onvolledig is, vraagt de afbeeldingsroute volledige itemmetadata en zo nodig de bovenliggende metadata op. Server- en browserfallbacks voorkomen een lege tegel; ontbrekende bronposters worden expliciet gemeld.

Referenties: [Plex Media Server API](https://developer.plex.tv/pms/), [Plex-aanmelding](https://forums.plex.tv/t/authenticating-with-plex/609370).

## YouTube

Dit is een optionele functie. Activeer haar met `--youtube` in de Linux-installer of een geschikte `YT_DLP_PATH`. Zonder helper blijft het menu verborgen.

De server gebruikt de actuele officiële yt-dlp-helper en een Node-JavaScript-runtime om openbare video’s te vinden en bron-URL’s op te halen. Video en audio kunnen afzonderlijke DASH-streams zijn. FFmpeg leest deze op dezelfde server, schaalt/encodeert het beeld naar canvasframes en levert audio aan het audio-element. Zoeken, links openen, pauzeren, spoelen, kwaliteitskeuze en persoonlijke geschiedenis gebruiken de eigen speler; er wordt geen YouTube-iframe of video-element ingevoegd.

Alleen de geselecteerde hoofdvideo- en audiostream worden afgespeeld. De YouTube-advertentieplayer wordt niet geladen. Dit is geen Brave-browserfilter of een garantie dat YouTube nooit een andere afleveringsmethode gaat gebruiken. In de video ingebakken sponsors blijven onderdeel van het beeld en geluid.

Beperkingen: geen Google-accountkoppeling, privé-/leden-/leeftijdsbeperkte video’s, DRM of YouTube-livestreams in deze route. Geografische restricties, verificatieverzoeken, tijdelijk geblokkeerde server-IP’s en verlopen bron-URL’s kunnen een video verhinderen. De app geeft dan een foutmelding; de installer belooft niet dat iedere video op iedere server werkt.

De helper wordt afzonderlijk gehouden en controleert zijn eigen JavaScript-componenten. Bron-URL’s blijven in kortdurend servergeheugen; de browser en kijkgeschiedenis krijgen alleen publieke metadata en video-ID’s. Zet bij problemen eerst de helper bij via de installer. Deel geen Google-cookies of persoonlijke accounts om een test te laten slagen.

Referentie: [yt-dlp EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

## Netflix

Netflix is niet ingebouwd. De huidige speler verwerkt vrij decodeerbare mediabronnen via FFmpeg en canvas. Er is geen werkende geautoriseerde Netflix-afspeelroute voor deze architectuur geïmplementeerd. De app toont daarom geen Netflix-knop die alleen een kapotte integratie oplevert. Gebruik de officiële Netflix-app of een ondersteunde browser buiten Tesla Media.

Referentie: [Netflix-browservereisten](https://help.netflix.com/en/node/30081).
