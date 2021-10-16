FROM python:3

WORKDIR /usr/src/app
COPY . .

# install dependencies 
RUN pip install -r requirements.txt

CMD ["obavestenja.py"] 
ENTRYPOINT ["python3"] 
