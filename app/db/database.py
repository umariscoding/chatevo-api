import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any, Optional
from app.models.models import (
    Base, Company, CompanyUser, GuestSession, KnowledgeBase, 
    Document, Chat, Message
)
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from app.core.config import DATABASE_URL
from app.utils.password import get_password_hash, verify_password

# Create new database for multi-tenant setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Initialize database tables. Called during app startup."""
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as e:
        print(f"Warning: Could not initialize database tables: {e}")

def get_db():
    """
    Creates and yields a database session.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password hashing functions imported from auth.jwt module

# =============================================================================
# COMPANY MANAGEMENT
# =============================================================================

async def create_company(name: str, email: str, password: str) -> Dict[str, Any]:
    """
    Create a new company account.
    
    Args:
        name: Company name
        email: Company email
        password: Company password
        
    Returns:
        dict: Company information
    """
    db = SessionLocal()
    try:
        # Check if company already exists
        existing = db.query(Company).filter(Company.email == email).first()
        if existing:
            raise ValueError("Company with this email already exists")
        
        # Create new company
        company = Company(
            name=name,
            email=email,
            password_hash=get_password_hash(password)
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        
        return {
            "company_id": company.company_id,
            "name": company.name,
            "email": company.email,
            "plan": company.plan,
            "status": company.status,
            "slug": company.slug,
            "is_published": company.is_published,
            "published_at": company.published_at.isoformat() if company.published_at else None,
            "chatbot_title": company.chatbot_title,
            "chatbot_description": company.chatbot_description,
            "created_at": company.created_at.isoformat()
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def authenticate_company(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a company and return company info.
    
    Args:
        email: Company email
        password: Company password
        
    Returns:
        dict: Company information if authenticated, None otherwise
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.email == email).first()
        if company and verify_password(plain_password=password, hashed_password=str(company.password_hash)):
            return {
                "company_id": company.company_id,
                "name": company.name,
                "email": company.email,
                "plan": company.plan,
                "status": company.status,
                "slug": company.slug,
                "is_published": company.is_published,
                "published_at": company.published_at.isoformat() if company.published_at else None,
                "chatbot_title": company.chatbot_title,
                "chatbot_description": company.chatbot_description,
                "created_at": company.created_at.isoformat()
            }
        return None
    except SQLAlchemyError:
        return None
    finally:
        db.close()

async def get_company_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    """Get company information by ID."""
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if company:
            return {
                "company_id": company.company_id,
                "name": company.name,
                "email": company.email,
                "slug": company.slug,
                "plan": company.plan,
                "status": company.status,
                "is_published": company.is_published,
                "published_at": company.published_at.isoformat() if company.published_at is not None else None,
                "chatbot_title": company.chatbot_title,
                "chatbot_description": company.chatbot_description,
                "settings": company.settings,
                "created_at": company.created_at.isoformat()
            }
        return None
    except SQLAlchemyError:
        return None
    finally:
        db.close()

async def get_company_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Get company by slug.
    
    Args:
        slug: Company slug
        
    Returns:
        dict: Company information if found, None otherwise
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == slug).first()
        if company:
            return {
                "company_id": company.company_id,
                "name": company.name,
                "email": company.email,
                "slug": company.slug,
                "plan": company.plan,
                "status": company.status,
                "is_published": company.is_published,
                "published_at": company.published_at.isoformat() if company.published_at is not None else None,
                "chatbot_title": company.chatbot_title,
                "chatbot_description": company.chatbot_description,
                "created_at": company.created_at.isoformat()
            }
        return None
    finally:
        db.close()

async def update_company_slug(company_id: str, slug: str) -> bool:
    """
    Update company slug.
    
    Args:
        company_id: Company ID
        slug: New slug
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    db = SessionLocal()
    try:
        # Check if slug already exists
        existing = db.query(Company).filter(Company.slug == slug, Company.company_id != company_id).first()
        if existing:
            raise ValueError("Slug already exists")
        
        # Update company slug
        result = db.query(Company).filter(Company.company_id == company_id).update({
            Company.slug: slug,
            Company.updated_at: datetime.now()
        })
        db.commit()
        return result > 0
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def update_chatbot_info(company_id: str, chatbot_title: Optional[str] = None, chatbot_description: Optional[str] = None) -> bool:
    """
    Update company's chatbot title and description.
    
    Args:
        company_id: Company ID
        chatbot_title: New chatbot title (optional)
        chatbot_description: New chatbot description (optional)
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    db = SessionLocal()
    try:
        update_data = {
            Company.updated_at: datetime.now()
        }
        
        if chatbot_title is not None:
            update_data[Company.chatbot_title] = chatbot_title
            
        if chatbot_description is not None:
            update_data[Company.chatbot_description] = chatbot_description
        
        # Only update if there's something to update
        if len(update_data) > 1:  # More than just updated_at
            result = db.query(Company).filter(Company.company_id == company_id).update(update_data)
            db.commit()
            return result > 0
        
        return True  # Nothing to update is considered success
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def publish_chatbot(company_id: str, is_published: bool) -> bool:
    """
    Publish or unpublish a company's chatbot.
    
    Args:
        company_id: Company ID
        is_published: Whether to publish or unpublish
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    db = SessionLocal()
    try:
        update_data = {
            Company.is_published: is_published,
            Company.updated_at: datetime.now()
        }
        
        if is_published:
            update_data[Company.published_at] = datetime.now()
        else:
            update_data[Company.published_at] = None
        
        result = db.query(Company).filter(Company.company_id == company_id).update(update_data)
        db.commit()
        return result > 0
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def get_published_company_info(slug: str) -> Optional[Dict[str, Any]]:
    """
    Get published company information by slug.
    
    Args:
        slug: Company slug
        
    Returns:
        dict: Published company information if found and published, None otherwise
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(
            Company.slug == slug,
            Company.is_published.is_(True),
            Company.status == 'active'
        ).first()
        
        if company:
            return {
                "company_id": company.company_id,
                "name": company.name,
                "slug": company.slug,
                "chatbot_title": company.chatbot_title or company.name,
                "chatbot_description": company.chatbot_description or f"Chat with {company.name}",
                "published_at": company.published_at.isoformat() if company.published_at is not None else None
            }
        return None
    finally:
        db.close()

# =============================================================================
# USER MANAGEMENT
# =============================================================================

async def create_user(company_id: str, email: str, password: str, name: str) -> Dict[str, Any]:
    """Create a new user for a company with password."""
    db = SessionLocal()
    try:
        # Check if user with this email already exists in this company
        existing_user = db.query(CompanyUser).filter(
            CompanyUser.company_id == company_id,
            CompanyUser.email == email
        ).first()
        
        if existing_user:
            raise ValueError(f"User with email {email} already exists in this company")
        
        user = CompanyUser(
            company_id=company_id,
            email=email,
            password_hash=get_password_hash(password),
            name=name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {
            "user_id": user.user_id,
            "company_id": user.company_id,
            "email": user.email,
            "name": user.name,
            "is_anonymous": user.is_anonymous,
            "created_at": user.created_at.isoformat()
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def authenticate_user(company_id: str, email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user and return user info."""
    db = SessionLocal()
    try:
        user = db.query(CompanyUser).filter(
            CompanyUser.company_id == company_id,
            CompanyUser.email == email
        ).first()
        
        if user and user.password_hash and verify_password(plain_password=password, hashed_password=str(user.password_hash)):
            return {
                "user_id": user.user_id,
                "company_id": user.company_id,
                "email": user.email,
                "name": user.name,
                "is_anonymous": user.is_anonymous,
                "created_at": user.created_at.isoformat()
            }
        return None
    except SQLAlchemyError:
        return None
    finally:
        db.close()

async def create_guest_session(company_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """Create a new guest session."""
    db = SessionLocal()
    try:
        expires_at = datetime.now() + timedelta(hours=24)  # 24 hour session
        
        session = GuestSession(
            company_id=company_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {
            "session_id": session.session_id,
            "company_id": session.company_id,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "expires_at": session.expires_at.isoformat(),
            "created_at": session.created_at.isoformat()
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user information by ID."""
    db = SessionLocal()
    try:
        user = db.query(CompanyUser).filter(CompanyUser.user_id == user_id).first()
        if user:
            return {
                "user_id": user.user_id,
                "company_id": user.company_id,
                "email": user.email,
                "name": user.name,
                "is_anonymous": user.is_anonymous,
                "created_at": user.created_at.isoformat()
            }
        return None
    except SQLAlchemyError:
        return None
    finally:
        db.close()

async def get_guest_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get guest session by ID."""
    db = SessionLocal()
    try:
        session = db.query(GuestSession).filter(
            GuestSession.session_id == session_id
        ).first()
        
        if not session:
            return None
        
        # Check if session is expired
        current_time = datetime.now()
        if session.expires_at.replace(tzinfo=None) <= current_time:
            return None
        
        return {
            "session_id": session.session_id,
            "company_id": session.company_id,
            "expires_at": session.expires_at.isoformat(),
            "created_at": session.created_at.isoformat(),
            "ip_address": session.ip_address,
            "user_agent": session.user_agent
        }
    except SQLAlchemyError as e:
        raise e
    finally:
        db.close()

async def get_users_by_company_id(company_id: str) -> List[Dict[str, Any]]:
    """Get all users for a specific company."""
    db = SessionLocal()
    try:
        users = db.query(CompanyUser).filter(
            CompanyUser.company_id == company_id
        ).order_by(CompanyUser.created_at.desc()).all()
        
        return [
            {
                "user_id": user.user_id,
                "company_id": user.company_id,
                "email": user.email,
                "name": user.name,
                "is_anonymous": user.is_anonymous,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
    except SQLAlchemyError as e:
        raise e
    finally:
        db.close()



# =============================================================================
# CHAT MANAGEMENT (COMPANY-SCOPED)
# =============================================================================

async def save_chat(company_id: str, chat_id: str, title: str, user_id: Optional[str] = None, session_id: Optional[str] = None):
    """
    Save a chat for a specific company.
    
    Args:
        company_id: Company ID
        chat_id: Chat ID
        title: Chat title
        user_id: User ID (for registered users)
        session_id: Session ID (for guest users)
    """
    db = SessionLocal()
    try:
        # Check if chat already exists
        chat = db.query(Chat).filter(Chat.chat_id == chat_id, Chat.company_id == company_id).first()
        if not chat:
            chat = Chat(
                chat_id=chat_id,
                company_id=company_id,
                title=title,
                user_id=user_id,
                session_id=session_id,
                is_guest=(session_id is not None)
            )
            db.add(chat)
            db.commit()
            db.refresh(chat)
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

async def save_message(company_id: str, chat_id: str, role: str, content: str):
    """Save a message for a specific company's chat."""
    db = SessionLocal()
    try:
        # Ensure chat exists
        chat = db.query(Chat).filter(Chat.chat_id == chat_id, Chat.company_id == company_id).first()
        if not chat:
            chat = Chat(
                chat_id=chat_id,
                company_id=company_id,
                title="New Chat",
                is_guest=True
            )
            db.add(chat)
            db.commit()
            db.refresh(chat)

        message = Message(
            chat_id=chat_id,
            company_id=company_id,
            role=role,
            content=content,
            timestamp=int(time.time())
        )
        db.add(message)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

async def fetch_messages(company_id: str, chat_id: str) -> List[Dict[str, Any]]:
    """Fetch all messages for a specific chat in a company."""
    db = SessionLocal()
    messages = []
    try:
        messages = db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.company_id == company_id
        ).order_by(Message.timestamp).all()
        
        messages = [
            {
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp
            } for message in messages
        ]
    except SQLAlchemyError:
        pass
    finally:
        db.close()
    
    return messages

async def fetch_company_chats(company_id: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all chats for a company, optionally filtered by user or session."""
    db = SessionLocal()
    try:
        query = db.query(Chat).filter(
            Chat.company_id == company_id,
            Chat.is_deleted == False
        )
        
        if user_id:
            query = query.filter(Chat.user_id == user_id)
        elif session_id:
            query = query.filter(Chat.session_id == session_id)
            
        chats = query.all()
        
        result = [
            {
                "chat_id": chat.chat_id,
                "title": chat.title,
                "is_guest": chat.is_guest,
                "is_deleted": chat.is_deleted,
                "created_at": chat.created_at.isoformat()
            } for chat in chats
        ]
    except SQLAlchemyError:
        result = []
    finally:
        db.close()
    
    return result

async def update_chat_title(company_id: str, chat_id: str, new_title: str):
    """Update chat title for a specific company."""
    db = SessionLocal()
    try:
        db.execute(
            update(Chat).where(
                Chat.chat_id == chat_id,
                Chat.company_id == company_id
            ).values(title=new_title)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

async def delete_chat(company_id: str, chat_id: str):
    """Delete a chat for a specific company."""
    db = SessionLocal()
    try:
        db.execute(
            update(Chat).where(
                Chat.chat_id == chat_id,
                Chat.company_id == company_id
            ).values(is_deleted=True)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

async def delete_all_chats(company_id: str):
    """Delete all chats for a specific company."""
    db = SessionLocal()
    try:
        db.execute(
            update(Chat).where(
                Chat.company_id == company_id
            ).values(is_deleted=True)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

def load_session_history(company_id: str, chat_id: str) -> ChatMessageHistory:
    """
    Load chat history for a specific chat in a company.
    
    Args:
        company_id: Company ID
        chat_id: Chat ID
        
    Returns:
        ChatMessageHistory: Object containing the chat's message history
    """
    db = SessionLocal()
    chat_history = ChatMessageHistory()
    
    try:
        # Query messages with company scoping
        messages = db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.company_id == company_id
        ).order_by(Message.timestamp).all()
        
        # Add messages to chat history in correct format
        for message in messages:
            role = str(message.role)
            content = str(message.content)
            if role == "human":
                chat_history.add_user_message(content)
            elif role == "ai":
                chat_history.add_ai_message(content)
                
    except SQLAlchemyError as e:
        print(f"Error loading session history: {e}")
    finally:
        db.close()
    
    return chat_history

# =============================================================================
# KNOWLEDGE BASE AND DOCUMENT MANAGEMENT
# =============================================================================

async def get_or_create_knowledge_base(company_id: str, name: str = "Default Knowledge Base", description: str = "Company knowledge base") -> Dict[str, Any]:
    """
    Get or create a knowledge base for a company.
    
    Args:
        company_id: Company ID
        name: Knowledge base name
        description: Knowledge base description
        
    Returns:
        Dict containing knowledge base information
    """
    db = SessionLocal()
    try:
        # Check if knowledge base already exists
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.company_id == company_id).first()
        if kb:
            return {
                "kb_id": kb.kb_id,
                "company_id": kb.company_id,
                "name": kb.name,
                "description": kb.description,
                "status": kb.status,
                "file_count": kb.file_count,
                "created_at": kb.created_at,
                "updated_at": kb.updated_at
            }
        
        # Create new knowledge base
        kb = KnowledgeBase(
            company_id=company_id,
            name=name,
            description=description,
            status='ready'
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        
        return {
            "kb_id": kb.kb_id,
            "company_id": kb.company_id,
            "name": kb.name,
            "description": kb.description,
            "status": kb.status,
            "file_count": kb.file_count,
            "created_at": kb.created_at,
            "updated_at": kb.updated_at
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def save_document(kb_id: str, filename: str, content: str, content_type: str = "text/plain") -> Dict[str, Any]:
    """
    Save a document to a knowledge base.
    
    Args:
        kb_id: Knowledge base ID
        filename: Document filename
        content: Document content
        content_type: Document content type
        
    Returns:
        Dict containing document information
    """
    db = SessionLocal()
    try:
        # Check if document already exists
        existing_doc = db.query(Document).filter(
            Document.kb_id == kb_id,
            Document.filename == filename
        ).first()
        
        if existing_doc:
            # Update existing document
            db.execute(
                update(Document).where(
                    Document.doc_id == existing_doc.doc_id
                ).values(
                    content=content,
                    content_type=content_type,
                    file_size=len(content.encode('utf-8')),
                    embeddings_status='pending'
                )
            )
            db.commit()
            db.refresh(existing_doc)
            document = existing_doc
        else:
            # Create new document
            document = Document(
                kb_id=kb_id,
                filename=filename,
                content=content,
                content_type=content_type,
                file_size=len(content.encode('utf-8')),
                embeddings_status='pending'
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Update knowledge base file count
            db.execute(
                update(KnowledgeBase).where(
                    KnowledgeBase.kb_id == kb_id
                ).values(
                    file_count=KnowledgeBase.file_count + 1
                )
            )
            db.commit()
        
        return {
            "doc_id": document.doc_id,
            "kb_id": document.kb_id,
            "filename": document.filename,
            "content_type": document.content_type,
            "file_size": document.file_size,
            "embeddings_status": document.embeddings_status,
            "created_at": document.created_at
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()

async def get_company_documents(company_id: str) -> List[Dict[str, Any]]:
    """
    Get all documents for a company.
    
    Args:
        company_id: Company ID
        
    Returns:
        List of documents
    """
    db = SessionLocal()
    try:
        documents = db.query(Document).join(KnowledgeBase).filter(
            KnowledgeBase.company_id == company_id
        ).all()
        
        return [
            {
                "doc_id": doc.doc_id,
                "kb_id": doc.kb_id,
                "filename": doc.filename,
                "content_type": doc.content_type,
                "file_size": doc.file_size,
                "embeddings_status": doc.embeddings_status,
                "created_at": doc.created_at
            }
            for doc in documents
        ]
    except SQLAlchemyError as e:
        raise e
    finally:
        db.close()

async def get_document_content(doc_id: str) -> Optional[str]:
    """
    Get document content by document ID.
    
    Args:
        doc_id: Document ID
        
    Returns:
        Document content or None if not found
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.doc_id == doc_id).first()
        if document:
            return str(document.content)
        return None
    except SQLAlchemyError as e:
        raise e
    finally:
        db.close()

async def update_document_embeddings_status(doc_id: str, status: str):
    """
    Update document embeddings processing status.
    
    Args:
        doc_id: Document ID
        status: New status (pending, processing, completed, failed)
    """
    db = SessionLocal()
    try:
        db.execute(
            update(Document).where(
                Document.doc_id == doc_id
            ).values(embeddings_status=status)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()

async def get_knowledge_base_by_company(company_id: str) -> Optional[Dict[str, Any]]:
    """
    Get knowledge base for a company.
    
    Args:
        company_id: Company ID
        
    Returns:
        Knowledge base information or None if not found
    """
    db = SessionLocal()
    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.company_id == company_id).first()
        if not kb:
            return None
            
        return {
            "kb_id": kb.kb_id,
            "company_id": kb.company_id,
            "name": kb.name,
            "description": kb.description,
            "status": kb.status,
            "file_count": kb.file_count,
            "created_at": kb.created_at,
            "updated_at": kb.updated_at
        }
    except SQLAlchemyError as e:
        raise e
    finally:
        db.close()

async def delete_document(doc_id: str, company_id: str) -> bool:
    """
    Delete a document from a company's knowledge base.
    
    Args:
        doc_id: Document ID
        company_id: Company ID (for authorization)
        
    Returns:
        True if deleted successfully, False otherwise
    """
    db = SessionLocal()
    try:
        # Find document with company verification
        document = db.query(Document).join(KnowledgeBase).filter(
            Document.doc_id == doc_id,
            KnowledgeBase.company_id == company_id
        ).first()
        
        if not document:
            return False
            
        # Delete the document
        kb_id = document.kb_id
        db.delete(document)
        
        # Update knowledge base file count
        db.execute(
            update(KnowledgeBase).where(
                KnowledgeBase.kb_id == kb_id
            ).values(
                file_count=KnowledgeBase.file_count - 1
            )
        )
        
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        return False
    finally:
        db.close()

# =============================================================================
# BACKWARD COMPATIBILITY LAYER (TEMPORARY)
# =============================================================================

# These functions provide backward compatibility with the old API
# They use a default company_id for now, will be updated when we add auth to endpoints

DEFAULT_COMPANY_ID = "default-company"

async def fetch_all_chats() -> List[Dict[str, Any]]:
    """Backward compatibility: Fetch chats for default company."""
    return await fetch_company_chats(DEFAULT_COMPANY_ID)

async def save_message_old(chat_id: str, role: str, content: str):
    """Backward compatibility: Save message for default company."""
    return await save_message(DEFAULT_COMPANY_ID, chat_id, role, content)

async def save_chat_old(chat_id: str, title: str):
    """Backward compatibility: Save chat for default company."""
    return await save_chat(DEFAULT_COMPANY_ID, chat_id, title)

async def fetch_messages_old(chat_id: str) -> List[Dict[str, Any]]:
    """Backward compatibility: Fetch messages for default company."""
    return await fetch_messages(DEFAULT_COMPANY_ID, chat_id)

async def update_chat_title_old(chat_id: str, new_title: str):
    """Backward compatibility: Update chat title for default company."""
    return await update_chat_title(DEFAULT_COMPANY_ID, chat_id, new_title)

async def delete_chat_old(chat_id: str):
    """Backward compatibility: Delete chat for default company."""
    return await delete_chat(DEFAULT_COMPANY_ID, chat_id)

async def delete_all_chats_old():
    """Backward compatibility: Delete all chats for default company."""
    return await delete_all_chats(DEFAULT_COMPANY_ID)

def load_session_history_old(chat_id: str) -> ChatMessageHistory:
    """Backward compatibility: Load session history for default company."""
    return load_session_history(DEFAULT_COMPANY_ID, chat_id)
