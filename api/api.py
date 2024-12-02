from fastapi import FastAPI
import uvicorn
import os
from db import AWSDB

app = FastAPI(title="labfolio-api")

######################
### HELPER METHODS ###
######################

def test_db_connection() -> None:
    """Runs a test to ensure we can connect to the database"""
    db = AWSDB(username=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), host=os.getenv('DB_HOST'), database_name=os.getenv('DB_NAME'))
    db.cursor.execute("SELECT 1")
    result = db.cursor.fetchone()
    del db
    if result:
        print('[ INFO | BACKEND ] Database connection successful')
    else:
        raise Exception('[ ERROR | BACKEND ] Database connection failed')

# TODO: validate a portfolio

####################
### GET REQUESTS ###
####################

@app.get("/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "pong"}

# TODO: get a user's portfolios

# TODO: get a list of available factors

#####################
### POST REQUESTS ###
#####################

# TODO: create account

# TODO: login

# TODO: validate a portfolio

# TODO: upload a portfolio

if __name__ == "__main__":
    test_db_connection()
    uvicorn.run(app, host="0.0.0.0", port=8000)