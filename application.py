import os
import requests

from flask import Flask, session, request, render_template, redirect, \
     url_for, flash, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from passlib.hash import sha256_crypt

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=['GET', 'POST'])
def index():
	logged_in = False
	
	if request.method == 'POST':
		isbn = request.form.get('isbn') + '%'
		title = request.form.get('title') + '%'
		author = request.form.get('author') + '%'
		books = False

		try:
			if isbn != '%' and title != '%' and author != '%':
				books = db.execute('SELECT * FROM books WHERE isbn ILIKE :isbn AND \
					title ILIKE :title AND author ILIKE :author', \
						{'isbn': isbn, 'title': title, 'author': author}).fetchall()
			
			elif isbn != '%' and title != '%' and author == '%':
				books = db.execute('SELECT * FROM books WHERE isbn ILIKE :isbn AND \
					title ILIKE :title', {'isbn': isbn, 'title': title}).fetchall()
			
			elif isbn != '%' and title == '%' and author == '%':
				books = db.execute('SELECT * FROM books WHERE isbn ILIKE :isbn', \
					{'isbn': isbn}).fetchall()
			
			elif isbn == '%' and title != '%' and author != '%':
				books = db.execute('SELECT * FROM books WHERE author ILIKE :author AND \
					title ILIKE :title', {'author': isbn, 'author': title}).fetchall()		

			elif isbn == '%' and title == '%' and author != '%':
				books = db.execute('SELECT * FROM books WHERE author ILIKE :author', \
					{'author': author}).fetchall()	

			elif isbn == '%' and title != '%' and author == '%':
				books = db.execute('SELECT * FROM books WHERE title ILIKE :title', \
					{'title': isbn}).fetchall()

			session['books'] = books			
				
			return redirect(url_for('books'))
		except:
			flash('No results returned')
			return redirect(url_for('index'))

	# get requests
	if "user_id" in session:
		logged_in = True

		return render_template('home.html', logged_in=logged_in)

	return render_template('home.html', logged_in=logged_in)

@app.route('/api/<string:isbn>', methods=['GET'])
def display_api(isbn):
	""" Returns a JSON with information about the book given the isbn """
	try:
		book = db.execute('SELECT * FROM books WHERE isbn = :isbn',
	  	  {'isbn': isbn}).fetchall()[0]
		
		good_reads = requests.get("https://www.goodreads.com/book/review_counts.json",
	 	  params={"key": "Dbt2cs7F42IK43VAaPrutw", "isbns": isbn}).json()['books'][0]

		api_value = {
			'title': book[1],
			'author': book[2],
			'year': book[3],
			'review_count': good_reads['reviews_count'],
			'average_score': good_reads['average_rating']
		}

		return (jsonify(api_value))
	except:
		flash('No book matching that isbn')
		return redirect(url_for('index'))

@app.route('/books', methods=['GET'])
def books():
	
	if session['books'] != []:
		results = session['books']
	else:
		results = False

	return render_template('searchResults.html', results=results)

@app.route('/books/<string:title>', methods=['GET', 'POST'])
def book_details(title):

	# get the book using the title in the URL
	book = db.execute('SELECT * FROM books WHERE title = :title', 
	  {'title': title}).fetchall()[0]

	# Get all review objects, and the users associated with them.
	reviews = db.execute('SELECT * FROM reviews2 JOIN users3 ON \
	  reviews2.user_id = users3.id WHERE book = :book' , {
		  'book': str(book[0])
	  }).fetchall()

	# Get review statistics from good reads API for the book
	good_reads = requests.get("https://www.goodreads.com/book/review_counts.json",
	 params={"key": "Dbt2cs7F42IK43VAaPrutw", "isbns": book[0]}).json()['books'][0]

	if request.method == 'POST':
		review_text = request.form.get('text')
		rating = request.form.get('rating')

		# if the user already written a review, do not let them write another
		try:
			user_review = db.execute('SELECT user_id FROM reviews2 WHERE \
			user_id = :user_id', {'user_id': session['user_id']}).fetchall()[0]
			flash('you have already reviewed this book')

		# if not, update the database with the new review
		except:
			db.execute('INSERT INTO reviews2 (book, user_id, rating, \
			review_text) VALUES(:book, :user_id, :rating, :review_text)', { 
				'book': book[0],
				'user_id': int(session['user_id']),
				'rating': rating,
				'review_text': review_text
			})
			db.commit()

			return redirect(url_for('book_details', title=title))

	return render_template(
		'bookDetails.html', 
		reviews=reviews,
		book=book,
	 	good_reads=good_reads
	)

@app.route('/register', methods=['GET', 'POST'])
def register():
	error = None
	logged_in = False

	if request.method == 'POST':
		username = request.form.get('username')
		password = sha256_crypt.encrypt(request.form.get('password'))
		email = request.form.get('email')

		if not username or not email or not password:
			error = 'you must provide all information to register'
			return render_template('register.html', error=error)

		# if the username already exists, reject the login attempt
		if db.execute('SELECT username FROM users3 WHERE username = :username',\
		 {'username': username}).fetchall():
			error = 'Username already taken'
			return render_template('register.html', error=error)

		else:
			try:
				# Create a row in the users database
				db.execute('INSERT INTO users3 (username, password, email)\
			 	  VALUES(:username, :password, :email)', \
			 	    {'username': username,'password': password,'email': email}) 
				db.commit()
				
				# log the user in.
				user_id = db.execute('SELECT * FROM users3 WHERE username = :username', \
				 {'username': username}).fetchall()[0][0]
				session["user_id"] = user_id
				flash('Successfully registered!')
			except: 
				error = 'unknown error'
				flash('Something went wrong, try again')
				return render_template('register.html', error=error)
		
		return redirect(url_for('index'))

	else:
		if "user_id" in session:
			logged_in = True
		return render_template('register.html', logged_in=logged_in)


@app.route('/login', methods=['GET', 'POST'])
def login():
	error = None
	if request.method == 'POST':
		username = request.form.get('username')		
		try:
			# get the info matching that username
			user_info = db.execute('SELECT * FROM users3 WHERE username = :username', \
			  {'username': username}).fetchall()[0]

			# if password hash matches, log the user in and redirect to the home page
			if sha256_crypt.verify(request.form.get('password'), user_info[3]):
				session["user_id"] = user_info[0]		
				return redirect(url_for('index'))		

			else:
				error = 'username or password is incorrect'
				return render_template('login.html', error=error)

		except:
			error = 'username does not exist'
			return render_template('login.html', error=error)
		
	# Get request
	logged_in = False

	if "user_id" in session:
		logged_in = True
	return render_template('login.html', logged_in=logged_in)


@app.route('/logout', methods=['GET'])
def logout():
	session.clear()
	return redirect(url_for('index'))