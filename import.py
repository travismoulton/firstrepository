from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import pandas
import os

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

data_frame = pandas.read_csv('books.csv')

isbn = data_frame.isbn.tolist()
title = data_frame.title.tolist()
author = data_frame.author.tolist()
year = data_frame.year.tolist()


ctr = 0
for line in isbn:
    db.execute('INSERT INTO books (isbn, title, author, year) VALUES(:isbn, :title, :author, :year)', \
        {'isbn': isbn[ctr], 'title': title[ctr], 'author': author[ctr], 'year': year[ctr]})
    db.commit()
    
    ctr += 1