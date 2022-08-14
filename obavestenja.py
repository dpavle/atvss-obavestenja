#!/usr/bin/env python3

import os 
import time
import hashlib
from urllib.error import URLError
import telegram
import logging

from dotenv import load_dotenv, find_dotenv
from difflib import SequenceMatcher
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup

# statičke globalne varijable
URL = ["https://vtsnis.edu.rs/obavestenja/", "https://vtsnis.edu.rs/studenti/"]

# ucitavanje env varijabli iz .env fajla
load_dotenv()

# ucitavanje env varijabli
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL'))

# telegram bot objekat
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

logging.basicConfig(filename='./obavestenja.log', encoding='utf-8', level=logging.DEBUG) # log se salje u obavestenja.log

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
                self.html = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read()
                self.soup = BeautifulSoup(self.html, features="html.parser")
            except URLError as error: 
                logging.error(f'{error} - greška pri učitavanju sajta. pokušavamo ponovo. . . ({p}/16)')
                time.sleep(UPDATE_INTERVAL)
            else:
                break
        else: 
            logging.error('svi pokušaji učitavanja sajta neuspeli. proverite internet konekciju')
            exit()

class TelegramObavestenje: 
    def __init__(self, naslov, sadrzaj):
        # formatiranje naslova
        self.naslov = str(naslov).replace("h1", "b").replace("h3", "b") # znamo da se naslov uvek piše u h3, h3 nije podržan pa ga menjamo u b

        # formatiranje sadrzaja
        self.sadrzaj = sadrzaj.text # sadrzaj se prvo konvertuje u plain text format
        for tag in sadrzaj.find_all():
            if tag.name in ['strong', 'em', 'ins', 'strike', 'del', 'u', 'b', 'i', 's', 'a', 'code', 'pre']: # ako se u originalnom html obliku sadryaja nadju podrzani tagovi
                self.sadrzaj = self.sadrzaj.replace(str(tag.string), str(tag)) # ti tagovi se konvertuju nazad u html na izlazu
        
        self.html_naslov = naslov
        self.html_sadrzaj = sadrzaj
        
    def send_msg(self) -> telegram.Message:
        ''' Funkcija od dobijenih argumenata konstruiše i šalje poruku na Telegram kanal '''
        try:
            poruka = bot.send_message(TELEGRAM_CHAT_ID, text="\n".join([self.naslov, str(self.html_sadrzaj)]), parse_mode='html') # poruka se salje na telegram kanal
        except telegram.error.BadRequest as err:
            # ako iz nekog razloga ostane neki nepodržan HTML tag i gornji send_message ne uspe, poruka se rekonstruiše i šalje u plain text formatu
            logging.warning(f'{err} - skidanje nepodržanih HTML tagova neuspešno, šaljemo poruku kao plain text bez HTML formatiranja')
            poruka = bot.send_message(TELEGRAM_CHAT_ID, text="\n".join([self.naslov, self.html_sadrzaj.text]), parse_mode='html')
        return poruka

    def send_img(self, src) -> telegram.Message: 
        try:
            bot.send_photo(TELEGRAM_CHAT_ID, src, parse_mode='html')
        except telegram.error.BadRequest as err:
            # ako slanje slike uz poruku ne uspe, salje se warning u log i nastavlja se bez slike
            logging.warning(f'{err} - slanje slike uz poruku neuspešno, šaljemo poruku bez slike')
        
    def edit(self, poruka) -> telegram.Message:
        ''' Funkcija edituje prethodno poslatu poruku'''
        try:
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=poruka.message_id, text="\n".join([self.naslov, self.sadrzaj]), parse_mode='html')
        except telegram.error.BadRequest as err:
            logging.warning(f'{err} - skidanje nepodržanih HTML tagova neuspešno, šaljemo poruku kao plain text bez HTML formatiranja')
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=poruka.message_id, text="\n".join([self.naslov, self.html_sadrzaj.text]), parse_mode='html')
        return poruka

def main():

    studenti_inithash = hash(Sajt(URL[0]).soup.select('div[class="site-content"]')) # inicijalni hash sajta
    obavestenja_inithash = hash(Sajt(URL[1]).soup.select('div[class="site-content"]')) 

    prethodni_naslov = ''
    prethodni_sadrzaj = ''

    while True:
        time.sleep(UPDATE_INTERVAL) # provera se vrsi na svakih UPDATE_INTERVAL sekundi

        studenti = Sajt(URL[0]) # ažurni instance sajta
        obavestenja = Sajt(URL[1]) 

        studenti_newhash = hash(studenti.soup.select('div[class="site-content"]')) # ažurni hash sajta
        obavestenja_newhash = hash(obavestenja.soup.select('div[class="site-content"]')) 

        if studenti_inithash != studenti_newhash: # ako se pocetni i azurni hash razlikuju, stanje na sajtu se promenilo
           
            naslov = studenti.soup.select('h3[class="subheading"]')[0] # prvi element liste naslova svih obavestenja sa sajta
            sadrzaj = studenti.soup.select('div[class="timeline-body"]')[0] # prvi element liste sadrzaja svih obavestenja sa sajta
            
            obavestenje = TelegramObavestenje(naslov, sadrzaj)

            if poklapanje(obavestenje.html_naslov.text, prethodni_naslov) < 0.85 or poklapanje(obavestenje.html_sadrzaj.text, prethodni_sadrzaj) < 0.85:
                aktuelna_poruka = obavestenje.send_msg() # korisnik se obavestava porukom putem obavestenje.send() 
                # ako su uz obavestenje prilozene slike, te slike se salju posebno nakon originalne poruke
                if len(sadrzaj.find_all('img')) > 0: 
                    for tag in sadrzaj.find_all('img'): 
                        obavestenje.send_img(tag['src'])
            else:
                aktuelna_poruka = obavestenje.edit(aktuelna_poruka)

            logging.info(studenti_inithash + " =/= " + studenti_newhash) # stari i azurni hash se salju u log

            prethodni_naslov = obavestenje.html_naslov.text # naslov poslatog obavestenja se setuje kao prethodni_naslov, radi poredjenja sa naslovom sledećeg obaveštenja
            prethodni_sadrzaj = obavestenje.html_sadrzaj.text # sadrzaj poslatog obavestenja se setuje kao prethodni_sadrzaj, radi poređenja sa sadržajem sledećeg obaveštenja
            studenti_inithash = studenti_newhash # pocetna vrednost hasha se setuje na novu azurnu vrednost

        elif obavestenja_inithash != obavestenja_newhash:

            naslov = obavestenja.soup.select('h1[class="entry-title"]')[0] # prvi element liste naslova svih obavestenja sa sajta
            sadrzaj = obavestenja.soup.select('div[class="entry-content"]')[0] # prvi element liste sadrzaja svih obavestenja sa sajta

            obavestenje = TelegramObavestenje(naslov, sadrzaj)
            
            if poklapanje(obavestenje.html_naslov.text, prethodni_naslov) < 0.85 or poklapanje(obavestenje.html_sadrzaj.text, prethodni_sadrzaj) < 0.85:
                aktuelna_poruka = obavestenje.send_msg() # korisnik se obavestava porukom putem obavestenje.send() 
                # ako su uz obavestenje prilozene slike, te slike se salju posebno nakon originalne poruke
                if len(sadrzaj.find_all('img')) > 0: 
                    for tag in sadrzaj.find_all('img'): 
                        obavestenje.send_img(tag['src'])
            else:
                try:
                    aktuelna_poruka = obavestenje.edit(aktuelna_poruka)
                except telegram.error.BadRequest: 
                    pass

            logging.info(obavestenja_inithash + " =/= " + obavestenja_newhash) # stari i azurni hash se salju u log

            prethodni_naslov = obavestenje.html_naslov.text # naslov poslatog obavestenja se setuje kao prethodni_naslov, radi poredjenja sa naslovom sledećeg obaveštenja
            prethodni_sadrzaj = obavestenje.html_sadrzaj.text # sadrzaj poslatog obavestenja se setuje kao prethodni_sadrzaj, radi poređenja sa sadržajem sledećeg obaveštenja
            obavestenja_inithash = obavestenja_newhash # pocetna vrednost hasha se setuje na novu azurnu vrednost 
        else:
            continue

if __name__ == '__main__':
    main()
