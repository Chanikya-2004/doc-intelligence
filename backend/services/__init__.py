def __init__(self, api_key: str | None = None):
    resolved_key = (
        api_key
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not resolved_key:
        raise EnvironmentError(
            "No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in your .env file."
        )

    self.client = genai.Client(
        api_key=resolved_key,
        http_options=genai_types.HttpOptions(api_version="v1alpha")
    )
    logger.info("Embedder initialized with model: %s", EMBEDDING_MODEL)