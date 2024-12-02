import streamlit as st
import requests
import json
from typing import Optional
import os

# Backend URL from environment variable with fallback
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:8000")

# Configure page settings
st.set_page_config(page_title="labfolio", layout="wide")

#####################
### SESSION STATE ###
#####################

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_create_account' not in st.session_state:
    st.session_state.is_create_account = False

##############################
### BACKEND HELPER METHODS ###
##############################

####################
### GET REQUESTS ###
####################

#####################
### POST REQUESTS ###
#####################

def login(username: str, password: str) -> bool:
    """Attempt to login user via API"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/login",
            params={"username": username, "password": password},
            timeout=5
        )
        if response.status_code == 200:
            st.session_state.authenticated = True
            st.session_state.username = username
            return True
        elif response.status_code == 401:
            st.error("Invalid username or password.")
            return False
        else:
            st.error(f"Login failed with error: {response.text}")
            return False
    except Exception as e:
        st.error(f"Login failed with error: {str(e)}")
        return False

def create_account(username: str, password: str) -> bool:
    """Attempt to create a new user account via API"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/account",
            params={"username": username, "password": password},
            timeout=5
        )

        if response.status_code == 200:  # Created successfully
            st.session_state.authenticated = True
            st.session_state.username = username
            return True
        elif response.status_code == 400:  # Username already exists
            st.error("Username already exists. Please choose a different username.")
            return False
        else:  # Other errors (500, etc)
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Account creation failed: {error_detail}")
            return False
            
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please try again later.")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return False

#########################
### UI HELPER METHODS ###
#########################

def check_auth() -> bool:
    """Check if the user is authenticated"""
    return st.session_state.authenticated

def toggle_create_account():
    st.session_state.is_create_account = not st.session_state.is_create_account

###########################
### AUTHENTICATION FORM ###
###########################

# Authentication form
if not check_auth():
    st.title("Welcome to labfolio")
    
    # Button to switch between modes
    if st.session_state.is_create_account:
        st.button("Back to Login", on_click=toggle_create_account)
        st.header("Create New Account")
    else:
        st.button("Create New Account", on_click=toggle_create_account)
        st.header("Login")
    
    with st.form("auth_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.session_state.is_create_account:
            submitted = st.form_submit_button("Create Account")
            if submitted:
                result = create_account(username, password)
                if result:
                    st.success("Account created successfully!")
                    st.rerun()
        else:
            submitted = st.form_submit_button("Login")
            if submitted:
                result = login(username, password)
                if result:
                    st.success("Logged in successfully!")
                    st.rerun()
    st.stop()

####################
### STREAMLIT UI ###
####################

# Landing Page
st.title("labfolio")
st.subheader(f"Welcome, {st.session_state.username}")