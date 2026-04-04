# Wispoke API - Multi-Tenant Chatbot-as-a-Service Platform

A FastAPI-based multi-tenant chatbot platform with Retrieval-Augmented Generation (RAG). Companies create AI chatbots, upload knowledge bases, and deploy them on custom subdomains.

## Features

- **Multi-Tenant Architecture** - Complete company isolation with row-level security
- **RAG-Powered Q&A** - Document upload, vector embeddings, and context-aware responses
- **Subdomain Routing** - Each company gets `companyname.wispoke.com`
- **Streaming Responses** - Real-time SSE streaming of AI responses
- **Multiple LLM Providers** - Groq (Llama), OpenAI (GPT-4o/4.1), Anthropic (Claude)
- **Guest & Registered Users** - Anonymous sessions and authenticated accounts
- **Billing & Subscriptions** - LemonSqueezy integration with Free/Pro plans
- **Analytics** - Dashboard metrics and user statistics
- **Google OAuth** - SSO for company authentication
- **Embed Widget** - Embeddable chatbot script for websites

## Tech Stack

- **FastAPI** - Async web framework
- **Supabase** - PostgreSQL database with row-level security
- **Pinecone** - Vector database for RAG embeddings
- **Cohere** - Embedding model (`embed-english-v3.0`)
- **LangChain** - LLM orchestration (OpenAI, Anthropic, Groq providers)
- **LangSmith** - LLM tracing and monitoring
- **PyJWT** - JWT authentication
- **Passlib/Bcrypt** - Password hashing
- **LemonSqueezy** - Subscription billing

## Project Structure

```
wispoke-api/
├── app/
│   ├── core/                          # Config, database, security, middleware
│   │   ├── config.py                  # Pydantic settings
│   │   ├── database.py                # Supabase client
│   │   ├── security.py                # Password hashing & JWT
│   │   ├── middleware.py              # CORS, logging, rate limiting, subdomain
│   │   └── exceptions.py             # Custom exceptions
│   ├── features/                      # Feature modules (router → service → repository)
│   │   ├── auth/                      # Company auth (register, login, Google OAuth)
│   │   ├── users/                     # User management (registered + guests)
│   │   ├── chat/                      # Chat messaging & history
│   │   ├── documents/                 # Document upload & knowledge base
│   │   ├── public/                    # Public chatbot endpoints
│   │   ├── billing/                   # LemonSqueezy subscriptions
│   │   └── analytics/                 # Dashboard & user analytics
│   ├── services/
│   │   ├── document_processing/       # PDF, DOCX, TXT parsing & chunking
│   │   └── rag/                       # Providers, vector store, retriever, chain, streaming
│   ├── main.py                        # FastAPI entry point
│   ├── static/                        # embed.js widget script
│   └── templates/                     # Widget preview HTML
├── migrations/                        # Supabase SQL migrations
├── tests/                             # Pytest tests
├── requirements.txt
├── Makefile                           # Dev commands (setup, venv, install, test)
├── Procfile                           # Heroku deployment
└── railway.json                       # Railway deployment
```

## Getting Started

### Prerequisites

- Python 3.11+
- Supabase account
- Pinecone account
- At least one LLM API key (Groq, OpenAI, or Anthropic)
- Cohere API key (for embeddings)

### Installation

```bash
# Using Makefile (recommended)
make setup     # Install system packages (libpq, python@3.11)
make venv      # Create .venv
make install   # Install Python dependencies

# Or manually
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
JWT_SECRET_KEY=your_secret_key_32_chars_min
PINECONE_API_KEY=your_pinecone_key
COHERE_API_KEY=your_cohere_key

# LLM Providers (at least one required)
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Optional
LEMONSQUEEZY_API_KEY=your_lemonsqueezy_key
LEMONSQUEEZY_WEBHOOK_SECRET=your_webhook_secret
GOOGLE_CLIENT_ID=your_google_client_id
BASE_DOMAIN=wispoke.com
USE_SUBDOMAIN_ROUTING=true
DEBUG=false
LOG_LEVEL=INFO
```

### Running

```bash
uvicorn app.main:app --reload --port 8081
```

The API will be available at `http://localhost:8081`. Interactive docs at `/docs`.

## API Endpoints

### Auth (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/company/register` | Register company |
| POST | `/auth/company/login` | Company login |
| POST | `/auth/company/google` | Google OAuth |
| GET | `/auth/company/profile` | Get company profile |
| POST | `/auth/refresh` | Refresh tokens |
| PUT | `/auth/company/slug` | Update subdomain slug |
| POST | `/auth/company/publish-chatbot` | Publish/unpublish chatbot |
| PUT | `/auth/company/chatbot-info` | Update chatbot title/description |

### Users (`/users`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users/guest/create` | Create guest session |
| POST | `/users/register` | Register user |
| POST | `/users/login` | User login |
| GET | `/users/profile` | Get user profile |

### Chat (`/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/send` | Send message (streaming) |
| GET | `/chat/history/{chat_id}` | Get chat messages |
| GET | `/chat/list` | List user chats |
| PUT | `/chat/title/{chat_id}` | Rename chat |
| DELETE | `/chat/{chat_id}` | Delete chat |

### Documents (`/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/upload-document` | Upload PDF/DOCX (Pro) |
| POST | `/chat/upload-text` | Upload text content |
| GET | `/chat/documents` | List documents |
| DELETE | `/chat/documents/{doc_id}` | Delete document |

### Public (`/public`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/public/chatbot/{slug}` | Get chatbot info |
| POST | `/public/chatbot/{slug}/chat` | Public chat (streaming) |
| GET | `/public/chatbot/{slug}/embed-settings` | Get embed settings |

### Billing (`/billing`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/billing/checkout` | Create checkout session |
| GET | `/billing/subscription` | Get subscription status |
| POST | `/billing/cancel` | Cancel subscription |
| POST | `/billing/resume` | Resume subscription |
| POST | `/billing/webhook` | LemonSqueezy webhook |

### Analytics (`/api/company/analytics`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/dashboard` | Dashboard metrics |
| GET | `/analytics/users` | User statistics (Pro) |

## Architecture

**Clean Architecture** with feature-based modules:

```
Router → Service → Repository → Supabase
```

- **Router** - HTTP endpoints and request validation
- **Service** - Business logic
- **Repository** - Database access abstraction
- **Dependencies** - JWT auth context injection, plan-based feature gating

## RAG Pipeline

1. **Upload** - Parse PDF/DOCX/TXT files
2. **Chunk** - Split into overlapping segments (LangChain text splitters)
3. **Embed** - Generate vectors with Cohere
4. **Store** - Index in Pinecone (company-isolated)
5. **Retrieve** - Query top-K relevant chunks
6. **Generate** - Stream response via LLM with retrieved context

## Testing

```bash
pytest
# or
make test
```

## Deployment

Configured for **Heroku** (`Procfile`) and **Railway** (`railway.json`).

## Security

- JWT authentication (HS256, 30min access / 7d refresh tokens)
- Bcrypt password hashing
- Row-level security in Supabase
- LemonSqueezy webhook HMAC verification
- Rate limiting (60 req/min)
- CORS and security headers
