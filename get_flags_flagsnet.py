import asyncio
import aiohttp
from bs4 import BeautifulSoup
from pathlib import Path
import orjson
import os
import string
import unicodedata
from PIL import Image
from io import BytesIO

dont_download = ["/misc/"]


def CanDownload(url: str) -> bool:
    return all(d not in url for d in dont_download)


def remove_accents_lower(input_str: str) -> str:
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join(c for c in nfkd_form if not unicodedata.combining(c)).lower().strip()


def resize_and_save_gif(data: bytes, outfile: str):
    img = Image.open(BytesIO(data))
    img = img.resize((64, int(img.height * (64 / img.width))), Image.LANCZOS)
    img.save(outfile, "PNG")


async def fetch_html(session: aiohttp.ClientSession, url: str) -> BeautifulSoup:
    async with session.get(url) as resp:
        text = await resp.text(encoding="utf-8", errors="ignore")
        return BeautifulSoup(text, "lxml")


async def fetch_binary(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url) as resp:
        return await resp.read()


async def fetch_keyword_pages(session):
    tasks = [
        fetch_html(session, f"https://www.fotw.info/flags/keyword{letter}.html")
        for letter in string.ascii_lowercase
    ]
    results = await asyncio.gather(*tasks)
    return dict(zip(string.ascii_lowercase, results))


async def fetch_countries_data(session):
    url = "https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/refs/heads/master/json/countries%2Bstates%2Bcities.json"
    raw = await fetch_binary(session, url)

    # validate JSON
    data = orjson.loads(raw)

    out_file = Path("./countries+states+cities.json")
    out_file.write_bytes(raw)  # write once

    return data


async def download_flag(session, url: str, outfile: str):
    data = await fetch_binary(session, url)
    resize_and_save_gif(data, outfile)


async def process_region(session, country, region, keywordSoups, countryPath):
    if region.get("iso2") == "CON":
        region["iso2"] = "_CON"

    tries = [remove_accents_lower(region["name"]), region["iso2"]]

    for nameTry in tries:
        try:
            url = f"https://www.fotw.info/flags/{country['iso2']}-{nameTry}.html"
            soup = await fetch_html(session, url)

            allImages = [img for img in soup.select("img") if CanDownload(img.get("src"))]

            if len(allImages) > 1:
                imgSrc = allImages[1]["src"]
                if imgSrc.startswith("../"):
                    imgSrc = f"https://www.fotw.info/{imgSrc[2:]}"
                print(f"Found {countryPath}/{region['iso2']} - {imgSrc}")
                await download_flag(
                    session, imgSrc, f"{countryPath}/{region['iso2'].upper()}.png"
                )
                return True
        except Exception as e:
            print("Error:", e)

    # Fallback: keyword page
    try:
        regionName = remove_accents_lower(region["name"])
        regionCountry = remove_accents_lower(country["name"])

        soup = keywordSoups[regionName[0]]
        links = soup.select("a")

        subpage = None
        for link in links:
            if (
                remove_accents_lower(link.text)
                == f"{regionName} ({regionCountry})"
                and link.get("href")
            ):
                subpage = "https://www.fotw.info/flags/" + link["href"]
                break

        if subpage:
            soup = await fetch_html(session, subpage)
            allImages = [img for img in soup.select("img") if CanDownload(img.get("src"))]
            if len(allImages) > 1:
                imgSrc = allImages[1]["src"]
                if imgSrc.startswith("../"):
                    imgSrc = f"https://www.fotw.info/{imgSrc[2:]}"
                print(f"Found alternative {countryPath}/{region['iso2']} - {imgSrc}")
                await download_flag(
                    session, imgSrc, f"{countryPath}/{region['iso2'].upper()}.png"
                )
    except Exception as e:
        print("Error:", e)


async def main():
    async with aiohttp.ClientSession() as session:
        print("Fetching keyword pages...")
        keywordSoups = await fetch_keyword_pages(session)

        print("Fetching country/state JSON...")
        data = await fetch_countries_data(session)

        numCountries = len(data)
        for i, country in enumerate(data, start=1):
            cname = country["name"]
            print(f"{cname} - {i}/{numCountries}")

            countryPath = f"./out_flagsnet/{country['iso2']}"
            os.makedirs(countryPath, exist_ok=True)

            # Run all region fetches in parallel
            tasks = [
                process_region(session, country, region, keywordSoups, countryPath)
                for region in country["states"]
            ]
            await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
