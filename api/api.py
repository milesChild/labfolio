# standard
import datetime
import io
import os
import uuid
from typing import Optional

# third party
import bcrypt
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from linearmodels.asset_pricing import LinearFactorModel

# locals
from common.models import (
    Account,
    Portfolio,
    PortfolioHolding,
    Factor
)
from db import AWSDB
from mdp import DatabaseMDP, YahooFinanceMDP
from s3 import AWSS3

app = FastAPI(title="labfolio-api")

DEMO_PORTFOLIO_ID = "7c2114c3-baa6-4c98-9f3c-939f414a4531"

######################
### HELPER METHODS ###
######################

def test_db_connection() -> None:
    """Runs a test to ensure we can connect to the database"""
    db = AWSDB(username=os.getenv('RDS_USER'), password=os.getenv('RDS_PASSWORD'), host=os.getenv('RDS_HOST'), database_name=os.getenv('RDS_NAME'))
    db.cursor.execute("SELECT 1")
    result = db.cursor.fetchone()
    del db
    if result:
        print('[ INFO | BACKEND ] Database connection successful')
    else:
        raise Exception('[ ERROR | BACKEND ] Database connection failed')

def test_s3_connection() -> None:
    """Runs a test to ensure we can connect to S3"""
    s3 = AWSS3(
        aws_access_key_id=os.getenv('S3_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET'),
        bucket_name=os.getenv('S3_BUCKET')
    )
    files = s3.list_files()
    del s3
    print('[ INFO | BACKEND ] S3 connection successful')

def check_username_exists(username: str) -> bool:
    """Checks if a username exists in the database"""
    db = AWSDB(username=os.getenv('RDS_USER'), password=os.getenv('RDS_PASSWORD'), host=os.getenv('RDS_HOST'), database_name=os.getenv('RDS_NAME'))
    db.cursor.execute("SELECT 1 FROM user_management.accounts WHERE username = %s", (username,))
    result = db.cursor.fetchone()
    del db
    return result is not None

def get_db_connection() -> AWSDB:
    """Gets a database connection"""
    return AWSDB(username=os.getenv('RDS_USER'), password=os.getenv('RDS_PASSWORD'), host=os.getenv('RDS_HOST'), database_name=os.getenv('RDS_NAME'))

def get_s3_connection() -> AWSS3:
    """Gets an S3 connection"""
    return AWSS3(aws_access_key_id=os.getenv('S3_KEY'), aws_secret_access_key=os.getenv('S3_SECRET'), bucket_name=os.getenv('S3_BUCKET'))

def verify_portfolio(df: pd.DataFrame) -> bool:
    """Verifies that the portfolio is well-formed"""
    # the only permitted columns are 'yf_ticker' and 'quantity'
    if not set(df.columns) == {'yf_ticker', 'quantity'}:
        return False
    # every value in the 'yf_ticker' column must be a string
    try:
        df['yf_ticker'].astype(str)
    except Exception:
        return False
    # every value in the 'quantity' column must be an integer
    try:
        df['quantity'].astype(int)
    except Exception:
        return False
    return True

def get_portfolio_df(portfolio_id: str) -> Optional[pd.DataFrame]:
    """
    Gets a portfolio DataFrame from S3 based on its portfolio_id
    :param portfolio_id: UUID of the portfolio
    :return: pandas DataFrame containing the portfolio data, or None if not found
    """
    try:
        # Get database connection and fetch portfolio address
        db = get_db_connection()
        db.cursor.execute(
            "SELECT portfolio_address FROM user_management.portfolios WHERE portfolio_id = %s",
            (portfolio_id,)
        )
        result = db.cursor.fetchone()
        
        if not result:
            return None
            
        portfolio_address = result[0]
        
        # Extract the S3 key from the portfolio address by removing the "s3://" prefix and bucket name
        s3_key = portfolio_address.split('/', 3)[3]
        
        # Get S3 connection and download the CSV
        s3 = get_s3_connection()
        df = s3.read_csv(s3_key)
        
        return df
        
    except Exception as e:
        print(f"Error getting portfolio CSV: {str(e)}")
        return None
    finally:
        if 'db' in locals(): del db
        if 's3' in locals(): del s3

def align_data(factor_df, asset_df):
    # Convert both DataFrames' indices to datetime if they aren't already
    factor_copy = factor_df.copy()
    asset_copy = asset_df.copy()
    factor_copy.index = pd.to_datetime(factor_copy.index)
    asset_copy.index = pd.to_datetime(asset_copy.index)
    
    # Find common dates between both DataFrames
    common_dates = factor_copy.index.intersection(asset_copy.index)
    
    # Reindex both DataFrames to use only the common dates
    factor_data = factor_copy.loc[common_dates]
    asset_data = asset_copy.loc[common_dates]

    # Delete intermediate dfs
    del factor_copy, asset_copy
    
    return factor_data, asset_data

def __validate_factor_model(factors: list[str], holdings: list[PortfolioHolding]) -> None:
    """Validates the factor model"""
    if len(factors) == 0:
        raise HTTPException(status_code=400, detail="No factors selected")
    if len(holdings) == 0:
        raise HTTPException(status_code=400, detail="No holdings selected")
    if len(holdings) < len(factors):
        raise HTTPException(status_code=400, detail="There must be at least as many holdings as factors")
    if len(factors) != len(set(factors)):
        raise HTTPException(status_code=400, detail="All factors must be unique")
    return True

####################
### GET REQUESTS ###
####################

@app.get("/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "pong"}

@app.get("/portfolios")
async def get_user_portfolios(user_id: str):
    """Gets a user's portfolios"""
    try:
        db = get_db_connection()
        
        # Get portfolio IDs associated with the user
        print(f"DEBUG: Fetching portfolios for user_id: {user_id}")
        db.cursor.execute(
            "SELECT portfolio_id FROM user_management.user_portfolios WHERE user_id = %s",
            (user_id,)
        )
        portfolio_ids = db.cursor.fetchall()
        print(f"DEBUG: Found portfolio_ids: {portfolio_ids}")
        
        # Extract portfolio IDs from tuples and include demo portfolio
        if portfolio_ids:
            portfolio_id_list = [str(id[0]) for id in portfolio_ids]  # Convert UUIDs to strings
        else:
            portfolio_id_list = []
        portfolio_id_list.append(DEMO_PORTFOLIO_ID)
        print(f"DEBUG: Final portfolio_id_list: {portfolio_id_list}")
        
        # Create the parameterized query
        placeholders = ','.join(['%s'] * len(portfolio_id_list))
        query = f"SELECT * FROM user_management.portfolios WHERE portfolio_id IN ({placeholders})"
        print(f"DEBUG: Executing query: {query}")
        print(f"DEBUG: With parameters: {tuple(portfolio_id_list)}")
        
        # Execute query with portfolio IDs as parameters
        db.cursor.execute(query, tuple(portfolio_id_list))
        
        result = db.cursor.fetchall()
        print(f"DEBUG: Query result: {result}")
        
        # Convert result to list of Portfolio objects
        column_names = [desc[0] for desc in db.cursor.description]
        portfolios = []
        for row in result:
            try:
                # Convert row to list so we can modify it
                row_list = list(row)
                # Find index of portfolio_id column
                pid_index = column_names.index('portfolio_id')
                # Convert UUID to string
                row_list[pid_index] = str(row_list[pid_index])
                # Create Portfolio object
                portfolio_dict = dict(zip(column_names, row_list))
                print(f"DEBUG: Creating Portfolio with data: {portfolio_dict}")
                portfolio = Portfolio(**portfolio_dict)
                portfolios.append(portfolio)
            except Exception as e:
                print(f"DEBUG: Error processing row {row}: {str(e)}")
                raise
        
        return portfolios
        
    except Exception as e:
        print(f"DEBUG: Error in get_user_portfolios: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching portfolios: {str(e)}"
        )
    finally:
        if 'db' in locals():
            del db

# TODO: get a specific portfolio
@app.get("/portfolio")
async def get_portfolio(portfolio_id: str, user_id: str):
    """Gets a specific portfolio"""
    # queries database to verify user_id owns portfolio_id
    if portfolio_id == DEMO_PORTFOLIO_ID:
        pass
    else:  # verify that user_id owns portfolio_id
        pass
    # queries s3 for the portfolio
    # verifies the portfolio is well-formed
    # returns the portfolio
    pass

# TODO: get a list of holdings for a portfolio
@app.get("/portfolio/holdings")
async def get_portfolio_holdings(portfolio_id: str) -> list[PortfolioHolding]:
    """Gets the holdings for a portfolio"""
    try:
        df = get_portfolio_df(portfolio_id)
        if df is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
            
        # Convert DataFrame rows to dictionaries using column names
        holdings = [
            PortfolioHolding(portfolio_id=portfolio_id, **dict(zip(df.columns, row))) 
            for row in df.values
        ]
        return holdings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio holdings: {str(e)}")

@app.get("/factors")
async def get_factors():
    """Gets a list of available factors"""
    # queries the database for all factors
    # returns a list of Factor objects
    try:
        db = get_db_connection()
        db.cursor.execute("SELECT * FROM factor.factors")
        result = db.cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching factors: {str(e)}")
    # convert result to list of Factor objects
    try:
        column_names = [desc[0] for desc in db.cursor.description]
        factors = [Factor(**dict(zip(column_names, row))) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting factors to objects: {str(e)}")
    finally:
        del db
    return factors

@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Downloads a file from S3"""
    try:
        s3 = get_s3_connection()
        file_obj = s3.download_fileobj(file_path)
        
        if file_obj is None:
            raise HTTPException(status_code=404, detail="File not found")
            
        # Create a streaming response
        return StreamingResponse(
            iter([file_obj.getvalue()]),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={file_path.split('/')[-1]}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")
    finally:
        if 's3' in locals(): del s3
        
#####################
### POST REQUESTS ###
#####################

@app.post("/account")
async def create_account(username: str, password: str):
    """Creates a new account"""
    # Check if username already exists
    if check_username_exists(username):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Hash the password
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    # Generate UUID for user
    user_id = str(uuid.uuid4())

    # Create an instance of Account
    account = Account(
        user_id=user_id,
        username=username,
        password_hash=password_hash
    )

    # Validate account
    Account.model_validate(account)

    # Convert account to dict
    account_dict = account.model_dump()
    
    # Create account in database
    db = get_db_connection()
    
    try:
        query = f"INSERT INTO user_management.accounts ({', '.join(account_dict.keys())}) VALUES ({', '.join(['%s'] * len(account_dict))})"
        db.cursor.execute(query, tuple(account_dict.values()))

        # Return user information instead of just status
        return {
            "status": "Account created successfully",
            "user_id": user_id,
            "username": username
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating account: {str(e)}")
    finally:
        del db

@app.post("/login")
async def login(username: str, password: str):
    """Authenticates a user and returns their account information"""
    # Get database connection
    db = get_db_connection()
    
    try:
        # Get account from database
        db.cursor.execute(
            """
            SELECT user_id, username, password_hash 
            FROM user_management.accounts 
            WHERE username = %s
            """, 
            (username,)
        )
        result = db.cursor.fetchone()
        
        # Check if user exists
        if not result:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Unpack result
        user_id, db_username, stored_hash = result
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Return user information instead of just status
        return {
            "status": "Successfully logged in",
            "user_id": user_id,
            "username": username
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")
    finally:
        del db

@app.post("/portfolio")
async def upload_portfolio(file: UploadFile, portfolio_name: str, user_id: str):
    """Uploads a portfolio CSV file and creates a new portfolio entry"""
    
    print(f"DEBUG: Starting portfolio upload for user {user_id}")
    print(f"DEBUG: File name: {file.filename}")
    print(f"DEBUG: Portfolio name: {portfolio_name}")
    
    # Verify file is CSV
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Portfolio file must be a CSV.")
    
    # Verify the portfolio name is not empty
    if not portfolio_name:
        raise HTTPException(status_code=400, detail="Portfolio name cannot be empty.")
    
    # Read and validate CSV content
    try:
        print("DEBUG: Reading file contents")
        contents = await file.read()
        print("DEBUG: File contents read successfully")
        print("DEBUG: Attempting to parse CSV")
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        print("DEBUG: CSV parsed successfully")
    except Exception as e:
        print(f"DEBUG: Error reading/parsing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading CSV file: {str(e)}")
        
    if not verify_portfolio(df):
        raise HTTPException(status_code=400, detail="Ill-formatted portfolio. Please use the exact format as the demo_portfolio.csv file.")
    
    # Generate unique portfolio ID
    portfolio_id = str(uuid.uuid4())
    
    try:
        # Upload to S3
        print("DEBUG: Attempting to upload file to S3")
        s3 = get_s3_connection()
        s3_path = f"portfolios/{portfolio_id}.csv"
        # Create BytesIO object with the contents
        file_obj = io.BytesIO(contents)
        address = s3.upload_fileobj(file_obj, s3_path)
        print(f"DEBUG: File uploaded to S3 at {address}")

        if not address:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload portfolio to storage"
            )
        
        # Create Portfolio record
        print("DEBUG: Creating portfolio record")
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
            portfolio_name=portfolio_name,
            portfolio_address=address
        )
        
        # Validate portfolio
        Portfolio.model_validate(portfolio)
        
        # Save to database
        print("DEBUG: Saving portfolio to database")
        db = get_db_connection()
        portfolio_dict = portfolio.model_dump()
        query = f"""
            INSERT INTO user_management.portfolios 
            ({', '.join(portfolio_dict.keys())}) 
            VALUES ({', '.join(['%s'] * len(portfolio_dict))})
        """
        db.cursor.execute(query, tuple(portfolio_dict.values()))
        print("DEBUG: Portfolio saved to database")

        # Upload a record to the user_portfolios mapping table
        print("DEBUG: Uploading record to user_portfolios mapping table")
        db.cursor.execute("INSERT INTO user_management.user_portfolios (user_id, portfolio_id) VALUES (%s, %s)", (user_id, portfolio_id))
        print("DEBUG: Record uploaded to user_portfolios mapping table")
        
        return {
            "status": "Portfolio uploaded successfully",
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name
        }
        
    except Exception as e:
        print(f"DEBUG: Error during portfolio upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading portfolio: {str(e)}")
    finally:
        if 'db' in locals(): del db
        if 's3' in locals(): del s3

@app.post("/analysis/validate_factor_model")
async def validate_factor_model(factors: list[str], holdings: list[PortfolioHolding]) -> bool:
    """Validates a factor model"""
    result = __validate_factor_model(factors, holdings)
    return result

# TODO: run a factor model analysis
@app.post("/analysis/factor_model")
async def analyze_factor_model(factors: list[str], holdings: list[PortfolioHolding]) -> dict:
    """
    Analyzes a portfolio using the specified factors
    Returns a JSON containing the analysis results
    """
    print(f"DEBUG: Starting factor model analysis")
    print(f"DEBUG: Received factors: {factors}")
    print(f"DEBUG: Received holdings: {[h.model_dump() for h in holdings]}")

    # model validate each holding
    for holding in holdings:
        PortfolioHolding.model_validate(holding)
    
    holdings_tickers = [str(h.yf_ticker) for h in holdings]
    
    # validate the factor model first
    if not __validate_factor_model(factors, holdings_tickers):
        print("DEBUG: Factor model validation failed")
        raise HTTPException(status_code=400, detail="Invalid factor model")
    print("DEBUG: Factor model validation passed")
    
    # start today and go back one year
    beginning_date = datetime.date.today() - datetime.timedelta(days=365)
    end_date = datetime.date.today()
    print(f"DEBUG: Analysis period: {beginning_date} to {end_date}")
    
    # get data for factors
    try:
        print("DEBUG: Fetching factor data")
        db = get_db_connection()
        mdp = DatabaseMDP(db)
        factor_returns = mdp.get_returns(factors, beginning_date, end_date)
    except Exception as e:
        print(f"DEBUG: Error fetching factor data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching factor data: {str(e)}")

    # get data for holdings
    try:
        print("DEBUG: Fetching portfolio data")
        yfmdp = YahooFinanceMDP()
        portfolio_returns = yfmdp.get_returns(holdings_tickers, beginning_date, end_date)
    except Exception as e:
        print(f"DEBUG: Error fetching portfolio data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio data: {str(e)}")
    
    factor_returns.index.name = 'date'
    portfolio_returns.index.name = 'date'
    print("DEBUG: Set index names to 'date'")

    # align the data
    try:
        print("DEBUG: Aligning factor and portfolio data")
        factor_df, portfolio_df = align_data(factor_returns, portfolio_returns)
        print(f"DEBUG: Aligned data shapes - Factors: {factor_df.shape}, Portfolio: {portfolio_df.shape}")
        print(f"DEBUG: Date range: {factor_df.index.min()} to {factor_df.index.max()}")
    except Exception as e:
        print(f"DEBUG: Error aligning data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error aligning data: {str(e)}")
    
    print(f"DEBUG: Factor returns head:\n{factor_df.head()}")
    print(f"DEBUG: Portfolio returns head:\n{portfolio_df.head()}")
    print(f"DEBUG: Factor returns info:\n{factor_df.info()}")
    print(f"DEBUG: Portfolio returns info:\n{portfolio_df.info()}")
    # # convert the date index values to strings
    # factor_df.index = factor_df.index.astype(str)
    # portfolio_df.index = portfolio_df.index.astype(str)

    # run a LinearFactorModel
    try:
        print("DEBUG: Fitting linear factor model")
        model = LinearFactorModel(portfolios=portfolio_df, factors=factor_df)
        res = model.fit()
        model_rsq = res.rsquared
        model_no_assets = len(res.params)
        model_no_factors = len(factor_df.columns)
        model_j_stat = res.j_statistic.stat
        params = res.params
        print(f"DEBUG: Model fit complete")
        print(f"DEBUG: R-squared: {model_rsq:.4f}")
        print(f"DEBUG: Number of assets: {model_no_assets}")
        print(f"DEBUG: Number of factors: {model_no_factors}")
        print(f"DEBUG: J-statistic: {model_j_stat:.4f}")
    except Exception as e:
        print(f"DEBUG: Error fitting factor model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fitting factor model: {str(e)}")
    
    try:
        print("DEBUG: Preparing response")
        response = {
            "status": "success",
            "analysis": {
                "statistics": {
                    "no_factors": model_no_factors,
                    "no_assets": model_no_assets,
                    "no_observations": len(factor_df),
                    "r_squared": model_rsq,
                    "j_statistic": model_j_stat
                },
                "covariance_matrix": res.cov.to_dict(),
                "params": params.to_dict(),
                "risk_premia": res.risk_premia.to_dict(),
                "timestamp": str(datetime.datetime.now())
            }
        }
        print(f"DEBUG: Final response: {response}")
        return response
        
    except Exception as e:
        print(f"DEBUG: Error preparing response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error performing factor analysis: {str(e)}")

if __name__ == "__main__":
    try:
        test_db_connection()
        test_s3_connection()
    except Exception as e:
        print(f"[ ERROR | BACKEND ] Failed to connect to database or S3: {str(e)}")
        exit(1)
    print("[ INFO | BACKEND ] Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)
