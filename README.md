# Health Care Assistant — Overview
## Description

Health Care Assistant is an application designed to help users manage information about medications, ask questions about their use, and receive AI-based guidance. The system allows uploading drug data, conducting multiple chat sessions, and evaluating the quality and accuracy of AI responses.

## Key Functionalities

Drug Upload:

- Upload single or multiple drug records (PDF).

- Each record includes detailed description about drug.

- Automatic extraction of metadata from uploaded documents.

Q&A and Advice:

- Interactive chat interface for users to ask questions about medications or combinations of drugs.

- The assistant provides context-aware answers (based on uploaded drug data or user-defined context).

- Maintains chat history per conversation.

Multiple Chats:

- Ability to create and manage multiple chat sessions.

- Each chat can have its own context (e.g., personal use, family member therapy, or professional discussion).

- Search and archive chat history.

Response Evaluation:

- After each AI response, users can provide excpected answer and validate model answer.

- Ratings are used to measure model accuracy and user satisfaction.

## Running the Application

### 1. Prerequisites

- Docker must be installed and running.

- Node.js and npm must be installed for the frontend.

- Python 3.10+ and pip must be installed for the backend.

### 2. Start the Document Processing Server

Run the following commands to pull and start the nlm-ingestor Docker image (used for document processing):
```
docker pull ghcr.io/nlmatics/nlm-ingestor:latest
docker run -p 5010:5001 ghcr.io/nlmatics/nlm-ingestor:latest-<version>
```
###  3. Configure Environment Variables

In the backend folder, create a .env file and define:

```
DB_PATH=
CHROMA_DB_PATH=
STORAGE_CONTEXT_PATH=
FOLDER_PATH=
EMBEDDING_MODEL_NAME_OPENAI=
LLM_MODEL_NAME_OPENAI=
EVALUATE_MODEL_NAME_OPENAI=
VITE_BACKEND_UR=
LLMSHERPA_API_URL=
API_KEY=
PROMPT=
```

You can specify different models depending on your setup.

### 4. Install Dependencies

Install required Python libraries for the backend:
```
pip install -r requirements.txt
```

Also install React and dependencies for the frontend:
```
cd frontend
npm install
```
### 5. Run Backend and Frontend

Start the backend server from the backend folder:
```
hypercorn api:app --reload --bind 0.0.0.0:5000
```

Start the frontend from the frontend folder:
```
npm run dev
```

Once both are running, the application will be available locally (typically on port 5173 for frontend and 5000 for backend).
