import urllib.request
import os

txt_file = 'C:/Users/bonkc/Downloads/74824v002.txt'
output_dir = 'data/wound_salve'

os.makedirs(output_dir, exist_ok=True)

lines = open(txt_file).readlines()
total = len(lines)

# Extract only image/video URLs
urls = [line.strip() for line in lines if line.strip().startswith('https://') and ('.jpg' in line or '.mp4' in line)]
print(f"Found {len(urls)} image/video files out of {total} lines")

for i, url in enumerate(urls):
    filename = url.split('/')[-1].split('?')[0]
    dest = f'{output_dir}/{filename}'
    if os.path.exists(dest):
        print(f'[{i+1}/{len(urls)}] Skipping {filename} (already exists)')
        continue
    print(f'[{i+1}/{len(urls)}] Downloading {filename}')
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        print(f'Failed: {e}')

print('Done.')