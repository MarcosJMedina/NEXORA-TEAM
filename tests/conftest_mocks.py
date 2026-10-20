import sys
import types
from unittest.mock import MagicMock

# =====================================================================
# SHIMS GLOBALES DE MOCK PARA EL ENTORNO DE PRUEBAS
# =====================================================================
if "crewai" not in sys.modules or not hasattr(sys.modules["crewai"], "LLM"):
    class MockLLM:
        def __init__(self, model=None, api_key=None, temperature=None, base_url=None, **kwargs):
            self.model = model
            self.api_key = api_key
            self.temperature = temperature
            self.base_url = base_url
            for k, v in kwargs.items():
                setattr(self, k, v)

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
    fastapi_mock.HTTPException = Exception
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

    # Mock para chromadb en tests unitarios aislados
    chromadb_mock = types.ModuleType("chromadb")
    class MockChromaClient:
        def get_collection(self, *args, **kwargs):
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            return mock_col
        def get_or_create_collection(self, *args, **kwargs):
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            return mock_col
    chromadb_mock.PersistentClient = lambda *args, **kwargs: MockChromaClient()
    sys.modules["chromadb"] = chromadb_mock

    chromadb_utils = types.ModuleType("chromadb.utils")
    chromadb_embed = types.ModuleType("chromadb.utils.embedding_functions")
    chromadb_embed.DefaultEmbeddingFunction = lambda *args, **kwargs: MagicMock()
    sys.modules["chromadb.utils"] = chromadb_utils
    sys.modules["chromadb.utils.embedding_functions"] = chromadb_embed

    # Mock para qdrant_client en tests unitarios aislados
    if "qdrant_client" not in sys.modules:
        qdrant_mock = types.ModuleType("qdrant_client")
        class MockQdrantClient:
            def __init__(self, *args, **kwargs): pass
            def get_collections(self):
                mock_res = MagicMock()
                mock_res.collections = []
                return mock_res
            def create_collection(self, *args, **kwargs): pass
            def upsert(self, *args, **kwargs): pass
            def search(self, *args, **kwargs): return []
            def count(self, *args, **kwargs):
                mock_res = MagicMock()
                mock_res.count = 0
                return mock_res
            def scroll(self, *args, **kwargs): return ([], None)
        qdrant_mock.QdrantClient = MockQdrantClient
        sys.modules["qdrant_client"] = qdrant_mock

        qdrant_models = types.ModuleType("qdrant_client.models")
        class MockModel:
            def __init__(self, *args, **kwargs): pass
        qdrant_models.Distance = MagicMock()
        qdrant_models.VectorParams = MockModel
        qdrant_models.PointStruct = MockModel
        qdrant_models.Filter = MockModel
        qdrant_models.FieldCondition = MockModel
        qdrant_models.MatchValue = MockModel
        sys.modules["qdrant_client.models"] = qdrant_models

    if "sentence_transformers" not in sys.modules:
        st_mock = types.ModuleType("sentence_transformers")
        class MockSentenceTransformer:
            def __init__(self, *args, **kwargs): pass
            def encode(self, texts, *args, **kwargs):
                if isinstance(texts, list):
                    return [[0.0] * 384 for _ in texts]
                return [0.0] * 384
        st_mock.SentenceTransformer = MockSentenceTransformer
        sys.modules["sentence_transformers"] = st_mock

