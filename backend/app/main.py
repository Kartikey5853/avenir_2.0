from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

# Routers
from app.routers import users  # we will create this next

# ----------------------------------
# Logging Configuration (Production Ready)
# ----------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------------
# App Initialization
# ----------------------------------
app = FastAPI(
    title="avenir API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# ----------------------------------
# Global Exception Handlers
# ----------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logging.warning(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Invalid request data",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error"
        }
    )

# ----------------------------------
# Include Routers
# ----------------------------------

#app.include_router(users.router, prefix="/api/users", tags=["Users"])

# ----------------------------------
# Health Check Route (Production Must)
# ----------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    logging.info("Health endpoint was called")
    return {
        
        "success": True,
        "message": "API is running"
    }