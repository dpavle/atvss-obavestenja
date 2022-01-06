# ATVSS Obaveštenja
 
## ENV Varijable

| Ime | Opis |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token Telegram bota koji šalje obaveštenja |
| `TELEGRAM_CHAT_ID` | ID Telegram kanala gde se šalju obaveštenja |
| `UPDATE_INTERVAL` | Inverval ažuriranja informacija sa sajta |

Standardne environment varijable, opcija učitavanja preko `.env` fajla
ili kod Docker-a koristimo `-e` flag-ove. Ove varijable su neophodne
za pokretanje skripte, **bez njih skripta neće raditi!**
