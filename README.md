# labfolio
Open-sourced portfolio analysis stack. Running on [AWS](http://52.207.247.226:8501/)

**Overview of the labfolio pipeline**

*Pipeline*

Labfolio is a streamlit dashboard that allows users to analyze their own personal equity portfolios using custom-build factor models. The dashboard communicates with a REST API, which in turn communicates with a PostgreSQL database and AWS S3. Equity returns data is obtained ad hoc (upon a user's request) using the `yfinance` library. Redundant data is stored in the database and regularly updated with a lambda function.

*AWS Technologies*

| AWS Service | Purpose |
|------------|----------|
| EC2 | Hosts this project's API and dashboard |
| RDS (PostgreSQL) | Stores factor data, user accounts, portfolio metadata, and factor returns in a relational database (see database design below) |
| S3 | Stores user-uploaded portfolio files |
| Lambda | Runs automated jobs to update factor return data in the database |
| ECR | Stores the lambda function's Docker image |
| EventBridge | Schedules the lambda function to update factor return data in the database |

*Goals*

Labfolio's main goal is to provide user-friendly and free access to expensive and complex portfolio analysis tools. Labfolio currently allows users to do the following:

- Upload and store their own portfolios in an easy and secure manner
- Build their own custom factor models using data that labfolio stores on the backend
- Run complex factor model analysis on their personal portfolios
- Visualize the most crucial and informative metrics of these analyses in a user-friendly manner

*Data*

Factor modeling requires granular return data for each factor and stock in the model. Because factor returns are redundant across analyses (irrespective of the portfolio being analyzed), we can store the data in a database and update it with a lambda function. This saves a great deal of time for users.

The database stores data about the following:
- Factors: factor names, descriptions, and categories
- Returns: factor returns for each date
- Portfolios: portfolio names and S3 addresses
- Holdings: portfolio holdings (ticker, quantity)
- User Accounts: user credentials and portfolio ownership

Labfolio also permits users to upload their own portfolios, which are stored in AWS S3.

# quickstart

First, you will need to configure your environment variables. Create a `.env` file in the root directory and populate it with the following:

```
# API CONFIGURATION

API_URL=http://api:8000

# RDS CREDENTIALS

RDS_HOST=
RDS_NAME=
RDS_USER=
RDS_PASSWORD=

# S3 CREDENTIALS

S3_BUCKET=
S3_KEY=
S3_SECRET=
```

This project uses [Docker](https://www.docker.com/) to containerize the API and dashboard. To run the project, you will need to have Docker installed. To build and run the labfolio stack, run the following command in the root directory:

```bash
docker compose up --build
```

A streamlit dashboard will automatically begin running, which you can access at `http://localhost:8501`.

# architecture

```mermaid
graph TB
    subgraph AWS Cloud
        EC2[EC2 Instance]
        RDS[(PostgreSQL RDS)]
        S3[(S3 Bucket)]
        Lambda[Lambda Function]
        ECR[(ECR Registry)]
        EventBridge[EventBridge]
    end

    subgraph EC2 Instance
        API[FastAPI Backend]
        Dashboard[Streamlit Dashboard]
    end

    subgraph Client
        Browser[Web Browser]
    end

    %% Client interactions
    Browser -->|HTTP/8501| Dashboard
    Dashboard -->|HTTP/8000| API

    %% API interactions
    API -->|Query Data| RDS
    API -->|Store/Fetch Files| S3
    API -->|Fetch Stock Data| YFinance[Yahoo Finance API]

    %% Lambda update flow
    EventBridge -->|Schedule Trigger| Lambda
    Lambda -->|Update Factor Returns| RDS
    Lambda -->|Pull Image| ECR

    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:white
    classDef service fill:#3F8624,stroke:#232F3E,stroke-width:2px,color:white
    classDef external fill:#666666,stroke:#232F3E,stroke-width:2px,color:white

    class RDS,S3,Lambda,ECR,EventBridge aws
    class API,Dashboard service
    class YFinance external
```

# project structure

Project subdirectories are as follows:

| Directory | Description |
|-----------|-------------|
| `api`     | REST API built with [FastAPI](https://fastapi.tiangolo.com/), serves the `dashboard` |
| `dashboard`      | Dashboard built with [Streamlit](https://streamlit.io/), consumes the `api` |
| `lambda`  | Lambda functions for updating factor returns |
| `common`  | Shared code between `api` and `dashboard` |

## `api`

The API is built with FastAPI and serves as the backend for the dashboard. Here's what each file does:

| File | Description |
|------|-------------|
| `api.py` | This provides all endpoints that the dashboard will call for data / analysis / etc. |
| `db.py` | Database connection and query management for PostgreSQL. Provides the `AWSDB` class for database operations. |
| `mdp.py` | Market Data Platform (MDP) implementations. Currently I have a (`DatabaseMDP`) and Yahoo Finance (`YahooFinanceMDP`). |
| `s3.py` | AWS S3 operations wrapper. Provides the `AWSS3` class with methods for file upload/download, CSV handling, and bucket management. |
| `requirements.txt` | This gets installed in the Docker container. |
| `Dockerfile` | Container configuration for the API service, using Python 3.11 slim base image. |

The API service runs on port 8000 and communicates with AWS RDS (PostgreSQL) for data persistence and AWS S3 for file storage. It implements RESTful endpoints for portfolio management, factor analysis, and user authentication.

## `dashboard`

The dashboard is built with Streamlit and provides an interactive interface for portfolio analysis. Here's what each file does:

| File | Description |
|------|-------------|
| `dashboard.py` | Main Streamlit application with three primary tabs: Portfolio Analysis, My Portfolios, and Factor Library. Handles user authentication, portfolio management, and factor analysis visualization. |
| `requirements.txt` | Python package dependencies including Streamlit, Pandas, Seaborn, and other visualization libraries. |
| `Dockerfile` | Container configuration for the dashboard service, using Python base image and exposing port 8501. |

The dashboard runs on port 8501 and communicates with the API service for all data operations. It features:

- **Portfolio Analysis Tab**: Select factors and analyze portfolio holdings using factor models
- **My Portfolios Tab**: Upload, view, and manage portfolio holdings
- **Factor Library Tab**: Browse available factors and their descriptions

## `lambda`

The dashboard functionality relies on up-to-date factor return data, but factor returns are constantly changing. Lambda is used in labfolio for one purpose: to update the returns for the factors (daily). Here are the short details:

| File | Description |
|-----------|-------------|
| `app.py`     | Lambda function for updating factor returns |
| `Dockerfile`  | Docker image definition for the Lambda function. This is stored in Amazon ECR |
| `update_image.sh`  | Script for updating the Lambda image in Amazon ECR |
| `requirements.txt`  | Python dependencies for the Lambda function |
| `labfolio-factors-daily-update.yaml`  | AWS SAM template for the Lambda function. You should be able to replicate the function by importing this template file. Be sure to update the placeholder values. |

Lambda is appropriate for this task because this level of sophistication for factor modeling does not require granularity of return data updates greater than daily. It also allows us to easily write a lightweight python script, host it on AWS, and maintain a simple schedule so the database stays up-to-date. 

My implementation is relatively memory-efficient, enforcing garbage collection between dataset uploads. Max memory usage is 80MB per run. *Improvements can undoubtedly be made here.*

The lambda function is scheduled with an EventBridge rule `rate(1 day)`.

You can see detailed instructions for updating the Lambda image in the [appendix](#appendix).

## `common`

The common directory contains shared code between the API and dashboard services. Here's what each file does:

| File | Description |
|------|-------------|
| `models.py` | Pydantic models for data validation and serialization. Used by both the API and dashboard for consistent data structures. |

The models defined in `models.py` are:

```python
class FactorCategory(str, enum.Enum):  # str so that its serializable
    COUNTRY = "Country"
    SECTOR = "Sector"
    STYLE = "Style"

class Account(BaseModel):
    user_id: Optional[str] = Field(None, min_length=1)  # uuid, can be generated by the database
    username: str = Field(..., min_length=1)  # must be non-empty
    password_hash: str = Field(..., min_length=1)  # must be non-empty
    created_at: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)

class Portfolio(BaseModel):
    portfolio_id: Optional[str] = Field(None, min_length=1)  # uuid, can be generated by the database
    portfolio_name: str = Field(..., min_length=1)  # the name the user gives for the portfolio, required
    portfolio_address: str = Field(None, min_length=1)  # the address of the portfolio on AWS S3
    created_at: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)

class PortfolioHolding(BaseModel):
    portfolio_id: Optional[str] = Field(None, min_length=1)
    yf_ticker: str = Field(..., min_length=1)
    quantity: int = Field(...)

class Factor(BaseModel):
    factor_id: Optional[str] = Field(None, min_length=1)  # uuid, can be generated by the database
    factor_name: str = Field(..., min_length=1)  # the name the user gives for the factor, required
    factor_description: str = Field(None, min_length=1)  # the description of the factor, optional
    factor_category: Union[FactorCategory, str] = Field(None, min_length=1)  # the category of the factor, optional
    created_at: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)
    last_updated: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)
```

# database schema

*Using [PostgreSQL](https://www.postgresql.org/) via [AWS RDS](https://aws.amazon.com/rds/).*

```mermaid
erDiagram
    accounts ||--o{ user_portfolios : has
    portfolios ||--o{ user_portfolios : belongs_to
    factors ||--|{ returns : has

    accounts {
        uuid user_id PK
        varchar username
        varchar password_hash
        timestamp created_at
    }

    portfolios {
        uuid portfolio_id PK
        varchar portfolio_name
        varchar portfolio_address
        timestamp created_at
    }

    user_portfolios {
        uuid user_id PK,FK
        uuid portfolio_id PK,FK
        timestamp created_at
    }

    factors {
        varchar factor_id PK
        varchar factor_name
        text factor_description
        varchar factor_category
        timestamp created_at
        timestamp last_updated
    }

    returns {
        varchar factor_id PK,FK
        date date PK
        decimal return_value
    }
```

You can also find the entire database schema written as SQL commands in the [appendix](#appendix).


# acknowledgements

| Resource | Thanks |
|------|---------|
| [streamlit](https://streamlit.io/) | For allowing me to make a frontend |
| [giuseppe paleologo](https://linktr.ee/paleologo) | For inspiring this project |
| [yfinance](https://pypi.org/project/yfinance/) | For generously providing free financial data |
| [cursor-ai](https://www.cursor.ai/) | For making coding easier and more efficient |
| [claude-3.5](https://www.anthropic.com/chat) | *used with cursor* |

# appendix

## Update Lambda Image Script

The `update_image.sh` script automates the process of building and deploying Docker images to Amazon ECR (Elastic Container Registry) for use with AWS Lambda.

Prerequisites:

- AWS CLI configured with appropriate credentials
- Docker installed and running
- `AWS_ACCOUNT_ID` environment variable set
- region is set to `us-east-1` (you can change this in the script if you need to)

Usage:

```bash
./update_image.sh <image_name> <repository_name>
```

Parameters:

- `image_name`: The name to give the local Docker image, I use `labfolio-factors-daily-update`
- `repository_name`: The name of your ECR repository, I use `labfolio`

What it does:

1. Validates that `AWS_ACCOUNT_ID` is set
2. Builds a Docker image compatible with AWS Lambda (linux/amd64)
3. Authenticates with Amazon ECR
4. Tags the local image for ECR
5. Pushes the image to your ECR repository

Example:

```bash
./update_image.sh labfolio-factors-daily-update labfolio
```

## Database Schema SQL

Below is the entire database schema for the project. You can replicate the entire backend database by running the following SQL commands.

```sql
-- schema for user management
CREATE SCHEMA IF NOT EXISTS user_management;

-- accounts table
CREATE TABLE user_management.accounts (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,  -- store ppls passwords as hash
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- portfolios table
CREATE TABLE user_management.portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_name VARCHAR(255) NOT NULL,
    portfolio_address VARCHAR(512),  -- S3 address
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- user-portfolio mapping table
CREATE TABLE user_management.user_portfolios (
    user_id UUID REFERENCES user_management.accounts(user_id) ON DELETE CASCADE,
    portfolio_id UUID REFERENCES user_management.portfolios(portfolio_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, portfolio_id)
);

-- indexes
CREATE INDEX idx_accounts_username ON user_management.accounts(username);
CREATE INDEX idx_portfolios_name ON user_management.portfolios(portfolio_name);

-- schema for factor management
CREATE SCHEMA IF NOT EXISTS factor;

-- factors table
CREATE TABLE factor.factors (
    factor_id VARCHAR(50) PRIMARY KEY NOT NULL UNIQUE, -- e.g., 'MKT'
    factor_name VARCHAR(255) NOT NULL, -- e.g., 'Market'
    factor_description TEXT,
    factor_category VARCHAR(100),  -- e.g., 'Style, Country'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- factor returns table (enhanced version of your factor.returns)
CREATE TABLE factor.returns (
    factor_id VARCHAR(50) REFERENCES factor.factors(factor_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    return_value DECIMAL(10,6) NOT NULL,  -- 6 decimal precision for returns
    PRIMARY KEY (factor_id, date)
);

-- indexes
CREATE INDEX idx_factor_returns_date ON factor.returns(date);
CREATE INDEX idx_factors_id ON factor.factors(factor_id);
```
