from apscheduler.schedulers.asyncio import AsyncIOScheduler

from managers.tournaments_manager import TournamentManager

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=100)
async def scheduled_status_update():
    await TournamentManager.update_tournaments_status()
