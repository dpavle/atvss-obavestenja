#!/usr/bin/env python3

import time
import logging
import hashlib
import telegram

from os import getenv
from dotenv import load_dotenv
from urllib.request import urlopen, Request
from urllib.error import URLError
from http.client import RemoteDisconnected
from difflib import SequenceMatcher
from bs4 import BeautifulSoup

# statičke globalne varijable
URL = ["https://odseknis.akademijanis.edu.rs/studenti/",
       "https://odseknis.akademijanis.edu.rs/obavestenja/"]

# ucitavanje env varijabli iz .env fajla
load_dotenv()

# ucitavanje env varijabli
TELEGRAM_BOT_TOKEN = getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = getenv('TELEGRAM_CHAT_ID')
UPDATE_INTERVAL = int(getenv('UPDATE_INTERVAL'))

# telegram bot objekat
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

logging.basicConfig(filename='./obavestenja.log',
                    encoding='utf-8',
                    level=logging.DEBUG)  # log se salje u obavestenja.log


def poklapanje(a, b) -> float:
    ''' Funkcija poredi objekte a i b i vraća odnos poklapanja 0-1 '''
    return SequenceMatcher(None, a, b).ratio()


def hash(content) -> str:
    ''' Funkcija generiše hash datog argumenta '''
    return hashlib.sha224(str(content).encode('utf-8')).hexdigest()


class Sajt:
    def __init__(self, url):
        for p in range(16):
            try:
                self.html = urlopen(
                    Request(url,
                            headers={'User-Agent': 'Mozilla/5.0'})).read()
                self.soup = BeautifulSoup(self.html, features="html.parser")
                break
            except (URLError, RemoteDisconnected) as error:
                logging.error(
                    f'''{error} - greška pri učitavanju sajta.
                    pokušavamo ponovo..({p}/16)'''
                    )
                time.sleep(UPDATE_INTERVAL)
        else:
            logging.error('''svi pokušaji učitavanja sajta neuspeli.
                          proverite internet konekciju'''
                          )
            exit()


class TelegramObavestenje:
    def __init__(self, naslov, sadrzaj):
        ''' init funkcija obrađuje naslov i sadržaj
            u oblik pogodan za slanje preko Telegrama '''
        # cuvamo tekstualne oblike naslova i sadrzaja
        # (bez HTML formatiranja)
        self.naslov_text = naslov.text
        self.sadrzaj_text = sadrzaj.text

        # formatiranje naslova
        self.naslov = str(naslov).replace("h1", "b").replace("h3", "b")
        # znamo da se naslov uvek piše u h3, h3 nije podržan pa ga menjamo u b

        # formatiranje sadrzaja
        self.sadrzaj = sadrzaj.text  # sadrzaj se prvo konvertuje u plain text
        for tag in sadrzaj.find_all():
            # ako se u originalnom html obliku sadrzaja nadju podrzani tagovi
            if tag.name in ['strong', 'em', 'ins', 'strike', 'del', 'u',
                            'b', 'i', 's', 'a', 'code', 'pre']:
                # ti tagovi se konvertuju nazad u html na izlazu
                self.sadrzaj = self.sadrzaj.replace(str(tag.string), str(tag))

    def send_msg(self) -> telegram.Message:
        ''' Funkcija konstruiše i šalje poruku na Telegram kanal '''
        try:
            poruka = bot.send_message(TELEGRAM_CHAT_ID,
                                      text="\n".join([self.naslov,
                                                      self.sadrzaj]),
                                      parse_mode='html')
        except telegram.error.BadRequest as err:
            # ako ostane neki nepodržan HTML tag i send_message ne uspe,
            # poruka se rekonstruiše i šalje u plain text formatu
            logging.warning(
                f'''{err} - skidanje nepodržanih HTML tagova neuspešno,
                šaljemo poruku kao plain text bez HTML formatiranja''')
            poruka = bot.send_message(TELEGRAM_CHAT_ID,
                                      text="\n".join([self.naslov_text,
                                                      self.sadrzaj_text]),
                                      parse_mode='html')
        return poruka

    def send_img(self, src) -> telegram.Message:
        try:
            bot.send_photo(TELEGRAM_CHAT_ID, src, parse_mode='html')
        except telegram.error.BadRequest as err:
            # ako slanje slike uz poruku ne uspe,
            # salje se warning u log i nastavlja se bez slike
            logging.warning(f'''{err} - slanje slike uz poruku neuspešno,
                            šaljemo poruku bez slike''')

    def edit_msg(self, poruka) -> telegram.Message:
        ''' Funkcija edituje prethodno poslatu poruku'''
        try:
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID,
                                           message_id=poruka.message_id,
                                           text="\n".join([self.naslov,
                                                           self.sadrzaj]),
                                            parse_mode="html")

        except telegram.error.BadRequest as err:
            logging.warning(
                f'''{err} - skidanje nepodržanih HTML tagova neuspešno,
                šaljemo poruku kao plain text bez HTML formatiranja''')
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID,
                                           message_id=poruka.message_id,
                                           text="\n".join([self.naslov_text,
                                                           self.sadrzaj_text]))
        return poruka


def main():

    # ažurni instance sajtova
    studenti = Sajt(URL[0])
    obavestenja = Sajt(URL[1])

    # inicijalni hash sajtova
    studenti_inithash = hash(
        studenti.soup.select('div[class=timeline-body]')[0]
        )
    obavestenja_inithash = hash(
        obavestenja.soup.select("article")[0]
        )

    prethodni_naslov = ''
    prethodni_sadrzaj = ''

    while True:
        # provera se vrsi na svakih UPDATE_INTERVAL sekundi
        time.sleep(UPDATE_INTERVAL)

        # ažurni instance sajtova
        studenti = Sajt(URL[0])
        obavestenja = Sajt(URL[1])

        # ažurni hash sajtova
        studenti_newhash = hash(
            studenti.soup.select('div[class=timeline-body]')[0]
            )
        obavestenja_newhash = hash(
            obavestenja.soup.select("article")[0]
            )

        # ako se pocetni i azurni hash razlikuju, stanje na sajtu se promenilo
        if studenti_inithash != studenti_newhash:
            # prvi element liste naslova svih obavestenja sa sajta
            naslov = studenti.soup.select('h3[class="subheading"]')[0]
            sadrzaj = studenti.soup.select('div[class="timeline-body"]')[0]

            tg = TelegramObavestenje(naslov, sadrzaj)

            poklapanje_naslova = poklapanje(
                naslov.text, prethodni_naslov
                )
            poklapanje_sadrzaja = poklapanje(
                sadrzaj.text, prethodni_sadrzaj
                )
            if 0.85 < poklapanje_naslova < 1 or 0.85 < poklapanje_sadrzaja < 1:
                telegram_poruka = tg.edit_msg(telegram_poruka)
            else:
                # korisnik se obavestava porukom putem tg.send_msg()
                telegram_poruka = tg.send_msg()
                # ako su uz obavestenje prilozene slike,
                # te slike se salju posebno nakon originalne poruke
                if len(sadrzaj.find_all('img')) > 0:
                    for tag in sadrzaj.find_all('img'):
                        tg.send_img(tag['src'])
            # stari i azurni hash se salju u log
            logging.info(studenti_inithash + " =/= " + studenti_newhash)

            # naslov poslatog obavestenja se setuje kao prethodni_naslov,
            # radi poredjenja sa naslovom sledećeg obaveštenja
            prethodni_naslov = naslov.text
            # sadrzaj poslatog obavestenja se setuje kao prethodni_sadrzaj,
            # radi poređenja sa sadržajem sledećeg obaveštenja
            prethodni_sadrzaj = sadrzaj.text

            # pocetna vrednost hasha se setuje na novu azurnu vrednost
            studenti_inithash = studenti_newhash

        elif obavestenja_inithash != obavestenja_newhash:

            # prvi element liste naslova svih obavestenja sa sajta
            naslov = obavestenja.soup.select('h1[class="entry-title"]')[0]
            # prvi element liste sadrzaja svih obavestenja sa sajta
            sadrzaj = obavestenja.soup.select('div[class="entry-content"]')[0]

            tg = TelegramObavestenje(naslov, sadrzaj)

            poklapanje_naslova = poklapanje(
                naslov.text, prethodni_naslov
                )
            poklapanje_sadrzaja = poklapanje(
                sadrzaj.text, prethodni_sadrzaj
                )

            if 0.85 < poklapanje_naslova < 1 or 0.85 < poklapanje_sadrzaja < 1:
                telegram_poruka = tg.edit_msg(telegram_poruka)
            # stari i azurni hash se salju u log
            else:
                # korisnik se obavestava porukom putem tg.send_msg()
                telegram_poruka = tg.send_msg()
                # ako su uz obavestenje prilozene slike,
                # te slike se salju posebno nakon originalne poruke
                if len(sadrzaj.find_all('img')) > 0:
                    for tag in sadrzaj.find_all('img'):
                        tg.send_img(tag['src'])

            # stari i azurni hash se salju u log
            logging.info(obavestenja_inithash + " =/= " + obavestenja_newhash)

            # naslov poslatog obavestenja se setuje kao prethodni_naslov,
            # radi poredjenja sa naslovom sledećeg obaveštenja
            prethodni_naslov = naslov.text
            # sadrzaj poslatog obavestenja se setuje kao prethodni_sadrzaj,
            # radi poređenja sa sadržajem sledećeg obaveštenja
            prethodni_sadrzaj = sadrzaj.text
            # pocetna vrednost hasha se setuje na novu azurnu vrednost
            obavestenja_inithash = obavestenja_newhash
        else:
            continue


if __name__ == '__main__':
    main()
