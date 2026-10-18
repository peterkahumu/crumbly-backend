"""Allow running the seed module with: python -m app.seed"""
from app.seed import main
import asyncio

asyncio.run(main())
