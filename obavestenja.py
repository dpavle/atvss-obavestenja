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

def soupup(URL) -> BeautifulSoup:
    ''' Funkcija šalje zahtev i preuzima trenutni 'raw HTML' stranice date sa 'URL' i isti pretvara u BeautifulSoup objekat, tj. ugnježdena struktura podataka '''

    html = urlopen(Request(URL, headers={'User-Agent': 'Mozilla/5.0'})).read() 
    soup = BeautifulSoup(html, features="html.parser")
    return soup

def slicnost(a, b) -> float: 
    ''' Funkcija poredi objekte a i b i vraća odnos poklapanja 0-1'''
    return SequenceMatcher(None, a, b).ratio()

def obavestenja_hash(soup) -> str:
    ''' Funkcija generiše hash sajta (tačnije, dela sajta sa informacijama koje nas zanimaju), 
    koji se kasnije poredi sa novo generisanim hashom da bi se videlo ima li ikakvih izmena na sajtu. 
    Kao argument se uzima BeautifulSoup objekat (obično generisan prethodnom funkcijom soupup()). '''

    # selektuje se deo stranice sa relevantnim informacijama
    site_content = soup.select('div[class="site-content"]')

    # hash podataka sa selektovanog 'info' objekta
    obavestenja_hash = hashlib.sha224(str(site_content).encode('utf-8')).hexdigest()
    
    return obavestenja_hash

def aktuelno_obavestenje(soup) -> BeautifulSoup:
    ''' Funkcija selektuje najaktuelnije obaveštenje sa sajta i vraća naslov i sadržaj istog kao dva odvojena objekta.
    Kao argument uzima BeautifulSoup objekat.'''
    
    # selektuju se naslov i sadrzaj najaktuelnijeg obavestenja sa sajta posebno
    sadrzaj = soup.select('div[class="entry-content"]')[0]
    naslov = soup.select('h1[class="entry-title"]')[0]
    return naslov, sadrzaj

def telegram_naslov(naslov) -> str: 
    '''Funkcija uzima prethodno dobijen naslov kao argument (verovatno iz funkcije aktuelno_obavestenje) i formatira ga
    tako da bude podržan od strane Telegram HTML parsera. 

    Pretpostavljamo da se naslov uvek piše u "h1" obliku.'''

    naslov_final = str(naslov).replace("h1", "b") # znamo da se naslov uvek pise u h1, ali h1 nije podrzan od strane Telegram HTML parsera, tako da ga menjamo na podrzan tag 'b'
    return naslov_final

def telegram_sadrzaj(sadrzaj) -> str:
    '''Funkcija uzima prethodno dobijen sadržaj kao argument (verovatno iz funkcije aktuelno_obavestenje) i formatira ga
    tako da bude podržan od strane Telegram HTML parsera. 

    Dati sadržaj se prvo pretvara u običan tekstualni objekat, pa se zatim iz prvobitnog HTML oblika sagledaju svi tagovi i 
    samo oni podržani od strane Telegram HTML parsera konvertuju nazad u HTML oblik. '''

    sadrzaj_final = sadrzaj.text # sadrzaj posta se konvertuje u obican tekstualni objekat, da bi se izbegli HTML tagovi nepodrzani od strane Telegram parsera

    for tag in sadrzaj.find_all(): # nalazi se svaki tag u objektu 'sadrzaj'
        # ako je tag podrzan od strane Telegram HTML parsera, taj deo poruke se vraca u HTML oblik
        if tag.name in ['strong', 'em', 'ins', 'strike', 'del', 'u', 'b', 'i', 's', 'a', 'code', 'pre']:
            sadrzaj_final = sadrzaj_final.replace(str(tag.string), str(tag))
    return sadrzaj_final

def telegram_obavestenje(naslov, sadrzaj) -> telegram.Message:    
    ''' Funkcija od dobijenih argumenata konstruiše i šalje poruku na Telegram kanal '''
    
    try:
        poruka = bot.send_message(TELEGRAM_CHAT_ID, text=telegram_naslov(naslov) + '\n' + telegram_sadrzaj(sadrzaj), parse_mode='html') # poruka se salje na telegram kanal
    except:
        # ako iz nekog razloga ostane neki nepodrzan HTML tag i gornji send_message ne uspe, poruka se rekonstruise i salje u plain text formatu
        logging.warning('skidanje nepodrzanih HTML tagova neuspesno, saljemo poruku kao plain text bez HTML formatiranja')
        poruka = bot.send_message(TELEGRAM_CHAT_ID, text=telegram_naslov(naslov) + '\n' + sadrzaj.text, parse_mode='html')

    try:
        # ako su uz obavestenje prilozene slike, te slike se salju posebno nakon originalne poruke
        for tag in sadrzaj.find_all('img'): 
            bot.send_photo(TELEGRAM_CHAT_ID, tag['src'], caption=telegram_naslov(naslov), parse_mode='html')
    except: 
        # ako slanje slike uz poruku ne uspe, salje se warning u log i nastavlja se bez slike
        logging.warning('slanje slike uz poruku neuspesno, saljemo poruku bez slike')
    return poruka

def main(): 

    hash_0 = obavestenja_hash(soupup(URL))
    prethodni_naslov = ''

    while True:
        time.sleep(int(UPDATE_INTERVAL)) # provera se vrsi na svakih 5 minuta 

        soup = soupup(URL) # azurna verzija sajta kao BS objekat
        hash_1 = obavestenja_hash(soup) # azurni hash sajta
        naslov, sadrzaj = aktuelno_obavestenje(soup)

        if hash_0 != hash_1: # ako se pocetni i azurni hash razlikuju, stanje na sajtu se promenilo
            if slicnost(telegram_naslov(naslov), prethodni_naslov) < 0.8:
                aktuelna_poruka = telegram_obavestenje(naslov, sadrzaj) # korisnik se obavestava porukom putem telegram_obavestenje() 
            else: 
                try:
                    bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=aktuelna_poruka.message_id, text=telegram_naslov(naslov) + '\n' + telegram_sadrzaj(sadrzaj), parse_mode='html')
                except: 
                    bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=aktuelna_poruka.message_id, text=telegram_naslov(naslov) + '\n' + sadrzaj.text, parse_mode='html')

            logging.info(hash_0 + " =/= " + hash_1) # stari i azurni hash se salju u log

            prethodni_naslov = telegram_naslov(naslov) # naslov poslatog obavestenja se setuje kao prethodni_naslov, radi poredjenja sa naslovom sledećeg obaveštenja
            hash_0 = hash_1 # pocetna vrednost hasha se setuje na novu azurnu vrednost

        else:
            continue

if __name__ == '__main__':
    main()
