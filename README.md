## Key Features

### Generative AI with Groq
HelpdeskAI utilizes Groq, a high-performance AI platform, to power its generative AI capabilities. This enables the system to:
- Generate concise, context-aware responses.
- Maintain a friendly, empathetic, and professional tone.
- Adhere to strict guardrails to ensure accurate and relevant answers.

### Retrieval-Augmented Generation (RAG)
The platform employs RAG to enhance its generative AI capabilities. By combining a knowledge base with generative models, HelpdeskAI ensures:
- Responses are grounded in factual, up-to-date information.
- Efficient retrieval of relevant context from uploaded documents, URLs, or structured text.

### Modular API Design
Built with FastAPI, HelpdeskAI offers a modular and high-performance API structure. Key modules include:
- **Authentication**: Secure user access with JWT-based authentication.
- **Agent Management**: Create and manage AI agents tailored to specific needs.
- **Knowledge Base**: Upload and manage documents for context-aware responses.
- **Chat Interface**: A robust chat system for real-time interactions.
- **Analytics**: Monitor key performance indicators (KPIs) to optimize support.

### Database Integration
The database stores:
- User information and authentication tokens.
- Agent configurations and knowledge base entries.
- Interaction logs for analytics.

### File and Data Handling
The platform supports multiple data ingestion methods:
- File uploads (PDF, TXT) with parsing capabilities.
- Structured text input.
- URL scraping to extract relevant content.

### Static Assets
Static files, such as JavaScript widgets, are served to enable easy integration into web applications.


## How It Works

1. **Agent Creation**: Users create AI agents by uploading files, providing structured text, or specifying URLs. Each agent is configured with a system prompt to guide its behavior.
2. **Knowledge Base**: Uploaded data is processed and stored in a vector database, enabling efficient retrieval during conversations.
3. **Chat System**: Customers interact with the AI through a chat interface, receiving context-aware and concise responses.
4. **Analytics Dashboard**: Administrators monitor system performance and user interactions to optimize the support experience.

## Getting Started

### Prerequisites

- Python 3.11+
- A `.env` file with the following variables:
  - `DATABASE_URL`: Connection string for the database.
  - `GROQ_API_KEY`: API key for Groq integration.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Khaleelhabeeb/helpdeskAi.git
   cd helpdeskAi
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up the database:
   ```bash
   python -m db.database
   ```

4. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

5. Access the API at `http://127.0.0.1:8000`.


## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
