
import asyncio

from DataBase_M.database import engine
from DataBase_M.tables import Base


async def reset_tables():

    async with engine.begin() as conn:

        # Drop all tables using CASCADE
        await conn.execute(
            __import__("sqlalchemy").text(
                "DROP SCHEMA public CASCADE"
            )
        )

        # Recreate public schema
        await conn.execute(
            __import__("sqlalchemy").text(
                "CREATE SCHEMA public"
            )
        )

        # Recreate all tables
        await conn.run_sync(Base.metadata.create_all)

    print("All tables reset successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_tables())
