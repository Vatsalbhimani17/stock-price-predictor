import numpy as np
import pandas as pd
from keras.models import load_model
import streamlit as st
import sqlite3
from passlib.hash import pbkdf2_sha256
from yahoo_fin import stock_info as si
import plotly.graph_objects as go
import requests
import yfinance as yf

# Load the machine learning model
model = load_model('model/Stock Prediction Model.keras')

# Function to create a database connection
def create_connection(db_file):
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return None

# Function to create a user table
def create_table(conn):
    sql_create_table = """CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            email TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL
                            );"""
    try:
        c = conn.cursor()
        c.execute(sql_create_table)
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Table creation error: {e}")

# Function to insert a new user
def insert_user(conn, username, email, password):
    sql_insert_user = "INSERT INTO users (username, email, password) VALUES (?, ?, ?)"
    try:
        c = conn.cursor()
        c.execute(sql_insert_user, (username, email, pbkdf2_sha256.hash(password)))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: users.username" in str(e):
            return -1
        elif "UNIQUE constraint failed: users.email" in str(e):
            return -2
        else:
            st.error(f"SQLite integrity error: {e}")
            return -3
    except sqlite3.Error as e:
        st.error(f"SQLite error: {e}")
        return -3

# Function to verify login credentials
def verify_user(conn, username, password):
    sql_verify_user = "SELECT * FROM users WHERE username = ?"
    try:
        c = conn.cursor()
        c.execute(sql_verify_user, (username,))
        user = c.fetchone()
        if user:
            stored_password = user[3]
            if pbkdf2_sha256.verify(password, stored_password):
                return True
        return False
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        conn.close()

# Function to fetch Yahoo Finance data
def fetch_table_from_yahoo(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    tables = pd.read_html(response.text)

    if not tables:
        raise ValueError("No table found on page.")

    df = tables[0]
    return df.head(10)

def fetch_yahoo_finance_data():
    gainers_url = "https://finance.yahoo.com/research-hub/screener/day_gainers/"
    losers_url = "https://finance.yahoo.com/research-hub/screener/losers/"
    active_url = "https://finance.yahoo.com/research-hub/screener/most_actives/"

    top_gainers = fetch_table_from_yahoo(gainers_url)
    top_losers = fetch_table_from_yahoo(losers_url)
    most_active = fetch_table_from_yahoo(active_url)

    return top_gainers, top_losers, most_active

# Function to display stock statistics
def display_stock_stats():
    st.header('Stock Statistics')

    top_gainers, top_losers, most_active = fetch_yahoo_finance_data()

    st.subheader('Top Gainers')
    st.write(top_gainers)

    st.subheader('Top Losers')
    st.write(top_losers)

    st.subheader('Most Active Stocks')
    st.write(most_active)

# Function to display the stock market predictor
def display_stock_predictor(symbol):
    if not symbol or symbol.strip() == "":
        st.error("Please enter a valid stock symbol.")
        return

    st.header(f'Prediction for Stock Symbol: {symbol}')

    start_date = st.date_input("Start Date", pd.to_datetime('2014-01-01'))
    end_date = st.date_input("End Date", pd.to_datetime('today'))

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    data = yf.download(symbol, start=start, end=end, auto_adjust=False)

    if data is None or data.empty:
        st.error(f"No data found for symbol: {symbol}")
        return

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.columns = [str(col).lower() for col in data.columns]

    st.subheader('Stock Data')
    st.write(data)

    data_train = pd.DataFrame(data['close'][0: int(len(data)*0.80)])
    data_test = pd.DataFrame(data['close'][int(len(data)*0.80): len(data)])

    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler(feature_range=(0,1))

    pas_100_days = data_train.tail(100)
    data_test = pd.concat([pas_100_days, data_test], ignore_index=True)
    data_test_scale = scaler.fit_transform(data_test)

    st.subheader('Price vs MA50')
    ma_50_days = data['close'].rolling(50).mean()
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=ma_50_days, mode='lines', name='MA50'))
    fig1.add_trace(go.Scatter(x=data.index, y=data['close'], mode='lines', name='Close Price'))
    fig1.update_layout(title='Price vs MA50', xaxis_title='Date', yaxis_title='Price')
    st.plotly_chart(fig1)

    st.subheader('Price vs MA50 vs MA100')
    ma_100_days = data['close'].rolling(100).mean()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=ma_50_days, mode='lines', name='MA50'))
    fig2.add_trace(go.Scatter(x=data.index, y=ma_100_days, mode='lines', name='MA100'))
    fig2.add_trace(go.Scatter(x=data.index, y=data['close'], mode='lines', name='Close Price'))
    fig2.update_layout(title='Price vs MA50 vs MA100', xaxis_title='Date', yaxis_title='Price')
    st.plotly_chart(fig2)

    st.subheader('Price vs MA100 vs MA200')
    ma_200_days = data['close'].rolling(200).mean()
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=data.index, y=ma_100_days, mode='lines', name='MA100'))
    fig3.add_trace(go.Scatter(x=data.index, y=ma_200_days, mode='lines', name='MA200'))
    fig3.add_trace(go.Scatter(x=data.index, y=data['close'], mode='lines', name='Close Price'))
    fig3.update_layout(title='Price vs MA100 vs MA200', xaxis_title='Date', yaxis_title='Price')
    st.plotly_chart(fig3)

    x = []
    y = []

    for i in range(100, data_test_scale.shape[0]):
        x.append(data_test_scale[i-100:i])
        y.append(data_test_scale[i,0])

    x, y = np.array(x), np.array(y)

    predict = model.predict(x)

    scale = 1 / scaler.scale_

    predict = predict * scale
    y = y * scale

    st.subheader('Original Price vs Predicted Price')
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=data.index[-len(predict):], y=predict.flatten(), mode='lines', name='Predicted Price'))
    fig4.add_trace(go.Scatter(x=data.index[-len(y):], y=y.flatten(), mode='lines', name='Original Price'))
    fig4.update_layout(title='Original Price vs Predicted Price', xaxis_title='Date', yaxis_title='Price')
    st.plotly_chart(fig4)

    if st.button("⬅ Back to Stock Page"):
        if st.session_state.get('login_auth', False):
            st.session_state['page'] = 'stock_page'
        else:
            st.session_state['page'] = 'login_signup'
        st.rerun()

# Function to display top gainers, top losers, and most active stocks along with search bar
def display_stock_page():
    st.header('Stock Page')

    st.subheader('Search Bar')
    symbol = st.text_input('Enter Stock Symbol')

    if st.button('Search'):
        st.session_state['page'] = 'predictor'
        st.session_state['symbol'] = symbol
        st.rerun()

    display_stock_stats()

# Function to display login/signup page
def login_signup_page():
    st.title('Login/Signup Page')

    if 'login_auth' not in st.session_state:
        st.session_state['login_auth'] = False

    conn = create_connection('users.db')
    create_table(conn)

    if not st.session_state.login_auth:
        signup = st.checkbox('Sign Up')
        if signup:
            new_username = st.text_input('New Username')
            new_email = st.text_input('Email')
            new_password = st.text_input('New Password', type='password')
            confirm_password = st.text_input('Confirm Password', type='password')

            if st.button('Sign Up'):
                if new_password == confirm_password:
                    result = insert_user(conn, new_username, new_email, new_password)
                    if result > 0:
                        st.success('Signup successful. Please login.')
                    elif result == -1:
                        st.error('Username already exists. Please choose another username.')
                    elif result == -2:
                        st.error('Email already exists. Please choose another email.')
                else:
                    st.error('Passwords do not match. Please try again.')
        else:
            username = st.text_input('Username')
            password = st.text_input('Password', type='password')

            if st.button('Login'):
                print("Logging in...")
                if verify_user(conn, username, password):
                    st.session_state['login_auth'] = True
                    st.success('Login successful. Welcome, ' + username + '!')
                    st.session_state['page'] = 'stock_page'
                    st.rerun()
                else:
                    st.error('Invalid username or password. Please try again.')
    else:
        display_stock_page()

# Function to display about us page
def about_us_page():
    st.header('About Us')
    st.write("Welcome to our stock prediction platform. Our platform provides valuable insights into the stock market.")
    st.write("You can find information about the top gainers, top losers, and most active stocks in the market.")
    st.write("Additionally, we offer a stock predictor model to help users understand how a stock is performing.")
    st.write("Please note that the predictor model provides information about historical stock performance and does not predict future stock prices.")

    st.markdown("---")

    if st.button("⬅ Back"):
        if st.session_state.get('login_auth', False):
            st.session_state['page'] = 'stock_page'
        else:
            st.session_state['page'] = 'login_signup'
        st.rerun()

# Function to handle logout
def logout():
    st.session_state['login_auth'] = False
    st.session_state['page'] = 'login_signup'
    st.success('Logout successful. You have been logged out.')
    st.rerun()

# Main function to handle page navigation
def main():
    if 'login_auth' not in st.session_state:
        st.session_state['login_auth'] = False

    if 'page' not in st.session_state:
        st.session_state['page'] = 'login_signup'

    if 'symbol' not in st.session_state:
        st.session_state['symbol'] = ''

    page = st.session_state.get('page', 'login_signup')
    symbol = st.session_state.get('symbol', '')

    st.sidebar.title('Navigation')

    # Always visible
    if st.sidebar.button('About Us'):
        st.session_state['page'] = 'about_us'
        st.rerun()

    # Show based on login status
    if st.session_state.get('login_auth', False):
        st.sidebar.success("Logged in")
        if st.sidebar.button('Logout'):
            st.session_state['page'] = 'logout'
            st.rerun()
    else:
        st.sidebar.info("Not logged in")
        if st.sidebar.button('Login/Signup'):
            st.session_state['page'] = 'login_signup'
            st.rerun()

    if page == 'stock_page':
        if st.session_state.get('login_auth', False):
            display_stock_page()
        else:
            st.warning("Please login first.")
            login_signup_page()

    elif page == 'predictor':
        if st.session_state.get('login_auth', False):
            display_stock_predictor(symbol)
        else:
            st.warning("Please login first.")
            login_signup_page()

    elif page == 'about_us':
        about_us_page()

    elif page == 'login_signup':
        login_signup_page()

    elif page == 'logout':
        logout()

    else:
        login_signup_page()

if __name__ == "__main__":
    main()