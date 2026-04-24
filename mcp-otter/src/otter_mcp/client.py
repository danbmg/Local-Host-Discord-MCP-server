"""
Otter.ai API Client

Based on gmchad/otterai-api with additions for advanced search.
https://github.com/gmchad/otterai-api
"""

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import xml.etree.ElementTree as ET


class OtterAIException(Exception):
    """Exception raised for Otter.ai API errors"""
    pass


class OtterAI:
    """Unofficial Otter.ai API client"""

    API_BASE_URL = 'https://otter.ai/forward/api/v1/'
    S3_BASE_URL = 'https://s3.us-west-2.amazonaws.com/'

    def __init__(self):
        self._session = requests.Session()
        self._userid = None
        self._cookies = None

    def _is_userid_invalid(self):
        return not self._userid

    def _handle_response(self, response, data=None):
        if data:
            return {'status': response.status_code, 'data': data}
        try:
            return {'status': response.status_code, 'data': response.json()}
        except ValueError:
            return {'status': response.status_code, 'data': {}}

    def login(self, username: str, password: str) -> dict:
        """
        Authenticate with Otter.ai

        Args:
            username: Otter.ai email address
            password: Otter.ai password

        Returns:
            Response dict with status and user data
        """
        auth_url = self.API_BASE_URL + 'login'
        payload = {'username': username}
        self._session.auth = (username, password)
        response = self._session.get(auth_url, params=payload)

        if response.status_code != requests.codes.ok:
            return self._handle_response(response)

        self._userid = response.json()['userid']
        self._cookies = response.cookies.get_dict()
        return self._handle_response(response)

    def get_user(self) -> dict:
        """Get current user information"""
        user_url = self.API_BASE_URL + 'user'
        response = self._session.get(user_url)
        return self._handle_response(response)

    def get_speakers(self) -> dict:
        """Get list of speakers"""
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        speakers_url = self.API_BASE_URL + 'speakers'
        payload = {'userid': self._userid}
        response = self._session.get(speakers_url, params=payload)
        return self._handle_response(response)

    def get_speeches(self, folder: int = 0, page_size: int = 45, source: str = "owned") -> dict:
        """
        Get list of transcripts/speeches

        Args:
            folder: Folder ID (0 for root)
            page_size: Number of results to return
            source: Source filter ("owned", "shared", etc.)

        Returns:
            Response dict with speeches list
        """
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        speeches_url = self.API_BASE_URL + 'speeches'
        payload = {
            'userid': self._userid,
            'folder': folder,
            'page_size': page_size,
            'source': source
        }
        response = self._session.get(speeches_url, params=payload)
        return self._handle_response(response)

    def get_speech(self, speech_id: str) -> dict:
        """
        Get a specific transcript/speech by ID

        Args:
            speech_id: The otid of the transcript

        Returns:
            Response dict with full transcript data
        """
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        speech_url = self.API_BASE_URL + 'speech'
        payload = {'userid': self._userid, 'otid': speech_id}
        response = self._session.get(speech_url, params=payload)
        return self._handle_response(response)

    def search(self, query: str, size: int = 50) -> dict:
        """
        Full-text search across ALL transcripts

        This uses the advanced_search API endpoint which searches
        the full transcript content, not just titles and summaries.

        Args:
            query: Search query (keywords, names, phrases)
            size: Maximum number of results to return

        Returns:
            Response dict with hits containing:
            - speech_otid: Transcript ID
            - title: Transcript title
            - speaker: List of speaker names
            - matched_transcripts: Snippets with highlights
        """
        search_url = self.API_BASE_URL + 'advanced_search'
        payload = {'query': query, 'size': size}
        response = self._session.get(search_url, params=payload)

        if response.status_code != 200:
            return {'status': response.status_code, 'data': {}, 'hits': []}

        data = response.json()
        return {
            'status': response.status_code,
            'data': data,
            'hits': data.get('hits', [])
        }

    def search_within_speech(self, query: str, speech_id: str, size: int = 500) -> dict:
        """
        Search within a specific transcript

        Args:
            query: Search query
            speech_id: The otid of the transcript to search within
            size: Maximum number of results

        Returns:
            Response dict with matching segments
        """
        search_url = self.API_BASE_URL + 'advanced_search'
        payload = {'query': query, 'size': size, 'otid': speech_id}
        response = self._session.get(search_url, params=payload)
        return self._handle_response(response)

    def get_folders(self) -> dict:
        """Get list of folders"""
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        folders_url = self.API_BASE_URL + 'folders'
        payload = {'userid': self._userid}
        response = self._session.get(folders_url, params=payload)
        return self._handle_response(response)

    def list_groups(self) -> dict:
        """Get list of groups"""
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        list_groups_url = self.API_BASE_URL + 'list_groups'
        payload = {'userid': self._userid}
        response = self._session.get(list_groups_url, params=payload)
        return self._handle_response(response)

    def create_speaker(self, speaker_name: str) -> dict:
        """Create a new speaker profile"""
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')
        create_speaker_url = self.API_BASE_URL + 'create_speaker'
        payload = {'userid': self._userid}
        data = {'speaker_name': speaker_name}
        headers = {'x-csrftoken': self._cookies['csrftoken']}
        response = self._session.post(create_speaker_url, params=payload, headers=headers, data=data)
        return self._handle_response(response)

    def upload_speech(self, file_name: str, content_type: str = 'audio/mp4') -> dict:
        """
        Upload an audio file for transcription

        Args:
            file_name: Path to the audio file
            content_type: MIME type of the file

        Returns:
            Response dict with upload status
        """
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')

        speech_upload_params_url = self.API_BASE_URL + 'speech_upload_params'
        speech_upload_prod_url = self.S3_BASE_URL + 'speech-upload-prod'
        finish_speech_upload = self.API_BASE_URL + 'finish_speech_upload'

        # Get upload params
        payload = {'userid': self._userid}
        response = self._session.get(speech_upload_params_url, params=payload)

        if response.status_code != requests.codes.ok:
            return self._handle_response(response)

        response_json = response.json()
        params_data = response_json['data']

        # Send OPTIONS request
        prep_req = requests.Request('OPTIONS', speech_upload_prod_url).prepare()
        prep_req.headers['Accept'] = '*/*'
        prep_req.headers['Connection'] = 'keep-alive'
        prep_req.headers['Origin'] = 'https://otter.ai'
        prep_req.headers['Referer'] = 'https://otter.ai/'
        prep_req.headers['Access-Control-Request-Method'] = 'POST'
        response = self._session.send(prep_req)

        if response.status_code != requests.codes.ok:
            return self._handle_response(response)

        # Upload file to S3
        fields = {}
        params_data['success_action_status'] = str(params_data['success_action_status'])
        del params_data['form_action']
        fields.update(params_data)
        fields['file'] = (file_name, open(file_name, mode='rb'), content_type)
        multipart_data = MultipartEncoder(fields=fields)
        response = requests.post(
            speech_upload_prod_url,
            data=multipart_data,
            headers={'Content-Type': multipart_data.content_type}
        )

        if response.status_code != 201:
            return self._handle_response(response)

        # Parse XML response
        xmltree = ET.ElementTree(ET.fromstring(response.text))
        xmlroot = xmltree.getroot()
        location = xmlroot[0].text
        bucket = xmlroot[1].text
        key = xmlroot[2].text

        # Finish upload
        payload = {
            'bucket': bucket,
            'key': key,
            'language': 'en',
            'country': 'us',
            'userid': self._userid
        }
        response = self._session.get(finish_speech_upload, params=payload)
        return self._handle_response(response)

    def download_speech(self, speech_id: str, name: str = None, fileformat: str = "txt,pdf,mp3,docx,srt") -> dict:
        """
        Download a transcript in various formats

        Args:
            speech_id: The otid of the transcript
            name: Output filename (defaults to speech_id)
            fileformat: Comma-separated formats (txt, pdf, mp3, docx, srt)

        Returns:
            Response dict with filename
        """
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')

        download_speech_url = self.API_BASE_URL + 'bulk_export'
        payload = {'userid': self._userid}
        data = {'formats': fileformat, 'speech_otid_list': [speech_id]}
        headers = {'x-csrftoken': self._cookies['csrftoken'], 'referer': 'https://otter.ai/'}
        response = self._session.post(download_speech_url, params=payload, headers=headers, data=data)

        filename = (name if name else speech_id) + '.' + ('zip' if ',' in fileformat else fileformat)
        if response.ok:
            with open(filename, 'wb') as f:
                f.write(response.content)
        else:
            raise OtterAIException(f'Got response status {response.status_code} when attempting to download {speech_id}')
        return self._handle_response(response, data={'filename': filename})

    def move_to_trash_bin(self, speech_id: str) -> dict:
        """Move a transcript to trash"""
        if self._is_userid_invalid():
            raise OtterAIException('userid is invalid - please login first')

        move_to_trash_bin_url = self.API_BASE_URL + 'move_to_trash_bin'
        payload = {'userid': self._userid}
        data = {'otid': speech_id}
        headers = {'x-csrftoken': self._cookies['csrftoken']}
        response = self._session.post(move_to_trash_bin_url, params=payload, headers=headers, data=data)
        return self._handle_response(response)
