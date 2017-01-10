from flask import *
import pandas as pd
import sqlite3
import re

DATABASE = 'database.db'

app = Flask(__name__)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/save", methods=['POST'])
def save():
    id = int(request.form['id'])
    rating = int(request.form['rating'])
    # If the rating is equal to the current one, remove it
    # Note: always, always, always use prepared statements, don't construct an SQL-string by hand
    # by appending values together. I.e. don't do 'SELECT rating FROM feedback WHERE id = ' + id
    previous_rating = query_db('SELECT rating FROM feedback WHERE id = ?', (id,), one=True)
    previous_rating = int(previous_rating['rating']) if previous_rating else 0
    if rating == previous_rating:
        get_db().cursor().execute('DELETE FROM feedback WHERE id = ?', (id,))
        get_db().commit()
        rating = 0
    else:
        get_db().cursor().execute('INSERT OR REPLACE INTO feedback (id, rating)  VALUES (?, ?)', (id, rating))
        get_db().commit()
    # If this request comes from JavaScript, return a JSON answer with the new rating
    if request.is_xhr:
        return jsonify(new_rating=rating)
    # Otherwise, redirect to user again to the table page
    return redirect(url_for('table_with_forms'))

@app.route("/")
@app.route("/forms")
def table_with_forms():
    table = query_db('SELECT data.id, date, film, gross, feedback.rating FROM data LEFT JOIN feedback ON feedback.id = data.id')
    return render_template('index-with-forms.html', table=table)

@app.route("/ajax")
def table_with_ajax():
    table = query_db('SELECT data.id, date, film, gross, feedback.rating FROM data LEFT JOIN feedback ON feedback.id = data.id')
    return render_template('index-with-ajax.html', table=table)

if __name__ == "__main__":
    # We need to use app_context since get_db() uses Flask's magic .g variable
    with app.app_context():
        # Read in a table from Wikipedia to use as our example data
        dt = pd.read_html('https://en.wikipedia.org/w/index.php?title=List_of_2016_box_office_number-one_films_in_the_United_States&oldid=759223313',
                 header=0, index_col=0, match='Date',
                 converters={'Date': lambda x: re.sub(r'\d+-\d+-\d+-\d+', '', str(x))})[0]
        dt.to_sql('data', get_db(), if_exists='replace', index=True, index_label='id')
        # Prepare the feedback table if it doesn't exist
        get_db().cursor().execute('CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, rating INTEGER)')
        get_db().commit()
    app.run(debug=True)