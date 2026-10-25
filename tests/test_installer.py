import argparse
import importlib.util
from pathlib import Path
import socket
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts/install.py')
i = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(i)

class DetectionTests(unittest.TestCase):
    def test_all_package_managers(self):
        for name, binary in i.MANAGERS.items():
            with self.subTest(name=name):
                self.assertEqual(i.detect_manager(lambda value: '/bin/' + value if value == binary else None), name)
                self.assertIn(binary, i.package_command(name, ['example']))
                self.assertIn('example', i.package_command(name, ['example']))
        self.assertIsNone(i.detect_manager(lambda _: None))

    def test_init_matrix(self):
        for expected, tools, paths in [
            ('systemd', {'systemctl'}, {'/run/systemd/system'}),
            ('openrc', {'rc-service', 'rc-update'}, set()),
            ('runit', {'sv'}, {'/etc/runit'}),
            (None, set(), set()),
        ]:
            self.assertEqual(i.detect_init(lambda x: x if x in tools else None, lambda x: x in paths), expected)

    def test_os_release_is_parsed_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'os-release'
            source.write_text('ID=rocky\nPRETTY_NAME="Rocky Linux 9"\nVERSION_ID="9.8"\nFOO="$(touch /tmp/not-executed)"\n')
            data=i.read_os(source)
            self.assertEqual(data['PRETTY_NAME'],'Rocky Linux 9')
            self.assertIn('$(touch',data['FOO'])

    def test_proxy_selection(self):
        obj=i.Installer.__new__(i.Installer)
        obj.active=lambda name: name=='nginx'
        self.assertEqual(obj.choose_proxy('auto'),'nginx')
        self.assertEqual(obj.choose_proxy('caddy'),'caddy')
        obj.active=lambda name: True
        with self.assertRaises(i.InstallError):obj.choose_proxy('auto')
        obj.active=lambda name: False
        with patch.object(i.shutil,'which',side_effect=lambda name:'/bin/caddy' if name=='caddy' else None):
            self.assertEqual(obj.choose_proxy('auto'),'caddy')

    def test_validated_domain_paths_and_ports(self):
        self.assertEqual(i.domain_name('Media.Example.Com.'),'media.example.com')
        for domain in ['https://example.com','example.com; include foo','*.example.com','x\nexample.com']:
            with self.assertRaises(argparse.ArgumentTypeError):i.domain_name(domain)
        for path in ['/var/lib','/etc/nginx','/','relative/path','/opt/a b','/opt/../etc']:
            with self.assertRaises(argparse.ArgumentTypeError):i.safe_path(path)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));used=sock.getsockname()[1]
            self.assertNotEqual(i.free_port(used),used)

class ConfigurationTests(unittest.TestCase):
    def test_nginx_streaming_and_acme(self):
        text=i.nginx_site('media.example.com',8765,tls=True)
        for value in ['proxy_buffering off','proxy_request_buffering off','proxy_read_timeout 3600s','X-Forwarded-Proto $scheme','location /.well-known/acme-challenge/','fullchain.pem','127.0.0.1:8765']:
            self.assertIn(value,text)
        self.assertNotIn('$request_uri"',text)
        stage=i.nginx_site('media.example.com',8765,staging=True)
        self.assertIn('return 503',stage)
        self.assertNotIn('ssl_certificate',stage)
        self.assertIn('proxy_pass',i.nginx_site('media.example.com',8765))

    def test_caddy_and_init_templates(self):
        caddy=i.caddy_site('media.example.com',8765,email='admin@example.com')
        self.assertIn('flush_interval 100ms',caddy)
        self.assertIn('keepalive 4s',caddy)
        self.assertIn('tls admin@example.com',caddy)
        self.assertIn('http://media.example.com',i.caddy_site('media.example.com',8765,tls=False))
        for init in ['systemd','openrc','runit']:
            text=i.app_service(init,'/usr/bin/node',Path('/opt/tesla/current'),Path('/var/lib/tesla'),8765,'/usr/bin/ffmpeg','/opt/yt-dlp')
            self.assertIn('/opt/yt-dlp',text)
            self.assertIn('/var/lib/tesla',text)
            self.assertIn('127.0.0.1',text)
            self.assertIn('tesla-media',text)
        self.assertIn('ReadWritePaths=/var/lib/tesla',i.app_service('systemd','/usr/bin/node','/opt/app','/var/lib/tesla',8765,'/usr/bin/ffmpeg'))

    def test_config_backups_ownership_and_rollback(self):
        obj=i.Installer.__new__(i.Installer);obj.modified=[];obj.proxy='none'
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'existing.conf';file.write_text(i.MARKER+'\nold\n');file.chmod(0o640)
            obj.backup_write(file,i.MARKER+'\nnew\n',owned=True)
            self.assertEqual(file.stat().st_mode&0o777,0o640)
            self.assertEqual(len(list(Path(tmp).glob('*.tesla-backup-*'))),1)
            foreign=Path(tmp)/'foreign.conf';foreign.write_text('do not touch')
            with self.assertRaises(i.InstallError):obj.backup_write(foreign,'new',owned=True)
            new=Path(tmp)/'new.conf';obj.backup_write(new,i.MARKER+'\n')
            obj.restore_configs()
            self.assertEqual(file.read_text(),i.MARKER+'\nold\n')
            self.assertEqual(foreign.read_text(),'do not touch')
            self.assertFalse(new.exists())

    def test_official_release_checksums_support_sha256_and_sha512(self):
        import hashlib
        data=b'official-release'
        self.assertTrue(i.checksum_valid(data,hashlib.sha256(data).hexdigest()))
        self.assertTrue(i.checksum_valid(data,hashlib.sha512(data).hexdigest()))
        self.assertFalse(i.checksum_valid(data,'0'*64))
        self.assertFalse(i.checksum_valid(data,'f'*96))

    def test_archive_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'evil.tar';target=Path(tmp)/'out'
            with tarfile.open(archive,'w') as tar:
                member=tarfile.TarInfo('../escape');tar.addfile(member)
            with self.assertRaises(i.InstallError):i.checked_extract(archive,target)
            self.assertFalse((Path(tmp)/'escape').exists())

if __name__=='__main__':unittest.main()
