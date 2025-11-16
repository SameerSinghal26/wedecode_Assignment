from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import json
import os
import math

from database import engine, get_db, Base
from models import Company, Product
from schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyWithProducts,
    ProductCreate, ProductUpdate, ProductResponse,
    PaginatedCompanies, PaginatedProducts
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Startup Company Data Manager API",
    description="REST API for managing startup companies and their products",
    version="1.0.0"
)

# Add CORS middleware to allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FRONTEND ENDPOINT

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend HTML page"""
    return FileResponse("index.html")

# LOAD DATA ENDPOINT

@app.post("/load-data", status_code=status.HTTP_201_CREATED)
def load_data_from_json(db: Session = Depends(get_db)):
    """
    Load data from startup_data.json into the database.
    Prevents duplicate entries by checking company names.
    """
    
    # Check if file exists
    if not os.path.exists("startup_data.json"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="startup_data.json file not found"
        )
    
    try:
        # Read JSON file
        with open("startup_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        companies_data = data.get("companies", [])
        
        if not companies_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No companies found in startup_data.json"
            )
        
        loaded_count = 0
        skipped_count = 0
        errors = []
        
        for company_data in companies_data:
            try:
                # Check if company already exists
                existing_company = db.query(Company).filter(
                    Company.name == company_data["name"]
                ).first()
                
                if existing_company:
                    skipped_count += 1
                    continue
                
                # Extract products data
                products_data = company_data.pop("products", [])
                
                # Create company - don't pass id if it exists
                company_dict = {k: v for k, v in company_data.items() if k != 'id'}
                new_company = Company(**company_dict)
                db.add(new_company)
                db.flush()  # Get the company ID without committing
                
                # Create products
                for product_data in products_data:
                    # Don't pass id if it exists
                    product_dict = {k: v for k, v in product_data.items() if k != 'id'}
                    new_product = Product(
                        company_id=new_company.id,
                        **product_dict
                    )
                    db.add(new_product)
                
                loaded_count += 1
                
            except Exception as e:
                db.rollback()  # Rollback this company's transaction
                errors.append({
                    "company": company_data.get("name", "Unknown"),
                    "error": str(e)
                })
                continue
        
        # Commit all successful changes
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error committing data: {str(e)}"
            )
        
        return {
            "message": "Data loading completed",
            "loaded": loaded_count,
            "skipped": skipped_count,
            "errors": errors if errors else None
        }
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in startup_data.json"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading data: {str(e)}"
        )

# COMPANY ENDPOINTS

@app.get("/companies", response_model=PaginatedCompanies)
def get_companies(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=1000, description="Items per page"),
    industry: str = Query(None, description="Filter by industry"),
    db: Session = Depends(get_db)
):
    """
    Get all companies with pagination (10 per page by default).
    Optionally filter by industry.
    """
    
    query = db.query(Company)
    
    # Apply industry filter if provided
    if industry:
        query = query.filter(Company.industry == industry)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / per_page)
    offset = (page - 1) * per_page
    
    # Get paginated results
    companies = query.offset(offset).limit(per_page).all()
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "companies": companies
    }

@app.get("/companies/{company_id}", response_model=CompanyWithProducts)
def get_company_by_id(company_id: str, db: Session = Depends(get_db)):  # Changed to str for UUID
    """
    Get a specific company by ID with all its products.
    """
    
    company = db.query(Company).filter(Company.id == company_id).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {company_id} not found"
        )
    
    return company

@app.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new company (manual entry, no AI).
    """
    
    # Check if company name already exists
    existing = db.query(Company).filter(Company.name == company.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company with name '{company.name}' already exists"
        )
    
    try:
        new_company = Company(**company.model_dump())
        db.add(new_company)
        db.commit()
        db.refresh(new_company)
        return new_company
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating company: {str(e)}"
        )

@app.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: str,  # Changed to str for UUID
    company_update: CompanyUpdate,
    db: Session = Depends(get_db)
):
    """
    Update company details.
    """
    
    company = db.query(Company).filter(Company.id == company_id).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {company_id} not found"
        )
    
    # Check if new name conflicts with existing company
    if company_update.name and company_update.name != company.name:
        existing = db.query(Company).filter(Company.name == company_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company with name '{company_update.name}' already exists"
            )
    
    try:
        # Update only provided fields
        update_data = company_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating company: {str(e)}"
        )

@app.delete("/companies/{company_id}", status_code=status.HTTP_200_OK)
def delete_company(company_id: str, db: Session = Depends(get_db)):  # Changed to str for UUID
    """
    Delete a company and all its products (cascade delete).
    """
    
    company = db.query(Company).filter(Company.id == company_id).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {company_id} not found"
        )
    
    try:
        company_name = company.name
        product_count = len(company.products)
        
        db.delete(company)
        db.commit()
        
        return {
            "message": f"Company '{company_name}' deleted successfully",
            "deleted_products": product_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting company: {str(e)}"
        )

# PRODUCT ENDPOINTS

@app.get("/products", response_model=PaginatedProducts)
def get_products(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=1000, description="Items per page"),
    company_id: str = Query(None, description="Filter by company UUID"),  # Changed to str for UUID
    pricing_model: str = Query(None, description="Filter by pricing model"),
    db: Session = Depends(get_db)
):
    """
    Get all products with pagination.
    Optionally filter by company_id or pricing_model.
    """
    
    query = db.query(Product)
    
    # Apply filters
    if company_id:
        query = query.filter(Product.company_id == company_id)
    if pricing_model:
        query = query.filter(Product.pricing_model == pricing_model)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / per_page)
    offset = (page - 1) * per_page
    
    # Get paginated results
    products = query.offset(offset).limit(per_page).all()
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "products": products
    }

@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product_by_id(product_id: str, db: Session = Depends(get_db)):  # Changed to str for UUID
    """
    Get a specific product by ID.
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    return product

@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """
    Create a new product for a company.
    """
    
    # Check if company exists
    company = db.query(Company).filter(Company.id == product.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {product.company_id} not found"
        )
    
    try:
        new_product = Product(**product.model_dump())
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return new_product
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating product: {str(e)}"
        )

@app.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    product_update: ProductUpdate,
    db: Session = Depends(get_db)
):
    """
    Update product details.
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    try:
        # Update only provided fields
        update_data = product_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
        
        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating product: {str(e)}"
        )

@app.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    """
    Delete a product.
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    try:
        product_name = product.name
        db.delete(product)
        db.commit()
        
        return {
            "message": f"Product '{product_name}' deleted successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting product: {str(e)}"
        )

# HEALTH CHECK

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Check API and database health.
    """
    try:
        company_count = db.query(Company).count()
        product_count = db.query(Product).count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "statistics": {
                "total_companies": company_count,
                "total_products": product_count
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )