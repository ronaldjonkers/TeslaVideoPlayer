use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;

const INDEX: &[u8] = include_bytes!("../../index.html");

fn main() {
    let addr = "127.0.0.1:8000";
    let listener = TcpListener::bind(addr).unwrap_or_else(|e| {
        eprintln!("Kon niet binden op {addr}: {e}\nStaat de server misschien al aan?");
        std::process::exit(1);
    });
    println!("Testpagina draait op http://localhost:8000 (Ctrl-C om te stoppen)");
    for stream in listener.incoming() {
        if let Ok(s) = stream {
            thread::spawn(move || handle(s));
        }
    }
}

fn handle(mut stream: TcpStream) {
    let mut buf = [0u8; 8192];
    let n = stream.read(&mut buf).unwrap_or(0);
    if n == 0 {
        return;
    }
    let req = String::from_utf8_lossy(&buf[..n]);
    let path = req
        .lines()
        .next()
        .unwrap_or("")
        .split_whitespace()
        .nth(1)
        .unwrap_or("/");

    let playlist;
    let (status, body, ctype): (&str, &[u8], &str) = if let Some(encoded) = path.strip_prefix("/playlist?url=") {
        let url = decode_url(encoded);
        if !(url.starts_with("https://") || url.starts_with("http://")) {
            ("400 Bad Request", &b"Gebruik een http(s)-URL"[..], "text/plain")
        } else {
            let output = std::process::Command::new("/usr/bin/curl")
                .args(["--fail", "--silent", "--location", "--max-time", "25", "--max-filesize", "20000000", "--proto", "=http,https", "--proto-redir", "=http,https", "--url", &url]).output();
            match output {
                Ok(result) if result.status.success() => {
                    playlist = result.stdout;
                    ("200 OK", playlist.as_slice(), "text/plain; charset=utf-8")
                }
                _ => ("502 Bad Gateway", &b"Lijst ophalen mislukt. Controleer de URL en toegang bij de aanbieder."[..], "text/plain"),
            }
        }
    } else { match path {
        "/" | "/index.html" => ("200 OK", INDEX, "text/html; charset=utf-8"),
        _ => ("404 Not Found", &b"niet gevonden"[..], "text/plain; charset=utf-8"),
    }};

    let head = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body);
}

fn decode_url(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let Ok(v) = u8::from_str_radix(&value[i+1..i+3], 16) {
                out.push(v); i += 3; continue;
            }
        }
        out.push(bytes[i]); i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}
