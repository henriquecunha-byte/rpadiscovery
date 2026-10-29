"""Build the demonstrated context UI without importing application or DB code.

Output is a disposable local build in cache/context-ui-preview. The canonical
form, rules and styles remain in rpa_docs/static instead of a divergent copy.
"""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'rpa_docs' / 'static'
SOURCE = ROOT / 'integrations' / 'context-ui'
OUTPUT = ROOT / 'cache' / 'context-ui-preview'


def build(output: Path = OUTPUT) -> Path:
    html = (STATIC / 'index.html').read_text(encoding='utf-8')
    start = html.index('      <fieldset id="step2"')
    end = html.index('      <fieldset id="step3"', start)
    fragment = html[start:end].replace(' hidden>', '>', 1)
    shell = (SOURCE / 'shell.html').read_text(encoding='utf-8')
    page = shell.replace('<!-- DISCOVERY_CONTEXT_FORM -->', fragment)
    files = {}
    for name in ('styles.css', 'context-form.css', 'context-model.js', 'context-form.js', 'context-rules.json'):
        # Only static asset URLs change; no service URL is added to the export.
        files[name] = (STATIC / name).read_text(encoding='utf-8').replace('/static/', './')
    files['index.html'] = page
    for name in ('context-preview.css', 'context-preview.js'):
        files[name] = (SOURCE / name).read_text(encoding='utf-8')
    files['manifest.json'] = json.dumps({
        'version': 1, 'component': 'discovery-context',
        'source': 'rpa_docs/static', 'reference_meeting': '2026-10-14',
        'reference_interval': '08:15–09:45',
        'profiles': list(json.loads(files['context-rules.json'])['profiles']),
        'event': 'discovery:requestready',
        'includes_backend': False, 'includes_credentials': False,
    }, ensure_ascii=False, indent=2) + '\n'
    output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (output / name).write_text(content, encoding='utf-8')
    fonts = output / 'btime' / 'fontes'
    fonts.mkdir(parents=True, exist_ok=True)
    for name in ('Branding-Semilight.woff', 'Branding-Medium.woff', 'Branding-Semibold.woff'):
        shutil.copyfile(STATIC / 'btime' / 'fontes' / name, fonts / name)
    return output


if __name__ == '__main__':
    print(build())
