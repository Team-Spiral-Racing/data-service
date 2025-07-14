
from flask import Flask, Response, redirect, url_for
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from googleapiclient.discovery import build
import json
import os

# Setup
load_dotenv()
MONGO_CLIENT = MongoClient(os.getenv('MONGO_CONNECTION'))
DATABASE = MONGO_CLIENT[os.getenv('MONGO_DB_NAME')]
CRON_SECRET = os.getenv('CRON_SECRET')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
app = Flask(__name__)

@app.route('/')
def root() -> Response:
    """
    This endpoint redirects users to the /status endpoint, where documentation can be found.

    Methods:
        GET: Redirects to the /status endpoint.

    Returns:
        Response: A redirect response to the /status URL.
    """
    return redirect(url_for('status'))


# --- APIs ---
@app.route('/status', methods=['GET'])
def status() -> Response:
    """
    This endpoint can be used to check the health of the server. 
    It responds with a message indicating that the server is running.

    Methods:
        GET: Retrieves the current status of the server.

    Returns:
        Response: A JSON object containing a message and an HTTP status code 200
    """
    return {"msg": 'Status OK, server is running'}, 200


@app.route('/youtube', methods=['POST'])
def youtube() -> Response:
    """
    Queries YouTube every 6hrs to check if new videos are uploaded. If it is, they
    are categorized into topics and further processed.
    """
    ...