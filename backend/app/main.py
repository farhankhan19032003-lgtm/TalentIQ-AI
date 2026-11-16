import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import jobs, matching, misc, resumes
from .core.config import ALGORITHM_VERSION, settings
from .core.database import Base, engine
from .core.errors import install_handlers
from .models import db  # noqa: F401  (register tables)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # dev convenience; production uses `alembic upgrade head`
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="TalentIQ AI", version=ALGORITHM_VERSION, lifespan=lifespan,
              description="Evidence-driven recruitment intelligence. Decision support only - recruiters make every decision.",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])
install_handlers(app)
app.include_router(misc.public, prefix="/api")
app.include_router(misc.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
