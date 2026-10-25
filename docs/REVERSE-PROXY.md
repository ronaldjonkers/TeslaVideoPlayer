# Reverse proxy en TLS

De [installer](INSTALLATION.md) genereert deze configuratie automatisch. Deze voorbeelden zijn bedoeld voor een bestaande, handmatig beheerde server. Gebruik je echte domein en gekozen applicatiepoort.

## Nginx

Plaats een nieuwe serverconfiguratie in een bestaande `http`-include. Voeg de ACME-locatie eerst aan een HTTP-vhost toe en vraag daarna het certificaat aan:

```sh
sudo install -d -m 755 /var/www/tesla-media-acme
sudo certbot certonly --webroot -w /var/www/tesla-media-acme \
  -d media.example.com --email beheerder@example.com --agree-tos
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name media.example.com;
    location /.well-known/acme-challenge/ { root /var/www/tesla-media-acme; }
    location / { return 301 https://media.example.com$request_uri; }
}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name media.example.com;
    ssl_certificate /etc/letsencrypt/live/media.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/media.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 64k;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Laat de `[::]`-regels weg als IPv6 op je host is uitgeschakeld. Test met `nginx -t` vóór herladen. Maak een Certbot-vernieuwingstaak en een deploy-hook die Nginx herlaadt. De installer regelt beide; bij handmatige installatie moet je dat zelf doen. Bij SELinux kan `httpd_can_network_connect` nodig zijn.

## Caddy

Voeg aan je bestaande Caddyfile toe, of importeer een apart bestand:

```caddyfile
media.example.com {
    tls beheerder@example.com
    request_body {
        max_size 64KB
    }
    reverse_proxy 127.0.0.1:8765 {
        flush_interval 100ms
        stream_close_delay 5m
        header_up X-Real-IP {remote_host}
        transport http {
            keepalive 4s
        }
    }
}
```

Valideer met `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` en herlaad via je servicemanager. Caddy vraagt en vernieuwt certificaten automatisch.

De flushinstelling houdt de streamingroute direct. Er is bewust geen `flush_interval -1` gebruikt: Caddy documenteert dat deze negatieve modus een backendverzoek bij een vroegtijdige clientdisconnect niet annuleert. De app gebruikt het sluiten van de beeldverbinding juist om FFmpeg op te ruimen. De upstream-keepalive van vier seconden blijft onder Nodes standaard keepalive-timeout.

## Headers en grenzen

- `Host` en `X-Forwarded-Proto` moeten de echte browser-origin beschrijven. Anders worden muterende verzoeken terecht afgewezen.
- De app mag alleen vanaf de proxy bereikbaar zijn. Vertrouw forwarded headers niet rechtstreeks van onbeperkte internetclients.
- Proxy-, CDN- en load-balancer-timeouts kunnen streams onderbreken, ook als Nginx/Caddy correct staat.
- Log bij voorkeur `$uri` in plaats van een querystring met afspeelsessie-ID’s. Bronwachtwoorden horen nooit in toegangslogs.

Referenties: [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [Certbot webroot en vernieuwing](https://eff-certbot.readthedocs.io/en/stable/using.html).
