"""Native SynHub host lifecycle and per-session file transport."""
import atexit
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from .registration import write_config


def installations():
    found = {}
    directory = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Autodesk/Synergy'
    for path in directory.glob('*.syncfg'):
        try:
            for app in ET.parse(path).getroot().findall('Application'):
                if app.get('Name') == 'MotionBuilder':
                    exe = Path(app.get('ExecutablePath', ''))
                    if exe.is_file() and exe.with_name('synHub.dll').is_file():
                        found[app.get('NumericVersion', '').split('.')[0]] = exe
        except (OSError, ET.ParseError):
            continue
    return found


class Agent:
    def __init__(self):
        self.process = None
        self.directory = None
        self.identity = None
        self.error = ''
        self.notice = ''
        self.peers = []
        self.targets = []
        self.lock = None
        self.environment = None
        self.mobu = None
        self.registration = None

    def start(self, product, year, mobu_year='2026', register_system=True):
        if self.process is not None and self.process.poll() is None:
            return
        self.stop()
        if product not in ('Maya', '3ds Max') or str(year) not in map(str, range(2023, 2028)):
            raise ValueError('Unsupported emulation identity')
        if os.name != 'nt':
            raise RuntimeError('Windows is required')
        found = installations()
        if str(mobu_year) not in found:
            raise RuntimeError(f'MotionBuilder {mobu_year} was not found in Autodesk Synergy registrations')
        self.mobu = found[str(mobu_year)]
        home = Path(os.environ.get('SEND2_HOME', str(Path(os.environ['LOCALAPPDATA']) / 'SaintMocap/Send2Mobu')))
        runtime = home / (product.replace(' ', '') + '-' + str(year))
        runtime.mkdir(parents=True, exist_ok=True)
        import msvcrt
        self.lock = (runtime / 'owner.lock').open('a+b')
        try:
            self.lock.seek(0); self.lock.write(b'0'); self.lock.flush(); self.lock.seek(0)
            msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.lock.close(); self.lock = None
            raise RuntimeError('This emulated product/version is already Online in another Blender instance')
        try:
            host = runtime / 'Send2MobuHost.exe'
            shutil.copy2(Path(__file__).with_name('bin') / host.name, host)
            self.directory = Path(tempfile.mkdtemp(prefix='session-', dir=runtime))
            self.identity = (product, str(year)); self.error = ''; self.notice = ''; self.peers = []
            config = self.directory / 'config'
            write_config(config, product, year, host)
            # Register the chosen Mobu executable under the emulated year for cross-version routing.
            root = ET.Element('SynHubConfig', SchemaVersion='1.0')
            ET.SubElement(root, 'Application', Name='MotionBuilder', StringVersion=f'MotionBuilder {mobu_year}',
                          NumericVersion=str(year), ExecutablePath=str(self.mobu), Architecture='x86_64')
            ET.ElementTree(root).write(config / 'MotionBuilder.syncfg', encoding='utf-8', xml_declaration=True)
            self.environment = dict(os.environ, SYNHUB_CONFIG_PATH=str(config))
            (runtime / 'host-config.txt').write_text('\n'.join([str(self.directory), str(self.mobu.with_name('synHub.dll')), str(os.getpid())]), encoding='utf-8')
            if register_system:
                self._register_system(product, year, host)
            arguments = [str(host), str(self.directory), str(self.mobu.with_name('synHub.dll')), str(os.getpid())]
            self.process = subprocess.Popen(arguments, env=self.environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            self.stop()
            raise

    def _register_system(self, product, year, host):
        directory = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Autodesk/Synergy'
        owned = f'Send2.{product.replace(" ", "")}.{year}.syncfg'
        for path in directory.glob('*.syncfg'):
            if path.name == owned:
                continue
            try:
                apps = ET.parse(path).getroot().findall('Application')
                if any(a.get('Name') == product and a.get('NumericVersion', '').split('.')[0] == str(year) for a in apps):
                    self.notice = 'Real product registration exists. Use Launch MotionBuilder for this session.'
                    return
            except (OSError, ET.ParseError):
                continue
        try:
            self.registration = write_config(directory, product, year, host)
            self.notice = 'If Send To is disabled, restart Mobu or use Launch MotionBuilder.'
        except OSError:
            self.notice = 'System registration is not writable. Use Launch MotionBuilder.'

    def launch_mobu(self):
        if self.status() not in {'ONLINE', 'CONNECTED'}:
            raise RuntimeError('Go Online first')
        # A fresh process receives isolated registrations; no Mobu plugin is installed.
        return subprocess.Popen([str(self.mobu)], env=self.environment)

    def status(self):
        if self.process is None:
            self.peers = []; self.targets = []
            return 'OFFLINE'
        if self.process.poll() is not None:
            self.peers = []; self.targets = []
            try:
                self.error = json.loads((self.directory / 'fatal.json').read_text())['error']
            except (OSError, ValueError, KeyError):
                self.error = f'Host exited ({self.process.returncode}). See {self.directory / "native.log"}'
            return 'ERROR'
        try:
            state = json.loads((self.directory / 'status.json').read_text(encoding='utf-8'))
            if state['pid'] != self.process.pid or time.time() - state['heartbeat'] > 5:
                self.peers = []; self.targets = []
                return 'UNRESPONSIVE'
            self.peers = state['peers']
            self.targets = state.get('targets', [])
            return 'CONNECTED' if self.peers else 'ONLINE'
        except (OSError, ValueError, KeyError):
            return 'STARTING'

    def connect(self, pid):
        if self.status() not in {'ONLINE', 'CONNECTED'}:
            raise RuntimeError('Go Online first')
        path = self.directory / f'connect-{uuid.uuid4().hex}.json'
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps({'pid': int(pid)}), encoding='utf-8')
        pending.replace(path)
        return path

    def send(self, link, xml):
        if self.status() not in {'ONLINE', 'CONNECTED'} or int(link) <= 0:
            raise RuntimeError('MotionBuilder is no longer connected')
        name = f'out-{time.time_ns():020d}-{uuid.uuid4().hex}.json'
        path = self.directory / name
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps({'link': int(link), 'xml': xml}), encoding='utf-8')
        pending.replace(path)
        return path

    def stop(self):
        try:
            if self.process is not None and self.process.poll() is None:
                (self.directory / 'stop').touch()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.terminate(); self.process.wait(timeout=3)
        finally:
            self.process = None; self.identity = None; self.peers = []; self.targets = []
            if self.lock:
                self.lock.close(); self.lock = None
            # Remove only this instance's own registration, never Autodesk's files.
            if self.registration:
                try: self.registration.unlink(missing_ok=True)
                except OSError: pass
                self.registration = None

agent = Agent()
atexit.register(agent.stop)
