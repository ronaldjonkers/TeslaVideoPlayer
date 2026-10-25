#!/usr/bin/env python3
"""Tesla Media Linux installer. No third-party Python packages are required."""
import argparse
import contextlib
import datetime
import getpass
import grp
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MARKER = '# Managed by Tesla Media installer'
MANAGERS = {
    'apt': 'apt-get', 'dnf': 'dnf', 'yum': 'yum', 'zypper': 'zypper',
    'pacman': 'pacman', 'apk': 'apk', 'xbps': 'xbps-install', 'emerge': 'emerge',
}
BASE = {
    'apt': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz-utils', 'passwd'],
    'dnf': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow-utils'],
    'yum': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow-utils'],
    'zypper': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow'],
    'pacman': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow'],
    'apk': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow'],
    'xbps': ['ca-certificates', 'curl', 'openssl', 'tar', 'xz', 'shadow'],
    'emerge': ['app-misc/ca-certificates', 'net-misc/curl', 'dev-libs/openssl', 'app-arch/tar', 'app-arch/xz-utils', 'sys-apps/shadow'],
}

class InstallError(Exception):
    pass


def run(args, *, check=True, capture=False, input=None, env=None):
    if not capture:
        print('+ ' + shlex.join([str(x) for x in args]), flush=True)
    result = subprocess.run([str(x) for x in args], input=input, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, env=env)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or '').strip()[-1500:] if capture else ''
        raise InstallError('Command failed: ' + shlex.join([str(x) for x in args]) + ('\n' + detail if detail else ''))
    return result


def read_os(path=Path('/etc/os-release')):
    result = {}
    path = Path(path)
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                try:
                    result[key] = shlex.split(value)[0] if value else ''
                except (ValueError, IndexError):
                    pass
    return result


def detect_manager(which=shutil.which):
    return next((name for name, binary in MANAGERS.items() if which(binary)), None)


def detect_init(which=shutil.which, exists=lambda p: Path(p).exists()):
    if exists('/run/systemd/system') and which('systemctl'):
        return 'systemd'
    if which('rc-service') and which('rc-update'):
        return 'openrc'
    if which('sv') and (exists('/run/runit') or exists('/etc/runit')):
        return 'runit'
    return None


def package_command(manager, packages):
    prefix = {'apt': ['apt-get', 'install', '-y'], 'dnf': ['dnf', 'install', '-y'],
              'yum': ['yum', 'install', '-y'], 'zypper': ['zypper', '--non-interactive', 'install'],
              'pacman': ['pacman', '-S', '--needed', '--noconfirm'],
              'apk': ['apk', 'add', '--no-cache'], 'xbps': ['xbps-install', '-Sy'],
              'emerge': ['emerge', '--noreplace']}
    return prefix[manager] + list(packages)


def domain_name(value):
    try:
        value = value.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise argparse.ArgumentTypeError('Invalid domain name')
    if len(value) > 253 or '.' not in value or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p) for p in value.split('.')):
        raise argparse.ArgumentTypeError('Use a full domain name, for example media.example.com')
    return value


def safe_path(value):
    p = Path(value)
    if str(p) in ['/var/lib','/var/log','/usr/local','/usr/lib','/etc/nginx','/etc/caddy','/etc/letsencrypt','/var/www']:
        raise argparse.ArgumentTypeError('Choose an application-specific directory, not a shared system directory')
    if not p.is_absolute() or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value) or '..' in p.parts or len(p.parts) < 3:
        raise argparse.ArgumentTypeError('Use an absolute application-specific path, without spaces or ..')
    return p


def free_port(preferred=8765):
    for port in range(preferred, min(preferred + 200, 65536)):
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                pass
    raise InstallError('No free local TCP port found')


def nginx_site(domain, port, *, tls=False, email=None, webroot='/var/www/tesla-media-acme', staging=False, ipv6=True):
    proxy = f'''        proxy_pass http://127.0.0.1:{port};
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
        proxy_socket_keepalive on;'''
    http_location = 'return 301 https://' + domain + '$request_uri;' if tls else ('return 503;' if staging else '\n' + proxy + '\n    ')
    text = f'''{MARKER}
# Query strings and source credentials are deliberately not logged.
log_format tesla_media_{port} '$remote_addr [$time_local] "$request_method $uri" $status $body_bytes_sent';
server {{
    listen 80;
{('    listen [::]:80;'+chr(10)) if ipv6 else ''}    server_name {domain};
    access_log /var/log/nginx/tesla-media.access.log tesla_media_{port};
    client_max_body_size 64k;
    location /.well-known/acme-challenge/ {{ root {webroot}; }}
    location / {{ {http_location} }}
}}
'''
    if tls:
        text += f'''server {{
    listen 443 ssl;
{('    listen [::]:443 ssl;'+chr(10)) if ipv6 else ''}    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    access_log /var/log/nginx/tesla-media.access.log tesla_media_{port};
    client_max_body_size 64k;
    location / {{
{proxy}
    }}
}}
'''
    return text


def caddy_site(domain, port, *, tls=True, email=None):
    address = domain if tls else 'http://' + domain
    email_line = f'    tls {email}\n' if tls and email else ''
    # Positive flushing preserves cancellation when the browser disconnects.
    return f'''{MARKER}
{address} {{
{email_line}    request_body {{
        max_size 64KB
    }}
    reverse_proxy 127.0.0.1:{port} {{
        flush_interval 100ms
        stream_close_delay 5m
        header_up X-Real-IP {{remote_host}}
        transport http {{
            keepalive 4s
        }}
    }}
}}
'''


def app_service(init, node, app, data, port, ffmpeg, youtube=None):
    if init == 'systemd':
        return f'''{MARKER}
[Unit]
Description=Tesla Media
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=tesla-media
Group=tesla-media
WorkingDirectory={app}
Environment=NODE_ENV=production
Environment=HOST=127.0.0.1
Environment=PORT={port}
Environment=DATA_DIR={data}
Environment=FFMPEG_PATH={ffmpeg}
{('Environment=YT_DLP_PATH='+str(youtube)+chr(10)) if youtube else ''}ExecStart={node} {app}/server.mjs
Restart=always
RestartSec=3
TimeoutStopSec=10
KillMode=control-group
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths={data}
UMask=0077
Nice=5
[Install]
WantedBy=multi-user.target
'''
    if init == 'openrc':
        return f'''#!/sbin/openrc-run
{MARKER}
name="Tesla Media"
command="{node}"
command_args="{app}/server.mjs"
command_user="tesla-media:tesla-media"
directory="{app}"
supervisor="supervise-daemon"
respawn_delay=3
export NODE_ENV=production HOST=127.0.0.1 PORT={port}
export DATA_DIR="{data}" FFMPEG_PATH="{ffmpeg}"
{('export YT_DLP_PATH="'+str(youtube)+'"'+chr(10)) if youtube else ''}output_log="/var/log/tesla-media/app.log"
error_log="/var/log/tesla-media/error.log"
umask 0077
depend() {{ need net; }}
'''
    return f'''#!/bin/sh
{MARKER}
exec 2>&1
cd '{app}' || exit 1
export NODE_ENV=production HOST=127.0.0.1 PORT={port}
export DATA_DIR='{data}' FFMPEG_PATH='{ffmpeg}'
{("export YT_DLP_PATH='"+str(youtube)+"'"+chr(10)) if youtube else ''}umask 0077
exec chpst -u tesla-media:tesla-media '{node}' '{app}/server.mjs'
'''


def checksum_valid(data,digest):
    if not re.fullmatch(r'(?:[a-f0-9]{64}|[a-f0-9]{128})',digest):
        return False
    algorithm='sha512' if len(digest)==128 else 'sha256'
    return hashlib.new(algorithm,data).hexdigest()==digest


def checked_extract(archive, target):
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            dest = (target / member.name).resolve()
            if not dest.is_relative_to(target.resolve()):
                raise InstallError('Unsafe archive path')
            if member.isdev() or member.isfifo():
                raise InstallError('Unexpected archive member')
            if member.issym() or member.islnk():
                link = (dest.parent / member.linkname).resolve() if member.issym() else (target / member.linkname).resolve()
                if not link.is_relative_to(target.resolve()):
                    raise InstallError('Unsafe archive link')
        if sys.version_info >= (3, 12):
            tar.extractall(target, filter='data')
        else:
            tar.extractall(target)


class Installer:
    def __init__(self, args):
        self.args = args
        self.os = read_os()
        self.manager = detect_manager()
        self.init = detect_init()
        self.config_dir = Path('/etc/tesla-media')
        self.state_path = self.config_dir / 'installation.json'
        try:
            self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        except PermissionError:
            if not args.plan:
                raise
            self.state = {}
        self.proxy = self.choose_proxy(args.proxy)
        self.port = args.port or self.state.get('port') or free_port()
        self.install = args.install_dir
        self.data = args.data_dir
        self.app = self.install / 'current'
        self.modified = []
        self.service_written = False
        self.ipv6 = False
        if socket.has_ipv6:
            try:
                with socket.socket(socket.AF_INET6) as probe:
                    probe.bind(("::1",0));self.ipv6=True
            except OSError:
                pass
        self.node = None
        self.ffmpeg = None
        self.youtube = None

    def active(self, name):
        if self.init == 'systemd':
            return run(['systemctl', 'is-active', '--quiet', name], check=False, capture=True).returncode == 0
        if self.init == 'openrc':
            return run(['rc-service', name, 'status'], check=False, capture=True).returncode == 0
        if self.init == 'runit':
            return run(['sv', 'status', '/var/service/' + name], check=False, capture=True).returncode == 0
        return False

    def choose_proxy(self, requested):
        if requested != 'auto':
            return requested
        running = [name for name in ['nginx', 'caddy'] if self.active(name)]
        if len(running) == 2:
            raise InstallError('Both Nginx and Caddy are active. Choose --proxy explicitly.')
        return running[0] if running else ('caddy' if shutil.which('caddy') and not shutil.which('nginx') else 'nginx')

    def packages(self, packages, optional=False):
        if not self.manager:
            raise InstallError('Unknown package manager. See docs/INSTALLATION.md for manual/container installation.')
        env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
        return run(package_command(self.manager, packages), check=not optional, env=env).returncode == 0

    def backup_write(self, path, content, mode=None, *, owned=False):
        path = Path(path)
        if path.is_symlink():
            raise InstallError('Refusing to replace a symlink: ' + str(path))
        old_stat = path.stat() if path.exists() else None
        old = path.read_bytes() if old_stat else None
        if owned and old is not None and MARKER.encode() not in old:
            raise InstallError('Existing file is not managed by this installer: ' + str(path))
        if old == content.encode():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if old is not None:
            stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
            backup = path.with_name(path.name + '.tesla-backup-' + stamp)
            shutil.copy2(path, backup)
        self.modified.append((path, old))
        temp = path.with_name(path.name + '.tesla-new')
        temp.write_text(content)
        temp.chmod(mode if mode is not None else (old_stat.st_mode & 0o777 if old_stat else 0o644))
        if old_stat:
            os.chown(temp, old_stat.st_uid, old_stat.st_gid)
        temp.replace(path)

    def restore_configs(self):
        for path, old in reversed(self.modified):
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old)
        if self.proxy == 'nginx' and shutil.which('nginx'):
            if run(['nginx', '-t'], check=False, capture=True).returncode == 0:
                self.service('nginx', 'reload', check=False)
        if self.proxy == 'caddy' and shutil.which('caddy'):
            self.service('caddy', 'reload', check=False)

    def service(self, name, action, check=True):
        if self.init == 'systemd':
            return run(['systemctl', action, name], check=check)
        if self.init == 'openrc':
            return run(['rc-service', name, action], check=check)
        mapping = {'start': 'up', 'stop': 'down', 'restart': 'restart', 'reload': 'hup'}
        return run(['sv', mapping[action], '/var/service/' + name], check=check)

    def enable(self, name):
        if self.init == 'systemd':
            run(['systemctl', 'daemon-reload'])
            run(['systemctl', 'enable', name])
        elif self.init == 'openrc':
            run(['rc-update', 'add', name, 'default'])
        else:
            target = Path('/var/service') / name
            if target.exists() and (not target.is_symlink() or target.resolve()!=(Path('/etc/sv')/name).resolve()):
                raise InstallError('Existing runit service is not the expected managed symlink: '+str(target))
            if not target.exists():
                target.symlink_to(Path('/etc/sv') / name)

    def download(self, url, destination=None):
        req = urllib.request.Request(url, headers={'User-Agent': 'TeslaMediaInstaller/1.0'})
        with urllib.request.urlopen(req, timeout=90) as response:
            if destination:
                with Path(destination).open('wb') as out:
                    shutil.copyfileobj(response, out)
                return None
            return response.read()

    def node_ok(self, binary):
        if not binary:
            return False
        if any(Path(binary).resolve().is_relative_to(Path(base)) for base in ['/home','/root']):
            return False
        probe = run([binary, '--input-type=module', '-e', "import {DatabaseSync} from 'node:sqlite';const v=process.versions.node.split('.').map(Number);if(v[0]<22||(v[0]===22&&v[1]<13))process.exit(1);const db=new DatabaseSync(':memory:');db.close();"], capture=True, check=False)
        return probe.returncode == 0

    def install_node(self):
        if self.args.node:
            if not self.node_ok(self.args.node):
                raise InstallError('--node must be a system-wide Node >=22.13 with node:sqlite, outside /home and /root')
            return str(Path(self.args.node).resolve())
        for candidate in [self.state.get('node'), shutil.which('node'), '/opt/tesla-node/current/bin/node']:
            if candidate and Path(candidate).exists() and self.node_ok(candidate):
                return str(Path(candidate).resolve())
        package = 'net-libs/nodejs' if self.manager == 'emerge' else 'nodejs'
        self.packages([package], optional=True)
        if self.node_ok(shutil.which('node')):
            return str(Path(shutil.which('node')).resolve())
        musl = Path('/etc/alpine-release').exists() or any(Path('/lib').glob('ld-musl-*.so.1'))
        arch = {'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64', 'armv7l': 'armv7l', 'ppc64le': 'ppc64le', 's390x': 's390x'}.get(platform.machine())
        if musl or not arch:
            raise InstallError('No suitable distro Node package. Install a compatible Node >=22.13 and rerun with --node /absolute/path/node; glibc binaries are not used on musl.')
        with tempfile.TemporaryDirectory(prefix='tesla-node-') as tmp:
            tmp = Path(tmp)
            checks = self.download('https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt').decode()
            match = re.search(r'^([a-f0-9]{64})\s+(node-v22\.[0-9]+\.[0-9]+-linux-' + arch + r'\.tar\.xz)$', checks, re.M)
            if not match:
                raise InstallError('No official Node 22 archive found for ' + arch)
            digest, filename = match.groups()
            archive = tmp / filename
            self.download('https://nodejs.org/dist/latest-v22.x/' + filename, archive)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
                raise InstallError('Node archive checksum mismatch')
            checked_extract(archive, tmp / 'unpacked')
            folder = next((tmp / 'unpacked').iterdir())
            destination = Path('/opt/tesla-node') / folder.name
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(folder), destination)
            binary = destination / 'bin/node'
            if not self.node_ok(binary):
                raise InstallError('Official Node binary cannot run on this OS/libc. Upgrade the OS or use --node.')
            return str(binary)

    def install_ffmpeg(self):
        binary = self.args.ffmpeg or shutil.which('ffmpeg')
        if not binary:
            package = 'media-video/ffmpeg' if self.manager == 'emerge' else 'ffmpeg'
            if not self.packages([package], optional=True):
                if self.args.extra_repos and self.manager in ['dnf', 'yum']:
                    self.rpm_repos()
                    self.packages(['ffmpeg'])
                elif self.manager in ['dnf', 'yum'] and self.packages(['ffmpeg-free'], optional=True):
                    pass
                else:
                    raise InstallError('FFmpeg is not available with these repositories. See the distro-specific instructions in docs/INSTALLATION.md, or pass --ffmpeg /path/ffmpeg.')
            binary = shutil.which('ffmpeg')
        if not binary:
            raise InstallError('ffmpeg was not found after installation')
        encoders = run([binary, '-hide_banner', '-encoders'], capture=True).stdout
        missing = [name for name in ['libvpx', 'mjpeg', 'libmp3lame'] if not re.search(r'\s' + name + r'\s', encoders)]
        decoders = run([binary, '-hide_banner', '-decoders'], capture=True).stdout
        missing += [name + ' decoder' for name in ['h264', 'aac', 'mp3'] if not re.search(r'\s' + name + r'\s', decoders)]
        if missing:
            raise InstallError('FFmpeg lacks: ' + ', '.join(missing) + '. Install a full-codec build; see docs/INSTALLATION.md. On Gentoo enable vpx/mp3/encode USE flags.')
        # Verify the actual encoder output, not only its name in a build report.
        for codec, fmt in [('libvpx', 'ivf'), ('mjpeg', 'image2pipe')]:
            with tempfile.TemporaryFile() as out:
                result = subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=20', '-frames:v', '1', '-c:v', codec, '-threads', '1', '-f', fmt, 'pipe:1'], stdout=out, stderr=subprocess.PIPE, timeout=20)
                if result.returncode:
                    raise InstallError('FFmpeg encoder smoke test failed: ' + codec)
        return str(Path(binary).resolve())

    def rpm_repos(self):
        ident = self.os.get('ID', '')
        version = self.os.get('VERSION_ID', '').split('.')[0]
        if ident == 'fedora':
            release = version
            base = 'fedora'
        elif ident in ['rhel', 'rocky', 'almalinux', 'centos', 'ol'] and version in ['8', '9', '10']:
            self.packages(['https://dl.fedoraproject.org/pub/epel/epel-release-latest-' + version + '.noarch.rpm'])
            release = version
            base = 'el'
        else:
            raise InstallError('--extra-repos supports Fedora and EL 8/9/10 only; configure repositories manually for this derivative.')
        self.packages(['https://mirrors.rpmfusion.org/free/' + base + '/rpmfusion-free-release-' + release + '.noarch.rpm'])

    def install_youtube(self):
        enabled=self.args.youtube if self.args.youtube is not None else bool(self.state.get('youtube'))
        if not enabled:
            return None
        if self.args.yt_dlp:
            binary=str(Path(self.args.yt_dlp).resolve())
        elif self.args.youtube is None and self.state.get('youtube') and Path(self.state['youtube']).is_file():
            binary=self.state['youtube']
        else:
            musl=Path('/etc/alpine-release').exists() or any(Path('/lib').glob('ld-musl-*.so.1'))
            names={'x86_64':'yt-dlp_musllinux' if musl else 'yt-dlp_linux','aarch64':'yt-dlp_musllinux_aarch64' if musl else 'yt-dlp_linux_aarch64','arm64':'yt-dlp_musllinux_aarch64' if musl else 'yt-dlp_linux_aarch64','armv7l':'yt-dlp_linux_armv7l'}
            name=names.get(platform.machine())
            metadata=json.loads(self.download('https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'))
            assets={x['name']:x['browser_download_url'] for x in metadata['assets']}
            if name not in assets or 'SHA2-256SUMS' not in assets:
                raise InstallError('No standalone yt-dlp for this architecture/libc. Install a recent yt-dlp manually and use --youtube --yt-dlp /path/yt-dlp.')
            version=metadata['tag_name']
            if not re.fullmatch(r'[A-Za-z0-9._-]+',version):
                raise InstallError('Unexpected yt-dlp release version')
            checks=self.download(assets['SHA2-256SUMS']).decode()
            match=re.search(r'^([a-f0-9]{64})\s+\*?'+re.escape(name)+r'$',checks,re.M)
            with tempfile.TemporaryDirectory(prefix='tesla-youtube-') as tmp:
                file=Path(tmp)/name;self.download(assets[name],file)
                if not match or hashlib.sha256(file.read_bytes()).hexdigest()!=match.group(1):
                    raise InstallError('yt-dlp archive checksum mismatch')
                destination=Path('/opt/tesla-ytdlp')/version/'yt-dlp'
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,destination);destination.chmod(0o755);binary=str(destination)
        help_text=run([binary,'--help'],capture=True).stdout
        if '--js-runtimes' not in help_text:
            raise InstallError('This yt-dlp is too old. Install a current official release with JavaScript runtime support.')
        return binary

    def user(self):
        try:
            account = pwd.getpwnam('tesla-media')
        except KeyError:
            nologin = shutil.which('nologin') or '/sbin/nologin'
            run(['useradd', '--system', '--user-group', '--home-dir', str(self.data), '--shell', nologin, 'tesla-media'])
            account = pwd.getpwnam('tesla-media')
        if account.pw_uid==0 or grp.getgrgid(account.pw_gid).gr_name!='tesla-media':
            raise InstallError('Existing tesla-media account does not use its own unprivileged group.')
        self.data.mkdir(parents=True, exist_ok=True)
        self.data.chmod(0o700)
        os.chown(self.data, account.pw_uid, account.pw_gid)
        logs = Path('/var/log/tesla-media')
        logs.mkdir(parents=True, exist_ok=True)
        os.chown(logs, account.pw_uid, account.pw_gid)
        return account

    def release(self):
        if not (ROOT / 'stream-lab/server.mjs').is_file():
            raise InstallError('Run install.sh from a complete repository checkout.')
        self.install.mkdir(parents=True, exist_ok=True)
        if self.app.exists() and not self.app.is_symlink():
            raise InstallError('The current path is not a managed symlink: ' + str(self.app))
        stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        release = self.install / 'releases' / stamp
        release.mkdir(parents=True)
        source = ROOT / 'stream-lab'
        for item in source.glob('*.mjs'):
            if not item.name.endswith('.test.mjs'):
                shutil.copy2(item, release / item.name)
        shutil.copytree(source / 'static', release / 'static')
        shutil.copy2(source / 'package.json', release / 'package.json')
        for item in release.rglob('*'):
            item.chmod(0o755 if item.is_dir() else 0o644)
        previous = str(self.app.resolve()) if self.app.is_symlink() else None
        temp = self.install / 'current.new'
        temp.unlink(missing_ok=True)
        temp.symlink_to(release)
        temp.replace(self.app)
        return previous

    def install_app_service(self):
        content = app_service(self.init, self.node, self.app, self.data, self.port, self.ffmpeg, self.youtube)
        path = {'systemd': '/etc/systemd/system/tesla-media.service', 'openrc': '/etc/init.d/tesla-media', 'runit': '/etc/sv/tesla-media/run'}[self.init]
        self.backup_write(path, content, 0o644 if self.init == 'systemd' else 0o755, owned=True)
        self.service_written=True
        if shutil.which('restorecon'):
            run(['restorecon','-F',path])
        if self.init == 'runit':
            log_dir = Path('/etc/sv/tesla-media/log')
            self.backup_write(log_dir / 'run', '#!/bin/sh\nexec svlogd -tt /var/log/tesla-media\n', 0o755)
        self.enable('tesla-media')
        self.service('tesla-media', 'restart')
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:' + str(self.port) + '/', timeout=2) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(1)
        raise InstallError('Application did not become healthy. Check service logs.')

    def firewall(self):
        if self.args.firewall == 'skip' or self.proxy == 'none':
            return
        if shutil.which('firewall-cmd') and run(['firewall-cmd', '--state'], capture=True, check=False).returncode == 0:
            for service in (['http','https'] if self.args.tls else ['http']):
                run(['firewall-cmd', '--add-service=' + service])
                run(['firewall-cmd', '--permanent', '--add-service=' + service])
        elif shutil.which('ufw') and 'Status: active' in run(['ufw', 'status'], capture=True, check=False).stdout:
            for port in (['80/tcp','443/tcp'] if self.args.tls else ['80/tcp']):
                run(['ufw', 'allow', port])
        else:
            print('Firewall unchanged. Ensure inbound TCP 80/443 is allowed, including any cloud firewall.')

    def nginx(self):
        if not shutil.which('nginx'):
            self.packages(['www-servers/nginx' if self.manager == 'emerge' else 'nginx'])
        if self.init == 'openrc' and self.manager == 'apk':
            self.packages(['nginx-openrc'], optional=True)
        configuration = run(['nginx', '-T'], capture=True)
        dump = configuration.stdout + configuration.stderr
        domain = self.args.domain
        target = None
        for pattern in [r'^\s*include\s+([^;\s]*conf\.d/\*\.conf);', r'^\s*include\s+([^;\s]*sites-enabled/\*[^;\s]*);']:
            found = re.search(pattern, dump, re.M)
            if found:
                directory = Path(found.group(1)).parent
                if not directory.is_absolute():
                    directory = Path('/etc/nginx') / directory
                target = directory / ('tesla-media-' + domain + '.conf')
                break
        if not target:
            raise InstallError('Cannot find a supported Nginx http include directory. Use --proxy none and the manual proxy guide.')
        if not target.exists() and re.search(r'^\s*server_name\s+[^;]*\b' + re.escape(domain) + r'\b', dump, re.M):
            raise InstallError('This domain already has an Nginx vhost. The installer will not overwrite it. Use --proxy none for the app and update that vhost manually.')
        webroot = Path('/var/www/tesla-media-acme')
        webroot.mkdir(parents=True, exist_ok=True)
        if shutil.which('getenforce') and run(['getenforce'], capture=True).stdout.strip() == 'Enforcing':
            run(['setsebool', '-P', 'httpd_can_network_connect', '1'])
            if shutil.which('restorecon'):
                run(['restorecon', '-RF', str(webroot)])
        cert = Path('/etc/letsencrypt/live') / domain / 'fullchain.pem'
        self.backup_write(target, nginx_site(domain, self.port, tls=self.args.tls and cert.exists(), staging=self.args.tls and not cert.exists(),ipv6=self.ipv6), owned=True)
        run(['nginx', '-t'])
        self.enable('nginx')
        self.service('nginx', 'reload' if self.active('nginx') else 'start')
        if self.args.tls:
            if not shutil.which('certbot'):
                self.packages(['app-crypt/certbot' if self.manager == 'emerge' else 'certbot'])
            hook = Path('/etc/letsencrypt/renewal-hooks/deploy/tesla-media-nginx')
            reload_command = {'systemd': 'systemctl reload nginx', 'openrc': 'rc-service nginx reload', 'runit': 'sv hup /var/service/nginx'}[self.init]
            self.backup_write(hook, '#!/bin/sh\n' + MARKER + '\nnginx -t && ' + reload_command + '\n', 0o755, owned=True)
            run(['certbot', 'certonly', '--webroot', '-w', str(webroot), '-d', domain, '--cert-name', domain, '--non-interactive', '--agree-tos', '--email', self.args.email, '--keep-until-expiring'])
            self.backup_write(target, nginx_site(domain, self.port, tls=True,ipv6=self.ipv6), owned=True)
            run(['nginx', '-t'])
            self.service('nginx', 'reload')
            self.renewal()

    def renewal(self):
        if self.init == 'systemd':
            unit = f'''{MARKER}
[Unit]
Description=Renew Tesla Media TLS certificate
[Service]
Type=oneshot
ExecStart={shutil.which('certbot')} renew --cert-name {self.args.domain} --quiet
'''
            timer = f'''{MARKER}
[Unit]
Description=Check Tesla Media TLS certificate twice daily
[Timer]
OnCalendar=*-*-* 03,15:15:00
RandomizedDelaySec=3600
Persistent=true
[Install]
WantedBy=timers.target
'''
            self.backup_write('/etc/systemd/system/tesla-media-cert-renew.service', unit, owned=True)
            self.backup_write('/etc/systemd/system/tesla-media-cert-renew.timer', timer, owned=True)
            self.enable('tesla-media-cert-renew.timer')
            self.service('tesla-media-cert-renew.timer', 'start')
        else:
            services=['crond','cron','cronie']
            def service_exists(name):
                return Path('/etc/init.d/'+name if self.init=='openrc' else '/etc/sv/'+name+'/run').exists()
            if not any(service_exists(name) for name in services) or not shutil.which('crontab'):
                package='sys-process/cronie' if self.manager=='emerge' else ('dcron' if self.manager=='apk' else 'cronie')
                self.packages([package])
            cron=next((name for name in services if service_exists(name)),None)
            if not cron:
                raise InstallError('Cron has no supported init service. Enable a daily certbot renew task manually.')
            current=run(['crontab','-u','root','-l'],capture=True,check=False).stdout
            job=MARKER+' certificate renewal'
            if job not in current:
                self.config_dir.mkdir(parents=True,exist_ok=True)
                backup=self.config_dir/('crontab.before-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                backup.write_text(current);backup.chmod(0o600)
                run(['crontab','-u','root','-'],input=current.rstrip()+'\n'+job+'\n23 3,15 * * * '+shutil.which('certbot')+' renew --cert-name '+self.args.domain+' --quiet\n')
            self.enable(cron)
            self.service(cron,'restart')

    def install_caddy_binary(self):
        # Prefer signed distribution packages. A static upstream release is a fallback.
        if self.packages(['www-servers/caddy' if self.manager == 'emerge' else 'caddy'], optional=True) and shutil.which('caddy'):
            return
        arch = {'x86_64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64', 'armv7l': 'armv7'}.get(platform.machine())
        if not arch:
            raise InstallError('No static Caddy binary for this architecture; install Caddy manually.')
        metadata = json.loads(self.download('https://api.github.com/repos/caddyserver/caddy/releases/latest'))
        version = metadata['tag_name'].removeprefix('v')
        name = 'caddy_' + version + '_linux_' + arch + '.tar.gz'
        assets = {item['name']: item['browser_download_url'] for item in metadata['assets']}
        checksum_name = next((n for n in assets if n.endswith('_checksums.txt')), None)
        if name not in assets or not checksum_name:
            raise InstallError('Caddy release assets do not match the expected format.')
        with tempfile.TemporaryDirectory(prefix='tesla-caddy-') as tmp:
            tmp = Path(tmp)
            checks = self.download(assets[checksum_name]).decode()
            match = re.search(r'^([a-f0-9]{128}|[a-f0-9]{64})\s+\*?' + re.escape(name) + r'$', checks, re.M)
            archive = tmp / name
            self.download(assets[name], archive)
            if not match or not checksum_valid(archive.read_bytes(),match.group(1)):
                raise InstallError('Caddy archive checksum mismatch')
            checked_extract(archive, tmp / 'unpacked')
            destination = Path('/usr/local/bin/caddy')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp / 'unpacked/caddy', destination)
            destination.chmod(0o755)
        self.caddy_service()

    def caddy_service(self):
        try:
            pwd.getpwnam('caddy')
        except KeyError:
            run(['useradd', '--system', '--user-group', '--home-dir', '/var/lib/caddy', '--shell', shutil.which('nologin') or '/sbin/nologin', 'caddy'])
        account = pwd.getpwnam('caddy')
        if account.pw_uid==0:
            raise InstallError('The caddy service account must not have root UID.')
        for directory in ['/var/lib/caddy', '/var/log/caddy', '/etc/caddy']:
            Path(directory).mkdir(parents=True, exist_ok=True)
        os.chown('/var/lib/caddy', account.pw_uid, account.pw_gid)
        os.chown('/var/log/caddy', account.pw_uid, account.pw_gid)
        binary = shutil.which('caddy')
        if self.init == 'systemd':
            self.backup_write('/etc/systemd/system/caddy.service', f'''{MARKER}
[Unit]
Description=Caddy web server
After=network-online.target
[Service]
User=caddy
Group=caddy
Environment=HOME=/var/lib/caddy XDG_DATA_HOME=/var/lib/caddy XDG_CONFIG_HOME=/var/lib/caddy
ExecStart={binary} run --config /etc/caddy/Caddyfile --adapter caddyfile
ExecReload={binary} reload --config /etc/caddy/Caddyfile --adapter caddyfile
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
Restart=on-failure
[Install]
WantedBy=multi-user.target
''', owned=True)
        else:
            if not shutil.which('setcap'):
                packages = {'apk': 'libcap-utils', 'apt': 'libcap2-bin', 'emerge': 'sys-libs/libcap'}
                self.packages([packages.get(self.manager, 'libcap')])
            run(['setcap', 'cap_net_bind_service=+ep', binary])
            if self.init == 'openrc':
                content = f'''#!/sbin/openrc-run
{MARKER}
command="{binary}"
command_args="run --config /etc/caddy/Caddyfile --adapter caddyfile"
command_user="caddy:caddy"
supervisor="supervise-daemon"
export HOME=/var/lib/caddy XDG_DATA_HOME=/var/lib/caddy XDG_CONFIG_HOME=/var/lib/caddy
depend() {{ need net; }}
reload() {{ {binary} reload --config /etc/caddy/Caddyfile --adapter caddyfile; }}
'''
                self.backup_write('/etc/init.d/caddy', content, 0o755, owned=True)
            else:
                self.backup_write('/etc/sv/caddy/run', '#!/bin/sh\n' + MARKER + '\nexport HOME=/var/lib/caddy XDG_DATA_HOME=/var/lib/caddy XDG_CONFIG_HOME=/var/lib/caddy\nexec chpst -u caddy:caddy ' + binary + ' run --config /etc/caddy/Caddyfile --adapter caddyfile\n', 0o755, owned=True)

    def caddy(self):
        if not shutil.which('caddy'):
            self.install_caddy_binary()
        if self.init == 'openrc' and self.manager == 'apk':
            self.packages(['caddy-openrc'], optional=True)
        has_service=(run(['systemctl','cat','caddy'],check=False,capture=True).returncode==0) if self.init=='systemd' else Path('/etc/init.d/caddy' if self.init=='openrc' else '/etc/sv/caddy/run').exists()
        if not has_service:
            self.caddy_service()
        main = Path('/etc/caddy/Caddyfile')
        directory = Path('/etc/caddy/tesla-media.d')
        site = directory / (self.args.domain + '.caddy')
        if self.init == 'systemd':
            exec_start = run(['systemctl', 'show', 'caddy', '-p', 'ExecStart', '--value'], check=False, capture=True).stdout
            if exec_start and ('--resume' in exec_start or ('--config' in exec_start and '/etc/caddy/Caddyfile' not in exec_start)):
                raise InstallError('Caddy uses an API/custom configuration. Use --proxy none and the manual Caddy guide.')
        original = main.read_text() if main.exists() else ''
        if original.strip():
            adapted = run(['caddy', 'adapt', '--config', main, '--adapter', 'caddyfile'], capture=True)
            if not site.exists() and '"' + self.args.domain + '"' in adapted.stdout:
                raise InstallError('This domain is already configured in Caddy; it will not be overwritten.')
        import_line = 'import /etc/caddy/tesla-media.d/*.caddy'
        if import_line not in original:
            self.backup_write(main, original.rstrip() + '\n\n' + MARKER + '\n' + import_line + '\n')
        self.backup_write(site, caddy_site(self.args.domain, self.port, tls=self.args.tls, email=self.args.email), owned=True)
        run(['caddy', 'validate', '--config', main, '--adapter', 'caddyfile'])
        self.enable('caddy')
        self.service('caddy', 'reload' if self.active('caddy') else 'start')

    def admin(self):
        if not self.args.admin:
            return
        existing = run([self.node, '--input-type=module', '-e', "import {DatabaseSync} from 'node:sqlite';const db=new DatabaseSync(process.argv[1]);console.log(JSON.stringify(db.prepare('SELECT admin FROM users WHERE username=?').get(process.argv[2])||null))", str(self.data / 'accounts.sqlite'), self.args.admin], capture=True)
        account=json.loads(existing.stdout.strip())
        if account is not None:
            if not account['admin']:
                raise InstallError('That username already belongs to a regular account. Choose another administrator name; existing accounts are not promoted.')
            print('Administrator account already exists; password unchanged.')
            return
        if self.args.admin_password_stdin:
            password = sys.stdin.readline().rstrip('\r\n')
        elif sys.stdin.isatty():
            password = getpass.getpass('Password for administrator ' + self.args.admin + ': ')
            if getpass.getpass('Repeat password: ') != password:
                raise InstallError('Passwords do not match')
        else:
            raise InstallError('Use an interactive terminal or --admin-password-stdin; passwords are not accepted as command-line arguments.')
        if not 10<=len(password)<=128:
            raise InstallError('Administrator password must contain 10 to 128 characters.')
        payload = json.dumps({'username': self.args.admin, 'name': self.args.admin_name or self.args.admin, 'password': password})
        env = {**os.environ, 'DATA_DIR': str(self.data)}
        # runuser is preferred; su works on Alpine and other minimal systems.
        if shutil.which('runuser'):
            args = ['runuser', '-u', 'tesla-media', '--', self.node, str(self.app / 'bootstrap.mjs')]
        else:
            args = ['su', '-s', '/bin/sh', 'tesla-media', '-c', shlex.join([self.node, str(self.app / 'bootstrap.mjs')])]
        run(args, input=payload, env=env)

    def verify_tls(self):
        if not self.args.tls or self.proxy == 'none':
            return
        for _ in range(20):
            try:
                with urllib.request.urlopen('https://' + self.args.domain + '/', timeout=3) as response:
                    if response.status == 200:
                        print('Public HTTPS verified with a trusted certificate.')
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(2)
        print('WARNING: HTTPS could not be verified from this server. Check DNS A/AAAA, TCP 80/443, cloud firewall and ACME logs. Caddy will retry certificate issuance automatically.')

    def execute(self):
        if self.args.plan:
            print(json.dumps({'platform': platform.system(), 'distro': self.os.get('PRETTY_NAME', 'unknown'), 'package_manager': self.manager, 'init': self.init, 'proxy': self.proxy, 'domain': self.args.domain, 'port': self.port, 'install_dir': str(self.install), 'data_dir': str(self.data), 'tls': self.args.tls and self.proxy != 'none', 'ipv6':self.ipv6, 'base_packages': BASE.get(self.manager, []), 'youtube': self.args.youtube if self.args.youtube is not None else bool(self.state.get('youtube')), 'changes': 'none (read-only plan)'}, indent=2))
            return
        if platform.system() != 'Linux' or os.geteuid() != 0:
            raise InstallError('Run this installer as root on Linux: sudo sh install.sh ...')
        if not self.manager or not self.init:
            raise InstallError('Automatic installation requires a supported package manager and systemd, OpenRC or runit. See docs/INSTALLATION.md for manual/container setup.')
        if self.proxy != 'none' and not self.args.domain:
            raise InstallError('--domain is required unless --proxy none is used.')
        if self.proxy == 'nginx' and self.args.tls and not self.args.email:
            raise InstallError('Nginx + Let’s Encrypt requires --email. Use --no-tls for HTTP-only setup.')
        other = 'caddy' if self.proxy == 'nginx' else 'nginx'
        if self.proxy=='caddy' and self.active('caddy-api'):
            raise InstallError('Caddy uses its API-managed service. Use --proxy none and configure the existing Caddy instance manually.')
        if self.proxy != 'none' and self.active(other):
            raise InstallError('The other web server (' + other + ') is active. Select that server or free TCP 80/443 before installing another proxy.')
        if self.proxy!='none' and not self.active(self.proxy):
            for public_port in ([80,443] if self.args.tls else [80]):
                with socket.socket() as probe:
                    try:
                        probe.bind(('0.0.0.0',public_port))
                    except OSError:
                        raise InstallError('TCP '+str(public_port)+' is owned by another server/process. Use --proxy none or configure that existing proxy.')
        if self.data.is_symlink() or self.install.is_symlink():
            raise InstallError('Installation/data directories must not be symlinks.')
        if any(self.install.is_relative_to(Path(base)) or self.data.is_relative_to(Path(base)) for base in ['/home','/root','/tmp','/run']):
            raise InstallError('Use persistent service directories outside /home, /root, /tmp and /run.')
        if self.args.port and self.state.get('port') != self.args.port:
            if free_port(self.args.port) != self.args.port:
                raise InstallError('Requested port is already in use.')
        if self.install == self.data or self.data.is_relative_to(self.install):
            raise InstallError('DATA_DIR must be outside the application installation directory.')
        for binary in [self.args.node,self.args.ffmpeg,self.args.yt_dlp]:
            if binary and (not Path(binary).is_file() or not os.access(binary,os.X_OK)):
                raise InstallError('Executable not found: '+str(binary))
        if not (ROOT/'stream-lab/server.mjs').is_file():
            raise InstallError('Run from a complete repository checkout.')
        if self.args.admin and not re.fullmatch(r'[A-Za-z0-9_.-]{3,32}',self.args.admin):
            raise InstallError('Administrator username must contain 3–32 letters, digits, dots or dashes.')
        if self.args.admin_password_stdin and not self.args.admin:
            raise InstallError('--admin-password-stdin requires --admin.')
        if self.manager == 'apt':
            run(['apt-get', 'update'])
        self.packages(BASE[self.manager])
        self.node = self.install_node()
        self.ffmpeg = self.install_ffmpeg()
        self.youtube = self.install_youtube()
        self.user()
        previous = str(self.app.resolve()) if self.app.is_symlink() else None
        try:
            self.release()
            if shutil.which('restorecon'):
                run(['restorecon','-RF',str(self.app.resolve()),str(self.data)])
            self.install_app_service()
            self.admin()
            self.firewall()
            if self.proxy == 'nginx':
                self.nginx()
            elif self.proxy == 'caddy':
                self.caddy()
        except Exception:
            self.restore_configs()
            if previous:
                self.app.unlink(missing_ok=True)
                self.app.symlink_to(previous)
            with contextlib.suppress(Exception):
                if self.init=='systemd':
                    run(['systemctl','daemon-reload'])
                if self.service_written:
                    if previous:
                        self.service('tesla-media','restart',check=False)
                    else:
                        self.service('tesla-media','stop',check=False)
                        if self.init=='systemd':
                            run(['systemctl','disable','tesla-media'],check=False)
                            link=Path('/etc/systemd/system/multi-user.target.wants/tesla-media.service')
                            if link.is_symlink() and str(link.readlink())=='/etc/systemd/system/tesla-media.service':
                                link.unlink()
                        elif self.init=='openrc':
                            run(['rc-update','del','tesla-media','default'],check=False)
                            link=Path('/etc/runlevels/default/tesla-media')
                            if link.is_symlink() and str(link.readlink())=='/etc/init.d/tesla-media':
                                link.unlink()
                        else:
                            Path('/var/service/tesla-media').unlink(missing_ok=True)
            if not previous and self.app.is_symlink():
                self.app.unlink()
            raise
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({'port': self.port, 'proxy': self.proxy, 'domain': self.args.domain, 'node': self.node, 'ffmpeg': self.ffmpeg, 'youtube': self.youtube, 'install_dir': str(self.install), 'data_dir': str(self.data), 'init': self.init}, indent=2) + '\n')
        self.state_path.chmod(0o600)
        self.verify_tls()
        address = ('https://' if self.args.tls else 'http://') + self.args.domain if self.proxy != 'none' else 'http://127.0.0.1:' + str(self.port)
        print('\nTesla Media installed: ' + address)
        print('Application: ' + str(self.app) + '\nPersistent data: ' + str(self.data))
        print('Rerun the same command to deploy an update. Existing users, passwords, sources and favorites are preserved.')


def parser():
    p = argparse.ArgumentParser(description='Install/update Tesla Media on Linux, with dependency and reverse-proxy detection.')
    p.add_argument('--domain', type=domain_name, help='Public hostname, e.g. media.example.com')
    p.add_argument('--email', help='ACME email (required for Nginx HTTPS)')
    p.add_argument('--proxy', choices=['auto', 'nginx', 'caddy', 'none'], default='auto')
    p.add_argument('--no-tls', dest='tls', action='store_false', help='HTTP only; do not request a certificate')
    p.add_argument('--port', type=int, help='Local application port; otherwise reuse or choose a free port')
    p.add_argument('--install-dir', type=safe_path, default=Path('/opt/tesla-media'))
    p.add_argument('--data-dir', type=safe_path, default=Path('/var/lib/tesla-media'))
    p.add_argument('--node', type=safe_path, help='Use this existing Node >=22.13 binary')
    p.add_argument('--ffmpeg', type=safe_path, help='Use this existing full-codec FFmpeg binary')
    youtube=p.add_mutually_exclusive_group()
    youtube.add_argument('--youtube',dest='youtube',action='store_true',default=None,help='Enable YouTube; install/update the official standalone yt-dlp helper')
    youtube.add_argument('--no-youtube',dest='youtube',action='store_false',help='Disable YouTube (keep stored history)')
    p.add_argument('--yt-dlp',type=safe_path,help='Existing recent yt-dlp executable, used with --youtube')
    p.add_argument('--admin', help='Create an administrator account (password prompted securely)')
    p.add_argument('--admin-name', help='Display name for a new administrator')
    p.add_argument('--admin-password-stdin', action='store_true', help='Read the new administrator password from stdin')
    p.add_argument('--extra-repos', action='store_true', help='Allow EPEL/RPM Fusion setup if EL/Fedora FFmpeg installation fails')
    p.add_argument('--firewall', choices=['auto', 'skip'], default='auto')
    p.add_argument('--plan', action='store_true', help='Print a read-only plan; do not install or write anything')
    return p


def main():
    args = parser().parse_args()
    if args.port is not None and not 1024 <= args.port <= 65535:
        raise InstallError('--port must be between 1024 and 65535')
    if args.email and not re.fullmatch(r'[^\s@{}]+@[^\s@{}]+\.[^\s@{}]+', args.email):
        raise InstallError('Invalid ACME email address')
    Installer(args).execute()

if __name__ == '__main__':
    try:
        main()
    except (InstallError, OSError, ValueError, subprocess.TimeoutExpired, urllib.error.URLError) as error:
        print('\nInstallation stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
