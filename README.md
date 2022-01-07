# ATVSS Obaveštenja

[![Actions Status](https://github.com/dpavle/atvss-obavestenja/workflows/Docker%20Hub/badge.svg)](https://github.com/dpavle/atvss-obavestenja/actions)

Python skripta koja dobavlja najnovija obaveštenja sa ATVSS sajta (vtsnis.edu.rs). 

Sajt se čekira za promene u datom intervalu i aktuelna obaveštenja šaljemo na dati Telegram kanal. 

## Docker

Skripta je dostupna i u obliku Docker image-a, može se naći na Docker Hub-u pod `pavled/atvss-obavestenja`. 
Image se automatski update-uje putem GitHub action-a. `:latest` tag prati `main` branch. 

Primer pokretanja containera:
```
docker run -d -e TELEGRAM_BOT_TOKEN="xxxx:xxxxxxx" -e TELEGRAM_CHAT_ID="-10xxxxxxx" -e UPDATE_INTERVAL="300" --name atvss pavled/atvss-obavestenja:latest
```

## ENV Varijable

| Ime | Opis |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token Telegram bota koji šalje obaveštenja |
| `TELEGRAM_CHAT_ID` | ID Telegram kanala gde se šalju obaveštenja |
| `UPDATE_INTERVAL` | Inverval ažuriranja informacija sa sajta |

Standardne environment varijable, opcija učitavanja preko `.env` fajla
ili kod Docker-a koristimo `-e` flag-ove. Ove varijable su neophodne
za pokretanje skripte, **bez njih skripta neće raditi!**
