"""Generate isolated registration files; never overwrite Autodesk registrations."""
from pathlib import Path
import xml.etree.ElementTree as ET


def write_config(directory, product, year, executable):
    if product not in ('Maya', '3ds Max') or str(year) not in map(str, range(2023, 2028)):
        raise ValueError('Unsupported emulation identity')
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    root = ET.Element('SynHubConfig', SchemaVersion='1.0')
    ET.SubElement(root, 'Application', Name=product,
        StringVersion=f'{product} {year}', NumericVersion=str(year),
        ExecutablePath=str(executable), Architecture='x86_64')
    path = directory / f'Send2.{product.replace(" ", "")}.{year}.syncfg'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    return path
