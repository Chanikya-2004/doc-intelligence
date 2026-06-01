from fastapi import FastAPI

app = FastAPI()

@app.get('/health')
def health():
    return {'status': 'healthy', 'message': 'Server is running!'}