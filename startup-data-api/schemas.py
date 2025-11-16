from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

# PRODUCT SCHEMAS

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    target_audience: str = Field(..., min_length=5)
    key_features: str = Field(..., min_length=10)
    pricing_model: str = Field(..., pattern="^(Free|Freemium|Subscription|Enterprise)$")
    
    @field_validator('pricing_model')
    @classmethod
    def validate_pricing_model(cls, v):
        allowed = ["Free", "Freemium", "Subscription", "Enterprise"]
        if v not in allowed:
            raise ValueError(f"pricing_model must be one of: {', '.join(allowed)}")
        return v

class ProductCreate(ProductBase):
    company_id: str = Field(..., description="Company UUID")

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    target_audience: Optional[str] = Field(None, min_length=5)
    key_features: Optional[str] = Field(None, min_length=10)
    pricing_model: Optional[str] = Field(None, pattern="^(Free|Freemium|Subscription|Enterprise)$")
    
    @field_validator('pricing_model')
    @classmethod
    def validate_pricing_model(cls, v):
        if v is not None:
            allowed = ["Free", "Freemium", "Subscription", "Enterprise"]
            if v not in allowed:
                raise ValueError(f"pricing_model must be one of: {', '.join(allowed)}")
        return v

class ProductResponse(ProductBase):
    id: str
    company_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# COMPANY SCHEMAS

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tagline: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=50)
    industry: str = Field(..., min_length=3)
    founded_year: int = Field(..., ge=1900, le=2025)
    employee_count: int = Field(..., gt=0)
    headquarters: str = Field(..., min_length=5)
    website_url: Optional[str] = Field(None, max_length=255)

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tagline: Optional[str] = Field(None, min_length=5, max_length=100)
    description: Optional[str] = Field(None, min_length=50)
    industry: Optional[str] = Field(None, min_length=3)
    founded_year: Optional[int] = Field(None, ge=1900, le=2025)
    employee_count: Optional[int] = Field(None, gt=0)
    headquarters: Optional[str] = Field(None, min_length=5)
    website_url: Optional[str] = Field(None, max_length=255)

class CompanyResponse(CompanyBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CompanyWithProducts(CompanyResponse):
    products: List[ProductResponse] = []
    
    class Config:
        from_attributes = True

# PAGINATION SCHEMA

class PaginatedCompanies(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    companies: List[CompanyResponse]

class PaginatedProducts(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    products: List[ProductResponse]