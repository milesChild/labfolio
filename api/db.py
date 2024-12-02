# imports
import psycopg2
import pandas as pd
from typing import Optional

class AWSDB():
    """
    Lightweight class for interacting with an AWS MySQL database.
    """

    def __init__(self, username: str, password: str, host: str, database_name: str, auto_commit: Optional[bool] = True, database_port: Optional[int] = 5432) -> None:
        """
        Initializes a connection to the specified AWS PostreSQL database.
        :param username: username for the database
        :param password: password for the database
        :param host: host for the database
        :param database_name: name of the database
        :param auto_commit: whether to automatically commit changes to the database
        :param database_port: port for the database
        """

        self.connection = psycopg2.connect(
            host=host,
            database=database_name,
            user=username,
            password=password,
            port=str(database_port)
        )
        self.cursor = self.connection.cursor()
        self.connection.autocommit = auto_commit
        print(f'Connected to database: {database_name}')
        self.__test_connection()
        
    def __test_connection(self) -> None:
        """
        Tests the connection to the database
        """
        self.execute('SELECT version();')
        version = self.fetch()
        print(f'Test Passed: {version}')

    def __del__(self) -> None:
        """
        Closes the database connection
        """
        self.connection.close()

    def execute(self, query: str, *params) -> None:
        """
        Executes a query with optional parameters
        :param query: the query to execute
        :param params: optional parameters for the query
        """
        query = self._cleaned_statement(query)
        if params:
            try:
                self.cursor.execute(query, params)
            except:
                self.connection.rollback()
                raise Exception(f'Error executing query: {query} with params: {params}')
        else:
            try:
                self.cursor.execute(query)
            except:
                self.connection.rollback()
                raise Exception(f'Error executing query: {query}')

    def execute_many(self, queries: list, batch_size: Optional[int] = 100) -> None:
        """
        Executes a list of queries with optional parameters
        :param queries: the queries to execute
        :param batch_size: the size of the batch to execute
        """
        
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            batch = [self._cleaned_statement(x) for x in batch]
            batch_sql = '\n'.join(batch)
            self.execute(batch_sql)
            
    def fetch(self) -> list:
        """
        Fetches the results of a query
        :return: the results of the query
        """
        return self.cursor.fetchall()
    
    def commit(self) -> None:
        """
        Commits changes to the database
        """
        self.connection.commit()

    def fetch_df(self) -> pd.DataFrame:
        """
        Fetches the results of a query
        :return: the results of the query
        """

        col_headers = [x[0] for x in self.cursor.description]
        json_data = []
        the_data = self.cursor.fetchall()
        for row in the_data:
            json_data.append(dict(zip(col_headers, row)))
        df = pd.DataFrame(json_data)
        return df
    
    def _cleaned_statement(self, statement: str) -> str:
        """
        Cleans a statement by removing leading and trailing whitespace and semicolons
        :param statement: the statement to clean
        :return: the cleaned statement
        """
        statement = statement.strip().rstrip(';')
        if not statement.endswith(';'):
            statement = statement + ';'

        return statement