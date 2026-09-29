import sys
import types
from unittest.mock import MagicMock

# =====================================================================
# SHIMS GLOBALES DE MOCK PARA EL ENTORNO DE PRUEBAS
# =====================================================================
if "crewai" not in sys.modules or not hasattr(sys.modules["crewai"], "LLM"):
    class MockLLM:
        def __init__(self, model=None, api_key=None, temperature=None):
            self.model = model
            self.api_key = api_key
            self.temperature = temperature

    class MockAgent:
        def __init__(self, role=None, goal=None, backstory=None, verbose=False, allow_delegation=False, llm=None, tools=None):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.verbose = verbose
            self.allow_delegation = allow_delegation
            self.llm = llm
            self.tools = tools or []

    class MockTask:
        def __init__(self, description=None, expected_output=None, agent=None):
            self.description = description
            self.expected_output = expected_output
            self.agent = agent

    class MockCrew:
        instancias_creadas = []

        def __init__(self, agents=None, tasks=None, verbose=False, cache=False):
            self.agents = agents or []
            self.tasks = tasks or []
            self.verbose = verbose
            self.cache = cache
            MockCrew.instancias_creadas.append(self)

        def kickoff(self):
            return "CHARLA|Ninguna"

    crewai_mod = types.ModuleType("crewai")
    crewai_mod.LLM = MockLLM
    crewai_mod.Agent = MockAgent
    crewai_mod.Task = MockTask
    crewai_mod.Crew = MockCrew
    sys.modules["crewai"] = crewai_mod

    sys.modules["crewai.llms"] = types.ModuleType("crewai.llms")
    sys.modules["crewai.llms.cache"] = types.ModuleType("crewai.llms.cache")
    sys.modules["crewai.tools"] = types.ModuleType("crewai.tools")
    sys.modules["crewai.tools"].tool = lambda name: (lambda f: f)

    dotenv_mock = types.ModuleType("dotenv")
    dotenv_mock.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_mock

    requests_mock = types.ModuleType("requests")
    requests_mock.get = MagicMock()
    requests_mock.post = MagicMock()
    sys.modules["requests"] = requests_mock

    docx_mock = types.ModuleType("docx")
    docx_mock.Document = MagicMock()
    sys.modules["docx"] = docx_mock

    sys.modules["pypdf"] = types.ModuleType("pypdf")

    fastapi_mock = types.ModuleType("fastapi")
    class MockFastAPI:
        def add_middleware(self, *args, **kwargs): pass
        def post(self, *args, **kwargs):
            def decorator(f): return f
            return decorator
    fastapi_mock.FastAPI = MockFastAPI
    sys.modules["fastapi"] = fastapi_mock

    cors_mock = types.ModuleType("fastapi.middleware.cors")
    cors_mock.CORSMiddleware = object
    sys.modules["fastapi.middleware.cors"] = cors_mock

    pydantic_mock = types.ModuleType("pydantic")
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    pydantic_mock.BaseModel = MockBaseModel
    sys.modules["pydantic"] = pydantic_mock

    sys.modules["uvicorn"] = types.ModuleType("uvicorn")
