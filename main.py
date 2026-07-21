import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select

# ---------------------------------------------------------------------------
# Stage 0: create your database
# ---------------------------------------------------------------------------

# Anchor tasks.db to this file's own folder instead of the process's current
# working directory. Working-directory can silently differ depending on how
# uvicorn/reloaders spawn subprocesses or which terminal tab you're in — this
# guarantees the app always reads/writes the same physical file.
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
    # Runs once when the app starts up, before it accepts any requests.
    create_db_and_tables()
    seed_tasks()
    yield


app = FastAPI(lifespan=lifespan)

# Stage 2 Example tasks
# NOTE: left untouched on purpose for Stage 0 — the endpoints below still read
# from this in-memory list. Stage 1 is where GET /tasks switches over to SQL.
tasks = [
    {"id": 1, "title": "Buy boba tea", "done": False},
    {"id": 2, "title": "Go grocery shopping", "done": False},
    {"id": 3, "title": "Clean the house", "done": True},
]

# Stage 3
class TaskCreate(BaseModel):
    title: Optional[str] = None

# Stage 4
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

# Stage 1
@app.get("/")
async def root():
    """Describe this API and list its main endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoint": ["/tasks"]}

#Stage 1
@app.get("/health")
async def health():
    """Check that the server is up and running."""
    return {"status": "ok"}

# Stage 2 Read (GET) - List of tasks
@app.get("/tasks")
async def get_tasks():
    """List all tasks currently in memory."""
    return tasks

# Stage 2 Read (GET) - A specific task
@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """Get a single task by its id, or 404 if it does not exist."""
    for task in tasks:
        if task["id"] == task_id:
            return task
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})

# Stage 3 Create (POST)
@app.post("/tasks", status_code=201)
async def create_task(task: TaskCreate):
    """Create a new task from a JSON body containing a title."""
    if not task.title or not task.title.strip():
        return JSONResponse(status_code=400, content={"error": "title is required"})

    next_id = max((t["id"] for t in tasks), default=0) + 1
    new_task = {"id": next_id, "title": task.title, "done": False}
    tasks.append(new_task)
    return new_task

# Stage 4 Update (PUT)
@app.put("/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate):
    """Update a task's title and/or done status, 404 if unknown, 400 if invalid."""
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

# Stage 4 Delete (DELETE) a task
@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    """Delete a task by id. Returns 204 with no body, or 404 if unknown."""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})

    tasks.remove(task)
    return Response(status_code=204)