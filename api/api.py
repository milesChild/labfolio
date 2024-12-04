from fastapi import FastAPI, HTTPException, UploadFile, File
import uvicorn
import os
import io
from db import AWSDB
from s3 import AWSS3
from common.models import (
    Account,
    Portfolio,
    PortfolioHolding,
    Factor
)
import bcrypt
import uuid
from typing import Optional
import pandas as pd
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
        db.cursor.execute(
            "SELECT portfolio_id FROM user_management.user_portfolios WHERE user_id = %s",
            (user_id,)
        )
        portfolio_ids = db.cursor.fetchall()
        
        # Extract portfolio IDs from tuples and include demo portfolio
        if portfolio_ids:
            portfolio_id_list = [id[0] for id in portfolio_ids]
        else:
            portfolio_id_list = []
        portfolio_id_list.append(DEMO_PORTFOLIO_ID)
        
        # Create the parameterized query
        placeholders = ','.join(['%s'] * len(portfolio_id_list))
        query = f"SELECT * FROM user_management.portfolios WHERE portfolio_id IN ({placeholders})"
        
        # Execute query with portfolio IDs as parameters
        db.cursor.execute(query, tuple(portfolio_id_list))
        
        result = db.cursor.fetchall()
        
        # Convert result to list of Portfolio objects
        column_names = [desc[0] for desc in db.cursor.description]
        portfolios = [
            Portfolio(**dict(zip(column_names, row))) 
            for row in result
        ]
        
        return portfolios
        
    except Exception as e:
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

# TODO: get a list of available factors
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

if __name__ == "__main__":
    try:
        test_db_connection()
        test_s3_connection()
    except Exception as e:
        print(f"[ ERROR | BACKEND ] Failed to connect to database or S3: {str(e)}")
        exit(1)
    print("[ INFO | BACKEND ] Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)
