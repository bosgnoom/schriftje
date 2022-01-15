#!/usr/bin/python3

"""
    SCHRIFTJE - Ophalen en versturen van berichten in de OuderApp van de kinderopvang

    - Haalt bij iedere run (aanroepen via crontab) de geplaatste berichten op
    - en de foto's
    - Nieuwe worden verstuurd aan de telefoonnummers in de config.ini file

    Versie 5: Config.ini, push naar github
    Versie 4: Aparte berichten sturen ipv 1 grote bij wijziging
"""

# Import modules
import sys
import redis
import hashlib
import logging
import requests
from pydbus import SystemBus
from bs4 import BeautifulSoup as bs
import configparser

# Standaard logging, alleen foutmeldingen
logging.basicConfig(level=logging.CRITICAL)

# Config file parsen, zijn globals (ja, wordt nog wel eens gefixt, maar hoe?)
config = configparser.ConfigParser()
config.read('config.ini')

# Instellingen ophalen uit config
ONTVANGERS = config['settings']['ontvangers'].split(',')
ROSA_URL = config['settings']['rosa_url']
ROSA_NR = config['settings']['rosa_nummer']
LOGIN_DATA = dict(config['login_data'])


def send_message(sleutel, bericht):
    # Controle of bericht al eens verzonden is, opslaan in **Redis** database
    r = redis.Redis()

    # Set up messaging system, **Signal** is used through SystemBus
    bus = SystemBus()
    signal = bus.get('org.asamk.Signal')

    # Verstuur bericht
    #logging.debug('Sleutel: {}'.format(sleutel))
    #logging.debug('Bericht: {}'.format(bericht))

    if (not(r.exists(sleutel)) or r.get(sleutel) != bericht.encode()):
        logging.info('Bericht sturen: {}-{}'.format(sleutel, bericht))
        r.set(sleutel, bericht)
        signal.sendMessage(bericht, [], ONTVANGERS)


def send_photo(datum, foto):
    # Inclusief controle of foto al eens verzonden is, opslaan in **Redis** database
    # URL naar dezelfde foto verandert iedere keer, vandaar check op MD5 (is hopelijk snel op een RPi)

    # Foto eerst opslaan als bestand
    md5hash = hashlib.md5(foto).hexdigest()
    bestand = '/home/pi/Pictures/{}-{}.jpg'.format(datum, md5hash)

    logging.debug('Bestand opslaan: {}'.format(bestand))
    with open(bestand, 'wb') as f:
        f.write(foto)

    # Verstuur bericht
    r = redis.Redis()
    if not(r.exists(md5hash)):
        logging.info('Foto sturen')
        r.set(md5hash, datum)
        
        # Set up messaging system, **Signal** is used through SystemBus
        bus = SystemBus()
        signal = bus.get('org.asamk.Signal')
        signal.sendMessage('Foto', [bestand], ONTVANGERS)


def poll_messages(login_data):
    # Start with polling rosasoftware's website
    with requests.Session() as session:
        # Opvragen pagina, stelt een cookie in (vandaar ook with requests.Session())
        logging.debug('Rosasoftware pagina openen')
        site = session.get(f'{ROSA_URL}{ROSA_NR}')

        # Inloggen zelf
        logging.debug('Inloggen met {}'.format(login_data["username"]))
        site = session.post(
            f'{ROSA_URL}loginvalidate_portal.php',
            login_data)

        # Schrift pagina opvragen, bevat data-pk (nodig voor opvragen schriftje)
        logging.debug('Schriftje ophalen')
        site = session.get(
            f'{ROSA_URL}schriftkeuze.php#')

        # Opzoeken data-pk met BeautifulSoup
        soup = bs(site.content, 'html.parser')
        data_pk = soup.find(id='get-schriftje')["data-pk"]

        # Inhoud schrift pagina opvragen met data-pk
        post_data = {
            'methode': 'get-schriftje',
            'pk': data_pk,
            #'datum': '2021-05-21'
        }

        site = session.post(
            f'{ROSA_URL}portal-service.php',
            post_data,
        )

        # Opzoeken onderdeel met de datum, notities en de foto's
        logging.debug('Notitieblok zoeken')
        soup = bs(site.content, 'html.parser')
        datum = soup.find(id='datum')["value"]
        notebookscroller = soup.find('div', class_='notebookscroller')
        gallery = soup.find('div', class_='gallery')

        logging.info('Gevonden datum: {}'.format(datum))

        # Controle of er wel een schriftje is vandaag
        # Opzoeken "algemeen" en "persoonlijk"
        for header in notebookscroller.find_all('h3'):
            if (header.string == 'Nog geen schriftje'):
                # Geen schrift voor vandaag, programma stopt
                logging.info('Vandaag (nog) geen schrift... Straks beter?')
                sys.exit()

            if (header.string == 'Algemeen'):
                algemeen = header.next_sibling.stripped_strings
                for i,zin in enumerate(algemeen):
                    logging.debug('Algemeen zin {}: {}\n'.format(i, zin))
                    send_message('{}:algemeen:{}'.format(datum, i), zin)

            if (header.string == 'Persoonlijk'):
                persoonlijk = header.next_sibling.stripped_strings
                for i,zin in enumerate(persoonlijk):
                    logging.debug('Persoonlijk {}: {}\n'.format(i, zin))
                    send_message('{}:persoonlijk:{}'.format(datum, i), zin)

        # Activiteitentabel
        logging.debug('Activiteiten')
        tabel = notebookscroller.find('table')
        if tabel:
            for row in tabel.find_all('tr'):
                cells = row.find_all('td')
                tijd = cells[0].string
                activiteit = cells[2].string

                logging.debug('Tijd: {} | {}'.format(tijd, activiteit))
                send_message(
                    '{}:activiteit:{}'.format(datum, tijd),
                    '{}: {}'.format(tijd, activiteit))

        # Foto's
        logging.debug('Gallerij: {}'.format(gallery))
        if gallery:
            for foto in gallery.find_all('img'):
                site = session.get(
                    f'{ROSA_URL}{foto["src"]}')
                send_photo(datum, site.content)


# Main function
poll_messages(LOGIN_DATA)
