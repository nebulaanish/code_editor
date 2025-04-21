### Locally through venv
To set up and run the application locally using a virtual environment, follow these steps:

1. **Create and activate a virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

2. **Install the required dependencies:**

```bash
pip install -r requirements.txt
```

3. **Create the database:**

Ensure PostgreSQL is running and create a new database:

```bash
createdb your_database_name
```

4. **Apply database migrations:**

```bash
alembic upgrade head
```

Now, you can run the application:

```bash
# Before running the application, ensure the .env file is created and updated by referring to the description in .env.example

# Create and update the .env file
cp .env.example .env
# Open .env file and update the necessary configurations

uvicorn app.main:app --reload
```

### Using Docker

To run this application using Docker Compose, use the following command:

```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate

```


## Migrations
All database migrations related to this project are located at `migrations/versions/`. The setup is located at `env.py`. Refer to the commands below when making any changes to the database schema to ensure they reflect correctly.

1.  When creating a new table, make sure to import this table in `env.py`, similar to how the `Transcripts` model is imported.
    
2.  Creating a new migration:
    

```bash
alembic revision --autogenerate -m "Describe the change here"

```

3.  Applying migration:

```bash
alembic upgrade head

```

4.  Rolling back migrations:

```bash
alembic downgrade -1

```

or

```bash
alembic downgrade <migration_id>

```
