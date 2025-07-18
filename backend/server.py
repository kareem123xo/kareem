from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Premium Subscription Store", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    first_name: str
    last_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class UserCreate(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class SubscriptionPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str
    plan_name: str
    price: float
    currency: str = "USD"
    duration: str  # e.g., "monthly", "yearly"
    features: List[str]
    image_url: str
    is_active: bool = True

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    subscription_plan_id: str
    amount: float
    currency: str = "USD"
    status: str = "pending"  # pending, completed, cancelled, failed
    payment_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    subscription_plan_id: str
    amount: float
    currency: str = "usd"
    status: str = "pending"  # pending, completed, failed, expired
    payment_status: str = "pending"  # pending, paid, failed, expired
    metadata: Optional[Dict[str, str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CheckoutRequest(BaseModel):
    subscription_plan_id: str
    user_email: Optional[str] = None
    origin_url: str

class OrderCreate(BaseModel):
    user_email: Optional[str] = None
    subscription_plan_id: str

# Predefined subscription plans
SUBSCRIPTION_PLANS = [
    {
        "id": "capcut-pro-monthly",
        "service_name": "CapCut",
        "plan_name": "Pro Monthly",
        "price": 9.99,
        "currency": "USD",
        "duration": "monthly",
        "features": [
            "HD video exports",
            "Premium effects & filters",
            "Advanced editing tools",
            "Cloud storage",
            "No watermark"
        ],
        "image_url": "https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODB8MHwxfHNlYXJjaHwyfHx2aWRlbyUyMGVkaXRpbmd8ZW58MHx8fHwxNzUyODczMTQzfDA&ixlib=rb-4.1.0&q=85",
        "is_active": True
    },
    {
        "id": "canva-pro-monthly",
        "service_name": "Canva",
        "plan_name": "Pro Monthly",
        "price": 12.99,
        "currency": "USD",
        "duration": "monthly",
        "features": [
            "Premium templates",
            "Background remover",
            "Brand kit tools",
            "Team collaboration",
            "Unlimited storage"
        ],
        "image_url": "https://images.unsplash.com/photo-1574717025058-2f8737d2e2b7?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODB8MHwxfHNlYXJjaHwxfHx2aWRlbyUyMGVkaXRpbmd8ZW58MHx8fHwxNzUyODczMTQzfDA&ixlib=rb-4.1.0&q=85",
        "is_active": True
    },
    {
        "id": "chatgpt-plus-monthly",
        "service_name": "ChatGPT",
        "plan_name": "Plus Monthly",
        "price": 20.0,
        "currency": "USD",
        "duration": "monthly",
        "features": [
            "GPT-4 access",
            "Faster response times",
            "Priority access",
            "Custom instructions",
            "Advanced data analysis"
        ],
        "image_url": "https://images.unsplash.com/photo-1712002641088-9d76f9080889?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwxfHxBSSUyMGFzc2lzdGFudHxlbnwwfHx8fDE3NTI4NzMxNTB8MA&ixlib=rb-4.1.0&q=85",
        "is_active": True
    },
    {
        "id": "adobe-creative-monthly",
        "service_name": "Adobe Creative Cloud",
        "plan_name": "All Apps Monthly",
        "price": 54.99,
        "currency": "USD",
        "duration": "monthly",
        "features": [
            "All Creative Cloud apps",
            "100GB cloud storage",
            "Premium fonts",
            "Creative tutorials",
            "Portfolio website"
        ],
        "image_url": "https://images.unsplash.com/photo-1740174459699-487aec1f7bc5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODF8MHwxfHNlYXJjaHwxfHxjcmVhdGl2ZSUyMHNvZnR3YXJlfGVufDB8fHx8MTc1Mjg3MzExOXww&ixlib=rb-4.1.0&q=85",
        "is_active": True
    }
]

# Basic routes
@api_router.get("/")
async def root():
    return {"message": "Premium Subscription Store API", "version": "1.0.0"}

@api_router.get("/subscriptions", response_model=List[SubscriptionPlan])
async def get_subscriptions():
    """Get all available subscription plans"""
    return [SubscriptionPlan(**plan) for plan in SUBSCRIPTION_PLANS]

@api_router.get("/subscriptions/{subscription_id}", response_model=SubscriptionPlan)
async def get_subscription(subscription_id: str):
    """Get a specific subscription plan"""
    plan = next((plan for plan in SUBSCRIPTION_PLANS if plan["id"] == subscription_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    return SubscriptionPlan(**plan)

@api_router.post("/users", response_model=User)
async def create_user(user_data: UserCreate):
    """Create a new user account"""
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user (in a real app, password would be hashed)
    user_dict = user_data.dict()
    user_dict.pop('password')  # Remove password from stored data
    user_obj = User(**user_dict)
    await db.users.insert_one(user_obj.dict())
    return user_obj

@api_router.post("/auth/login")
async def login(user_data: UserLogin):
    """User login"""
    user = await db.users.find_one({"email": user_data.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # In a real app, verify password hash
    return {"message": "Login successful", "user_id": user["id"]}

@api_router.post("/orders", response_model=Order)
async def create_order(order_data: OrderCreate):
    """Create a new order"""
    # Validate subscription plan exists
    plan = next((plan for plan in SUBSCRIPTION_PLANS if plan["id"] == order_data.subscription_plan_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    # Create order
    order_dict = order_data.dict()
    order_dict.update({
        "amount": plan["price"],
        "currency": plan["currency"],
        "status": "pending"
    })
    
    order_obj = Order(**order_dict)
    await db.orders.insert_one(order_obj.dict())
    return order_obj

@api_router.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """Get order details"""
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return Order(**order)

@api_router.get("/orders", response_model=List[Order])
async def get_orders(user_email: Optional[str] = None):
    """Get orders, optionally filtered by user email"""
    query = {}
    if user_email:
        query["user_email"] = user_email
    
    orders = await db.orders.find(query).to_list(1000)
    return [Order(**order) for order in orders]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()