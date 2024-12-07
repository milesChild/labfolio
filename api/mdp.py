# imports
import pandas as pd
import datetime
import yfinance as yf
from db import AWSDB

class IMDP:
    """Interface for a market data platform."""

    def get_returns(tickers: list[str] | str, beginning_date: datetime.date | str, end_date: datetime.date | str, null_threshold: float = 0.1) -> pd.DataFrame:
        """Gets factor data for a list of factors"""
        pass

class YahooFinanceMDP(IMDP):
    """Market data platform using Yahoo Finance"""

    def __init__(self):
        pass

    def get_returns(self, tickers: list[str] | str, beginning_date: datetime.date | str, end_date: datetime.date | str, null_threshold: float = 0.1) -> pd.DataFrame:
        """
        Get the returns for a list of tickers between two dates

        Parameters:
            tickers (list[str] | str): The tickers to get returns for
            beginning_date (datetime.date | str): The beginning date to get returns for
            end_date (datetime.date | str): The end date to get returns for
            null_threshold (float): Maximum allowable fraction of null values in a column (default: 0.9)
        """

        if isinstance(tickers, str):
            tickers = [tickers]

        # Download data for all tickers at once
        stock_data = yf.download(
            tickers=tickers,
            start=str(beginning_date),
            end=str(end_date),
            interval='1d'
        )

        prices = stock_data['Close']
        returns = prices.pct_change()

        # Drop columns (tickers) where more than threshold% of values are null
        null_pct = returns.isnull().mean()
        cols_to_keep = null_pct[null_pct < null_threshold].index
        returns = returns[cols_to_keep]

        # Then drop any remaining rows with null values
        returns = returns.dropna()

        # Ensure all date values are datetime.date objects
        returns.index = pd.to_datetime(returns.index).date

        # ensure all returns are floats
        returns = returns.astype(float)

        return returns
    
class DatabaseMDP(IMDP):
    """Market data platform using a database"""

    def __init__(self, db: AWSDB):
        self.db = db

    def get_returns(self, tickers: list[str] | str, beginning_date: datetime.date | str, end_date: datetime.date | str, null_threshold: float = 0.1) -> pd.DataFrame:
        # Convert dates to strings if they're datetime objects
        beginning_date = str(beginning_date)
        end_date = str(end_date)
        
        if tickers:
            # Add quotes around each ticker
            quoted_tickers = [f"'{ticker}'" for ticker in tickers]
            query = """
                SELECT date::date as date, factor_id, return_value 
                FROM factor.returns 
                WHERE factor_id IN ({}) 
                AND date >= %s::date 
                AND date <= %s::date 
                ORDER BY date
            """.format(', '.join(quoted_tickers))
            self.db.cursor.execute(query, (beginning_date, end_date))
        else:
            query = """
                SELECT date::date as date, factor_id, return_value 
                FROM factor.returns 
                WHERE date >= %s::date 
                AND date <= %s::date 
                ORDER BY date
            """
            self.db.cursor.execute(query, (beginning_date, end_date))

        # Get column names from cursor description
        columns = [desc[0] for desc in self.db.cursor.description]
        
        # Fetch all rows
        rows = self.db.cursor.fetchall()
        
        # Create DataFrame with explicit column names
        factor_returns = pd.DataFrame(rows, columns=columns)

        # Pivot the DataFrame
        factor_returns = factor_returns.pivot(
            index='date',
            columns='factor_id',
            values='return_value'
        )

        # Drop columns where more than threshold% of values are null
        null_pct = factor_returns.isnull().mean()
        cols_to_keep = null_pct[null_pct < null_threshold].index
        factor_returns = factor_returns[cols_to_keep]

        # Then drop any remaining rows with null values
        factor_returns = factor_returns.dropna()

        # Ensure all date values are datetime.date objects
        factor_returns.index = pd.to_datetime(factor_returns.index).date

        # ensure all returns are floats
        factor_returns = factor_returns.astype(float)

        return factor_returns