import json
import os
from typing import List

import requests
from bs4 import BeautifulSoup

districts = [
    ('Gdańsk', 'Zaspa'),
    ('Gdańsk', 'Oliwa'),
    ('Gdańsk', 'Śródmieście'),
    ('Gdańsk', 'Morena'),
    ('Gdańsk', 'Wrzeszcz'),
    ('Gdynia', 'Redłowo'),
    ('Gdynia', 'Orłowo'),
    ('Gdynia', 'Śródmieście'),
    ('Gdynia', 'Wzgórze'),
    ('Gdynia', 'Witomino'),
]


class District:

    def __init__(self,
                 text: str,
                 name: str,
                 region_id: str,
                 subregion_id: str,
                 city_id: str,
                 district_id: str,
                 lat_lon: str):
        self.text = text
        self.name = name
        self.region_id = int(region_id)
        self.subregion_id = int(subregion_id)
        self.city_id = int(city_id)
        self.district_id = int(district_id)
        self.lat_lon = lat_lon

    @classmethod
    def from_dict(cls, d: dict):
        return District(d.get('text'),
                        d.get('name'),
                        d.get('region_id'),
                        d.get('subregion_id'),
                        d.get('city_id'),
                        d.get('district_id'),
                        d.get('lat_lon'))

    def to_dict(self):
        return self.__dict__

    def __str__(self):
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)


class Offer:

    def __init__(self,
                 title: str,
                 rooms: str,
                 price: str,
                 area: str,
                 price_per_m: str,
                 details: str,
                 link: str):
        self.title = title
        self.rooms = int(rooms.replace(' ', '').replace('pokoje', ''))
        self.price = float(price.replace(' ', '').replace('zł', '').replace(',', '.'))
        self.area = float(area.replace(' ', '').replace('m²', '').replace(',', '.'))
        self.price_per_m = float(price_per_m.replace(' ', '').replace('zł/m²', '').replace(',', '.'))
        self.details = details
        self.link = link

    @classmethod
    def from_html(cls, html_offer):
        mappings = {
            'title': '.offer-item-title',
            'rooms': '.offer-item-rooms',
            'area': '.offer-item-area',
            'price_per_m': '.offer-item-price-per-m',
            'price': '.offer-item-price',
            'details': '.offer-item-details-bottom',
        }
        link = html_offer['data-url']
        kwargs = {key: html_offer.select_one(value).text.strip() for key, value in mappings.items()}
        return Offer(link=link, **kwargs)

    def __str__(self):
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)


def find_all_districts() -> List[District]:
    districts_file = 'districts.json'
    if os.path.exists(districts_file):
        with open(districts_file, 'r') as f:
            content = f.read()
        matches = json.loads(content)
        return [District.from_dict(match) for match in matches]
    else:
        matches = [find_district(city, district) for city, district in districts]
        content = json.dumps([match.to_dict() for match in matches])
        with open(districts_file, 'w') as f:
            f.write(content)
        return matches


def find_district(city: str, district: str) -> District:
    r = requests.get(
        f'https://www.otodom.pl/ajax/geo6/autosuggest/?data={district}&lowPriorityStreetsSearch=true&levels%5B0%5D=REGION&levels%5B1%5D=SUBREGION&levels%5B2%5D=CITY&levels%5B3%5D=DISTRICT&levels%5B4%5D=STREET&withParents=false',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })
    for match in r.json():
        parents = match.get('parents', {})
        for parent in parents:
            if parent.get('level') == 'SUBREGION' and parent.get('name') == city:
                return District.from_dict(match)


def find_offers(district: District, since: int = 1):
    r = requests.post('https://www.otodom.pl/ajax/search/list/',
                      data={
                          'search[category_id]': 101,
                          'search[dealType]': 1,
                          'search[filter_float_price:to]': 700000,
                          'search[filter_float_m:from]': 55,
                          'search[filter_float_m:to]': 70,
                          'search[filter_enum_rooms_num][]': 3,
                          'search[created_since]': since,
                          'search[region_id]': district.region_id,
                          'search[subregion_id]': district.subregion_id,
                          'search[city_id]': district.city_id,
                          'search[district_id]': district.district_id,
                          'search[locationsPool_id]': json.dumps([{
                              "region_id": str(district.region_id),
                              "subregion_id": str(district.subregion_id),
                              "city_id": str(district.city_id),
                              "district_id": district.district_id,
                              "lat_lon": str(district.lat_lon)
                          }]).replace(' ', ''),
                          'search[dist]': 0
                      },
                      headers={
                          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36',
                          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                      })

    soup = BeautifulSoup(r.text, 'html.parser')
    missing_offers = soup.select_one('.search-location-extended-warning')
    if missing_offers:
        return []
    offers = soup.select('.offer-item')
    return [Offer.from_html(offer) for offer in offers if offer['data-featured-name'] == 'listing_no_promo']


if __name__ == '__main__':
    already_mentioned = set()
    for district in find_all_districts():
        offers = find_offers(district)
        print(f'found {len(offers)} for {district.text}')
        if offers:
            print('\n'.join([str(offer) for offer in offers if offer.link not in already_mentioned]))
            already_mentioned.update([offer.link for offer in offers])
