#!/usr/bin/env python3

import os 
import time
import hashlib
import telegram
import logging

from dotenv import load_dotenv, find_dotenv
from difflib import SequenceMatcher
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup

logging.basicConfig(filename='obavestenja.log', encoding='utf-8', level=logging.DEBUG) # log se salje u obavestenja.log

# ucitavanje env varijabli iz .env fajla
load_dotenv()

# ucitavanje env varijabli
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL'))
URL = os.getenv('URL')

# telegram bot objekat
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

def slicnost(a, b) -> float: 
    ''' Funkcija poredi objekte a i b i vraća odnos poklapanja 0-1 '''
    return SequenceMatcher(None, a, b).ratio()

def hash(content) -> str:
    ''' Funkcija generiše hash datog argumenta '''
    return hashlib.sha224(str(content).encode('utf-8')).hexdigest()

class Sajt:
    def __init__(self, url):
        self.html = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read()
        self.soup = BeautifulSoup(self.html, features="html.parser")

class TelegramObavestenje: 
    def __init__(self, naslov, sadrzaj):
        # formatiranje naslova
        self.naslov = str(naslov).replace("h1", "b") # znamo da se naslov uvek piše u h1, h1 nije podržan pa ga menjamo u b
        # formatiranje sadrzaja
        self.sadrzaj = sadrzaj.text # sadrzaj se prvo konvertuje u plain text format
        for tag in sadrzaj.find_all():
            if tag.name in ['strong', 'em', 'ins', 'strike', 'del', 'u', 'b', 'i', 's', 'a', 'code', 'pre']: # ako se u originalnom html obliku sadryaja nadju podrzani tagovi
                self.sadrzaj = self.sadrzaj.replace(str(tag.string), str(tag)) # ti tagovi se konvertuju nazad u html na izlazu
        
        self.html_naslov = naslov
        self.html_sadrzaj = sadrzaj
        
    def send(self) -> telegram.Message:
        ''' Funkcija od dobijenih argumenata konstruiše i šalje poruku na Telegram kanal '''
        try:
            poruka = bot.send_message(TELEGRAM_CHAT_ID, text=self.naslov + self.sadrzaj, parse_mode='html') # poruka se salje na telegram kanal
        except:
            # ako iz nekog razloga ostane neki nepodrzan HTML tag i gornji send_message ne uspe, poruka se rekonstruise i salje u plain text formatu
            logging.warning('skidanje nepodrzanih HTML tagova neuspesno, saljemo poruku kao plain text bez HTML formatiranja')
            poruka = bot.send_message(TELEGRAM_CHAT_ID, text=self.naslov + self.html_sadrzaj.text, parse_mode='html')
        try:
            # ako su uz obavestenje prilozene slike, te slike se salju posebno nakon originalne poruke
            for tag in self.html_sadrzaj.find_all('img'): 
                bot.send_photo(TELEGRAM_CHAT_ID, tag['src'], caption=self.naslov, parse_mode='html')
        except: 
            # ako slanje slike uz poruku ne uspe, salje se warning u log i nastavlja se bez slike
            logging.warning('slanje slike uz poruku neuspesno, saljemo poruku bez slike')
        return poruka

    def edit(self, poruka) -> telegram.Message:
        ''' Funkcija edituje prethodno poslatu poruku'''
        try:
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=poruka.message_id, text=self.naslov + '\n' + self.sadrzaj, parse_mode='html')
        except: 
            poruka = bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=poruka.message_id, text=self.naslov + '\n' + self.html_sadrzaj.text, parse_mode='html')
        return poruka

def main():  
    sajt = Sajt(URL) # inicijalni instance sajta
    hash_0 = hash(sajt.soup.select('div[class="site-content"]')) # inicijalni hash sajta
    prethodni_naslov = ''

    while True:
        time.sleep(int(UPDATE_INTERVAL)) # provera se vrsi na svakih 5 minuta 

        sajt = Sajt(URL) # azurni instance sajta 
        hash_1 = hash(sajt.soup.select('div[class="site-content"]')) # azurni hash sajta
        naslov = sajt.soup.select('h1[class="entry-title"]')[0] # prvi element liste naslova svih obavestenja sa sajta
        sadrzaj = sajt.soup.select('div[class="entry-content"]')[0] # prvi element liste sadrzaja svih obavestenja sa sajta

        if hash_0 != hash_1: # ako se pocetni i azurni hash razlikuju, stanje na sajtu se promenilo
            obavestenje = TelegramObavestenje(naslov, sadrzaj)

            if slicnost(obavestenje.naslov, prethodni_naslov) < 0.8:
                aktuelna_poruka = obavestenje.send() # korisnik se obavestava porukom putem obavestenje.send() 
            else:
                aktuelna_poruka = obavestenje.edit(aktuelna_poruka)
        
            logging.info(hash_0 + " =/= " + hash_1) # stari i azurni hash se salju u log

            prethodni_naslov = obavestenje.naslov # naslov poslatog obavestenja se setuje kao prethodni_naslov, radi poredjenja sa naslovom sledećeg obaveštenja
            hash_0 = hash_1 # pocetna vrednost hasha se setuje na novu azurnu vrednost

        else:
            continue

if __name__ == '__main__':
    main()
