import os
import time
import logging
import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")

class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "project-brand-guardian-001")
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """
        Obtains an Azure Active Directory (AAD) issued access token for Azure Resource Manager (ARM).
        """
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure token: {e}")
            raise

    def get_account_token(self, arm_access_token):
        """
        Generates a Video Indexer account access token by calling the Azure Resource Manager (ARM) generateAccessToken API using an AAD-issued access token scoped for ARM.
        """
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")

    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """
        Downloads the youtube video to a local file
        """
        logger.info(f"Downloading Youtube Video: {url}")

        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'extractor_orgs': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Download Complete")
            return output_path
        except Exception as e:
            raise Exception(f"Youtube video download failed: {str(e)}")

    def upload_video(self, sas_url: str, video_name: str) -> str:
        """
        Upload a video to Azure Video Indexer via a Blob Storage SAS URL.
        Returns the Video Indexer video ID.
        """
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"

        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
            "videoUrl": sas_url
        }

        logger.info(f"Submitting video to Azure Video Indexer: {video_name}")
        response = requests.post(api_url, params=params)

        if response.status_code != 200:
            raise Exception(f"Azure Upload Failed: {response.text}")

        return response.json().get("id")

    def get_video_insights(self, video_id: str) -> dict:
        """
        Poll Azure Video Indexer until the video is processed, then return the full insights JSON.
        """
        logger.info(f"Waiting for Video Indexer to process video: {video_id}")
        url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"

        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            response = requests.get(url, params={"accessToken": vi_token})
            if response.status_code != 200:
                raise Exception(f"Failed to get video insights: {response.text}")

            data = response.json()
            state = data.get("state")

            if state == "Processed":
                logger.info(f"Video {video_id} processing complete")
                return data
            elif state == "Failed":
                raise Exception(f"Video Indexing Failed in Azure for video: {video_id}")
            elif state == "Quarantined":
                raise Exception(f"Video Quarantined (Copyright/Content Policy Violation): {video_id}")

            logger.info(f"Video {video_id} status: {state} — waiting 30s")
            time.sleep(30)

    def extract_data(self, vi_json):
        """
        Parses the JSON into our state format
        """
        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("transcript", []):
                transcript_lines.append(insight.get("Text"))

        ocr_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text"))
        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration"),
                "platform": "youtube"
            }
        }


        
