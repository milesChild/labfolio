import os
import yfinance as yf
import psycopg2
from datetime import datetime, timedelta
import pandas as pd
import gc

# helper function to get a database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD']
    )

def clean_market_data(df):
    # Calculate returns from Close prices
    returns = df['Close'].pct_change().dropna()
    returns.index = returns.index.date
    returns = returns.reset_index()
    # The column is already named 'Date' from yfinance, and we're working with the 'Close' returns
    returns.columns = ['date', 'return_value']
    return returns

# helper function to fetch market data for a symbol between two dates
def fetch_market_data(symbol, start_date, end_date):
    # fetch the market data from yfinance
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    return df

# helper function to get the list of factor_ids from the database
def get_factors(cursor):
    # get the list of factor_ids from the database
    cursor.execute("SELECT factor_id FROM factor.factors")
    return [row[0] for row in cursor.fetchall()]

# helper function to upload returns to the database
def upload_to_database(factor_id: str, returns: pd.DataFrame, conn, cursor):
    # Ensure we have the correct data structure
    data = [(factor_id, row['date'], row['return_value']) for _, row in returns.iterrows()]
    
    # insert the data into the database
    cursor.executemany(
        "INSERT INTO factor.returns (factor_id, date, return_value) VALUES (%s, %s, %s)", 
        data
    )
    conn.commit()

# helper function to clear all existing return data for a factor_id
def clear_returns(factor_id: str, conn, cursor):
    cursor.execute(f"DELETE FROM factor.returns WHERE factor_id = '{factor_id}'")
    conn.commit()

def handler(event, context):
    """Lambda handler function"""

    # set the date range
    LOOKBACK_YEARS = 2
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * LOOKBACK_YEARS)

    # get a database connection
    print(f'[ INFO ] Getting database connection')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f'[ ERROR ] Error getting database connection: {e}')
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

    # obtain the list of factor_ids from the database
    print(f'[ INFO ] Fetching factor_ids from database')
    try:
        factors = get_factors(cursor)
    except Exception as e:
        print(f'[ ERROR ] Error fetching factor_ids from database: {e}')
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
    
    success = 0

    # for each factor_id, fetch the market data and insert it into the database
    for factor_id in factors:
        try:
            print(f'[ INFO ] Processing factor_id: {factor_id}')
            # fetch the market data
            returns = fetch_market_data(factor_id, start_date, end_date)
            print(f'[ INFO ] Fetched market data for {factor_id}')
            # clean the market data
            returns = clean_market_data(returns)
            print(f'[ INFO ] Cleaned market data for {factor_id}')
            # clear the existing returns for the factor_id
            clear_returns(factor_id, conn, cursor)
            print(f'[ INFO ] Cleared existing returns for {factor_id}')
            # upload the returns to the database
            upload_to_database(factor_id, returns, conn, cursor)
            print(f'[ INFO ] Uploaded returns for {factor_id}')
            # delete the returns dataframe
            del returns
            gc.collect()
            success += 1
        except Exception as e:
            print(f'[ ERROR ] Error processing factor_id: {factor_id}: {e}')
            continue

    print(f'[ INFO ] Successfully processed {success} factor_ids')
    
    return {
        'statusCode': 200,
        'body': f'Successfully updated market returns from {start_date} to {end_date}'
    }