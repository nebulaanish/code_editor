# Python Code Editor

A web-based Python code editor with real-time execution capabilities, built with Next.js and FastAPI.

## Features

- Real-time code editing with Monaco Editor
- Python code execution with secure sandboxing using nsjail
  - Each user's code runs in an isolated environment
  - Prevents interference between different users' code
  - Ensures system security and resource isolation
- Syntax highlighting and code suggestions
- Auto-indentation and bracket matching
- Terminal output display
- Docker support for easy deployment

## Limitations

- **Resource Constraints**: The sandbox environment has limited resources (CPU, memory) to prevent abuse
- **System Access**: Restricted access to system files and network to maintain security

## Quick Start with Docker Compose

The easiest way to run the application is using Docker Compose:

1. Clone the repository:
```bash
git clone <repository-url>
cd code_editor
```

2. Set up environment variables:
```bash
# For backend
cp backend/.env.example backend/.env
# For frontend
cp frontend/.env.example frontend/.env
```

3. Edit the `.env` files with your desired values:
- Backend: Configure sandbox settings and server parameters
- Frontend: Set the API URL and other frontend-specific variables

4. Build and start the services:
```bash
docker compose up --build
```

5. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

6. To stop the services:
```bash
docker compose down
```

## Manual Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your desired values
```

3. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Start the backend server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at http://localhost:8000

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your desired values
```

3. Install dependencies:
```bash
npm install
```

4. Start the development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:3000

## Development

### Backend Development

- The backend is built with FastAPI
- Main application file: `backend/main.py`
- API routes are defined in `backend/src/app.py`
- Environment variables can be set in `.env` file

### Frontend Development

- The frontend is built with Next.js
- Main components are in `frontend/components/`
- Pages are in `frontend/app/`
- Styling uses Tailwind CSS

