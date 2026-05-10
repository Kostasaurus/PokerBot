from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_email = State()
    waiting_nickname = State()

class Actions(StatesGroup):
    waiting_email = State()
    starting = State()
    just_registered = State()

class Admin(StatesGroup):
    waiting_tournament_info = State()
    waiting_dealer = State()
    waiting_results = State()

