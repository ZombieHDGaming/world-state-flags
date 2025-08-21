from bs4 import BeautifulSoup
import orjson
import os
import requests
import subprocess
import traceback


def download_flag(url, outfile):
    response = requests.get(url)

    if response.status_code == 200:
        with open("./tmp.gif", 'wb') as f:
            f.write(response.content)

        subprocess.call(f'convert ./tmp.gif -resize 64x {outfile}', shell=True)


f = open('./curated_links.json')
data = orjson.loads(f.read())

for country in data:
    for s, (state_code, flag_link) in enumerate(data[country].items()):
        try:
            print(f'{country} - {state_code} {s}/{len(data[country].keys())}')
            countryPath = f"./out_curated/{country}"
            os.makedirs(countryPath, exist_ok=True)
            download_flag(
                flag_link,
                f'{countryPath}/{state_code.upper()}.png'
            )
        except Exception as e:
            print(traceback.format_exc())
