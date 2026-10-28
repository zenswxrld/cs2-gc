"""CI only: print the failing ctest names and their first error lines as GitHub annotations (readable from the API
when the job log itself can not be downloaded)."""
from pathlib import Path
import re

folder = Path('build/Testing/Temporary')
failed = folder / 'LastTestsFailed.log'
print('::error::failed tests: ' + (' '.join(failed.read_text(errors='replace').split()) if failed.exists() else 'unknown'))
log = (folder / 'LastTest.log').read_text(errors='replace') if (folder / 'LastTest.log').exists() else ''
hits = [line.strip()[:300] for line in log.splitlines() if re.search(r'FAIL|Error|Traceback|assert|Exception', line)]
for line in hits[:9]:
    print('::error::' + line.replace('%', '%25').replace('\r', '').replace('\n', ' '))
