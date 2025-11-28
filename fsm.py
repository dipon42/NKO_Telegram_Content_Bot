from aiogram.fsm.state import State, StatesGroup


class AddInfoNkoStateGroup(StatesGroup):
    name: str = State()
    description: str = State()
    forms_of_activity: str = State()
    organization_size: str = State()

class TextGenerationState(StatesGroup):
    choosing_model = State()
    entering_description = State()
    choosing_style = State()

class StructuredPostState(StatesGroup):
    entering_event = State()
    entering_date = State()
    entering_location = State()
    entering_invitees = State()
    entering_details = State()

class TextFromExamplesState(StatesGroup):
    entering_examples = State()
    entering_new_idea = State()

class ImageGenerationState(StatesGroup):
    entering_description = State()
    choosing_improvement = State()
    style_selection = State()

class ContentPlanState(StatesGroup):
    entering_period = State()
    entering_frequency = State()
    choosing_plan_type = State()
    entering_goal = State()

class TextEditorState(StatesGroup):
    entering_text = State()

class AddAPIkeyState(StatesGroup):
    entering_api_key = State()

class APIKeyState(StatesGroup):
    entering_api_key = State()
    confirming_replacement = State()
