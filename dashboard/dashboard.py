import streamlit as st
import requests
import json
from typing import Optional
import os
import io
from common.models import Portfolio, PortfolioHolding, Factor
from pydantic import ValidationError, fields
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

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
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'is_create_account' not in st.session_state:
    st.session_state.is_create_account = False
if 'selected_portfolio_id' not in st.session_state:
    st.session_state.selected_portfolio_id = None
if 'portfolios_table' not in st.session_state:
    st.session_state.portfolios_table = None
if 'factor_selection' not in st.session_state:
    st.session_state.factor_selection = None
if 'analysis_running' not in st.session_state:
    st.session_state.analysis_running = False
if 'selected_factors' not in st.session_state:
    st.session_state.selected_factors = []
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

##############################
### BACKEND HELPER METHODS ###
##############################

####################
### GET REQUESTS ###
####################

def get_user_portfolios() -> list[Portfolio]:
    """
    Get all portfolios for the current user
    Returns a list of validated Portfolio objects
    """
    try:
        # Verify user is authenticated and we have their user_id
        if not st.session_state.authenticated or not st.session_state.user_id:
            st.error("You must be logged in to view portfolios.")
            return []
            
        # Make the request to the API
        response = requests.get(
            f"{BACKEND_URL}/portfolios",
            params={"user_id": st.session_state.user_id},
            timeout=5
        )
        
        if response.status_code == 200:
            portfolios = []
            for portfolio_data in response.json():
                try:
                    # Ensure portfolio_id is converted to string
                    portfolio = Portfolio.model_validate(portfolio_data)
                    portfolios.append(portfolio)
                except ValidationError as e:
                    st.error(f"Invalid portfolio data received: {str(e)}")
            return portfolios
        else:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Failed to fetch portfolios: {error_detail}")
            return []
            
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please try again later.")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

# TODO: Implement get_portfolio
def get_portfolio_holdings(portfolio_id: str) -> list[PortfolioHolding]:
    """Method to get a single portfolio by its ID from the backend."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/portfolio/holdings",
            params={"portfolio_id": portfolio_id},
            timeout=5
        )
        if response.status_code == 200:
            holdings = []
            for holding_data in response.json():
                try:
                    holding = PortfolioHolding.model_validate(holding_data)
                    holdings.append(holding)
                except ValidationError as e:
                    st.error(f"Invalid holding data received: {str(e)}")
            return holdings
        else:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Failed to fetch holdings: {error_detail}")
            return []
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please try again later.")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

def get_factors() -> list[Factor]:
    try:
        response = requests.get(
            f"{BACKEND_URL}/factors",
            params={"user_id": st.session_state.user_id},
            timeout=5
        )
        if response.status_code == 200:
            factors = []
            for factor_data in response.json():
                try:
                    factor = Factor.model_validate(factor_data)
                    factors.append(factor)
                except ValidationError as e:
                    st.error(f"Invalid factor data received: {str(e)}")
            return factors
        else:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Failed to fetch factors: {error_detail}")
            return []
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please try again later.")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

def validate_factor_model():
    """
    Validates the factor model using selected factors and holdings from session state
    """
    try:
        # First check if we have a selected portfolio
        if not st.session_state.selected_portfolio_id:
            st.warning("Please select a portfolio first")
            return
            
        # Get selected factors and holdings from session state
        factors = st.session_state.get('selected_factors', [])
        if not factors:
            st.warning("Please select at least one factor")
            return
            
        # Now get holdings since we know we have a portfolio_id
        holdings = get_portfolio_holdings(st.session_state.selected_portfolio_id)
        if not holdings:
            st.warning("Selected portfolio has no holdings")
            return
            
        # Convert holdings to expected format
        portfolio_holdings = [
            {
                "portfolio_id": st.session_state.selected_portfolio_id,
                "yf_ticker": h.yf_ticker,
                "quantity": h.quantity
            }
            for h in holdings
        ]
        
        # Make POST request to API endpoint
        response = requests.post(
            f"{BACKEND_URL}/analysis/validate_factor_model",
            json={
                "factors": factors,
                "holdings": portfolio_holdings
            },
            timeout=5
        )
            
        if response.status_code == 200:
            if response.json():
                st.success("Factor model is valid!")
            else:
                st.warning("Factor model is not valid.")
        else:
            st.error(f"Error validating factor model: {response.text}")
            
    except Exception as e:
        st.error(f"Error validating factor model: {str(e)}")

def run_factor_analysis() -> None:
    """
    Runs a factor analysis using selected factors and holdings from session state
    """
    try:
        # First check if we have a selected portfolio
        if not st.session_state.selected_portfolio_id:
            st.warning("Please select a portfolio first")
            return
            
        # Get selected factors and holdings from session state
        factors = st.session_state.get('selected_factors', [])
        if not factors:
            st.warning("Please select at least one factor")
            return
            
        # Now get holdings since we know we have a portfolio_id
        holdings = get_portfolio_holdings(st.session_state.selected_portfolio_id)
        if not holdings:
            st.warning("Selected portfolio has no holdings")
            return
            
        # Convert holdings to expected format
        portfolio_holdings = [
            {
                "portfolio_id": st.session_state.selected_portfolio_id,
                "yf_ticker": h.yf_ticker,
                "quantity": h.quantity
            }
            for h in holdings
        ]
        
        # Set analysis running state
        st.session_state.analysis_running = True
        
        # Make POST request to API endpoint
        response = requests.post(
            f"{BACKEND_URL}/analysis/factor_model",
            json={
                "factors": factors,
                "holdings": portfolio_holdings
            },
            timeout=25
        )
            
        if response.status_code == 200:
            # Store analysis results in session state
            st.session_state.analysis_results = response.json()
            st.success("Factor analysis completed successfully!")
        else:
            st.error(f"Error running factor analysis: {response.text}")
            
    except Exception as e:
        st.error(f"Error running factor analysis: {str(e)}")
    finally:
        st.session_state.analysis_running = False


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
            response_data = response.json()
            st.session_state.authenticated = True
            st.session_state.username = response_data["username"]
            st.session_state.user_id = response_data["user_id"]
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
            response_data = response.json()
            st.session_state.authenticated = True
            st.session_state.username = response_data["username"]
            st.session_state.user_id = response_data["user_id"]
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

def upload_portfolio(file, portfolio_name: str) -> bool:
    """
    Uploads a portfolio file to the backend
    :param file: The CSV file to upload
    :param portfolio_name: Name for the portfolio
    :return: True if successful, False otherwise
    """
    try:
        # Verify user is authenticated and we have their user_id
        if not st.session_state.authenticated or not st.session_state.user_id:
            st.error("You must be logged in to upload a portfolio.")
            return False
            
        print(f"DEBUG: Starting upload for file {file.name}")
        print(f"DEBUG: Portfolio name: {portfolio_name}")
        print(f"DEBUG: User ID: {st.session_state.user_id}")
        
        # Seek to beginning of file
        file.seek(0)
        
        # Create BytesIO object from file
        file_bytes = io.BytesIO(file.read())
        file_bytes.seek(0)
        
        # Create the multipart form data
        files = {"file": (file.name, file_bytes, "text/csv")}
        params = {
            "portfolio_name": portfolio_name,
            "user_id": st.session_state.user_id
        }
        
        print("DEBUG: Sending request to API")
        # Make the request to the API
        response = requests.post(
            f"{BACKEND_URL}/portfolio",
            files=files,
            params=params,
            timeout=10
        )
        print(f"DEBUG: Received response with status code: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            st.success(f"Portfolio '{response_data['portfolio_name']}' uploaded successfully!")
            return True
        elif response.status_code == 400:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Invalid portfolio format: {error_detail}")
            return False
        else:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Failed to upload portfolio: {error_detail}")
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

def download_portfolio_template() -> None:
    """Downloads the template portfolio file from S3"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/download/portfolios/template_portfolio.csv",
            timeout=5,
            stream=True
        )
        
        if response.status_code == 200:
            # Trigger browser download
            st.download_button(
                label="Download Template Portfolio",
                data=response.content,
                file_name="template_portfolio.csv",
                mime="text/csv"
            )
        else:
            error_detail = response.json().get("detail", "Unknown error occurred")
            st.error(f"Failed to download template: {error_detail}")
            
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please try again later.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")

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
if not st.session_state.is_create_account:
    st.subheader(f"Welcome back, {st.session_state.username}.")
else:
    st.subheader(f"Welcome, {st.session_state.username}.")

tabs = st.tabs(["Portfolio Analysis", "My Portfolios", "Factor Library"])

# Portfolio Analysis tab
with tabs[0]:
    st.header("Portfolio Analysis")
    
    # First section - Factor Selection and Portfolio View
    col1, col2 = st.columns(2)
    
    # Left column - Factor Library
    with col1:
        st.subheader("Factor Library")
        factors = get_factors()
        if factors:
            # Convert factors to a more concise display format
            factor_data = [{
                "Factor ID": f.factor_id,
                "Factor Name": f.factor_name,
                "Category": f.factor_category
            } for f in factors]
            
            # Create DataFrame for better formatting
            factor_df = pd.DataFrame(factor_data)
            
            def handle_factor_selection():
                """Handle selection of factors in the dataframe"""
                table = st.session_state.factor_selection
                
                # Check if any rows are selected
                if not table['selection']['rows']:
                    st.session_state.selected_factors = []
                    return
                
                # Get selected row indices
                selected_indices = table['selection']['rows']
                
                # Convert indices to factor IDs instead of names
                selected_factors = factor_df.iloc[selected_indices]['Factor ID'].tolist()
                
                # Store selected factors
                st.session_state.selected_factors = selected_factors

            st.dataframe(
                factor_df,
                hide_index=True,
                use_container_width=True,
                selection_mode="multi-row",
                key="factor_selection",
                on_select=handle_factor_selection
            )
            
            # Add buttons in two columns for better layout
            button_col1, button_col2 = st.columns(2)
            with button_col1:
                st.button("Validate Factor Model", 
                         on_click=validate_factor_model,
                         use_container_width=True)
            with button_col2:
                st.button("Run Analysis", 
                         on_click=run_factor_analysis,
                         use_container_width=True)
    
    # Right column - Portfolio Holdings
    with col2:
        st.subheader("Portfolio Holdings")
        if st.session_state.selected_portfolio_id:
            holdings = get_portfolio_holdings(st.session_state.selected_portfolio_id)
            if holdings:
                holdings_data = [{"Ticker": h.yf_ticker, "Quantity": h.quantity} for h in holdings]
                st.dataframe(holdings_data, hide_index=True, use_container_width=True)
        else:
            st.info("Please select a portfolio from the 'My Portfolios' tab to view holdings.")
    
    # Add a divider before next sections
    st.divider()
    
    # actual analysis
    if st.session_state.analysis_results:
        st.subheader("Factor Model Analysis")
        
        # Display statistics
        stats = st.session_state.analysis_results['analysis']['statistics']

        # Display statistics as a table
        stats_df = pd.DataFrame({
            'Metric': ['Number of Factors', 'Number of Assets', 'Number of Observations', 'R-squared', 'J-statistic'],
            'Value': [
                stats['no_factors'],
                stats['no_assets'],
                stats['no_observations'],
                f"{stats['r_squared']:.4f}",
                f"{stats['j_statistic']:.4f}"
            ]
        })
        
        st.dataframe(
            stats_df,
            hide_index=True,
            use_container_width=True
        )

        # Portfolio Factor Exposures
        st.subheader("Portfolio Factor Exposures")
        st.write("""Factor exposures are the weights of each factor in the portfolio.
        These can help you understand how much risk each factor is contributing to your portfolio.""")

        n_assets = stats['no_assets']
        equal_weights = np.repeat(1/n_assets, n_assets)
        params = st.session_state.analysis_results['analysis']['params']
        params = pd.DataFrame.from_dict(params)
        betas = params.copy()
        if 'alpha' in betas.columns:
            portfolio_betas = betas.drop('alpha', axis=1).T @ equal_weights
        else:
            portfolio_betas = betas.T @ equal_weights

        fig, ax = plt.subplots()
        portfolio_betas.plot.barh(ax=ax)
        plt.title('Portfolio Factor Exposures')
        for i, v in enumerate(portfolio_betas):
            ax.text(v, i, f'{v:.2f}', color='black', va='center')
        plt.xlabel('Beta')
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.dataframe(portfolio_betas, use_container_width=True)

        # Factor Risk Premia Estimates
        st.subheader("Factor Risk Premia Estimates")
        st.write("""Factor risk premia are the expected returns of each factor.
        These can help you understand how much return each factor is contributing to your portfolio.""")

        risk_premia = st.session_state.analysis_results['analysis']['risk_premia']
        risk_premia = pd.DataFrame.from_dict(risk_premia, orient='index', columns=['Mean Annualized Return'])
        fig, ax = plt.subplots(figsize=(10, 8))
        risk_premia.sort_values(by='Mean Annualized Return', ascending=False).plot.barh(ax=ax)
        sns.despine()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.dataframe(risk_premia, hide_index=False, use_container_width=True)

        # Holdings Data
        st.subheader("Portfolio Holdings Data")
        st.write("""Granular data on the individual holdings from the portfolio factor analysis.""")

        st.markdown("### Individual Asset Factor Betas")
        # Plot the model betas
        fig, ax = plt.subplots(figsize=(10, 8))
        params.plot.barh(ax=ax)
        sns.despine()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.dataframe(params, hide_index=True, use_container_width=True)

        # Create covariance matrix heatmap
        st.markdown("### Factor Covariance Matrix")
        # Subtitle explaining what the covariance matrix is used for
        st.write("The covariance matrix can help in understanding how the factors are correlated with each other.")
        
        # Convert covariance dictionary to DataFrame
        cov_matrix = pd.DataFrame.from_dict(
            st.session_state.analysis_results['analysis']['covariance_matrix']
        )
        
        # Create the heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            cov_matrix,
            annot=False,
            cmap='coolwarm',
            center=0,
            fmt='.2e',
            ax=ax
        )
        plt.title('Factor Covariance Matrix')
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Display the plot
        st.pyplot(fig)
        
        # Clean up
        plt.close(fig)

# My Portfolios tab
with tabs[1]:
    st.header("My Portfolios")
    
    st.subheader("Upload a New Portfolio")
    
    # Upload form
    with st.form("upload_portfolio_form"):
        uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
        portfolio_name = st.text_input("Portfolio Name*", placeholder="Enter a name for your portfolio")
        submitted = st.form_submit_button("Upload Portfolio")
        
        if submitted:
            if not portfolio_name:
                st.error("Please enter a portfolio name.")
            elif not uploaded_file:
                st.error("Please select a CSV file.")
            else:
                if upload_portfolio(uploaded_file, portfolio_name):
                    st.rerun()
    
    # Place download button to the right of the form
    download_portfolio_template()
    
    # Display holdings if a portfolio is selected
    if st.session_state.selected_portfolio_id:
        st.divider()
        st.subheader("Selected Portfolio Holdings")
        
        # Add a button to clear selection
        if st.button("Clear Selection"):
            st.session_state.selected_portfolio_id = None
            st.rerun()
        
        # Get and display the holdings
        holdings = get_portfolio_holdings(st.session_state.selected_portfolio_id)
        if holdings:
            holdings_data = [{"Ticker": h.yf_ticker, "Quantity": h.quantity} for h in holdings]
            st.dataframe(holdings_data, hide_index=True, use_container_width=True)
        else:
            st.info("No holdings found for this portfolio.")

    # Table of existing portfolios
    st.subheader("Your Existing Portfolios")
    portfolios = get_user_portfolios()
    
    if portfolios:
        # Create a list of dictionaries with portfolio data
        portfolio_data = [{
            "Portfolio ID": p.portfolio_id,
            "Portfolio Name": p.portfolio_name,
            "Created At": p.created_at
        } for p in portfolios]
        
        # Create a DataFrame for better formatting
        portfolio_df = pd.DataFrame(portfolio_data)

        def handle_portfolio_selection():
            """Handle selection of portfolios in the dataframe"""
            table = st.session_state.portfolios_table
            
            # Check if any rows are selected
            if not table['selection']['rows']:
                # Clear the selection state
                st.session_state.selected_portfolio_id = None
                return
            
            # Process selection if a row is selected
            row_number = table['selection']['rows'][0]
            row = portfolio_df.iloc[row_number]
            st.session_state.selected_portfolio_id = row['Portfolio ID']

        # Display interactive dataframe with hidden Portfolio ID column
        selected_rows = st.dataframe(
            portfolio_df[["Portfolio Name", "Created At"]],  # Only show these columns
            hide_index=True,
            use_container_width=True,
            height=300,
            on_select=handle_portfolio_selection,
            selection_mode="single-row",
            key="portfolios_table"
        )
    else:
        st.info("You don't have any portfolios yet. Upload one using the form above.")

# Factor Library tab
with tabs[2]:
    st.header("Factor Library")
    st.subheader("Return Factors:")
    st.write("""
    Return factors are systematic drivers of investment returns that can help understand where your portfolio's risk and returns are "coming from".
    These factors can represent the return of a particular market/country, a particular sector, or a custom investment style (such as momentum investing or value investing).
    All factors quoted on labfolio source return data from publicly-traded, highly liquid ETFs. The implication is that factor quality is lower but hedging recommendations are actually implementable.
    Below is a list of all factors currently available for portfolio analysis on labfolio.
    """)
    factors = get_factors()
    if factors:
        # Convert factors to a list of dictionaries, excluding created_at
        factor_data = []
        for factor in factors:
            factor_dict = {
                "Factor ID": factor.factor_id,
                "Factor Name": factor.factor_name,
                "Description": factor.factor_description,
                "Category": factor.factor_category,
                "Last Updated": factor.last_updated
            }
            factor_data.append(factor_dict)
        # Display the scrollable table without index and full width
        st.dataframe(factor_data, hide_index=True, use_container_width=True)
    else:
        st.info("No factors found in the library.")