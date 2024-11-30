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

- TODO: database schema diagram
- TODO: post database tables here

# acknowledgements

| Resource | Thanks |
|------|---------|
| [yfinance](https://pypi.org/project/yfinance/) | For generously providing free financial data |
| [cursor-ai](https://www.cursor.ai/) | For making coding easier and more efficient |
| [claude-3.5](https://www.anthropic.com/chat) | *with cursor* |