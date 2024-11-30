from fastapi import FastAPI
import uvicorn

app = FastAPI(title="labfolio-api")

######################
### HELPER METHODS ###
######################

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

    uvicorn.run(app, host="0.0.0.0", port=8000)