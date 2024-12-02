# labfolio
Open-sourced portfolio analysis stack

# quickstart


# architecture

![architecture](./labfolio-architecture.png)


# project structure

Project subdirectories are as follows:

| Directory | Description |
|-----------|-------------|
| `api`     | REST API built with [FastAPI](https://fastapi.tiangolo.com/), serves the `dashboard` |
| `dashboard`      | Dashboard built with [Streamlit](https://streamlit.io/), consumes the `api` |
| `common`  | Shared code between `api` and `dashboard` |

## `api`



## `dashboard`



## `common`


# database schema

*Using [MySQL](https://www.mysql.com/) via [AWS RDS](https://aws.amazon.com/rds/).*

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
        varchar source
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
| [giuseppe paleologo](https://linktr.ee/paleologo) | For inspiring this project |
| [yfinance](https://pypi.org/project/yfinance/) | For generously providing free financial data |
| [cursor-ai](https://www.cursor.ai/) | For making coding easier and more efficient |
| [claude-3.5](https://www.anthropic.com/chat) | *used with cursor* |

# appendix

## Database Schema SQL

Below is the entire database schema for the project. You can replicate the entire backend database by running the following SQL commands.

```sql
-- schema for user management
CREATE SCHEMA IF NOT EXISTS user;

-- accounts table
CREATE TABLE user.accounts (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,  -- store ppls passwords as hash
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- portfolios table
CREATE TABLE user.portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_name VARCHAR(255) NOT NULL,
    portfolio_address VARCHAR(512),  -- S3 address
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- user-portfolio mapping table
CREATE TABLE user.user_portfolios (
    user_id UUID REFERENCES user.accounts(user_id) ON DELETE CASCADE,
    portfolio_id UUID REFERENCES user.portfolios(portfolio_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, portfolio_id)
);

-- indexes
CREATE INDEX idx_accounts_username ON user.accounts(username);
CREATE INDEX idx_portfolios_name ON user.portfolios(portfolio_name);

-- schema for factor management
CREATE SCHEMA IF NOT EXISTS factor;

-- factors table
CREATE TABLE factor.factors (
    factor_id VARCHAR(50) PRIMARY KEY NOT NULL UNIQUE, -- e.g., 'MKT'
    factor_name VARCHAR(255) NOT NULL, -- e.g., 'Market'
    factor_description TEXT,
    source VARCHAR(100),  -- e.g., 'French Data Library'
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