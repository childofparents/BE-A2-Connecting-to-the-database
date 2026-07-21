import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select

# ---------------------------------------------------------------------------
# Stage 0: Create database & tables
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(BASE_DIR, "tasks.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})


class Task(SQLModel, table=True):
    """The `tasks` table: id (auto), title (text), done (boolean -> stored as 0/1)."""
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    done: bool = False


def create_db_and_tables():
    """Create tasks.db (if missing) and the tasks table (if missing)."""
    print(f"[Stage 0] Using database file: {sqlite_file_name}")
    SQLModel.metadata.create_all(engine)


def seed_tasks():
    """Insert the three example tasks, but only the very first time the table is empty."""
    with Session(engine) as session:
        first_row = session.exec(select(Task)).first()
        if first_row is None:
            session.add_all([
                Task(title="Buy boba tea", done=False),
                Task(title="Go grocery shopping", done=False),
                Task(title="Clean the house", done=True),
            ])
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    seed_tasks()
    yield


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------
class TaskCreate(BaseModel):
    title: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    """Describe this API and list its main endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoint": ["/tasks"]}


@app.get("/health")
async def health():
    """Check that the server is up and running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 1: Read endpoints backed by SQLite
# ---------------------------------------------------------------------------
@app.get("/tasks")
async def get_tasks():
    """List all tasks live from tasks.db."""
    with Session(engine) as session:
        statement = select(Task)
        tasks = session.exec(statement).all()
        return tasks


@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """Get a single task by id from tasks.db, or 404 if missing."""
    with Session(engine) as session:
        statement = select(Task).where(Task.id == task_id)
        task = session.exec(statement).first()
        if task is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Task {task_id} not found"}
            )
        return task


# ---------------------------------------------------------------------------
# Remaining Endpoints (Temporary Stage 0 placeholders - will update in Stages 2 & 3)
# ---------------------------------------------------------------------------
tasks = [
    {"id": 1, "title": "Buy boba tea", "done": False},
    {"id": 2, "title": "Go grocery shopping", "done": False},
    {"id": 3, "title": "Clean the house", "done": True},
]


@app.post("/tasks", status_code=201)
async def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        return JSONResponse(status_code=400, content={"error": "title is required"})

    next_id = max((t["id"] for t in tasks), default=0) + 1
    new_task = {"id": next_id, "title": task.title, "done": False}
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})

    if update.title is None and update.done is None:
        return JSONResponse(status_code=400, content={"error": "provide title and/or done to update"})

    if update.title is not None and not update.title.strip():
        return JSONResponse(status_code=400, content={"error": "title cannot be empty"})

    if update.title is not None:
        task["title"] = update.title
    if update.done is not None:
        task["done"] = update.done

    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})

    tasks.remove(task)
    return Response(status_code=204)