from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.agents import agents, chat, knowledge_base
from api.auth import auth, password_reset
from api.scrape import scrape
from api.storage import storage, upload
from api.users import users
from db.database import Base, engine
from api.analystics import analytic
from fastapi.staticfiles import StaticFiles


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

# Custom exception handler for 422 validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract form data safely
    try:
        body_str = str(exc.body) if exc.body else "No body"
    except:
        body_str = "Could not serialize body"
    
    print(f"\n{'='*80}")
    print(f"[VALIDATION ERROR] 422 Unprocessable Entity")
    print(f"Endpoint: {request.method} {request.url.path}")
    print(f"Errors: {exc.errors()}")
    print(f"Body: {body_str}")
    print(f"{'='*80}\n")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

# rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/auth")
app.include_router(password_reset.router, prefix="/auth")

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(upload.router, prefix="/knowledge", tags=["Knowledge Upload"])
app.include_router(knowledge_base.router, prefix="/kb", tags=["Knowledge Base"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(users.router, prefix="/users", tags=["users"]) 
app.include_router(storage.router, prefix="/users", tags=["Storage"])
app.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
app.include_router(analytic.router, tags=["KPI"])
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)