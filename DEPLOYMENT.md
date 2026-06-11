# Deployment

This app is ready for Render/Railway style deployment.

## Render

1. Push the project to GitHub.
2. Create a new Render Web Service.
3. Use `render.yaml` or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
4. Add environment variables:
   - `OPENAI_API_KEY` or `GEMINI_API_KEY` if using live LLM responses
   - `SESSION_TTL_HOURS=24`
   - `DATABASE_URL` if switching to PostgreSQL in production

## PostgreSQL Note

The current local app uses SQLite for simplicity. `DATABASE_URL` is documented for production migration; use PostgreSQL with SQLAlchemy or psycopg when deploying at scale.
