# Wispoke Multi-Tenant API Documentation

## Overview
This API provides a comprehensive multi-tenant chatbot platform with company-based data isolation, user management, and AI-powered chat functionality. Each company has its own knowledge base, users, and data that are completely isolated from other companies.

**🆕 NEW FEATURES:**
- **Subdomain Support**: Chatbots can be accessed via custom subdomains (e.g., `companyname.yourdomain.com`)
- **Enhanced User Management**: Support for both registered users and guest sessions
- **Advanced Document Management**: File uploads and text content management
- **Improved Security**: Enhanced access controls and company data isolation

## Base URL
```
http://127.0.0.1:8000
```

## Subdomain Access
```
http://companyslug.yourdomain.com  (for published chatbots)
```

## Authentication
The API uses JWT Bearer tokens for authentication. Include the token in the Authorization header:
```
Authorization: Bearer <token>
```

### Token Types
- **Company Tokens**: For company administrators (access all company endpoints)
- **User Tokens**: For registered users (access user-specific endpoints)  
- **Guest Tokens**: For temporary sessions (limited access)

---

## 🏢 Authentication Endpoints

### 1. Company Registration
**POST** `/auth/company/register`

Register a new company and create admin account.

**Request Body:**
```json
{
  "name": "TechCorp Solutions Inc",
  "email": "admin@techcorp-solutions.com",
  "password": "TechCorpPass123!"
}
```

**Response (200):**
```json
{
  "message": "Company registered successfully",
  "company": {
    "company_id": "company_uuid",
    "name": "TechCorp Solutions Inc",
    "email": "admin@techcorp-solutions.com",
    "created_at": "2024-01-01T12:00:00Z",
    "slug": null,
    "is_published": false,
    "plan": "free",
    "status": "active"
  },
  "tokens": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "token_type": "bearer"
  }
}
```

**Error (400):**
```json
{
  "detail": "Email already registered"
}
```

---

### 2. Company Login
**POST** `/auth/company/login`

Authenticate company admin and get tokens.

**Request Body:**
```json
{
  "email": "admin@techcorp-solutions.com",
  "password": "TechCorpPass123!"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "company": {
    "company_id": "company_uuid",
    "name": "TechCorp Solutions Inc",
    "email": "admin@techcorp-solutions.com",
    "created_at": "2024-01-01T12:00:00Z",
    "slug": "techcorp-solutions",
    "is_published": true,
    "plan": "free",
    "status": "active"
  },
  "tokens": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "token_type": "bearer"
  }
}
```

**Error (401):**
```json
{
  "detail": "Invalid email or password"
}
```

---

### 3. Get Company Profile
**GET** `/auth/company/profile`

Get the authenticated company's profile information.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "company": {
    "company_id": "company_uuid",
    "name": "TechCorp Solutions Inc",
    "email": "admin@techcorp-solutions.com",
    "slug": "techcorp-solutions",
    "is_published": true,
    "chatbot_title": "TechCorp AI Assistant",
    "chatbot_description": "AI technology expert assistant",
    "plan": "free",
    "status": "active",
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

---

### 4. Company Logout
**POST** `/auth/company/logout`

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "message": "Logout successful",
  "company_id": "company_uuid"
}
```

---

### 5. Set Company Slug
**PUT** `/auth/company/slug`

Set or update company slug for public chatbot URL.

**Headers:** `Authorization: Bearer <company_token>`

**Request Body:**
```json
{
  "slug": "techcorp-solutions"
}
```

**Response (200):**
```json
{
  "message": "Company slug updated successfully",
  "slug": "techcorp-solutions",
  "public_url": "http://127.0.0.1:8000/public/chatbot/techcorp-solutions"
}
```

**Error (400):**
```json
{
  "detail": "Slug must contain only letters, numbers, hyphens, and underscores"
}
```

---

### 6. Publish/Unpublish Chatbot
**POST** `/auth/company/publish-chatbot`

Control public chatbot visibility.

**Headers:** `Authorization: Bearer <company_token>`

**Request Body:**
```json
{
  "is_published": true,
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant"
}
```

**Response (200):**
```json
{
  "message": "Chatbot published successfully",
  "is_published": true,
  "public_url": "http://127.0.0.1:8000/public/chatbot/techcorp-solutions"
}
```

---

### 7. Get Chatbot Status
**GET** `/auth/company/chatbot-status`

Get current chatbot publishing status.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "slug": "techcorp-solutions",
  "is_published": true,
  "published_at": "2024-01-01T12:00:00Z",
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant",
  "public_url": "http://127.0.0.1:8000/public/chatbot/techcorp-solutions"
}
```

---

### 8. Refresh Token
**POST** `/auth/refresh`

Get new access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "jwt_refresh_token"
}
```

**Response (200):**
```json
{
  "access_token": "new_jwt_access_token",
  "token_type": "bearer"
}
```

---

### 9. Verify Token
**GET** `/auth/verify`

Verify and decode a JWT token.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "valid": true,
  "user_info": {
    "user_id": "user_uuid",
    "company_id": "company_uuid",
    "email": "user@company.com",
    "user_type": "company"
  }
}
```

---

### 10. Get Company Users
**GET** `/auth/company/users`

Get all users for the current company (company admin only).

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "company_name": "TechCorp Solutions Inc",
  "users": [
    {
      "user_id": "user_uuid_1",
      "company_id": "company_uuid",
      "email": "alice@techcorp-solutions.com",
      "name": "Alice Johnson",
      "is_anonymous": false,
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "user_id": "user_uuid_2",
      "company_id": "company_uuid",
      "email": "bob@techcorp-solutions.com",
      "name": "Bob Smith",
      "is_anonymous": false,
      "created_at": "2024-01-02T10:30:00Z"
    }
  ],
  "total_users": 2
}
```

**Error (404):**
```json
{
  "detail": "Company not found"
}
```

---

### 11. Authentication Health Check
**GET** `/auth/health`

**Response (200):**
```json
{
  "status": "healthy",
  "service": "authentication"
}
```

---

## 👥 User Management Endpoints

### 1. User Registration
**POST** `/users/register`

Register a new user for a company.

**Request Body:**
```json
{
  "company_id": "company_uuid",
  "email": "alice@techcorp-solutions.com",
  "password": "AlicePass123!",
  "name": "Alice Johnson"
}
```

**Response (200):**
```json
{
  "message": "User registered successfully",
  "user": {
    "user_id": "user_uuid",
    "company_id": "company_uuid",
    "email": "alice@techcorp-solutions.com",
    "name": "Alice Johnson",
    "is_anonymous": false,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "tokens": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "token_type": "bearer"
  }
}
```

**Error (400):**
```json
{
  "detail": "User with this email already exists in this company"
}
```

---

### 2. User Login
**POST** `/users/login`

Authenticate user and get tokens.

**Request Body:**
```json
{
  "email": "alice@techcorp-solutions.com",
  "password": "AlicePass123!",
  "company_id": "company_uuid"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "user": {
    "user_id": "user_uuid",
    "company_id": "company_uuid",
    "email": "alice@techcorp-solutions.com",
    "name": "Alice Johnson",
    "is_anonymous": false,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "tokens": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "token_type": "bearer"
  }
}
```

---

### 3. Create Guest Session
**POST** `/users/guest/create`

Create temporary session for anonymous users.

**Request Body:**
```json
{
  "company_id": "company_uuid",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0 (Test Guest)"
}
```

**Response (200):**
```json
{
  "message": "Guest session created successfully",
  "session": {
    "session_id": "session_uuid",
    "company_id": "company_uuid",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0 (Test Guest)",
    "created_at": "2024-01-01T12:00:00Z",
    "expires_at": "2024-01-01T20:00:00Z"
  },
  "tokens": {
    "access_token": "jwt_access_token",
    "token_type": "bearer"
  }
}
```

---

### 4. Get User Profile
**GET** `/users/profile`

Get the current user's profile (works for both guests and registered users).

**Headers:** `Authorization: Bearer <user_token>` or `Bearer <guest_token>`

**Response (200) - Registered User:**
```json
{
  "user": {
    "user_id": "user_uuid",
    "company_id": "company_uuid",
    "email": "alice@techcorp-solutions.com",
    "name": "Alice Johnson",
    "is_anonymous": false,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "user_type": "user"
}
```

**Response (200) - Guest User:**
```json
{
  "session": {
    "session_id": "session_uuid",
    "company_id": "company_uuid",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0 (Test Guest)",
    "created_at": "2024-01-01T12:00:00Z",
    "expires_at": "2024-01-01T20:00:00Z"
  },
  "user_type": "guest"
}
```

---

### 5. Check Session Validity
**GET** `/users/session/check`

Check if the current session/user is still valid.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "valid": true,
  "user_info": {
    "user_id": "user_uuid",
    "company_id": "company_uuid",
    "email": "alice@techcorp-solutions.com",
    "user_type": "user"
  }
}
```

---

### 6. Get Company Info
**GET** `/users/company/{company_id}/info`

Get company information (users can only access their own company).

**Headers:** `Authorization: Bearer <user_token>`

**Response (200):**
```json
{
  "company": {
    "company_id": "company_uuid",
    "name": "TechCorp Solutions Inc",
    "status": "active"
  }
}
```

**Error (403):**
```json
{
  "detail": "Access denied: You can only access your own company's information"
}
```

---

### 7. User Management Health Check
**GET** `/users/health`

**Response (200):**
```json
{
  "status": "healthy",
  "service": "user_management"
}
```

---

## 💬 Chat Endpoints

### 1. Send Chat Message
**POST** `/chat/send`

Send message to AI chatbot and get streaming response.

**Headers:** `Authorization: Bearer <user_token>` or `Bearer <guest_token>`

**Request Body:**
```json
{
  "message": "What is your company's annual revenue?",
  "chat_id": "chat_uuid",
  "chat_title": "Revenue Discussion",
  "model": "OpenAI"
}
```

**Response (200):** Server-Sent Events Stream
```
Content-Type: text/event-stream
X-Chat-ID: chat_uuid

data: {"chat_id": "chat_uuid", "type": "start"}

data: {"content": "TechCorp Solutions Inc has an annual revenue", "type": "chunk"}

data: {"content": " of $10 million...", "type": "chunk"}

data: {"type": "end"}
```

**Error (500):**
```json
{
  "detail": "Failed to send message: OpenAI API key not configured"
}
```

---

### 2. Get Chat History
**GET** `/chat/history/{chat_id}`

Get all messages in a specific chat.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "messages": [
    {
      "message_id": "msg_uuid",
      "chat_id": "chat_uuid",
      "role": "human",
      "content": "What is your company's annual revenue?",
      "timestamp": 1704067200,
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "message_id": "msg_uuid",
      "chat_id": "chat_uuid",
      "role": "ai",
      "content": "TechCorp Solutions Inc has an annual revenue of $10 million...",
      "timestamp": 1704067205,
      "created_at": "2024-01-01T12:00:05Z"
    }
  ]
}
```

**Error (404):**
```json
{
  "detail": "Chat not found or access denied"
}
```

---

### 3. List User Chats
**GET** `/chat/list`

Get all chats for current user/guest session.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "chats": [
    {
      "chat_id": "chat_uuid",
      "title": "Revenue Discussion",
      "created_at": "2024-01-01T12:00:00Z",
      "is_guest": false,
      "message_count": 4
    }
  ]
}
```

---

### 4. Update Chat Title
**PUT** `/chat/title/{chat_id}`

Update the title of a chat.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "title": "Updated Revenue Discussion"
}
```

**Response (200):**
```json
{
  "message": "Chat title updated successfully"
}
```

---

### 5. Delete Chat
**DELETE** `/chat/{chat_id}`

Delete a chat and all its messages.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "message": "Chat deleted successfully"
}
```

---

### 6. Setup Knowledge Base
**POST** `/chat/setup-knowledge-base`

Initialize AI knowledge base for company.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "message": "Knowledge base set up successfully"
}
```

---

### 7. Upload Text Document
**POST** `/chat/upload-text`

Upload text content to knowledge base.

**Headers:** `Authorization: Bearer <company_token>`

**Request Body:**
```json
{
  "content": "TechCorp Solutions Inc is a leading AI technology company...",
  "filename": "techcorp-company-info.txt"
}
```

**Response (200):**
```json
{
  "message": "Text content uploaded and processed successfully",
  "document": {
    "doc_id": "doc_uuid",
    "filename": "techcorp-company-info.txt",
    "content_type": "text/plain",
    "file_size": 500,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "knowledge_base": {
    "kb_id": "kb_uuid",
    "name": "Company Knowledge Base",
    "status": "ready"
  }
}
```

---

### 8. Upload File Document
**POST** `/chat/upload-document`

Upload file to knowledge base.

**Headers:** `Authorization: Bearer <company_token>`

**Request:** Form data with file upload
```
Content-Type: multipart/form-data

file: <uploaded_file>
```

**Response (200):**
```json
{
  "message": "Document uploaded and processed successfully",
  "document": {
    "doc_id": "doc_uuid",
    "filename": "document.pdf",
    "content_type": "text/plain",
    "file_size": 2048,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "knowledge_base": {
    "kb_id": "kb_uuid",
    "name": "Company Knowledge Base",
    "status": "ready"
  }
}
```

---

### 9. List Documents
**GET** `/chat/documents`

List all documents in company's knowledge base.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "documents": [
    {
      "doc_id": "doc_uuid",
      "filename": "techcorp-company-info.txt",
      "content_type": "text/plain",
      "file_size": 500,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

---

### 10. Delete Document
**DELETE** `/chat/documents/{doc_id}`

Delete a document from knowledge base.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "message": "Document deleted successfully"
}
```

**Error (404):**
```json
{
  "detail": "Document not found"
}
```

---

### 11. Get Knowledge Base Info
**GET** `/chat/knowledge-base`

Get knowledge base statistics and info.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "kb_id": "kb_uuid",
  "name": "Company Knowledge Base",
  "description": "Knowledge base for company documents",
  "status": "ready",
  "file_count": 5,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T15:30:00Z"
}
```

---

### 12. Clear Knowledge Base
**POST** `/chat/clear-knowledge-base`

Remove all documents from knowledge base.

**Headers:** `Authorization: Bearer <company_token>`

**Response (200):**
```json
{
  "message": "Knowledge base cleared successfully"
}
```

---

### 13. Get Company Info
**GET** `/chat/company-info`

Get information about the current company.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "company": {
    "company_id": "company_uuid",
    "name": "TechCorp Solutions Inc",
    "plan": "free",
    "status": "active"
  }
}
```

---

### 14. Chat Service Health Check
**GET** `/chat/health`

**Response (200):**
```json
{
  "status": "healthy",
  "service": "chat"
}
```

---

## 🌐 Public Endpoints

### Subdomain-Based Access (NEW)

### 1. Get Subdomain Chatbot Info
**GET** `/public/` (via subdomain)

Get public chatbot information via subdomain routing.

**Example URL:** `http://techcorp-solutions.yourdomain.com/public/`

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "name": "TechCorp Solutions Inc",
  "slug": "techcorp-solutions",
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant",
  "published_at": "2024-01-01T12:00:00Z"
}
```

---

### 2. Send Subdomain Chat Message
**POST** `/public/chat` (via subdomain)

Send message to subdomain-based public chatbot.

**Example URL:** `http://techcorp-solutions.yourdomain.com/public/chat`

**Request Body:**
```json
{
  "message": "How many companies have you served?",
  "chat_id": "optional_chat_uuid",
  "model": "OpenAI"
}
```

**Response (200):** Server-Sent Events Stream
```
Content-Type: text/event-stream
X-Chat-ID: chat_uuid
X-Session-ID: session_uuid
X-Company-Slug: techcorp-solutions

data: {"chat_id": "chat_uuid", "session_id": "session_uuid", "type": "start"}

data: {"content": "TechCorp Solutions has served over 500 companies", "type": "chunk"}

data: {"type": "end"}
```

---

### 3. Get Subdomain Company Info
**GET** `/public/info` (via subdomain)

Get public company information via subdomain.

**Example URL:** `http://techcorp-solutions.yourdomain.com/public/info`

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "name": "TechCorp Solutions Inc",
  "slug": "techcorp-solutions",
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant",
  "is_published": true,
  "published_at": "2024-01-01T12:00:00Z"
}
```

---

### Path-Based Access (Legacy Support)

### 4. Public Chat (by Slug)
**POST** `/public/chatbot/{company_slug}/chat`

Send message to public chatbot without authentication.

**Request Body:**
```json
{
  "message": "How many companies have you served?",
  "chat_id": "optional_chat_uuid",
  "model": "OpenAI"
}
```

**Response (200):** Streaming response
```
Content-Type: text/event-stream
X-Chat-ID: chat_uuid

data: {"content": "TechCorp Solutions has served over 500 companies worldwide...", "type": "chunk"}
```

**Error (404):**
```json
{
  "detail": "Chatbot not found or not published"
}
```

---

### 5. Get Public Chatbot Info
**GET** `/public/chatbot/{company_slug}`

Get public information about a chatbot.

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "name": "TechCorp Solutions Inc",
  "slug": "techcorp-solutions",
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant",
  "published_at": "2024-01-01T12:00:00Z"
}
```

---

### 6. Get Public Company Info
**GET** `/public/company/{company_slug}/info`

Get basic public company information.

**Response (200):**
```json
{
  "company_id": "company_uuid",
  "name": "TechCorp Solutions Inc",
  "slug": "techcorp-solutions",
  "chatbot_title": "TechCorp AI Assistant",
  "chatbot_description": "AI technology expert assistant",
  "is_published": true,
  "published_at": "2024-01-01T12:00:00Z"
}
```

---

### 7. Public Service Health Check
**GET** `/public/health`

**Response (200):**
```json
{
  "status": "healthy",
  "service": "public_chatbot"
}
```

---

## 🔒 Security & Data Isolation

### Multi-Tenant Architecture
- **Company Isolation**: Each company's data is completely isolated
- **User Access Control**: Users can only access their company's data
- **Guest Sessions**: Temporary sessions tied to specific companies
- **JWT Authentication**: Secure token-based authentication

### Security Boundaries
- Users cannot access other companies' information
- Cross-company data access is blocked at the API level
- Guest sessions are company-specific and time-limited
- All operations enforce company-based authorization
- Chat ownership validation prevents cross-user access

### Access Control Matrix

| User Type | Company Management | Own Company Data | User Management | Other Company Data | Public Chatbots |
|-----------|-------------------|------------------|-----------------|-------------------|-----------------|
| Company Admin | ✅ Full Access | ✅ Full Access | ✅ View All Users | ❌ Blocked | ✅ Read Only |
| Registered User | ❌ Blocked | ✅ Limited Access | ❌ Blocked | ❌ Blocked | ✅ Read Only |
| Guest Session | ❌ Blocked | ✅ Session Only | ❌ Blocked | ❌ Blocked | ✅ Read Only |

---

## ❌ Error Handling

### Common HTTP Status Codes

**400 Bad Request**
- Invalid request body
- Missing required fields
- Invalid data format
- File size too large
- Invalid slug format

**401 Unauthorized**
- Missing or invalid authentication token
- Expired token
- Invalid credentials

**403 Forbidden**
- Insufficient permissions
- Cross-company access attempt
- Guest trying to access company functions

**404 Not Found**
- Resource not found
- Invalid ID
- Chatbot not published

**500 Internal Server Error**
- Server configuration issues
- Database connection errors
- AI service unavailable

### Error Response Format
```json
{
  "detail": "Error description"
}
```

---

## 🔧 Environment Configuration

### Required Environment Variables
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Pinecone Configuration  
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment

# Domain Configuration
DOMAIN_URL=yourdomain.com
```

---

## 🆕 New Features & Improvements

### Subdomain Support
- **Custom Subdomains**: `companyslug.yourdomain.com`
- **Automatic Detection**: Middleware automatically detects subdomain requests
- **Backward Compatibility**: Path-based access still supported

### Enhanced User Management
- **Guest Sessions**: Anonymous access with session management
- **User Context**: Unified authentication for users and guests
- **Profile Management**: Comprehensive user/guest profile endpoints

### Advanced Document Management
- **File Uploads**: Support for file uploads via multipart/form-data
- **Text Upload**: Direct text content upload
- **Document Listing**: View all documents in knowledge base
- **Document Deletion**: Remove individual documents

### Improved Security
- **Access Validation**: Chat ownership validation
- **Company Isolation**: Enhanced multi-tenant security
- **Session Management**: Proper guest session handling

---

## 📊 Testing

### Postman Collection
Use the provided `POSTMAN_COLLECTION_COMPREHENSIVE.json` for complete API testing:

- **46 test requests** across 8 phases
- **Multi-tenant data isolation testing**
- **Security boundary validation**
- **Complete CRUD operations**
- **Error handling scenarios**
- **Health check monitoring**
- **Subdomain access testing**

### Test Coverage
- ✅ Company registration and management
- ✅ User registration and authentication  
- ✅ Guest session management
- ✅ Chat functionality with AI responses
- ✅ Knowledge base management
- ✅ Public chatbot access (both subdomain and path-based)
- ✅ Document upload and management
- ✅ Data isolation between companies
- ✅ Security boundary enforcement
- ✅ Error handling and edge cases
- ✅ Service health monitoring

---

## 🚀 Getting Started

1. **Set up environment variables** in `app/.env`
2. **Start the API server**: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
3. **Import Postman collection** for testing
4. **Register a company** using `/auth/company/register`
5. **Set up knowledge base** using `/chat/setup-knowledge-base`
6. **Upload content** using `/chat/upload-text` or `/chat/upload-document`
7. **Test chat functionality** using `/chat/send`
8. **Set company slug** using `/auth/company/slug`
9. **Publish chatbot** using `/auth/company/publish-chatbot`
10. **Test public access** via subdomain or path-based URLs

Your multi-tenant AI chatbot platform with subdomain support is now ready! 