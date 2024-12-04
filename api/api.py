from fastapi import FastAPI, HTTPException
import uvicorn
import os
from db import AWSDB
from s3 import AWSS3
from common.models import Account
import bcrypt
import uuid
from typing import Optional
app = FastAPI(title="labfolio-api")

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

####################
### GET REQUESTS ###
####################

@app.get("/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "pong"}

# TODO: get a user's portfolios
@app.get("/portfolios")
async def get_user_portfolios(user_id: Optional[str], username: Optional[str]):
    """Gets a user's portfolios"""
    if user_id is None and username is None:
        raise HTTPException(status_code=400, detail="Either user_id or username must be provided.")
    pass

# TODO: get a specific portfolio
@app.get("/portfolio")
async def get_portfolio(portfolio_id: str):
    """Gets a specific portfolio"""
    pass




# TODO: get a list of available factors
@app.get("/factors")
async def get_factors():
    """Gets a list of available factors"""
    pass

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
    db = AWSDB(
        username=os.getenv('RDS_USER'),
        password=os.getenv('RDS_PASSWORD'),
        host=os.getenv('RDS_HOST'),
        database_name=os.getenv('RDS_NAME')
    )
    
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
    db = AWSDB(
        username=os.getenv('RDS_USER'),
        password=os.getenv('RDS_PASSWORD'),
        host=os.getenv('RDS_HOST'),
        database_name=os.getenv('RDS_NAME')
    )
    
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

# TODO: validate a portfolio

# TODO: upload a portfolio

if __name__ == "__main__":
    try:
        test_db_connection()
        test_s3_connection()
    except Exception as e:
        print(f"[ ERROR | BACKEND ] Failed to connect to database or S3: {str(e)}")
        exit(1)
    print("[ INFO | BACKEND ] Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)
