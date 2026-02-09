import asyncio
import httpx
from bot.services.import_ratings import import_ratings_from_sheet

async def test_import():
    try:
        result = await import_ratings_from_sheet(
            api_base_url="http://localhost:8000",
            sheet_csv_url="https://docs.google.com/spreadsheets/d/e/2PACX-1vRF-2FRf8dOD4f-6M0dg-LwYcu0PFWf30hBq-Bf-O-X6Fjmqzd74PBR_IMm5dSZ0FifxlApcT02vRDa/pub?gid=2097969953&single=true&output=csv"
        )
        print(f"Import successful: {result} games imported")
    except Exception as e:
        print(f"Import failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_import())
