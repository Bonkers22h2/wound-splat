import urllib.request
import os
import argparse
from pathlib import Path

GAUSSIAN_SPLATTING_DIR = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(description="Download wound salve dataset files from a URL list.")
parser.add_argument(
    "txt_file",
    nargs="?",
    default=os.getenv("SALVE_URL_LIST"),
    help="Path to the text file containing image/video URLs.",
)
parser.add_argument(
    "--output-dir",
    default=str(GAUSSIAN_SPLATTING_DIR / "data" / "wound_salve"),
    help="Directory where downloaded files will be stored.",
)
args = parser.parse_args()

if not args.txt_file:
    raise SystemExit("Provide a URL list file path or set SALVE_URL_LIST.")

txt_file = Path(args.txt_file).resolve()
output_dir = Path(args.output_dir).resolve()
output_dir.mkdir(parents=True, exist_ok=True)

lines = txt_file.read_text().splitlines()
total = len(lines)

# Extract only image/video URLs
urls = [line.strip() for line in lines if line.strip().startswith('https://') and ('.jpg' in line or '.mp4' in line)]
print(f"Found {len(urls)} image/video files out of {total} lines")

for i, url in enumerate(urls):
    filename = url.split('/')[-1].split('?')[0]
    dest = output_dir / filename
    if os.path.exists(dest):
        print(f'[{i+1}/{len(urls)}] Skipping {filename} (already exists)')
        continue
    print(f'[{i+1}/{len(urls)}] Downloading {filename}')
    try:
        urllib.request.urlretrieve(url, str(dest))
    except Exception as e:
        print(f'Failed: {e}')

print('Done.')
