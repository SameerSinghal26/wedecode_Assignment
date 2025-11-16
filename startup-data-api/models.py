from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import uuid

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    tagline = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    industry = Column(String(50), nullable=False, index=True)
    founded_year = Column(Integer, nullable=False)
    employee_count = Column(Integer, nullable=False)
    headquarters = Column(String(255), nullable=False)
    website_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship with products
    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    target_audience = Column(String(255), nullable=False)
    key_features = Column(Text, nullable=False)
    pricing_model = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship with company
    company = relationship("Company", back_populates="products")