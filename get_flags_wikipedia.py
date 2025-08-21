from bs4 import BeautifulSoup
import orjson
from pathlib import Path
import re
import unicodedata
import os
import requests


def GenStateNameTries(stateName):
    stateName = stateName.strip()
    stateName = re.sub(r'\([^)]*\)', "", stateName).strip()
    stateName = stateName.split(",")[0]

    stateNameReduced = re.sub(
        r'(Flag of|Region|Municipality|Province|Province of|Governorate|Department|Country|Republic|District|Oblast|Voblast|Territory|City|Metropolitan City of|Metropolitan|Special|Self-Governing)', "", stateName, flags=re.IGNORECASE
    ).strip()

    stateNameTries = [
        stateName,
        stateNameReduced,
        "Flag of "+stateName,
        "Flag of "+stateNameReduced,
        stateNameReduced+" Region",
        stateNameReduced+" Municipality",
        stateNameReduced+" Province",
        stateNameReduced+" Governorate",
        stateNameReduced+" Department",
        stateNameReduced+" Country",
        stateNameReduced+" Republic",
        stateNameReduced+" District",
        stateNameReduced+" District Municipality",
        "Canton of "+stateNameReduced,
        "Province of "+stateNameReduced,
        "City of "+stateNameReduced,
        "Metropolitan City of "+stateNameReduced,
        "Federal State of "+stateNameReduced,
        stateNameReduced+" Oblast",
        stateNameReduced+" Voblast",
        stateNameReduced+" Prefecture",
        stateNameReduced+" Territory",
        stateNameReduced+" City",
        stateNameReduced+" Emirate",
        stateNameReduced+" Canton"
    ]

    return stateNameTries


url = 'https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/refs/heads/master/json/countries%2Bstates%2Bcities.json'

out_file = Path('./countries+states+cities.json')

r = requests.get(url, allow_redirects=True)
tmp_file = Path('./countries+states+cities.json.tmp')

with tmp_file.open(mode='wb') as f:
    f.write(r.content)

try:
    # Test if downloaded JSON is valid
    with tmp_file.open(mode='r', encoding='utf-8') as f:
        orjson.loads(f.read())

    # Remove old file, overwrite with new one
    tmp_file.replace(out_file)
except Exception as e:
    print(f"An exception occurred: {e}")

def remove_accents_lower(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


f = open('./countries+states+cities.json', 'r', encoding='utf-8')
data = orjson.loads(f.read())

f = open('./country_name_remapping.json', 'r', encoding='utf-8')
remap = orjson.loads(f.read())

url = 'https://en.wikipedia.org/wiki/Flags_of_country_subdivisions'
page = requests.get(url).text
soup = BeautifulSoup(page, features="lxml")

additionalURLs = {
    "PT": [
        "https://en.wikipedia.org/wiki/List_of_Portuguese_municipal_flags"
    ]
}

countries = soup.select('h2 > span.mw-headline, h3 > span.mw-headline')

def get_flag_url_from_infobox(url):
    page = requests.get(url).text
    soup = BeautifulSoup(page, features="lxml")

    infobox = soup.select_one(".infobox.ib-settlement.vcard")

    if infobox:
        images = infobox.select("img")

        for img in images:
            if (img["alt"] and "flag" in img["alt"].lower()):
                print("> Found flag in infobox!")
                return img["src"]
    
    return None

def download_flag(url, country_code, state_code):
    if not url.startswith("http"):
        url = "http:"+url
    
    if state_code == "CON":
        state_code = "_CON"
    
    response = requests.get(re.sub(r'\d*px', "64px", url),
                            headers={'User-Agent': "Magic Browser"})
    if response.status_code == 200:
        with open("./out_wikipedia/"+country_code+"/"+state_code+".png", 'wb') as f:
            f.write(response.content)
    else:
        print(response.status_code)
        
        response = requests.get(url, headers={'User-Agent': "Magic Browser"})
        if response.status_code == 200:
            with open("./out_wikipedia/"+country_code+"/"+state_code+".png", 'wb') as f:
                f.write(response.content)
        else:
            print(response.status_code)

for country in countries:
    countryname = country.text.strip()

    if countryname in remap.keys():
       countryname = remap[countryname]

    found = next((c for c in data if c["name"] == countryname), None)

    if found:
        print(countryname)

        os.makedirs("./out_wikipedia/"+found["iso2"], exist_ok=True)

        nextElement = country.findNext()

        foundStates = 0
        foundStateCodes = []
        foundStateCodesOverrided = []

        dataStates = found["states"]

        while nextElement != None:
            # Title for the next country. Break
            if nextElement.name == "h2":
                break

            # if it's a list of flags in the same page
            stateList = nextElement

            # See if it's the easy case
            allImages = stateList.select("img")

            for image in allImages:
                if image["alt"]:
                    for state in dataStates:
                        if state["iso2"] in foundStateCodes:
                            continue
                        tries = GenStateNameTries(state["name"])
                        for _try in tries:
                            if image["alt"].strip().lower() == "flag of "+_try.lower():
                                print("=> Found image: ", image["alt"])
                                download_flag(image["src"], found["iso2"], state["iso2"])
                                foundStateCodes.append(state["state_code"])
                                foundStateCodesOverrided.append(state["iso2"])
                                break

            for state in stateList.select("li"):
                stateName = state.select("a")[-1].text
                stateNameTries = GenStateNameTries(stateName)

                dataState = None

                for stateNameTry in stateNameTries:
                    dataState = next((s for s in dataStates if remove_accents_lower(
                        s["name"]) == remove_accents_lower(stateNameTry)), None)
                    if dataState and dataState["iso2"] != None:
                        if dataState["iso2"] not in foundStateCodes:
                            download_flag(state.find("img")["src"], found["iso2"], dataState["iso2"])
                            foundStateCodes.append(dataState["iso2"])
                        break

                if not dataState:
                    print("> Not found: "+remove_accents_lower(stateName))
                else:
                    foundStates += 1
            
            # If it's a redirect to a flags page
            # Page with lots of flags?
            linkElements = nextElement.select('a')
            links = set()

            for link in linkElements:
                links.add(link["href"].split("#")[0])
            
            for link in additionalURLs.get(found["iso2"], []):
                links.add(link)

            for link in links:
                try:
                    url = link

                    if not url.startswith("http"):
                        url = f'https://en.wikipedia.org{link}'

                    print(url)

                    page = requests.get(url, verify=False, allow_redirects=True).text
                    subSoup = BeautifulSoup(page, features="lxml")

                    # See if it's the easy case
                    allImages = subSoup.select("img")

                    for image in allImages:
                        if image["alt"]:
                            for state in dataStates:
                                if state["iso2"] in foundStateCodes:
                                    continue
                                tries = GenStateNameTries(state["name"])
                                for _try in tries:
                                    if image["alt"].strip().lower() in ["flag of "+_try.lower(), "flag of "+_try.lower()+".svg", "flag of "+_try.lower()+".png"]:
                                        print("=> Found image: ", image["alt"])
                                        download_flag(image["src"], found["iso2"], state["iso2"])
                                        foundStateCodes.append(state["state_code"])
                                        foundStateCodesOverrided.append(state["iso2"])
                                        break

                    # Try tables instead
                    linksInTables = subSoup.select("table a")

                    dataState = None

                    for tableLink in linksInTables:
                        stateName = tableLink.text

                        stateNameTries = GenStateNameTries(stateName)

                        for stateNameTry in stateNameTries:
                            dataState = next((s for s in dataStates if remove_accents_lower(
                                s["name"]) == remove_accents_lower(stateNameTry)), None)

                            if dataState and dataState["iso2"] != None and (
                                    (dataState["iso2"] not in foundStateCodes) or (
                                        tableLink.text.strip().lower().startswith("flag of") and dataState["iso2"] not in foundStateCodesOverrided)):
                                print("=> Found "+tableLink.text)
                                try:
                                    # tryGet = get_flag_url_from_infobox(url)

                                    # if tryGet:
                                    #     download_flag(tryGet, found["iso2"], dataState["state_code"])
                                    #     foundStateCodes.append(dataState["state_code"])
                                    #     foundStateCodesOverrided.append(dataState["state_code"])
                                    #     continue

                                    tableRow = tableLink.find_parent("tr")

                                    # Try to find table column with title "Flag"
                                    tableCols = tableRow.parent.findChildren("th")
                                    tableCol = None
                                    for i, c in enumerate(tableCols):
                                        if c.get_text().strip().lower() == "flag":
                                            print("Found by table column:", c.get_text().strip().lower())
                                            tableCol = i
                                            tableRow = tableRow.findChildren("td")[i]
                                            break

                                    imagesInRow = tableRow.select("img")

                                    if len(imagesInRow) > 0:
                                        # If
                                        # Has alt and "Flag" is not in it, probably not the flag or
                                        # There's "flag" in the link itself
                                        # Order image first
                                        imagesInRow.sort(key=lambda x: -1 if (x["alt"] and "flag" in x["alt"].lower()) else 1)

                                        for flagElement in imagesInRow:
                                            if (flagElement["src"] and "no_flag" in flagElement["src"].lower()):
                                                continue
                                        
                                            if dataState["iso2"] in foundStateCodes:
                                                continue
                                            
                                            download_flag(flagElement["src"], found["iso2"], dataState["iso2"])

                                            foundStateCodes.append(dataState["iso2"])

                                            if tableLink.text.strip().lower().startswith("flag of"):
                                                foundStateCodesOverrided.append(dataState["iso2"])

                                            break
                                except Exception as e:
                                    print(e)

                                break

                        if dataState:
                            foundStates += 1
                except Exception as e:
                    print("Error:", e)

            nextElement = nextElement.findNext()

        print("Coverage: "+str(foundStates)+"/"+str(len(found["states"])))
    else:
        print("Not found: "+countryname)
