#!/usr/bin/env python3

import os 
import time
import hashlib
import telegram
import logging

from dotenv import load_dotenv, find_dotenv
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup

logging.basicConfig(filename='obavestenja.log', encoding='utf-8', level=logging.DEBUG) # log se salje u obavestenja.log

# ucitavanje env varijabli iz .env fajla
load_dotenv()

# ucitavanje env varijabli
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# globalne varijable
URL = 'https://vtsnis.edu.rs/obavestenja/' ## NE MENJAJ

# telegram bot objekat
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

def soupup(URL):
    ''' Funkcija salje zahtev i preuzima trenutni 'raw HTML' stranice date sa 'URL' i isti pretvara u BeautifulSoup objekat, tj. ugnjezdena struktura podataka '''

    html = urlopen(Request(URL, headers={'User-Agent': 'Mozilla/5.0'})).read() 
    soup = BeautifulSoup(html, features="html.parser")

    return soup

def obavestenja_hash(soup) -> str:
    ''' Funkcija generise hash sajta (tacnije, dela sajta sa informacijama koje nas zanimaju), 
    koji se kasnije poredi sa novo generisanim hashom da bi se videlo ima li ikakvih izmena na sajtu. 
    Kao argument se uzima BeautifulSoup objekat (obicno generisan prethodnom funkcijom soupup()). '''

    # selektuje se deo stranice sa relevantnim informacijama
    site_content = soup.select('div[class="site-content"]')

    # hash podataka sa selektovanog 'info' objekta
    obavestenja_hash = hashlib.sha224(str(site_content).encode('utf-8')).hexdigest()
    
    return obavestenja_hash

def telegram_obavestenje(soup):
    ''' Funkcija od dobijenih podataka sa sajta konstruise i salje poruku na Telegram kanal '''

    # selektuju se naslov i sadrzaj najaktuelnijeg obavestenja sa sajta posebno
    sadrzaj = soup.select('div[class="entry-content"]')[0]
    naslov = soup.select('h1[class="entry-title"]')[0]

    naslov_poruke = str(naslov).replace("h1", "b") # znamo da se naslov uvek pise u h1, ali h1 nije podrzan od strane Telegram HTML parsera, tako da ga menjamo na podrzan tag 'b'
    sadrzaj_poruke = sadrzaj.text # sadrzaj posta se konvertuje u obican tekstualni objekat, da bi se izbegli HTML tagovi nepodrzani od strane Telegram parsera
    
    for tag in sadrzaj.find_all(): # nalazi se svaki tag u objektu 'sadrzaj'
        # ako je tag podrzan od strane Telegram HTML parsera, taj deo poruke se vraca u HTML oblik
        if tag.name in ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'b', 'i', 's', 'u', 'a', 'a', 'code', 'pre', 'pre', 'code']:
            sadrzaj_poruke = sadrzaj_poruke.replace(str(tag.string), str(tag)) 

    poruka = naslov_poruke + '\n' + sadrzaj_poruke # finalna konstrukcija poruke
    bot.send_message(TELEGRAM_CHAT_ID, text=poruka, parse_mode='html') # poruka se salje na telegram kanal

    # ako su uz obavestenje prilozene slike, te slike se salju posebno nakon originalne poruke
    for tag in sadrzaj.find_all('img'): 
        bot.send_photo(TELEGRAM_CHAT_ID, tag['src'], caption=naslov_poruke, parse_mode='html')

    return sadrzaj_poruke

def main(): 

    # prethodno generisani inicijalni hash sajta se cita iz fajla 
    if os.path.isfile('hash'): 
        with open('hash', 'r') as hash_f:
            hash_0 = hash_f.read()
    else:
        # ako fajl ne postoji, hash se generise pozivom obavestenja_hash funkcije 
        hash_0 = obavestenja_hash(soupup(URL))
        # upis generisanog hasha u fajl 'hash.txt'
        with open('hash', 'w') as hash_f: 
            hash_f.write(hash_0)
    

    while True:
        time.sleep(300) # provera se vrsi na svakih 5 minuta 

        soup = soupup(URL) # azurna verzija sajta kao BS objekat
        hash_1 = obavestenja_hash(soup) # azurni hash sajta

        if hash_0 != hash_1:
            # ako se pocetni i azurni hash razlikuju, stanje na sajtu se promenilo, korisnik se obavestava porukom putem telegram_obavestenje() 
            telegram_obavestenje(soup)
            # azurni hash se upisuje u fajl 'hash.txt'
            with open('hash', 'w') as hash_f: 
                hash_f.write(hash_1)
            # stari i azurni hash se salju u log
            logging.info(hash_0 + " =/= " + hash_1) 

            hash_0 = hash_1 # pocetna vrednost hasha se setuje na novu azurnu vrednost

        else:
            continue

if __name__ == '__main__':
    main()
